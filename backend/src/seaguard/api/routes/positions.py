from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from seaguard.api.schemas.maritime import (
    RecentPositionResponse,
    RecentPositionsResponse,
)
from seaguard.db.models import AISMessage, Vessel
from seaguard.db.session import get_session

router = APIRouter(
    prefix="/api/v1/positions",
    tags=["positions"],
)

DatabaseSession = Annotated[
    Session,
    Depends(get_session),
]


@router.get(
    "/recent",
    response_model=RecentPositionsResponse,
)
def get_recent_positions(
    session: DatabaseSession,
    limit: Annotated[
        int,
        Query(ge=1, le=1_000),
    ] = 500,
    maximum_age_minutes: Annotated[
        int | None,
        Query(
            ge=1,
            le=525_600,
            description=("Optionally exclude positions older than this many minutes."),
        ),
    ] = None,
) -> RecentPositionsResponse:
    """Return the latest available position per vessel."""

    position_rank = (
        func.row_number()
        .over(
            partition_by=AISMessage.vessel_id,
            order_by=(
                AISMessage.timestamp.desc(),
                AISMessage.id.desc(),
            ),
        )
        .label("position_rank")
    )

    ranked_positions = select(
        AISMessage.id.label("message_id"),
        position_rank,
    ).subquery()

    statement = (
        select(
            AISMessage,
            Vessel,
        )
        .join(
            ranked_positions,
            AISMessage.id == ranked_positions.c.message_id,
        )
        .join(
            Vessel,
            Vessel.id == AISMessage.vessel_id,
        )
        .where(ranked_positions.c.position_rank == 1)
        .order_by(AISMessage.timestamp.desc())
        .limit(limit)
    )

    if maximum_age_minutes is not None:
        cutoff = datetime.now(UTC) - timedelta(minutes=maximum_age_minutes)

        statement = statement.where(AISMessage.timestamp >= cutoff)

    rows = session.execute(statement).all()

    items = [
        RecentPositionResponse(
            id=message.id,
            mmsi=vessel.mmsi,
            vessel_name=vessel.name,
            vessel_type=vessel.vessel_type,
            timestamp=message.timestamp,
            latitude=message.latitude,
            longitude=message.longitude,
            sog=message.sog,
            cog=message.cog,
            heading=message.heading,
            navigation_status=(message.navigation_status),
        )
        for message, vessel in rows
    ]

    return RecentPositionsResponse(
        items=items,
        total=len(items),
    )
