from datetime import datetime

from pydantic import BaseModel, Field


class PlaybackPosition(BaseModel):
    """One vessel state in a historical playback frame."""

    id: int
    mmsi: str = Field(pattern=r"^\d{9}$")
    vessel_name: str | None = None
    timestamp: datetime
    latitude: float
    longitude: float
    sog: float | None = None
    cog: float | None = None
    heading: float | None = None
    navigation_status: int | None = None


class PlaybackBoundsResponse(BaseModel):
    """Available AIS time range for playback."""

    start_time: datetime | None
    end_time: datetime | None
    observation_count: int = Field(ge=0)
    vessel_count: int = Field(ge=0)


class PlaybackSnapshotResponse(BaseModel):
    """One historical playback frame."""

    requested_at: datetime
    window_start: datetime
    tolerance_minutes: float = Field(gt=0)
    total: int = Field(ge=0)
    items: list[PlaybackPosition]
