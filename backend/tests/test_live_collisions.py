from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from seaguard.ingestion.analytics import (
    IngestionAnalyticsContext,
)
from seaguard.ingestion.live_collisions import (
    persist_live_collision_snapshot,
)


def test_live_collision_stage_reuses_collision_persistence(
    monkeypatch,
) -> None:
    session = Mock()

    context = IngestionAnalyticsContext(
        job_id=42,
        source_file=Path("/tmp/live-collision.csv"),
        rows_read=2,
        rows_imported=2,
        rows_rejected=0,
        duplicates_skipped=0,
    )

    persistence_result = SimpleNamespace(
        assessed_candidate_count=7,
        inserted_count=3,
    )

    persist_mock = Mock(return_value=persistence_result)

    monkeypatch.setattr(
        "seaguard.ingestion.live_collisions.persist_collision_snapshot",
        persist_mock,
    )

    result = persist_live_collision_snapshot(
        session,
        context,
    )

    persist_mock.assert_called_once_with(session)

    assert result.name == "collision_snapshot"
    assert result.processed == 7
    assert result.created == 3
