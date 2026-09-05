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

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text
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
    incident_analyses: Mapped[list["IncidentAnalysis"]] = relationship(
        back_populates="alert", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<Alert {self.rule_id} asset_id={self.asset_id} status={self.status}>"


class IncidentAnalysis(Base):
    """
    Milestone 14: the AI Incident Analyst's output for one alert, kept
    as an append-only history rather than overwritten on re-analysis -
    an operator re-running analysis after gathering more evidence
    should be able to compare the new explanation against the old one,
    the same way a human analyst's incident notes accumulate rather
    than get erased.
    """

    __tablename__ = "incident_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"), index=True)
    model: Mapped[str] = mapped_column(String(50))
    summary: Mapped[str] = mapped_column(Text)
    possible_causes: Mapped[list[str]] = mapped_column(JSON)
    recommended_actions: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    alert: Mapped["Alert"] = relationship(back_populates="incident_analyses")

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<IncidentAnalysis alert_id={self.alert_id} model={self.model}>"


class AuditLog(Base):
    """
    Milestone 15: an immutable record of "who did what, when" for
    security-relevant actions - distinct from both Telemetry (physical
    process state) and Alert (detection engine findings). Audit
    entries answer accountability questions a SOC always gets asked
    after the fact: who acknowledged this, when was analysis
    requested, was there ever a write to this PLC's registers.

    No rows are ever updated or deleted by application code - only
    inserted. That's what makes an audit log trustworthy as a record;
    a log an application can quietly edit isn't one.

    Two distinct sources feed this table:
      - API actions (actor is whatever backend/auth.py's
        get_current_actor resolved for the request - a real per-caller
        principal if the operator configured API_KEYS, or the
        "api-client" placeholder if they haven't, since auth is
        opt-in for this local lab - see backend/auth.py's docstring.)
      - Modbus write commands observed by the PLC simulator (actor=
        "modbus-client" - see simulator/modbus/server.py's
        AuditingSlaveContext for how genuine external writes (FC06/16)
        are distinguished from the simulator's own internal tick
        updates (FC03/01). Source IP is NOT captured yet - pymodbus's
        single-context server model doesn't expose per-connection
        info to setValues() without deeper protocol-layer surgery;
        documented here as a known gap, not a silent omission.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(50), index=True)
    resource_type: Mapped[str] = mapped_column(String(30), index=True)
    resource_id: Mapped[str] = mapped_column(String(50))
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<AuditLog {self.action} {self.resource_type}:{self.resource_id}>"
