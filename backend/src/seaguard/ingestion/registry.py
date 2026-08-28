from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from seaguard.ingestion.directory import DiscoveredAISFile


@dataclass(frozen=True)
class IngestionClaim:
    """
    Result of checking an incoming AIS file against
    the persistent ingestion registry.
    """

    job_id: int
    should_process: bool
    previous_status: str


def _utc_now() -> datetime:
    return datetime.now(UTC)


def claim_ingestion_file(
    session: Session,
    discovered: DiscoveredAISFile,
) -> IngestionClaim:
    """
    Register an incoming AIS file and determine whether
    it should be processed.

    New SHA-256:
        create a pending import job.

    Completed SHA-256:
        skip it permanently.

    Pending or failed SHA-256:
        allow another attempt.
    """

    now = _utc_now()

    session.execute(
        text(
            """
            INSERT INTO import_jobs (
                source_file,
                status,
                rows_read,
                rows_imported,
                rows_rejected,
                duplicates_skipped,
                error_message,
                started_at,
                finished_at,
                content_sha256,
                file_size_bytes
            )
            VALUES (
                :source_file,
                'pending',
                0,
                0,
                0,
                0,
                NULL,
                :started_at,
                NULL,
                :content_sha256,
                :file_size_bytes
            )
            ON CONFLICT (content_sha256)
            DO NOTHING
            """
        ),
        {
            "source_file": str(discovered.path),
            "started_at": now,
            "content_sha256": discovered.sha256,
            "file_size_bytes": discovered.size_bytes,
        },
    )

    row = session.execute(
        text(
            """
            SELECT
                id,
                status
            FROM import_jobs
            WHERE content_sha256 = :content_sha256
            LIMIT 1
            """
        ),
        {
            "content_sha256": discovered.sha256,
        },
    ).one()

    job_id = int(row.id)

    previous_status = str(row.status)

    if previous_status == "completed":
        session.commit()

        return IngestionClaim(
            job_id=job_id,
            should_process=False,
            previous_status=previous_status,
        )

    # A failed job or a job interrupted by a previous
    # worker process is safe to attempt again.
    session.execute(
        text(
            """
            UPDATE import_jobs
            SET
                source_file = :source_file,
                status = 'pending',
                error_message = NULL,
                started_at = :started_at,
                finished_at = NULL,
                file_size_bytes = :file_size_bytes
            WHERE id = :job_id
            """
        ),
        {
            "source_file": str(discovered.path),
            "started_at": now,
            "file_size_bytes": discovered.size_bytes,
            "job_id": job_id,
        },
    )

    session.commit()

    return IngestionClaim(
        job_id=job_id,
        should_process=True,
        previous_status=previous_status,
    )


def complete_ingestion_job(
    session: Session,
    job_id: int,
    *,
    rows_read: int,
    rows_imported: int,
    rows_rejected: int,
    duplicates_skipped: int,
) -> None:
    """
    Mark one watched AIS file as successfully processed.
    """

    session.execute(
        text(
            """
            UPDATE import_jobs
            SET
                status = 'completed',
                rows_read = :rows_read,
                rows_imported = :rows_imported,
                rows_rejected = :rows_rejected,
                duplicates_skipped = :duplicates_skipped,
                error_message = NULL,
                finished_at = :finished_at
            WHERE id = :job_id
            """
        ),
        {
            "rows_read": rows_read,
            "rows_imported": rows_imported,
            "rows_rejected": rows_rejected,
            "duplicates_skipped": duplicates_skipped,
            "finished_at": _utc_now(),
            "job_id": job_id,
        },
    )

    session.commit()


def fail_ingestion_job(
    session: Session,
    job_id: int,
    error: str,
) -> None:
    """
    Record a failed ingestion attempt.

    Failed files may be retried by a later watcher run.
    """

    cleaned_error = error.strip() or "Unknown ingestion error."

    session.execute(
        text(
            """
            UPDATE import_jobs
            SET
                status = 'failed',
                error_message = :error_message,
                finished_at = :finished_at
            WHERE id = :job_id
            """
        ),
        {
            "error_message": cleaned_error[:4000],
            "finished_at": _utc_now(),
            "job_id": job_id,
        },
    )

    session.commit()
