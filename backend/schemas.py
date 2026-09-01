"""
Pydantic response models: the API's public contract.

These are DELIBERATELY separate classes from db/models.py's SQLAlchemy
models, even though their fields mostly mirror each other right now.
Reasons this separation matters (not just boilerplate):

    1. The ORM model is shaped by storage concerns (foreign keys,
       indexes); the API schema is shaped by what a client should see.
       They will diverge - e.g. we may never want to expose an
       internal surrogate `asset.id` primary key to external API
       consumers as a stable identifier, only `asset_code`.
    2. `model_config = ConfigDict(from_attributes=True)` lets Pydantic
       read straight from a SQLAlchemy ORM instance's attributes, so
       routes can `return` an ORM object directly and FastAPI
       serializes it through this schema - no manual field-by-field
       copying.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HealthOut(BaseModel):
    status: str  # "ok" or "degraded"
    database: str  # "ok" or "unreachable"


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_code: str
    name: str
    asset_type: str
    protocol: str | None
    ip_address: str | None
    status: str
    first_seen: datetime
    last_seen: datetime


class TelemetryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    timestamp: datetime
    temperature: float
    pressure: float
    tank_level_percent: float
    pump_state: str
    cooling_active: bool
    inlet_open: bool


class ReportRequestOut(BaseModel):
    task_id: str
    status: str


class ReportStatusOut(BaseModel):
    task_id: str
    status: str  # Celery states: PENDING, STARTED, SUCCESS, FAILURE, RETRY, REVOKED
    result: dict | None = None
    error: str | None = None


class IncidentAnalysisRequestOut(BaseModel):
    task_id: str
    status: str


class IncidentAnalysisTaskStatusOut(BaseModel):
    task_id: str
    status: str  # Celery states: PENDING, STARTED, SUCCESS, FAILURE, RETRY, REVOKED
    result: dict | None = None
    error: str | None = None


class IncidentAnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_id: int
    model: str
    summary: str
    possible_causes: list[str]
    recommended_actions: list[str]
    created_at: datetime


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    rule_id: str
    severity: str
    title: str
    description: str
    status: str
    created_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    actor: str
    action: str
    resource_type: str
    resource_id: str
    details: dict | None
