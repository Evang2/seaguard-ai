from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from seaguard.api.schemas.playback import (
    PlaybackBoundsResponse,
    PlaybackPosition,
    PlaybackSnapshotResponse,
)
from seaguard.db.models import AISMessage, Vessel
from seaguard.db.session import get_session

router = APIRouter(
    prefix="/api/v1/playback",
    tags=["playback"],
)

DatabaseSession = Annotated[
    Session,
    Depends(get_session),
]


def _as_utc(value: datetime) -> datetime:
    """Normalize an API timestamp to timezone-aware UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


@router.get(
    "/bounds",
    response_model=PlaybackBoundsResponse,
)
def get_playback_bounds(
    session: DatabaseSession,
) -> PlaybackBoundsResponse:
    """Return the imported AIS recording time range."""

    (
        start_time,
        end_time,
        observation_count,
        vessel_count,
    ) = session.execute(
        select(
            func.min(AISMessage.timestamp),
            func.max(AISMessage.timestamp),
            func.count(AISMessage.id),
            func.count(func.distinct(AISMessage.vessel_id)),
        )
    ).one()

    return PlaybackBoundsResponse(
        start_time=start_time,
        end_time=end_time,
        observation_count=int(observation_count or 0),
        vessel_count=int(vessel_count or 0),
    )


@router.get(
    "/snapshot",
    response_model=PlaybackSnapshotResponse,
)
def get_playback_snapshot(
    session: DatabaseSession,
    at: Annotated[
        datetime,
        Query(
            description=("Historical UTC timestamp for the playback frame."),
        ),
    ],
    tolerance_minutes: Annotated[
        float,
        Query(
            gt=0,
            le=60,
            description=(
                "Maximum age of a vessel AIS report relative to the requested frame."
            ),
        ),
    ] = 5.0,
    limit: Annotated[
        int,
        Query(ge=1, le=1000),
    ] = 500,
) -> PlaybackSnapshotResponse:
    """
    Return one historical AIS state per vessel.

    The newest observation at or before ``at`` is used,
    provided it is no older than ``tolerance_minutes``.
    """

    requested_at = _as_utc(at)
    window_start = requested_at - timedelta(minutes=tolerance_minutes)

    ranked_messages = (
        select(
            AISMessage.id.label("ais_message_id"),
            AISMessage.vessel_id.label("vessel_id"),
            func.row_number()
            .over(
                partition_by=AISMessage.vessel_id,
                order_by=(
                    AISMessage.timestamp.desc(),
                    AISMessage.id.desc(),
                ),
            )
            .label("row_number"),
        )
        .where(
            AISMessage.timestamp >= window_start,
            AISMessage.timestamp <= requested_at,
        )
        .subquery()
    )

    frame_count = (
        session.scalar(
            select(func.count())
            .select_from(ranked_messages)
            .where(ranked_messages.c.row_number == 1)
        )
        or 0
    )

    rows = session.execute(
        select(
            AISMessage,
            Vessel.mmsi,
            Vessel.name,
        )
        .join(
            ranked_messages,
            ranked_messages.c.ais_message_id == AISMessage.id,
        )
        .join(
            Vessel,
            Vessel.id == AISMessage.vessel_id,
        )
        .where(ranked_messages.c.row_number == 1)
        .order_by(Vessel.mmsi.asc())
        .limit(limit)
    ).all()

    items = [
        PlaybackPosition(
            id=message.id,
            mmsi=mmsi,
            vessel_name=vessel_name,
            timestamp=message.timestamp,
            latitude=message.latitude,
            longitude=message.longitude,
            sog=message.sog,
            cog=message.cog,
            heading=message.heading,
            navigation_status=message.navigation_status,
        )
        for message, mmsi, vessel_name in rows
    ]

    return PlaybackSnapshotResponse(
        requested_at=requested_at,
        window_start=window_start,
        tolerance_minutes=tolerance_minutes,
        total=int(frame_count),
        items=items,
    )
