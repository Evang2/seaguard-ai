from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from seaguard.db.ais_importer import (
    import_clean_ais_csv,
)
from seaguard.ingestion.directory import (
    DiscoveredAISFile,
)
from seaguard.ingestion.registry import (
    claim_ingestion_file,
)

IngestionAction = Literal[
    "imported",
    "skipped",
]


@dataclass(frozen=True)
class IngestionOutcome:
    """
    Result of processing one discovered AIS file.
    """

    job_id: int
    file_name: str
    action: IngestionAction
    rows_read: int = 0
    rows_imported: int = 0
    rows_rejected: int = 0
    duplicates_skipped: int = 0


def process_discovered_file(
    session: Session,
    discovered: DiscoveredAISFile,
    *,
    chunk_size: int = 5_000,
    insert_batch_size: int = 1_000,
) -> IngestionOutcome:
    """
    Process one stable incoming AIS CSV.

    The SHA-256 registry is checked before the real importer
    is invoked.

    Completed files are skipped.

    New, failed, or interrupted jobs reuse the claimed
    import_jobs row.
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
        )

    summary = import_clean_ais_csv(
        session,
        discovered.path,
        chunk_size=chunk_size,
        insert_batch_size=(insert_batch_size),
        existing_job_id=(claim.job_id),
    )

    return IngestionOutcome(
        job_id=summary.job_id,
        file_name=discovered.name,
        action="imported",
        rows_read=summary.rows_read,
        rows_imported=(summary.rows_imported),
        rows_rejected=(summary.rows_rejected),
        duplicates_skipped=(summary.duplicates_skipped),
    )
