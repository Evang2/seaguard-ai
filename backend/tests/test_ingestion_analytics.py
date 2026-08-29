from pathlib import Path
from typing import Any

import pytest

from seaguard.db.ais_importer import ImportSummary
from seaguard.ingestion.analytics import (
    AnalyticsStageResult,
    IngestionAnalyticsContext,
    IngestionAnalyticsSummary,
    run_ingestion_analytics,
)
from seaguard.ingestion.directory import DiscoveredAISFile
from seaguard.ingestion.registry import IngestionClaim
from seaguard.ingestion.worker import process_discovered_file


class FakeSession:
    def __init__(self) -> None:
        self.rollback_count = 0

    def rollback(self) -> None:
        self.rollback_count += 1


def discovered_file() -> DiscoveredAISFile:
    return DiscoveredAISFile(
        path=Path("/tmp/incoming.csv"),
        size_bytes=123,
        modified_ns=456,
        sha256="a" * 64,
    )


def test_analytics_stages_run_in_order() -> None:
    session = FakeSession()
    calls: list[str] = []

    context = IngestionAnalyticsContext(
        job_id=10,
        source_file=Path("/tmp/incoming.csv"),
        rows_read=3,
        rows_imported=3,
        rows_rejected=0,
        duplicates_skipped=0,
    )

    def anomalies(
        db: Any,
        incoming: IngestionAnalyticsContext,
    ) -> AnalyticsStageResult:
        assert incoming.job_id == 10
        calls.append("anomalies")

        return AnalyticsStageResult(
            name="anomalies",
            processed=3,
            created=1,
        )

    def risk(
        db: Any,
        incoming: IngestionAnalyticsContext,
    ) -> AnalyticsStageResult:
        calls.append("risk")

        return AnalyticsStageResult(
            name="risk",
            processed=3,
            created=3,
        )

    result = run_ingestion_analytics(
        session,  # type: ignore[arg-type]
        context,
        stages=[
            anomalies,
            risk,
        ],
    )

    assert calls == [
        "anomalies",
        "risk",
    ]

    assert result.stages == (
        AnalyticsStageResult(
            name="anomalies",
            processed=3,
            created=1,
        ),
        AnalyticsStageResult(
            name="risk",
            processed=3,
            created=3,
        ),
    )


def test_analytics_failure_rolls_back_stage() -> None:
    session = FakeSession()

    context = IngestionAnalyticsContext(
        job_id=10,
        source_file=Path("/tmp/incoming.csv"),
        rows_read=1,
        rows_imported=1,
        rows_rejected=0,
        duplicates_skipped=0,
    )

    def failing_stage(
        db: Any,
        incoming: IngestionAnalyticsContext,
    ) -> AnalyticsStageResult:
        raise RuntimeError("analytics exploded")

    with pytest.raises(
        RuntimeError,
        match="analytics exploded",
    ):
        run_ingestion_analytics(
            session,  # type: ignore[arg-type]
            context,
            stages=[
                failing_stage,
            ],
        )

    assert session.rollback_count == 1


def test_worker_runs_analytics_after_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_claim(
        session: Any,
        discovered: DiscoveredAISFile,
    ) -> IngestionClaim:
        calls.append("claim")

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
        calls.append("import")

        return ImportSummary(
            job_id=51,
            source_file=str(source_file),
            rows_read=3,
            rows_imported=3,
            rows_rejected=0,
            duplicates_skipped=0,
        )

    def fake_analytics(
        session: Any,
        context: IngestionAnalyticsContext,
    ) -> IngestionAnalyticsSummary:
        calls.append("analytics")

        assert context.job_id == 51
        assert context.rows_imported == 3

        return IngestionAnalyticsSummary(
            stages=(
                AnalyticsStageResult(
                    name="test",
                    processed=3,
                    created=2,
                ),
            )
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
        analytics_runner=fake_analytics,
    )

    assert calls == [
        "claim",
        "import",
        "analytics",
    ]

    assert outcome.action == "imported"
    assert outcome.analytics_status == "completed"
    assert outcome.analytics_summary is not None


def test_worker_keeps_successful_import_when_analytics_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_claim(
        session: Any,
        discovered: DiscoveredAISFile,
    ) -> IngestionClaim:
        return IngestionClaim(
            job_id=52,
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
        return ImportSummary(
            job_id=52,
            source_file=str(source_file),
            rows_read=1,
            rows_imported=1,
            rows_rejected=0,
            duplicates_skipped=0,
        )

    def failing_analytics(
        session: Any,
        context: IngestionAnalyticsContext,
    ) -> IngestionAnalyticsSummary:
        raise RuntimeError("risk model unavailable")

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
        analytics_runner=failing_analytics,
    )

    assert outcome.action == "imported"
    assert outcome.rows_imported == 1
    assert outcome.analytics_status == "failed"
    assert outcome.analytics_error == "risk model unavailable"
