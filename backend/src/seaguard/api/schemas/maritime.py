from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VesselSummary(BaseModel):
    """Summary information about one vessel."""

    model_config = ConfigDict(from_attributes=True)

    mmsi: str
    imo: str | None = None
    name: str | None = None
    call_sign: str | None = None
    vessel_type: int | None = None
    length_m: float | None = None
    width_m: float | None = None
    draft_m: float | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class VesselListResponse(BaseModel):
    """Paginated vessel-search response."""

    items: list[VesselSummary]
    total: int
    limit: int
    offset: int


class PositionResponse(BaseModel):
    """One AIS position observation."""

    id: int
    timestamp: datetime
    latitude: float
    longitude: float
    sog: float | None = None
    cog: float | None = None
    heading: float | None = None
    navigation_status: int | None = None


class VesselDetail(VesselSummary):
    """Detailed vessel response."""

    message_count: int
    alert_count: int
    latest_position: PositionResponse | None = None


class TrajectoryPoint(PositionResponse):
    """One point in a vessel trajectory."""

    pass


class VesselTrajectoryResponse(BaseModel):
    """Ordered vessel trajectory and GeoJSON geometry."""

    mmsi: str
    point_count: int
    start_time: datetime | None = None
    end_time: datetime | None = None
    geometry: dict[str, Any]
    points: list[TrajectoryPoint]


class RecentPositionResponse(PositionResponse):
    """Latest known position of a vessel."""

    mmsi: str
    vessel_name: str | None = None
    vessel_type: int | None = None


class RecentPositionsResponse(BaseModel):
    """Collection of latest vessel positions."""

    items: list[RecentPositionResponse]
    total: int


class AnomalyResponse(BaseModel):
    """One stored explainable anomaly alert."""

    id: int
    mmsi: str
    observed_at: datetime
    anomaly_type: str
    severity: str
    metric_name: str
    metric_value: float | None = None
    threshold: float | None = None
    message: str


class AnomalyListResponse(BaseModel):
    """Paginated anomaly-alert response."""

    items: list[AnomalyResponse]
    total: int
    limit: int
    offset: int


class APIMessage(BaseModel):
    """Simple API status response."""

    message: str = Field(min_length=1)
