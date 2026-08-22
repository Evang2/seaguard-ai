from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from seaguard.db.base import Base


class RiskAssessment(Base):
    """Persisted hybrid ML/rule investigation-priority assessment."""

    __tablename__ = "risk_assessments"

    __table_args__ = (
        UniqueConstraint(
            "ais_message_id",
            name="uq_risk_assessments_ais_message_id",
        ),
        CheckConstraint(
            "ml_anomaly_percentile >= 0.0 AND ml_anomaly_percentile <= 100.0",
            name="ck_risk_assessments_ml_percentile_range",
        ),
        CheckConstraint(
            "rule_flag_count >= 0",
            name="ck_risk_assessments_rule_flag_count_nonnegative",
        ),
        CheckConstraint(
            "rule_severity IN ('none', 'warning', 'high', 'critical')",
            name="ck_risk_assessments_rule_severity",
        ),
        CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')",
            name="ck_risk_assessments_risk_level",
        ),
        Index(
            "ix_risk_assessments_vessel_observed_at",
            "vessel_id",
            "observed_at",
        ),
        Index(
            "ix_risk_assessments_risk_level_observed_at",
            "risk_level",
            "observed_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    ais_message_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "ais_messages.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    vessel_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "vessels.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    ml_anomaly_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    ml_anomaly_percentile: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    rule_flag_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    rule_severity: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    detector_agreement: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    risk_level: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    risk_reasons: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    assessment_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="hybrid-v1",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
