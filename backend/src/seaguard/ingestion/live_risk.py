from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from seaguard.ais.anomalies import detect_rule_based_anomalies
from seaguard.db.models import AISMessage, Vessel
from seaguard.db.risk_importer import (
    DEFAULT_ASSESSMENT_VERSION,
    _build_risk_records,
    _message_ids_for_chunk,
    _prepare_risk_chunk,
    _upsert_risk_records,
    _vessel_ids_for_chunk,
)
from seaguard.ingestion.analytics import (
    AnalyticsStageResult,
    IngestionAnalyticsContext,
)
from seaguard.ingestion.live_anomalies import (
    _load_affected_history,
    _source_message_keys,
    build_live_motion_features,
)
from seaguard.ml.anomaly_detector import AISIsolationForestDetector
from seaguard.risk.hybrid import HybridRiskAssessor


@dataclass(frozen=True, slots=True)
class LiveRiskRuntime:
    """
    Stable fitted ML/hybrid objects used by the ingestion watcher.

    The Isolation Forest and percentile calibration are fitted from the
    primary dense historical recording, never from an incoming live file.
    """

    detector: AISIsolationForestDetector
    assessor: HybridRiskAssessor
    reference_start: datetime
    reference_end: datetime
    reference_observations: int


_LIVE_RISK_RUNTIME: LiveRiskRuntime | None = None


def reset_live_risk_runtime() -> None:
    """Forget the cached runtime so it is rebuilt on the next live import."""

    global _LIVE_RISK_RUNTIME
    _LIVE_RISK_RUNTIME = None


def _as_utc(
    value: datetime,
) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


def _reference_day(
    session: Session,
) -> datetime:
    """
    Select the UTC day containing the most AIS observations.

    This is the same v1 principle used by historical playback: the dense
    recording is the reference dataset, while sparse live observations must
    not move or retrain the baseline.
    """

    day = func.date_trunc(
        "day",
        AISMessage.timestamp,
    ).label("reference_day")

    row = session.execute(
        select(
            day,
            func.count(AISMessage.id).label("observation_count"),
        )
        .group_by(day)
        .order_by(
            func.count(AISMessage.id).desc(),
            day.asc(),
        )
        .limit(1)
    ).one_or_none()

    if row is None:
        raise RuntimeError(
            "Cannot build the live ML baseline because no AIS observations "
            "exist in the database."
        )

    return _as_utc(row.reference_day)


def _load_reference_history(
    session: Session,
    start_time: datetime,
    end_time: datetime,
) -> pd.DataFrame:
    """Load the complete dense historical reference recording."""

    rows = session.execute(
        select(
            AISMessage.id,
            Vessel.mmsi,
            AISMessage.timestamp,
            AISMessage.latitude,
            AISMessage.longitude,
            AISMessage.sog,
            AISMessage.cog,
            AISMessage.heading,
        )
        .join(
            Vessel,
            Vessel.id == AISMessage.vessel_id,
        )
        .where(
            AISMessage.timestamp >= start_time,
            AISMessage.timestamp < end_time,
        )
        .order_by(
            Vessel.mmsi.asc(),
            AISMessage.timestamp.asc(),
            AISMessage.id.asc(),
        )
    ).all()

    return pd.DataFrame(
        rows,
        columns=[
            "id",
            "mmsi",
            "timestamp",
            "latitude",
            "longitude",
            "sog",
            "cog",
            "heading",
        ],
    )


def _filter_to_message_keys(
    dataframe: pd.DataFrame,
    keys: set[
        tuple[
            str,
            datetime,
        ]
    ],
) -> pd.DataFrame:
    """Keep dataframe rows belonging to the current incoming source file."""

    if dataframe.empty or not keys:
        return dataframe.iloc[0:0].copy()

    filtered = dataframe.copy()

    filtered["mmsi"] = (
        filtered["mmsi"]
        .astype("string")
        .str.strip()
        .str.replace(
            r"\.0$",
            "",
            regex=True,
        )
    )

    filtered["timestamp"] = pd.to_datetime(
        filtered["timestamp"],
        errors="coerce",
        utc=True,
    )

    mask: list[bool] = []

    for row in filtered.itertuples(index=False):
        timestamp = row.timestamp

        if isinstance(
            timestamp,
            pd.Timestamp,
        ):
            timestamp = timestamp.to_pydatetime()

        mask.append(
            (
                str(row.mmsi),
                timestamp,
            )
            in keys
        )

    return filtered.loc[mask].copy().reset_index(drop=True)


