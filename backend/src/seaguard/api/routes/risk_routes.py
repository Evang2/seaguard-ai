from datetime import datetime, timedelta
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
)
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from seaguard.api.schemas.risk import (
    RiskAssessmentListResponse,
    RiskLevel,
    RiskSummaryResponse,
)
from seaguard.db.models import AISMessage, Vessel
from seaguard.db.risk_models import RiskAssessment
from seaguard.db.session import get_session

router = APIRouter(
    prefix="/api/v1/risk",
    tags=["risk"],
)

DatabaseSession = Annotated[
    Session,
    Depends(get_session),
]

RISK_PRIORITY = case(
    {
        "low": 1,
        "medium": 2,
        "high": 3,
        "critical": 4,
    },
    value=RiskAssessment.risk_level,
    else_=0,
)


def _active_risk_window(
    session: Session,
    *,
    active_window_minutes: int,
) -> tuple[datetime, datetime] | None:
    """Return the global AIS watermark window used by Current mode."""

    watermark = session.scalar(select(func.max(AISMessage.timestamp)))

    if watermark is None:
        return None

    cutoff = watermark - timedelta(
        minutes=active_window_minutes,
    )

    return cutoff, watermark


def _empty_risk_list(
    *,
    limit: int,
    offset: int,
) -> RiskAssessmentListResponse:
    return RiskAssessmentListResponse.model_validate(
        {
            "items": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
        }
    )


