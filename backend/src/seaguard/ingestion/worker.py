from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from seaguard.db.ais_importer import import_clean_ais_csv
from seaguard.ingestion.analytics import (
    IngestionAnalyticsContext,
    IngestionAnalyticsSummary,
)
from seaguard.ingestion.directory import DiscoveredAISFile
from seaguard.ingestion.registry import claim_ingestion_file

IngestionAction = Literal[
    "imported",
    "skipped",
]

AnalyticsStatus = Literal[
    "not_requested",
    "skipped",
    "completed",
    "failed",
]

AnalyticsRunner = Callable[
    [Session, IngestionAnalyticsContext],
    IngestionAnalyticsSummary,
]


@dataclass(frozen=True)
class IngestionOutcome:
    """Result of processing one discovered AIS file."""

    job_id: int
    file_name: str
    action: IngestionAction

    rows_read: int = 0
    rows_imported: int = 0
    rows_rejected: int = 0
    duplicates_skipped: int = 0

    analytics_status: AnalyticsStatus = "not_requested"
    analytics_summary: IngestionAnalyticsSummary | None = None
    analytics_error: str | None = None


def process_discovered_file(
    session: Session,
    discovered: DiscoveredAISFile,
    *,
    chunk_size: int = 5_000,
    insert_batch_size: int = 1_000,
    analytics_runner: AnalyticsRunner | None = None,
) -> IngestionOutcome:
    """
    Process one stable incoming AIS CSV.

    Import identity is claimed by SHA-256 before the importer runs.

    A completed SHA is skipped.

    When an analytics runner is provided, post-ingestion analytics run
    only after the AIS import succeeds. Analytics failure does not turn
    a successfully completed AIS import back into a failed import job.
    """

    claim = claim_ingestion_file(
        session,
        discovered,
    )

    if not claim.should_process:
        return IngestionOutcome(
            job_id=claim.job_id,
            file_name=discovered.name,
            action="skipped",
            analytics_status="skipped",
        )

    summary = import_clean_ais_csv(
        session,
        discovered.path,
        chunk_size=chunk_size,
        insert_batch_size=insert_batch_size,
        existing_job_id=claim.job_id,
    )

    if analytics_runner is None:
        return IngestionOutcome(
            job_id=summary.job_id,
            file_name=discovered.name,
            action="imported",
            rows_read=summary.rows_read,
            rows_imported=summary.rows_imported,
            rows_rejected=summary.rows_rejected,
            duplicates_skipped=summary.duplicates_skipped,
            analytics_status="not_requested",
        )

    if summary.rows_imported == 0:
        return IngestionOutcome(
            job_id=summary.job_id,
            file_name=discovered.name,
            action="imported",
            rows_read=summary.rows_read,
            rows_imported=summary.rows_imported,
            rows_rejected=summary.rows_rejected,
            duplicates_skipped=summary.duplicates_skipped,
            analytics_status="skipped",
        )

    context = IngestionAnalyticsContext(
        job_id=summary.job_id,
        source_file=discovered.path,
        rows_read=summary.rows_read,
        rows_imported=summary.rows_imported,
        rows_rejected=summary.rows_rejected,
        duplicates_skipped=summary.duplicates_skipped,
    )

    try:
        analytics_summary = analytics_runner(
            session,
            context,
        )
    except Exception as error:
        return IngestionOutcome(
            job_id=summary.job_id,
            file_name=discovered.name,
            action="imported",
            rows_read=summary.rows_read,
            rows_imported=summary.rows_imported,
            rows_rejected=summary.rows_rejected,
            duplicates_skipped=summary.duplicates_skipped,
            analytics_status="failed",
            analytics_error=(str(error).strip() or "Unknown analytics error.")[:4000],
        )

    return IngestionOutcome(
        job_id=summary.job_id,
        file_name=discovered.name,
        action="imported",
        rows_read=summary.rows_read,
        rows_imported=summary.rows_imported,
        rows_rejected=summary.rows_rejected,
        duplicates_skipped=summary.duplicates_skipped,
        analytics_status="completed",
        analytics_summary=analytics_summary,
    )
