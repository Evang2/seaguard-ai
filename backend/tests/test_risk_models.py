from sqlalchemy import UniqueConstraint

from seaguard.db.base import Base
from seaguard.db.risk_models import RiskAssessment


def test_risk_assessment_table_is_registered() -> None:
    assert RiskAssessment.__tablename__ == "risk_assessments"
    assert "risk_assessments" in Base.metadata.tables


def test_risk_assessment_links_to_message_and_vessel() -> None:
    table = RiskAssessment.__table__

    message_foreign_keys = {
        foreign_key.target_fullname
        for foreign_key in table.c.ais_message_id.foreign_keys
    }

    vessel_foreign_keys = {
        foreign_key.target_fullname for foreign_key in table.c.vessel_id.foreign_keys
    }

    assert message_foreign_keys == {"ais_messages.id"}
    assert vessel_foreign_keys == {"vessels.id"}


def test_one_risk_assessment_per_ais_message() -> None:
    table = RiskAssessment.__table__

    unique_constraints = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    ]

    assert any(
        constraint.name == "uq_risk_assessments_ais_message_id"
        and {column.name for column in constraint.columns} == {"ais_message_id"}
        for constraint in unique_constraints
    )


def test_risk_assessment_contains_required_fields() -> None:
    columns = set(RiskAssessment.__table__.columns.keys())

    assert {
        "id",
        "ais_message_id",
        "vessel_id",
        "observed_at",
        "ml_anomaly_score",
        "ml_anomaly_percentile",
        "rule_flag_count",
        "rule_severity",
        "detector_agreement",
        "risk_level",
        "risk_reasons",
        "assessment_version",
        "created_at",
    }.issubset(columns)
