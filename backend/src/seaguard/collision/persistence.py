from dataclasses import dataclass
from datetime import datetime
from math import isfinite

from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from seaguard.collision.candidates import EncounterVessel
from seaguard.collision.engine import evaluate_collision_encounters
from seaguard.collision.risk import CollisionRiskThresholds
from seaguard.db.collision_models import CollisionEncounterRecord
from seaguard.db.models import AISMessage, Vessel

DEFAULT_ASSESSMENT_VERSION = "cpa-tcpa-v1"
DEFAULT_MAX_DISTANCE_NM = 20.0
DEFAULT_MAX_PAIR_TIME_GAP_MINUTES = 5.0


@dataclass(frozen=True, slots=True)
class CollisionSnapshotVessel:
    """Vessel motion state linked to its source database records."""

    vessel_id: int
    ais_message_id: int
    observed_at: datetime
    vessel: EncounterVessel


@dataclass(frozen=True, slots=True)
class CollisionPersistenceResult:
    """Summary of one persisted collision scan."""

    latest_position_count: int
    usable_vessel_count: int
    skipped_unusable_count: int

    possible_pair_count: int
    candidate_count: int
    assessed_candidate_count: int

    elevated_encounter_count: int
    eligible_encounter_count: int
    skipped_time_gap_count: int

    inserted_count: int
    duplicate_count: int


def _number_or_none(
    value: object,
) -> float | None:
    if value is None:
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not isfinite(number):
        return None

    return number


def load_latest_collision_snapshot(
    session: Session,
) -> tuple[
    tuple[CollisionSnapshotVessel, ...],
    int,
    int,
]:
    """
    Load the newest AIS observation for every vessel.

    The newest observation is selected first. Only after that do
    we decide whether the record contains usable CPA/TCPA motion
    data.

    This is important: we do not silently fall back to an older
    AIS record merely because the newest record lacks SOG or COG.
    """

    ranked_positions = (
        select(
            Vessel.id.label("vessel_id"),
            Vessel.mmsi.label("mmsi"),
            AISMessage.id.label("ais_message_id"),
            AISMessage.timestamp.label("observed_at"),
            func.ST_Y(
                cast(
                    AISMessage.position,
                    Geometry(
                        geometry_type="POINT",
                        srid=4326,
                    ),
                )
            ).label("latitude"),
            func.ST_X(
                cast(
                    AISMessage.position,
                    Geometry(
                        geometry_type="POINT",
                        srid=4326,
                    ),
                )
            ).label("longitude"),
            AISMessage.sog.label("sog"),
            AISMessage.cog.label("cog"),
            func.row_number()
            .over(
                partition_by=(AISMessage.vessel_id),
                order_by=(
                    AISMessage.timestamp.desc(),
                    AISMessage.id.desc(),
                ),
            )
            .label("position_rank"),
        )
        .join(
            Vessel,
            Vessel.id == AISMessage.vessel_id,
        )
        .subquery()
    )

    statement = (
        select(ranked_positions)
        .where(ranked_positions.c.position_rank == 1)
        .order_by(ranked_positions.c.mmsi)
    )

    rows = session.execute(statement).mappings().all()

    latest_position_count = len(rows)

    vessels: list[CollisionSnapshotVessel] = []

    skipped_unusable_count = 0

    for row in rows:
        mmsi_value = row["mmsi"]

        observed_at = row["observed_at"]

        latitude = _number_or_none(row["latitude"])

        longitude = _number_or_none(row["longitude"])

        sog_knots = _number_or_none(row["sog"])

        cog_degrees = _number_or_none(row["cog"])

        if (
            mmsi_value is None
            or observed_at is None
            or latitude is None
            or longitude is None
            or sog_knots is None
            or cog_degrees is None
        ):
            skipped_unusable_count += 1
            continue

        if not (-90.0 <= latitude <= 90.0):
            skipped_unusable_count += 1
            continue

        if not (-180.0 <= longitude <= 180.0):
            skipped_unusable_count += 1
            continue

        if sog_knots < 0.0:
            skipped_unusable_count += 1
            continue

        mmsi = str(mmsi_value).strip()

        if not mmsi:
            skipped_unusable_count += 1
            continue

        vessels.append(
            CollisionSnapshotVessel(
                vessel_id=int(row["vessel_id"]),
                ais_message_id=int(row["ais_message_id"]),
                observed_at=(observed_at),
                vessel=EncounterVessel(
                    mmsi=mmsi,
                    latitude=latitude,
                    longitude=longitude,
                    sog_knots=sog_knots,
                    cog_degrees=(cog_degrees),
                ),
            )
        )

    return (
        tuple(vessels),
        latest_position_count,
        skipped_unusable_count,
    )


