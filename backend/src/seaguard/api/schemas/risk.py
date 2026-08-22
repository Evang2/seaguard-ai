from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RiskLevel = Literal[
    "low",
    "medium",
    "high",
    "critical",
]

RuleSeverity = Literal[
    "none",
    "warning",
    "high",
    "critical",
]


class RiskAssessmentResponse(BaseModel):
    """One persisted hybrid investigation-priority assessment."""

    id: int
    ais_message_id: int
    mmsi: str = Field(pattern=r"^\d{9}$")
    observed_at: datetime
    latitude: float
    longitude: float
    ml_anomaly_score: float
    ml_anomaly_percentile: float = Field(
        ge=0.0,
        le=100.0,
    )
    rule_flag_count: int = Field(ge=0)
    rule_severity: RuleSeverity
    detector_agreement: bool
    risk_level: RiskLevel
    risk_reasons: str
    assessment_version: str


class RiskAssessmentListResponse(BaseModel):
    """Paginated hybrid-risk search response."""

    items: list[RiskAssessmentResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