def _search_risk_assessments(
    session: Session,
    *,
    mmsi: str | None,
    risk_level: RiskLevel | None,
    minimum_ml_percentile: float | None,
    detector_agreement: bool | None,
    start_time: datetime | None,
    end_time: datetime | None,
    current_only: bool,
    active_window_minutes: int,
    limit: int,
    offset: int,
) -> RiskAssessmentListResponse:
    """Execute one persisted hybrid-risk search."""

    if start_time is not None and end_time is not None and start_time > end_time:
        raise HTTPException(
            status_code=422,
            detail=("start_time must be earlier than or equal to end_time."),
        )

    conditions = []

    if current_only:
        active_window = _active_risk_window(
            session,
            active_window_minutes=active_window_minutes,
        )

        if active_window is None:
            return _empty_risk_list(
                limit=limit,
                offset=offset,
            )

        active_cutoff, watermark = active_window

        conditions.extend(
            [
                AISMessage.timestamp >= active_cutoff,
                AISMessage.timestamp <= watermark,
            ]
        )

    if mmsi is not None:
        conditions.append(Vessel.mmsi == mmsi)

    if risk_level is not None:
        conditions.append(RiskAssessment.risk_level == risk_level)

    if minimum_ml_percentile is not None:
        conditions.append(RiskAssessment.ml_anomaly_percentile >= minimum_ml_percentile)

    if detector_agreement is not None:
        conditions.append(RiskAssessment.detector_agreement == detector_agreement)

    if start_time is not None:
        conditions.append(RiskAssessment.observed_at >= start_time)

    if end_time is not None:
        conditions.append(RiskAssessment.observed_at <= end_time)

    count_statement = (
        select(func.count(RiskAssessment.id))
        .join(
            Vessel,
            Vessel.id == RiskAssessment.vessel_id,
        )
        .join(
            AISMessage,
            AISMessage.id == RiskAssessment.ais_message_id,
        )
        .where(*conditions)
    )

    query_statement = (
        select(
            RiskAssessment,
            Vessel.mmsi,
            AISMessage.latitude,
            AISMessage.longitude,
        )
        .join(
            Vessel,
            Vessel.id == RiskAssessment.vessel_id,
        )
        .join(
            AISMessage,
            AISMessage.id == RiskAssessment.ais_message_id,
        )
        .where(*conditions)
        .order_by(
            RISK_PRIORITY.desc(),
            RiskAssessment.ml_anomaly_percentile.desc(),
            RiskAssessment.observed_at.desc(),
            RiskAssessment.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    total = session.scalar(count_statement) or 0
    rows = session.execute(query_statement).all()

    items = [
        {
            "id": assessment.id,
            "ais_message_id": assessment.ais_message_id,
            "mmsi": row_mmsi,
            "observed_at": assessment.observed_at,
            "latitude": latitude,
            "longitude": longitude,
            "ml_anomaly_score": (assessment.ml_anomaly_score),
            "ml_anomaly_percentile": (assessment.ml_anomaly_percentile),
            "rule_flag_count": assessment.rule_flag_count,
            "rule_severity": assessment.rule_severity,
            "detector_agreement": (assessment.detector_agreement),
            "risk_level": assessment.risk_level,
            "risk_reasons": assessment.risk_reasons,
            "assessment_version": (assessment.assessment_version),
        }
        for (
            assessment,
            row_mmsi,
            latitude,
            longitude,
        ) in rows
    ]

    return RiskAssessmentListResponse.model_validate(
        {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@router.get(
    "",
    response_model=RiskAssessmentListResponse,
)
def list_risk_assessments(
    session: DatabaseSession,
    mmsi: Annotated[
        str | None,
        Query(
            pattern=r"^\d{9}$",
            description="Optional vessel MMSI filter.",
        ),
    ] = None,
    risk_level: Annotated[
        RiskLevel | None,
        Query(description=("Filter by persisted investigation priority.")),
    ] = None,
    minimum_ml_percentile: Annotated[
        float | None,
        Query(
            ge=0.0,
            le=100.0,
            description=("Minimum calibrated ML anomaly percentile."),
        ),
    ] = None,
    detector_agreement: Annotated[
        bool | None,
        Query(description=("Filter by agreement between rule and ML evidence.")),
    ] = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    current_only: Annotated[
        bool,
        Query(
            description=("Restrict results to the global active AIS watermark window."),
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
) -> RiskAssessmentListResponse:
    """Search persisted hybrid investigation priorities."""

    return _search_risk_assessments(
        session,
        mmsi=mmsi,
        risk_level=risk_level,
        minimum_ml_percentile=minimum_ml_percentile,
        detector_agreement=detector_agreement,
        start_time=start_time,
        end_time=end_time,
        current_only=current_only,
        active_window_minutes=active_window_minutes,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/summary",
    response_model=RiskSummaryResponse,
)
def get_risk_summary(
    session: DatabaseSession,
    current_only: Annotated[
        bool,
        Query(
            description=(
                "Restrict statistics to the global active AIS watermark window."
            ),
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
) -> RiskSummaryResponse:
    """Return aggregate persisted hybrid-risk statistics."""

    conditions = []

    if current_only:
        active_window = _active_risk_window(
            session,
            active_window_minutes=active_window_minutes,
        )

        if active_window is None:
            return RiskSummaryResponse(
                total=0,
                low=0,
                medium=0,
                high=0,
                critical=0,
                elevated=0,
                detector_agreement=0,
            )

        active_cutoff, watermark = active_window

        conditions.extend(
            [
                AISMessage.timestamp >= active_cutoff,
                AISMessage.timestamp <= watermark,
            ]
        )

    statement = (
        select(
            func.count(RiskAssessment.id).label("total"),
            func.count(RiskAssessment.id)
            .filter(RiskAssessment.risk_level == "low")
            .label("low"),
            func.count(RiskAssessment.id)
            .filter(RiskAssessment.risk_level == "medium")
            .label("medium"),
            func.count(RiskAssessment.id)
            .filter(RiskAssessment.risk_level == "high")
            .label("high"),
            func.count(RiskAssessment.id)
            .filter(RiskAssessment.risk_level == "critical")
            .label("critical"),
            func.count(RiskAssessment.id)
            .filter(RiskAssessment.risk_level != "low")
            .label("elevated"),
            func.count(RiskAssessment.id)
            .filter(RiskAssessment.detector_agreement.is_(True))
            .label("detector_agreement"),
        )
        .select_from(RiskAssessment)
        .join(
            AISMessage,
            AISMessage.id == RiskAssessment.ais_message_id,
        )
        .where(*conditions)
    )

    row = session.execute(statement).one()

    return RiskSummaryResponse(
        total=row.total,
        low=row.low,
        medium=row.medium,
        high=row.high,
        critical=row.critical,
        elevated=row.elevated,
        detector_agreement=(row.detector_agreement),
    )


@router.get(
    "/{mmsi}",
    response_model=RiskAssessmentListResponse,
)
def get_vessel_risk_assessments(
    session: DatabaseSession,
    mmsi: Annotated[
        str,
        Path(pattern=r"^\d{9}$"),
    ],
    risk_level: Annotated[
        RiskLevel | None,
        Query(description=("Filter by persisted investigation priority.")),
    ] = None,
    minimum_ml_percentile: Annotated[
        float | None,
        Query(
            ge=0.0,
            le=100.0,
            description=("Minimum calibrated ML anomaly percentile."),
        ),
    ] = None,
    detector_agreement: Annotated[
        bool | None,
        Query(description=("Filter by agreement between rule and ML evidence.")),
    ] = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    current_only: Annotated[
        bool,
        Query(
            description=("Restrict results to the global active AIS watermark window."),
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
) -> RiskAssessmentListResponse:
    """Return persisted hybrid risk assessments for one vessel."""

    vessel_exists = session.scalar(select(Vessel.id).where(Vessel.mmsi == mmsi))

    if vessel_exists is None:
        raise HTTPException(
            status_code=404,
            detail=f"Vessel {mmsi} was not found.",
        )

    return _search_risk_assessments(
        session,
        mmsi=mmsi,
        risk_level=risk_level,
        minimum_ml_percentile=minimum_ml_percentile,
        detector_agreement=detector_agreement,
        start_time=start_time,
        end_time=end_time,
        current_only=current_only,
        active_window_minutes=active_window_minutes,
        limit=limit,
        offset=offset,
    )
