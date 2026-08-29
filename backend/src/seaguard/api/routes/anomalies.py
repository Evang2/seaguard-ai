from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from seaguard.api.schemas.maritime import AnomalyListResponse
from seaguard.db.models import AISMessage, AnomalyAlert, Vessel
from seaguard.db.session import get_session

router = APIRouter(
    prefix="/api/v1/anomalies",
    tags=["anomalies"],
)

DatabaseSession = Annotated[
    Session,
    Depends(get_session),
]


@router.get(
    "",
    response_model=AnomalyListResponse,
)
def list_anomalies(
    session: DatabaseSession,
    mmsi: Annotated[
        str | None,
        Query(pattern=r"^\d{9}$"),
    ] = None,
    severity: Annotated[
        str | None,
        Query(min_length=1, max_length=16),
    ] = None,
    anomaly_type: Annotated[
        str | None,
        Query(min_length=1, max_length=64),
    ] = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    current_only: Annotated[
        bool,
        Query(
            description=("Restrict alerts to the global active AIS watermark window."),
        ),
    ] = False,
    active_window_minutes: Annotated[
        int,
        Query(
            ge=1,
            le=1440,
            description=(
                "Size of the active AIS window used when current_only is true."
            ),
        ),
    ] = 15,
    limit: Annotated[
        int,
        Query(ge=1, le=500),
    ] = 100,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> AnomalyListResponse:
    """Search stored anomaly alerts."""

    conditions = []

    if current_only:
        watermark = session.scalar(select(func.max(AISMessage.timestamp)))

        if watermark is None:
            return AnomalyListResponse.model_validate(
                {
                    "items": [],
                    "total": 0,
                    "limit": limit,
                    "offset": offset,
                }
            )

        active_cutoff = watermark - timedelta(
            minutes=active_window_minutes,
        )

        conditions.extend(
            [
                AISMessage.timestamp >= active_cutoff,
                AISMessage.timestamp <= watermark,
            ]
        )

    if mmsi is not None:
        conditions.append(Vessel.mmsi == mmsi)

    if severity is not None:
        conditions.append(AnomalyAlert.severity == severity)

    if anomaly_type is not None:
        conditions.append(AnomalyAlert.anomaly_type == anomaly_type)

    if start_time is not None:
        conditions.append(AnomalyAlert.observed_at >= start_time)

    if end_time is not None:
        conditions.append(AnomalyAlert.observed_at <= end_time)

    count_statement = (
        select(func.count(AnomalyAlert.id))
        .join(
            Vessel,
            Vessel.id == AnomalyAlert.vessel_id,
        )
        .join(
            AISMessage,
            AISMessage.id == AnomalyAlert.ais_message_id,
        )
        .where(*conditions)
    )

    query_statement = (
        select(
            AnomalyAlert,
            Vessel.mmsi,
            AISMessage.latitude,
            AISMessage.longitude,
        )
        .join(
            Vessel,
            Vessel.id == AnomalyAlert.vessel_id,
        )
        .join(
            AISMessage,
            AISMessage.id == AnomalyAlert.ais_message_id,
        )
        .where(*conditions)
        .order_by(
            AnomalyAlert.observed_at.desc(),
            AnomalyAlert.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    total = session.scalar(count_statement) or 0
    rows = session.execute(query_statement).all()

    items = [
        {
            "id": alert.id,
            "mmsi": row_mmsi,
            "observed_at": alert.observed_at,
            "latitude": latitude,
            "longitude": longitude,
            "anomaly_type": alert.anomaly_type,
            "severity": alert.severity,
            "metric_name": alert.metric_name,
            "metric_value": alert.metric_value,
            "threshold": alert.threshold,
            "message": alert.message,
        }
        for alert, row_mmsi, latitude, longitude in rows
    ]

    return AnomalyListResponse.model_validate(  # noqa: F706
        {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )
