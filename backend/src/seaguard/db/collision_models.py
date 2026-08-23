from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from seaguard.db.base import Base


class CollisionEncounterRecord(Base):
    """Persisted vessel-to-vessel CPA/TCPA assessment."""

    __tablename__ = "collision_encounters"

    __table_args__ = (
        UniqueConstraint(
            "vessel_a_ais_message_id",
            "vessel_b_ais_message_id",
            "assessment_version",
            name="uq_collision_encounter_source_messages_version",
        ),
        Index(
            "ix_collision_encounters_risk_observed_at",
            "risk_level",
            "observed_at",
        ),
        Index(
            "ix_collision_encounters_vessels_observed_at",
            "vessel_a_id",
            "vessel_b_id",
            "observed_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    vessel_a_id: Mapped[int] = mapped_column(
        ForeignKey(
            "vessels.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    vessel_b_id: Mapped[int] = mapped_column(
        ForeignKey(
            "vessels.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    vessel_a_ais_message_id: Mapped[int] = mapped_column(
        ForeignKey(
            "ais_messages.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    vessel_b_ais_message_id: Mapped[int] = mapped_column(
        ForeignKey(
            "ais_messages.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    vessel_a_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    vessel_b_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    current_distance_nm: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    cpa_distance_nm: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    tcpa_minutes: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    relative_speed_knots: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    closing_speed_knots: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    bearing_from_a_to_b_degrees: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    risk_level: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    reasons: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    assessment_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="cpa-tcpa-v1",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
