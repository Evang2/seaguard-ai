from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class IngestionAnalyticsContext:
    """Information about one successfully imported AIS file."""

    job_id: int
    source_file: Path
    rows_read: int
    rows_imported: int
    rows_rejected: int
    duplicates_skipped: int


@dataclass(frozen=True)
class AnalyticsStageResult:
    """Outcome from one post-ingestion analytics stage."""

    name: str
    processed: int = 0
    created: int = 0


@dataclass(frozen=True)
class IngestionAnalyticsSummary:
    """Combined result from the ordered analytics stages."""

    stages: tuple[AnalyticsStageResult, ...]


AnalyticsStage = Callable[
    [Session, IngestionAnalyticsContext],
    AnalyticsStageResult,
]


def run_ingestion_analytics(
    session: Session,
    context: IngestionAnalyticsContext,
    *,
    stages: Sequence[AnalyticsStage],
) -> IngestionAnalyticsSummary:
    """
    Run post-ingestion analytics in dependency order.

    The AIS import itself has already completed before this function
    is called. If an analytics stage fails, its transaction is rolled
    back and the error is propagated to the worker. The completed AIS
    import is not reverted.
    """

    results: list[AnalyticsStageResult] = []

    for stage in stages:
        try:
            result = stage(
                session,
                context,
            )
        except Exception:
            session.rollback()
            raise

        results.append(result)

    return IngestionAnalyticsSummary(stages=tuple(results))
