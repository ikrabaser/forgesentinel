"""
Repositories: the only place in the codebase that writes SQLAlchemy
queries. Everything else (collector persistence, and later FastAPI
routes) talks to these methods instead of the ORM/Session directly.

Real-world analogy / why this layer exists:
    This is the "repository" in the route -> service -> repository ->
    database layering the project rules call for. It exists so that
    if we ever needed to change *how* assets/telemetry are stored
    (different table shape, a caching layer, a different database
    entirely), only this file would need to change - nothing calling
    into it would know the difference.

Note these classes take plain values (strings, floats, datetimes) in
their method signatures, not domain objects from other layers (like
collector.telemetry.TelemetryRecord). That's deliberate: db/ has zero
knowledge of collector/ or simulator/, which keeps the dependency
direction one-way (collector -> db, never db -> collector).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Asset, AssetStatus, Telemetry


class AssetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_code(self, asset_code: str) -> Asset | None:
        stmt = select(Asset).where(Asset.asset_code == asset_code)
        return self.session.execute(stmt).scalar_one_or_none()

    def list_all(self) -> list[Asset]:
        stmt = select(Asset).order_by(Asset.asset_code)
        return list(self.session.execute(stmt).scalars().all())

    def upsert_seen(
        self,
        asset_code: str,
        name: str,
        asset_type: str,
        seen_at: datetime,
        protocol: str | None = None,
        ip_address: str | None = None,
    ) -> Asset:
        """
        Record that an asset was just observed (e.g. a collector poll
        succeeded). Creates the asset on first sighting, otherwise
        just advances last_seen and marks it ONLINE.

        This mirrors how real OT asset inventories are often built in
        practice: not from a manually maintained list, but "discovered"
        passively from the traffic/telemetry a device actually
        produces - which is also exactly the kind of signal Rule 004
        (DEVICE_OFFLINE) will later depend on: an asset whose
        last_seen stops advancing is the anomaly.
        """
        asset = self.get_by_code(asset_code)
        if asset is None:
            asset = Asset(
                asset_code=asset_code,
                name=name,
                asset_type=asset_type,
                protocol=protocol,
                ip_address=ip_address,
                status=AssetStatus.ONLINE.value,
                first_seen=seen_at,
                last_seen=seen_at,
            )
            self.session.add(asset)
        else:
            asset.last_seen = seen_at
            asset.status = AssetStatus.ONLINE.value

        self.session.flush()  # populate asset.id for callers that need it immediately
        return asset


class TelemetryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self,
        asset_id: int,
        timestamp: datetime,
        temperature: float,
        pressure: float,
        tank_level_percent: float,
        pump_state: str,
        cooling_active: bool,
        inlet_open: bool,
    ) -> Telemetry:
        record = Telemetry(
            asset_id=asset_id,
            timestamp=timestamp,
            temperature=temperature,
            pressure=pressure,
            tank_level_percent=tank_level_percent,
            pump_state=pump_state,
            cooling_active=cooling_active,
            inlet_open=inlet_open,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def latest_for_asset(self, asset_id: int) -> Telemetry | None:
        stmt = (
            select(Telemetry)
            .where(Telemetry.asset_id == asset_id)
            .order_by(Telemetry.timestamp.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_recent(self, asset_id: int, limit: int = 100) -> list[Telemetry]:
        stmt = (
            select(Telemetry)
            .where(Telemetry.asset_id == asset_id)
            .order_by(Telemetry.timestamp.desc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())
