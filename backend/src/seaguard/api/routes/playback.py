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
    """Normalize API timestamps to timezone-aware UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


def _recording_day(
    session: Session,
) -> datetime | None:
    """
    Return the UTC day that contains the most AIS observations.

    SeaGuard's database can contain both a dense historical recording
    and sparse live/recent AIS observations. Playback should represent
    the historical recording rather than stretching from the oldest
    observation to the newest live observation.

    For v1, the densest UTC day is treated as the playback recording.
    """

    day = func.date_trunc(
        "day",
        AISMessage.timestamp,
    ).label("recording_day")

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
        return None

    return _as_utc(row.recording_day)


@router.get(
    "/bounds",
    response_model=PlaybackBoundsResponse,
)
def get_playback_bounds(
    session: DatabaseSession,
) -> PlaybackBoundsResponse:
    """
    Return the primary historical AIS recording range.

    The database may also contain continuously ingested live AIS data.
    To keep replay usable, v1 selects the UTC day with the greatest
    number of AIS observations and reports bounds only for that day.
    """

    recording_start = _recording_day(session)

    if recording_start is None:
        return PlaybackBoundsResponse(
            start_time=None,
            end_time=None,
            observation_count=0,
            vessel_count=0,
        )

    recording_end = recording_start + timedelta(days=1)

    row = session.execute(
        select(
            func.min(AISMessage.timestamp),
            func.max(AISMessage.timestamp),
            func.count(AISMessage.id),
            func.count(func.distinct(AISMessage.vessel_id)),
        ).where(
            AISMessage.timestamp >= recording_start,
            AISMessage.timestamp < recording_end,
        )
    ).one()

    (
        start_time,
        end_time,
        observation_count,
        vessel_count,
    ) = row

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
                "Maximum age of a vessel's AIS "
                "report relative to the requested "
                "playback time."
            ),
        ),
    ] = 5.0,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=1000,
        ),
    ] = 500,
) -> PlaybackSnapshotResponse:
    """
    Return one historical vessel state per MMSI.

    For each vessel, select its newest AIS message
    at or before ``at`` while rejecting observations
    older than ``tolerance_minutes``.
    """

    requested_at = _as_utc(at)

    window_start = requested_at - timedelta(minutes=tolerance_minutes)

    ranked_messages = (
        select(
            AISMessage.id.label("ais_message_id"),
            AISMessage.vessel_id.label("vessel_id"),
            func.row_number()
            .over(
                partition_by=(AISMessage.vessel_id),
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

    statement = (
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
    )

    rows = session.execute(statement).all()

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
            navigation_status=(message.navigation_status),
        )
        for (
            message,
            mmsi,
            vessel_name,
        ) in rows
    ]

    return PlaybackSnapshotResponse(
        requested_at=requested_at,
        window_start=window_start,
        tolerance_minutes=(tolerance_minutes),
        total=int(frame_count),
        items=items,
    )
