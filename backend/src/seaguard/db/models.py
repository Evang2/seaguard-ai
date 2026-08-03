from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from seaguard.db.base import Base


class Vessel(Base):
    """A maritime vessel identified primarily by MMSI."""

    __tablename__ = "vessels"

    __table_args__ = (
        CheckConstraint(
            "mmsi ~ '^[0-9]{9}$'",
            name="mmsi_nine_digits",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    mmsi: Mapped[str] = mapped_column(
        String(9),
        nullable=False,
        unique=True,
        index=True,
    )

    imo: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        index=True,
    )

    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    call_sign: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    vessel_type: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
    )

    length_m: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )

    width_m: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )

    draft_m: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )

    first_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    messages: Mapped[list[AISMessage]] = relationship(
        back_populates="vessel",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    alerts: Mapped[list[AnomalyAlert]] = relationship(
        back_populates="vessel",
        passive_deletes=True,
    )


class AISMessage(Base):
    """One cleaned AIS position observation."""

    __tablename__ = "ais_messages"

    __table_args__ = (
        UniqueConstraint(
            "vessel_id",
            "timestamp",
            "latitude",
            "longitude",
            name="identity",
        ),
        CheckConstraint(
            "latitude BETWEEN -90 AND 90",
            name="latitude_range",
        ),
        CheckConstraint(
            "longitude BETWEEN -180 AND 180",
            name="longitude_range",
        ),
        CheckConstraint(
            "sog IS NULL OR sog >= 0",
            name="sog_nonnegative",
        ),
        CheckConstraint(
            "cog IS NULL OR (cog >= 0 AND cog < 360)",
            name="cog_range",
        ),
        CheckConstraint(
            "heading IS NULL OR (heading >= 0 AND heading < 360)",
            name="heading_range",
        ),
        Index(
            "ix_ais_messages_vessel_timestamp",
            "vessel_id",
            "timestamp",
        ),
        Index(
            "ix_ais_messages_timestamp",
            "timestamp",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    vessel_id: Mapped[int] = mapped_column(
        ForeignKey(
            "vessels.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    position: Mapped[WKBElement] = mapped_column(
        Geography(
            geometry_type="POINT",
            srid=4326,
            spatial_index=True,
        ),
        nullable=False,
    )

    sog: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    cog: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    heading: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    navigation_status: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
    )

    cargo: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    transceiver_class: Mapped[str | None] = mapped_column(
        String(8),
        nullable=True,
    )

    sog_unavailable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    cog_unavailable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    heading_unavailable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    vessel: Mapped[Vessel] = relationship(
        back_populates="messages",
    )

    alerts: Mapped[list[AnomalyAlert]] = relationship(
        back_populates="ais_message",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AnomalyAlert(Base):
    """An explainable anomaly generated for an AIS observation."""

    __tablename__ = "anomaly_alerts"

    __table_args__ = (
        UniqueConstraint(
            "ais_message_id",
            "anomaly_type",
            name="message_anomaly_type",
        ),
        Index(
            "ix_anomaly_alerts_vessel_observed_at",
            "vessel_id",
            "observed_at",
        ),
        Index(
            "ix_anomaly_alerts_type_severity",
            "anomaly_type",
            "severity",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    ais_message_id: Mapped[int] = mapped_column(
        ForeignKey(
            "ais_messages.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    vessel_id: Mapped[int] = mapped_column(
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

    anomaly_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    severity: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    metric_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    metric_value: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    threshold: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    vessel: Mapped[Vessel] = relationship(
        back_populates="alerts",
    )

    ais_message: Mapped[AISMessage] = relationship(
        back_populates="alerts",
    )


class ImportJob(Base):
    """Metadata and results for one AIS file import."""

    __tablename__ = "import_jobs"

    __table_args__ = (
        Index(
            "ix_import_jobs_status_started_at",
            "status",
            "started_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    source_file: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    rows_read: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )

    rows_imported: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )

    rows_rejected: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )

    duplicates_skipped: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
