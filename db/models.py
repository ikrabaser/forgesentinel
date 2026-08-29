"""
ORM models: Asset and Telemetry.

Real-world analogy:
    `Asset` is the plant's equipment inventory - every physical/
    virtual thing security or operations cares about tracking
    (PLC-001, TEMP-001, ...). `Telemetry` is the time-series log of
    what each asset reported, one row per collector poll. This is the
    same shape as a real OT asset-management + historian system, just
    much smaller.

Why asset_type / status / pump_state are stored as String, not a
native PostgreSQL ENUM type:
    A Postgres ENUM is convenient but rigid - adding a new value later
    requires an `ALTER TYPE ... ADD VALUE` migration, which has its
    own sharp edges (e.g. it can't run inside the same transaction as
    other DDL in older Postgres versions). Storing the value as a
    plain string, validated by a Python Enum at the application layer,
    gets us the same type-safety in our own code while keeping schema
    evolution simple - a trade-off worth knowing explicitly rather
    than discovering by accident during a future migration.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

# Note: unlike Telemetry (which stores pump_state as a plain String,
# no enum imported here), we deliberately do NOT import
# detection.models' AlertSeverity/AlertStatus into this file either -
# same reasoning as pump_state: db/ has zero knowledge of any other
# package's domain objects, including detection/'s. Alert.severity and
# Alert.status below are plain strings, validated by whichever
# application layer produces them (detection/models.py's Alert
# dataclass, in this case).


class AssetType(str, enum.Enum):
    PLC = "PLC"
    TANK = "TANK"
    PUMP = "PUMP"
    TEMPERATURE_SENSOR = "TEMPERATURE_SENSOR"
    PRESSURE_SENSOR = "PRESSURE_SENSOR"


class AssetStatus(str, enum.Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    asset_type: Mapped[str] = mapped_column(String(30))
    protocol: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default=AssetStatus.UNKNOWN.value)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    telemetry: Mapped[list["Telemetry"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<Asset {self.asset_code} status={self.status}>"


class Telemetry(Base):
    __tablename__ = "telemetry"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    temperature: Mapped[float] = mapped_column(Float)
    pressure: Mapped[float] = mapped_column(Float)
    tank_level_percent: Mapped[float] = mapped_column(Float)
    pump_state: Mapped[str] = mapped_column(String(10))
    cooling_active: Mapped[bool] = mapped_column(Boolean)
    inlet_open: Mapped[bool] = mapped_column(Boolean)

    asset: Mapped["Asset"] = relationship(back_populates="telemetry")

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<Telemetry asset_id={self.asset_id} ts={self.timestamp}>"


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    rule_id: Mapped[str] = mapped_column(String(20), index=True)
    severity: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(15), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    asset: Mapped["Asset"] = relationship(back_populates="alerts")

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<Alert {self.rule_id} asset_id={self.asset_id} status={self.status}>"
