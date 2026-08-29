from __future__ import annotations

from datetime import timedelta

from sqlalchemy import (
    and_,
    exists,
    func,
    or_,
    select,
)

from seaguard.db.collision_models import (
    CollisionEncounterRecord,
)
from seaguard.db.models import AISMessage

DEFAULT_ACTIVE_WINDOW_MINUTES = 15


def current_collision_conditions(
    *,
    active_window_minutes: int = (DEFAULT_ACTIVE_WINDOW_MINUTES),
) -> tuple[
    object,
    object,
]:
    """
    Return SQL predicates identifying a collision encounter as current.

    Historical collision rows are deliberately retained.

    A persisted encounter is considered current only when:

    1. each source AIS message is still the newest message for its vessel;
    2. both source messages fall inside the active AIS window measured
       backwards from the newest AIS timestamp stored in the database.

    The second condition is essential. A vessel last seen in 2024 may still
    have a 2024 message as its latest-ever message, but that does not make the
    vessel operationally current in a 2026 live view.

    AIS newest-message ordering matches the collision snapshot loader:

        timestamp DESC, id DESC
    """

    if active_window_minutes < 1:
        raise ValueError("active_window_minutes must be at least 1.")

    vessel_a_has_newer_message = exists().where(
        AISMessage.vessel_id == CollisionEncounterRecord.vessel_a_id,
        or_(
            AISMessage.timestamp > CollisionEncounterRecord.vessel_a_observed_at,
            and_(
                AISMessage.timestamp == CollisionEncounterRecord.vessel_a_observed_at,
                AISMessage.id > CollisionEncounterRecord.vessel_a_ais_message_id,
            ),
        ),
    )

    vessel_b_has_newer_message = exists().where(
        AISMessage.vessel_id == CollisionEncounterRecord.vessel_b_id,
        or_(
            AISMessage.timestamp > CollisionEncounterRecord.vessel_b_observed_at,
            and_(
                AISMessage.timestamp == CollisionEncounterRecord.vessel_b_observed_at,
                AISMessage.id > CollisionEncounterRecord.vessel_b_ais_message_id,
            ),
        ),
    )

    watermark = select(func.max(AISMessage.timestamp)).scalar_subquery()

    active_cutoff = watermark - timedelta(minutes=active_window_minutes)

    vessel_a_is_current = and_(
        ~vessel_a_has_newer_message,
        CollisionEncounterRecord.vessel_a_observed_at >= active_cutoff,
    )

    vessel_b_is_current = and_(
        ~vessel_b_has_newer_message,
        CollisionEncounterRecord.vessel_b_observed_at >= active_cutoff,
    )

    return (
        vessel_a_is_current,
        vessel_b_is_current,
    )