def _build_live_risk_runtime(
    session: Session,
) -> LiveRiskRuntime:
    """
    Fit the stable Isolation Forest and hybrid percentile calibration.

    This runs once per watcher process. Because the historical reference day,
    model random state, and feature logic are stable, a process restart
    reconstructs the same v1 baseline instead of learning from live files.
    """

    reference_start = _reference_day(session)

    reference_end = reference_start + timedelta(days=1)

    history = _load_reference_history(
        session,
        reference_start,
        reference_end,
    )

    if len(history) < 2:
        raise RuntimeError(
            "Cannot build the live ML baseline because the historical "
            "reference contains fewer than two AIS observations."
        )

    features = build_live_motion_features(history)

    annotated, _ = detect_rule_based_anomalies(features)

    detector = AISIsolationForestDetector()

    detector.fit(annotated)

    scored_reference = detector.score(annotated)

    assessor = HybridRiskAssessor()

    assessor.fit(scored_reference)

    return LiveRiskRuntime(
        detector=detector,
        assessor=assessor,
        reference_start=(reference_start),
        reference_end=(reference_end),
        reference_observations=(len(scored_reference)),
    )


def get_live_risk_runtime(
    session: Session,
) -> LiveRiskRuntime:
    """Return the process-wide stable live risk runtime."""

    global _LIVE_RISK_RUNTIME

    if _LIVE_RISK_RUNTIME is None:
        _LIVE_RISK_RUNTIME = _build_live_risk_runtime(session)

    return _LIVE_RISK_RUNTIME


def _persist_assessed_rows(
    session: Session,
    assessed: pd.DataFrame,
    *,
    insert_batch_size: int,
) -> int:
    """
    Persist assessed rows through the existing risk-import persistence logic.

    The existing RiskAssessment identity is one row per AIS message, so this
    remains idempotent when analytics is retried.
    """

    prepared, rejected = _prepare_risk_chunk(assessed)

    if rejected:
        raise RuntimeError(
            f"Live hybrid risk produced {rejected} invalid assessment row(s)."
        )

    if prepared.empty:
        return 0

    vessel_ids = _vessel_ids_for_chunk(
        session,
        prepared,
    )

    message_ids = _message_ids_for_chunk(
        session,
        prepared,
        vessel_ids,
    )

    records, missing = _build_risk_records(
        prepared,
        vessel_ids,
        message_ids,
        assessment_version=(DEFAULT_ASSESSMENT_VERSION),
    )

    if missing:
        raise RuntimeError(
            "Live hybrid risk could not resolve "
            f"{missing} AIS message(s) for persistence."
        )

    written = _upsert_risk_records(
        session,
        records,
        batch_size=(insert_batch_size),
    )

    session.commit()

    return written


def persist_live_hybrid_risk(
    session: Session,
    context: IngestionAnalyticsContext,
    *,
    insert_batch_size: int = 1_000,
) -> AnalyticsStageResult:
    """
    Score and persist hybrid risk for newly imported AIS observations.

    Vessel history is loaded only to derive motion context. The Isolation
    Forest itself is NOT refitted from that history or from the incoming CSV.
    """

    incoming_keys = _source_message_keys(context.source_file)

    if not incoming_keys:
        return AnalyticsStageResult(
            name="hybrid_risk",
            processed=0,
            created=0,
        )

    history = _load_affected_history(
        session,
        incoming_keys,
    )

    if history.empty:
        return AnalyticsStageResult(
            name="hybrid_risk",
            processed=0,
            created=0,
        )

    features = build_live_motion_features(history)

    annotated, _ = detect_rule_based_anomalies(features)

    incoming = _filter_to_message_keys(
        annotated,
        incoming_keys,
    )

    if incoming.empty:
        return AnalyticsStageResult(
            name="hybrid_risk",
            processed=0,
            created=0,
        )

    runtime = get_live_risk_runtime(session)

    scored = runtime.detector.score(incoming)

    assessed = runtime.assessor.assess(scored)

    written = _persist_assessed_rows(
        session,
        assessed,
        insert_batch_size=(insert_batch_size),
    )

    return AnalyticsStageResult(
        name="hybrid_risk",
        processed=len(incoming),
        created=written,
    )
