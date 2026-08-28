from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from seaguard.api.schemas.live import (
    LiveImportStatus,
    LiveStatusResponse,
)
from seaguard.db.models import (
    AISMessage,
    ImportJob,
    Vessel,
)
from seaguard.db.session import get_session

router = APIRouter(
    prefix="/api/v1/live",
    tags=["live"],
)


DatabaseSession = Annotated[
    Session,
    Depends(get_session),
]


@router.get(
    "/status",
    response_model=LiveStatusResponse,
)
def get_live_status(
    session: DatabaseSession,
) -> LiveStatusResponse:
    """
    Return the current operational state of SeaGuard.

    This endpoint describes what is currently stored and
    whether an AIS ingestion job is active.
    """

    vessel_count = session.scalar(select(func.count(Vessel.id))) or 0

    message_count = session.scalar(select(func.count(AISMessage.id))) or 0

    latest_ais_timestamp = session.scalar(select(func.max(AISMessage.timestamp)))

    latest_import_job = session.scalar(
        select(ImportJob)
        .order_by(
            ImportJob.started_at.desc(),
            ImportJob.id.desc(),
        )
        .limit(1)
    )

    latest_import = None

    if latest_import_job is not None:
        latest_import = LiveImportStatus(
            job_id=latest_import_job.id,
            source_file=(latest_import_job.source_file),
            status=(latest_import_job.status),
            rows_read=(latest_import_job.rows_read),
            rows_imported=(latest_import_job.rows_imported),
            rows_rejected=(latest_import_job.rows_rejected),
            duplicates_skipped=(latest_import_job.duplicates_skipped),
            started_at=(latest_import_job.started_at),
            finished_at=(latest_import_job.finished_at),
        )

    ingestion_active = latest_import_job is not None and latest_import_job.status in {
        "pending",
        "running",
    }

    return LiveStatusResponse(
        server_time=datetime.now(UTC),
        latest_ais_timestamp=(latest_ais_timestamp),
        vessel_count=int(vessel_count),
        message_count=int(message_count),
        ingestion_active=(ingestion_active),
        latest_import=latest_import,
    )
