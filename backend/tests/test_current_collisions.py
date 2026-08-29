from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from seaguard.collision.current import (
    current_collision_conditions,
)
from seaguard.db.collision_models import (
    CollisionEncounterRecord,
)


def test_current_collision_conditions_return_two_predicates() -> None:
    conditions = current_collision_conditions()

    assert len(conditions) == 2


def test_current_collision_conditions_compile_as_not_exists() -> None:
    conditions = current_collision_conditions()

    statement = select(CollisionEncounterRecord.id).where(*conditions)

    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True,
            },
        )
    ).lower()

    assert sql.count("not (exists") == 2 or sql.count("not exists") == 2

    assert "ais_messages.timestamp > collision_encounters.vessel_a_observed_at" in sql

    assert "ais_messages.timestamp > collision_encounters.vessel_b_observed_at" in sql

    assert "ais_messages.id > collision_encounters.vessel_a_ais_message_id" in sql

    assert "ais_messages.id > collision_encounters.vessel_b_ais_message_id" in sql
