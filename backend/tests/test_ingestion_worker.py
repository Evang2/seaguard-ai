from pathlib import Path
from typing import Any

import pytest

from seaguard.db.ais_importer import (
    ImportSummary,
)
from seaguard.ingestion.directory import (
    DiscoveredAISFile,
)
from seaguard.ingestion.registry import (
    IngestionClaim,
)
from seaguard.ingestion.worker import (
    process_discovered_file,
)


def discovered_file() -> DiscoveredAISFile:
    return DiscoveredAISFile(
        path=Path("/tmp/incoming.csv"),
        size_bytes=123,
        modified_ns=456,
        sha256="a" * 64,
    )


def test_completed_file_is_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_claim(
        session: Any,
        discovered: DiscoveredAISFile,
    ) -> IngestionClaim:
        return IngestionClaim(
            job_id=42,
            should_process=False,
            previous_status="completed",
        )

    def unexpected_import(
        *args: Any,
        **kwargs: Any,
    ) -> None:
        raise AssertionError("Importer should not be called.")

    monkeypatch.setattr(
        "seaguard.ingestion.worker.claim_ingestion_file",
        fake_claim,
    )

    monkeypatch.setattr(
        "seaguard.ingestion.worker.import_clean_ais_csv",
        unexpected_import,
    )

    outcome = process_discovered_file(
        object(),  # type: ignore[arg-type]
        discovered_file(),
    )

    assert outcome.job_id == 42
    assert outcome.action == "skipped"


def test_claimed_file_uses_existing_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_claim(
        session: Any,
        discovered: DiscoveredAISFile,
    ) -> IngestionClaim:
        return IngestionClaim(
            job_id=51,
            should_process=True,
            previous_status="pending",
        )

    def fake_import(
        session: Any,
        source_file: Path,
        *,
        chunk_size: int,
        insert_batch_size: int,
        maximum_rows: int | None = None,
        existing_job_id: int | None = None,
    ) -> ImportSummary:
        assert source_file == Path("/tmp/incoming.csv")

        assert existing_job_id == 51
        assert chunk_size == 250
        assert insert_batch_size == 100

        return ImportSummary(
            job_id=51,
            source_file=str(source_file),
            rows_read=10,
            rows_imported=8,
            rows_rejected=1,
            duplicates_skipped=1,
        )

    monkeypatch.setattr(
        "seaguard.ingestion.worker.claim_ingestion_file",
        fake_claim,
    )

    monkeypatch.setattr(
        "seaguard.ingestion.worker.import_clean_ais_csv",
        fake_import,
    )

    outcome = process_discovered_file(
        object(),  # type: ignore[arg-type]
        discovered_file(),
        chunk_size=250,
        insert_batch_size=100,
    )

    assert outcome.job_id == 51
    assert outcome.action == "imported"

    assert outcome.rows_read == 10
    assert outcome.rows_imported == 8
    assert outcome.rows_rejected == 1
    assert outcome.duplicates_skipped == 1


def test_import_failure_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_claim(
        session: Any,
        discovered: DiscoveredAISFile,
    ) -> IngestionClaim:
        return IngestionClaim(
            job_id=99,
            should_process=True,
            previous_status="failed",
        )

    def failing_import(
        *args: Any,
        **kwargs: Any,
    ) -> None:
        raise RuntimeError("bad AIS CSV")

    monkeypatch.setattr(
        "seaguard.ingestion.worker.claim_ingestion_file",
        fake_claim,
    )

    monkeypatch.setattr(
        "seaguard.ingestion.worker.import_clean_ais_csv",
        failing_import,
    )

    with pytest.raises(
        RuntimeError,
        match="bad AIS CSV",
    ):
        process_discovered_file(
            object(),  # type: ignore[arg-type]
            discovered_file(),
        )
