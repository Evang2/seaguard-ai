from __future__ import annotations

from sqlalchemy.orm import Session

from seaguard.collision.persistence import (
    persist_collision_snapshot,
)
from seaguard.ingestion.analytics import (
    AnalyticsStageResult,
    IngestionAnalyticsContext,
)


def persist_live_collision_snapshot(
    session: Session,
    _context: IngestionAnalyticsContext,
) -> AnalyticsStageResult:
    """
    Recompute CPA/TCPA collision encounters from the latest AIS state.

    This deliberately reuses SeaGuard's milestone-6 collision persistence
    implementation. That implementation is idempotent for a pair of source
    AIS messages plus assessment version, so retrying analytics does not
    duplicate the same encounter.
    """

    result = persist_collision_snapshot(
        session,
    )

    return AnalyticsStageResult(
        name="collision_snapshot",
        processed=(result.assessed_candidate_count),
        created=(result.inserted_count),
    )