def persist_collision_snapshot(
    session: Session,
    *,
    max_distance_nm: float = (DEFAULT_MAX_DISTANCE_NM),
    max_pair_time_gap_minutes: float = (DEFAULT_MAX_PAIR_TIME_GAP_MINUTES),
    thresholds: (CollisionRiskThresholds | None) = None,
    assessment_version: str = (DEFAULT_ASSESSMENT_VERSION),
) -> CollisionPersistenceResult:
    """
    Evaluate and persist elevated collision encounters.

    Only MEDIUM, HIGH, and CRITICAL encounters are persisted.

    Vessel pairs whose source AIS observations are too far apart
    in time are rejected because their CPA/TCPA geometry does not
    represent a sufficiently aligned vessel snapshot.

    Persistence is idempotent for a pair of source AIS messages
    and assessment version.
    """

    if not isfinite(max_pair_time_gap_minutes) or max_pair_time_gap_minutes < 0.0:
        raise ValueError("Maximum pair time gap must be a non-negative finite number.")

    if not assessment_version.strip():
        raise ValueError("Assessment version cannot be empty.")

    (
        snapshot,
        latest_position_count,
        skipped_unusable_count,
    ) = load_latest_collision_snapshot(session)

    source_by_mmsi = {item.vessel.mmsi: item for item in snapshot}

    scan = evaluate_collision_encounters(
        (item.vessel for item in snapshot),
        max_distance_nm=(max_distance_nm),
        thresholds=thresholds,
        include_low=False,
    )

    inserted_count = 0
    eligible_encounter_count = 0
    skipped_time_gap_count = 0

    for encounter in scan.encounters:
        source_a = source_by_mmsi[encounter.vessel_a.mmsi]

        source_b = source_by_mmsi[encounter.vessel_b.mmsi]

        time_gap_minutes = (
            abs((source_a.observed_at - source_b.observed_at).total_seconds()) / 60.0
        )

        if time_gap_minutes > max_pair_time_gap_minutes:
            skipped_time_gap_count += 1
            continue

        eligible_encounter_count += 1

        observed_at = max(
            source_a.observed_at,
            source_b.observed_at,
        )

        statement = (
            insert(CollisionEncounterRecord)
            .values(
                vessel_a_id=(source_a.vessel_id),
                vessel_b_id=(source_b.vessel_id),
                vessel_a_ais_message_id=(source_a.ais_message_id),
                vessel_b_ais_message_id=(source_b.ais_message_id),
                observed_at=(observed_at),
                vessel_a_observed_at=(source_a.observed_at),
                vessel_b_observed_at=(source_b.observed_at),
                current_distance_nm=(encounter.risk.current_distance_nm),
                cpa_distance_nm=(encounter.risk.cpa_distance_nm),
                tcpa_minutes=(encounter.risk.tcpa_minutes),
                relative_speed_knots=(encounter.risk.relative_speed_knots),
                closing_speed_knots=(encounter.risk.closing_speed_knots),
                bearing_from_a_to_b_degrees=(encounter.cpa.bearing_from_a_to_b_degrees),
                risk_level=(encounter.risk.risk_level),
                reasons=list(encounter.risk.reasons),
                assessment_version=(assessment_version),
            )
            .on_conflict_do_nothing(
                constraint=("uq_collision_encounter_source_messages_version")
            )
        )

        result = session.execute(statement)

        if result.rowcount:
            inserted_count += int(result.rowcount)

    session.commit()

    duplicate_count = eligible_encounter_count - inserted_count

    return CollisionPersistenceResult(
        latest_position_count=(latest_position_count),
        usable_vessel_count=(len(snapshot)),
        skipped_unusable_count=(skipped_unusable_count),
        possible_pair_count=(scan.candidate_search.possible_pair_count),
        candidate_count=(scan.candidate_search.candidate_count),
        assessed_candidate_count=(scan.assessed_candidate_count),
        elevated_encounter_count=(scan.encounter_count),
        eligible_encounter_count=(eligible_encounter_count),
        skipped_time_gap_count=(skipped_time_gap_count),
        inserted_count=(inserted_count),
        duplicate_count=(duplicate_count),
    )
