from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, aliased

from seaguard.api.schemas.collision import (
    CollisionEncounterListResponse,
    CollisionEncounterResponse,
    CollisionRiskLevel,
    CollisionSummaryResponse,
    CollisionVesselState,
)
from seaguard.db.collision_models import CollisionEncounterRecord
from seaguard.db.models import AISMessage, Vessel
from seaguard.db.session import get_session

router = APIRouter(
    prefix="/collisions",
    tags=["collisions"],
)


SessionDependency = Annotated[
    Session,
    Depends(get_session),
]


RISK_PRIORITY = case(
    (
        CollisionEncounterRecord.risk_level == "critical",
        0,
    ),
    (
        CollisionEncounterRecord.risk_level == "high",
        1,
    ),
    (
        CollisionEncounterRecord.risk_level == "medium",
        2,
    ),
    else_=3,
)


def _build_collision_query():
    vessel_a = aliased(
        Vessel,
        name="collision_vessel_a",
    )

    vessel_b = aliased(
        Vessel,
        name="collision_vessel_b",
    )

    message_a = aliased(
        AISMessage,
        name="collision_message_a",
    )

    message_b = aliased(
        AISMessage,
        name="collision_message_b",
    )

    statement = (
        select(
            CollisionEncounterRecord,
            vessel_a.mmsi.label("vessel_a_mmsi"),
            vessel_a.name.label("vessel_a_name"),
            vessel_b.mmsi.label("vessel_b_mmsi"),
            vessel_b.name.label("vessel_b_name"),
            func.ST_Y(message_a.position).label("vessel_a_latitude"),
            func.ST_X(message_a.position).label("vessel_a_longitude"),
            message_a.sog.label("vessel_a_sog"),
            message_a.cog.label("vessel_a_cog"),
            func.ST_Y(message_b.position).label("vessel_b_latitude"),
            func.ST_X(message_b.position).label("vessel_b_longitude"),
            message_b.sog.label("vessel_b_sog"),
            message_b.cog.label("vessel_b_cog"),
        )
        .join(
            vessel_a,
            vessel_a.id == CollisionEncounterRecord.vessel_a_id,
        )
        .join(
            vessel_b,
            vessel_b.id == CollisionEncounterRecord.vessel_b_id,
        )
        .join(
            message_a,
            message_a.id == CollisionEncounterRecord.vessel_a_ais_message_id,
        )
        .join(
            message_b,
            message_b.id == CollisionEncounterRecord.vessel_b_ais_message_id,
        )
    )

    return (
        statement,
        vessel_a,
        vessel_b,
    )


def _row_to_response(
    row,
) -> CollisionEncounterResponse:
    encounter = row[0]

    return CollisionEncounterResponse(
        id=encounter.id,
        observed_at=encounter.observed_at,
        vessel_a=CollisionVesselState(
            vessel_id=encounter.vessel_a_id,
            ais_message_id=(encounter.vessel_a_ais_message_id),
            mmsi=str(row.vessel_a_mmsi),
            name=row.vessel_a_name,
            observed_at=(encounter.vessel_a_observed_at),
            latitude=float(row.vessel_a_latitude),
            longitude=float(row.vessel_a_longitude),
            sog=(float(row.vessel_a_sog) if row.vessel_a_sog is not None else None),
            cog=(float(row.vessel_a_cog) if row.vessel_a_cog is not None else None),
        ),
        vessel_b=CollisionVesselState(
            vessel_id=encounter.vessel_b_id,
            ais_message_id=(encounter.vessel_b_ais_message_id),
            mmsi=str(row.vessel_b_mmsi),
            name=row.vessel_b_name,
            observed_at=(encounter.vessel_b_observed_at),
            latitude=float(row.vessel_b_latitude),
            longitude=float(row.vessel_b_longitude),
            sog=(float(row.vessel_b_sog) if row.vessel_b_sog is not None else None),
            cog=(float(row.vessel_b_cog) if row.vessel_b_cog is not None else None),
        ),
        current_distance_nm=(encounter.current_distance_nm),
        cpa_distance_nm=(encounter.cpa_distance_nm),
        tcpa_minutes=(encounter.tcpa_minutes),
        relative_speed_knots=(encounter.relative_speed_knots),
        closing_speed_knots=(encounter.closing_speed_knots),
        bearing_from_a_to_b_degrees=(encounter.bearing_from_a_to_b_degrees),
        risk_level=(encounter.risk_level),
        reasons=list(encounter.reasons or []),
        assessment_version=(encounter.assessment_version),
        created_at=(encounter.created_at),
    )


