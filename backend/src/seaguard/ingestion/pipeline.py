from __future__ import annotations

from sqlalchemy.orm import Session

from seaguard.ingestion.analytics import (
    IngestionAnalyticsContext,
    IngestionAnalyticsSummary,
    run_ingestion_analytics,
)
from seaguard.ingestion.live_anomalies import (
    persist_live_rule_anomalies,
)
from seaguard.ingestion.live_collisions import (
    persist_live_collision_snapshot,
)
from seaguard.ingestion.live_risk import (
    persist_live_hybrid_risk,
)


def run_live_analytics(
    session: Session,
    context: IngestionAnalyticsContext,
) -> IngestionAnalyticsSummary:
    """
    Run SeaGuard's post-import live analytics stages in dependency order.

    1. Persist deterministic rule-based anomaly alerts.
    2. Score/persist hybrid ML investigation risk.
    3. Recompute/persist CPA/TCPA collision encounters from latest AIS state.
    """

    return run_ingestion_analytics(
        session,
        context,
        stages=(
            persist_live_rule_anomalies,
            persist_live_hybrid_risk,
            persist_live_collision_snapshot,
        ),
    )
