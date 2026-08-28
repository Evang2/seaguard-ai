from datetime import datetime

from pydantic import BaseModel, Field


class LiveImportStatus(BaseModel):
    job_id: int
    source_file: str
    status: str

    rows_read: int = Field(ge=0)
    rows_imported: int = Field(ge=0)
    rows_rejected: int = Field(ge=0)
    duplicates_skipped: int = Field(ge=0)

    started_at: datetime
    finished_at: datetime | None


class LiveStatusResponse(BaseModel):
    server_time: datetime

    latest_ais_timestamp: datetime | None

    vessel_count: int = Field(ge=0)
    message_count: int = Field(ge=0)

    ingestion_active: bool

    latest_import: LiveImportStatus | None
