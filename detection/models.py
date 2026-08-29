"""
Alert: the in-memory result of a detection rule firing.

This is deliberately a plain dataclass, not persisted anywhere yet -
Milestone 7 (Alert management) will add a matching `Alert` SQLAlchemy
model in db/models.py and a repository, following the exact same
domain-object-vs-ORM-model split already used for telemetry
(collector.telemetry.TelemetryRecord vs. db.models.Telemetry). Keeping
detection logic fully decoupled from the database means every rule in
this milestone can be unit tested with zero database/network setup.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime


class AlertSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, enum.Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


@dataclass
class Alert:
    rule_id: str
    asset_id: str
    severity: AlertSeverity
    title: str
    description: str
    created_at: datetime
    status: AlertStatus = AlertStatus.OPEN
    id: int | None = None  # assigned once persisted (Milestone 7)
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
