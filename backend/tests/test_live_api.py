from datetime import UTC, datetime

from seaguard.api.schemas.live import (
    LiveImportStatus,
    LiveStatusResponse,
)
from seaguard.main import app


def test_live_status_route_is_registered() -> None:
    paths = set(app.openapi()["paths"])

    assert "/api/v1/live/status" in paths


def test_live_status_schema_without_import() -> None:
    response = LiveStatusResponse(
        server_time=datetime.now(UTC),
        latest_ais_timestamp=None,
        vessel_count=0,
        message_count=0,
        ingestion_active=False,
        latest_import=None,
    )

    assert response.vessel_count == 0
    assert response.message_count == 0
    assert not response.ingestion_active


def test_live_status_schema_with_import() -> None:
    now = datetime.now(UTC)

    import_status = LiveImportStatus(
        job_id=12,
        source_file=("/data/incoming/ais.csv"),
        status="running",
        rows_read=500,
        rows_imported=490,
        rows_rejected=5,
        duplicates_skipped=5,
        started_at=now,
        finished_at=None,
    )

    response = LiveStatusResponse(
        server_time=now,
        latest_ais_timestamp=now,
        vessel_count=24,
        message_count=500,
        ingestion_active=True,
        latest_import=import_status,
    )

    assert response.ingestion_active
    assert response.latest_import is not None
    assert response.latest_import.job_id == 12