@router.get(
    "/summary",
    response_model=CollisionSummaryResponse,
)
def get_collision_summary(
    session: SessionDependency,
) -> CollisionSummaryResponse:
    rows = session.execute(
        select(
            CollisionEncounterRecord.risk_level,
            func.count(CollisionEncounterRecord.id),
        ).group_by(CollisionEncounterRecord.risk_level)
    ).all()

    counts = {
        "low": 0,
        "medium": 0,
        "high": 0,
        "critical": 0,
    }

    for risk_level, count in rows:
        if risk_level in counts:
            counts[risk_level] = int(count)

    return CollisionSummaryResponse(
        total=sum(counts.values()),
        low=counts["low"],
        medium=counts["medium"],
        high=counts["high"],
        critical=counts["critical"],
    )


@router.get(
    "",
    response_model=CollisionEncounterListResponse,
)
def list_collision_encounters(
    session: SessionDependency,
    risk_level: Annotated[
        CollisionRiskLevel | None,
        Query(),
    ] = None,
    minimum_tcpa_minutes: Annotated[
        float | None,
        Query(),
    ] = None,
    maximum_tcpa_minutes: Annotated[
        float | None,
        Query(),
    ] = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=500,
        ),
    ] = 100,
    offset: Annotated[
        int,
        Query(
            ge=0,
        ),
    ] = 0,
) -> CollisionEncounterListResponse:
    statement, _, _ = _build_collision_query()

    count_statement = select(func.count(CollisionEncounterRecord.id))

    filters = []

    if risk_level is not None:
        filters.append(CollisionEncounterRecord.risk_level == risk_level)

    if minimum_tcpa_minutes is not None:
        filters.append(CollisionEncounterRecord.tcpa_minutes >= minimum_tcpa_minutes)

    if maximum_tcpa_minutes is not None:
        filters.append(CollisionEncounterRecord.tcpa_minutes <= maximum_tcpa_minutes)

    if filters:
        statement = statement.where(*filters)

        count_statement = count_statement.where(*filters)

    total = session.scalar(count_statement)

    statement = (
        statement.order_by(
            RISK_PRIORITY,
            CollisionEncounterRecord.tcpa_minutes.asc().nulls_last(),
            CollisionEncounterRecord.cpa_distance_nm.asc(),
            CollisionEncounterRecord.observed_at.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    rows = session.execute(statement).all()

    items = [_row_to_response(row) for row in rows]

    return CollisionEncounterListResponse(
        items=items,
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{mmsi}",
    response_model=CollisionEncounterListResponse,
)
def list_vessel_collision_encounters(
    mmsi: str,
    session: SessionDependency,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=500,
        ),
    ] = 100,
    offset: Annotated[
        int,
        Query(
            ge=0,
        ),
    ] = 0,
) -> CollisionEncounterListResponse:
    (
        statement,
        vessel_a,
        vessel_b,
    ) = _build_collision_query()

    vessel_filter = or_(
        vessel_a.mmsi == mmsi,
        vessel_b.mmsi == mmsi,
    )

    statement = (
        statement.where(vessel_filter)
        .order_by(
            RISK_PRIORITY,
            CollisionEncounterRecord.tcpa_minutes.asc().nulls_last(),
            CollisionEncounterRecord.cpa_distance_nm.asc(),
            CollisionEncounterRecord.observed_at.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    count_vessel_a = aliased(Vessel)

    count_vessel_b = aliased(Vessel)

    count_statement = (
        select(func.count(CollisionEncounterRecord.id))
        .join(
            count_vessel_a,
            count_vessel_a.id == CollisionEncounterRecord.vessel_a_id,
        )
        .join(
            count_vessel_b,
            count_vessel_b.id == CollisionEncounterRecord.vessel_b_id,
        )
        .where(
            or_(
                count_vessel_a.mmsi == mmsi,
                count_vessel_b.mmsi == mmsi,
            )
        )
    )

    total = session.scalar(count_statement)

    rows = session.execute(statement).all()

    items = [_row_to_response(row) for row in rows]

    return CollisionEncounterListResponse(
        items=items,
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )
