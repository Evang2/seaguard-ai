from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from seaguard.api.converters import position_response
from seaguard.api.schemas.maritime import (
    TrajectoryPoint,
    VesselDetail,
    VesselListResponse,
    VesselSummary,
    VesselTrajectoryResponse,
)
from seaguard.db.models import AISMessage, AnomalyAlert, Vessel
from seaguard.db.session import get_session

router = APIRouter(
    prefix="/api/v1/vessels",
    tags=["vessels"],
)

DatabaseSession = Annotated[
    Session,
    Depends(get_session),
]


@router.get(
    "",
    response_model=VesselListResponse,
)
def list_vessels(
    session: DatabaseSession,
    search: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=100,
            description=("Search by MMSI, vessel name, IMO, or call sign."),
        ),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=200),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> VesselListResponse:
    """Search and paginate vessels."""

    conditions = []

    if search is not None:
        search_pattern = f"%{search.strip()}%"

        conditions.append(
            or_(
                Vessel.mmsi.ilike(search_pattern),
                Vessel.name.ilike(search_pattern),
                Vessel.imo.ilike(search_pattern),
                Vessel.call_sign.ilike(search_pattern),
            )
        )

    count_statement = select(func.count(Vessel.id))

    vessel_statement = (
        select(Vessel)
        .order_by(
            Vessel.name.asc().nulls_last(),
            Vessel.mmsi.asc(),
        )
        .limit(limit)
        .offset(offset)
    )

    if conditions:
        count_statement = count_statement.where(*conditions)

        vessel_statement = vessel_statement.where(*conditions)

    total = session.scalar(count_statement) or 0
    vessels = session.scalars(vessel_statement).all()

    return VesselListResponse(
        items=[VesselSummary.model_validate(vessel) for vessel in vessels],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{mmsi}",
    response_model=VesselDetail,
)
def get_vessel(
    session: DatabaseSession,
    mmsi: Annotated[
        str,
        Path(pattern=r"^\d{9}$"),
    ],
) -> VesselDetail:
    """Return vessel metadata and its latest position."""

    vessel = session.scalar(select(Vessel).where(Vessel.mmsi == mmsi))

    if vessel is None:
        raise HTTPException(
            status_code=404,
            detail=f"Vessel {mmsi} was not found.",
        )

    message_count = (
        session.scalar(
            select(func.count(AISMessage.id)).where(AISMessage.vessel_id == vessel.id)
        )
        or 0
    )

    alert_count = (
        session.scalar(
            select(func.count(AnomalyAlert.id)).where(
                AnomalyAlert.vessel_id == vessel.id
            )
        )
        or 0
    )

    latest_message = session.scalar(
        select(AISMessage)
        .where(AISMessage.vessel_id == vessel.id)
        .order_by(
            AISMessage.timestamp.desc(),
            AISMessage.id.desc(),
        )
        .limit(1)
    )

    vessel_data = VesselSummary.model_validate(vessel).model_dump()

    return VesselDetail(
        **vessel_data,
        message_count=message_count,
        alert_count=alert_count,
        latest_position=(
            position_response(latest_message) if latest_message is not None else None
        ),
    )


@router.get(
    "/{mmsi}/trajectory",
    response_model=VesselTrajectoryResponse,
)
def get_vessel_trajectory(
    session: DatabaseSession,
    mmsi: Annotated[
        str,
        Path(pattern=r"^\d{9}$"),
    ],
    start_time: Annotated[
        datetime | None,
        Query(description="Optional inclusive UTC start timestamp."),
    ] = None,
    end_time: Annotated[
        datetime | None,
        Query(description="Optional inclusive UTC end timestamp."),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=50_000),
    ] = 10_000,
) -> VesselTrajectoryResponse:
    """Return an ordered trajectory for one vessel."""

    if start_time is not None and end_time is not None and start_time > end_time:
        raise HTTPException(
            status_code=422,
            detail=("start_time must be earlier than or equal to end_time."),
        )

    vessel = session.scalar(select(Vessel).where(Vessel.mmsi == mmsi))

    if vessel is None:
        raise HTTPException(
            status_code=404,
            detail=f"Vessel {mmsi} was not found.",
        )

    conditions = [
        AISMessage.vessel_id == vessel.id,
    ]

    if start_time is not None:
        conditions.append(AISMessage.timestamp >= start_time)

    if end_time is not None:
        conditions.append(AISMessage.timestamp <= end_time)

    messages = session.scalars(
        select(AISMessage)
        .where(*conditions)
        .order_by(
            AISMessage.timestamp.asc(),
            AISMessage.id.asc(),
        )
        .limit(limit)
    ).all()

    points = [
        TrajectoryPoint(**position_response(message).model_dump())
        for message in messages
    ]

    coordinates = [[point.longitude, point.latitude] for point in points]

    if len(coordinates) == 1:
        geometry = {
            "type": "Point",
            "coordinates": coordinates[0],
        }
    else:
        geometry = {
            "type": "LineString",
            "coordinates": coordinates,
        }

    return VesselTrajectoryResponse(
        mmsi=mmsi,
        point_count=len(points),
        start_time=(points[0].timestamp if points else None),
        end_time=(points[-1].timestamp if points else None),
        geometry=geometry,
        points=points,
    )
