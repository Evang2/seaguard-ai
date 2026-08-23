from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

CollisionRiskLevel = Literal[
    "low",
    "medium",
    "high",
    "critical",
]


class CollisionVesselState(BaseModel):
    vessel_id: int
    ais_message_id: int

    mmsi: str
    name: str | None = None

    observed_at: datetime

    latitude: float
    longitude: float

    sog: float | None = None
    cog: float | None = None


class CollisionEncounterResponse(BaseModel):
    id: int
    observed_at: datetime

    vessel_a: CollisionVesselState
    vessel_b: CollisionVesselState

    current_distance_nm: float = Field(ge=0.0)

    cpa_distance_nm: float = Field(ge=0.0)

    tcpa_minutes: float | None = None

    relative_speed_knots: float = Field(ge=0.0)

    closing_speed_knots: float

    bearing_from_a_to_b_degrees: float = Field(
        ge=0.0,
        lt=360.0,
    )

    risk_level: CollisionRiskLevel

    reasons: list[str]

    assessment_version: str
    created_at: datetime


class CollisionEncounterListResponse(BaseModel):
    items: list[CollisionEncounterResponse]

    total: int = Field(ge=0)

    limit: int = Field(ge=1)

    offset: int = Field(ge=0)


class CollisionSummaryResponse(BaseModel):
    total: int = Field(ge=0)

    low: int = Field(ge=0)

    medium: int = Field(ge=0)

    high: int = Field(ge=0)

    critical: int = Field(ge=0)
