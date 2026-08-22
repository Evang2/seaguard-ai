from datetime import datetime
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


def _search_risk_assessments(
    session: Session,
    *,
    mmsi: str | None,
    risk_level: RiskLevel | None,
    minimum_ml_percentile: float | None,
    detector_agreement: bool | None,
    start_time: datetime | None,
    end_time: datetime | None,
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
        limit=limit,
        offset=offset,
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
        limit=limit,
        offset=offset,
    )
