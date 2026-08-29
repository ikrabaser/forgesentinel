"""
Tests for collector/persistence.py's adapter between TelemetryRecord
and the repository layer. Uses the real test database (db_session's
underlying engine) so we exercise the full path: TelemetryRecord ->
repository calls -> actual committed rows.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import sessionmaker

from collector.persistence import make_persisting_callback
from collector.telemetry import TelemetryRecord
from db.repository import AssetRepository, TelemetryRepository
from simulator.process.pump import PumpState


def test_persisting_callback_writes_asset_and_telemetry(test_engine, monkeypatch, db_session):
    # make_persisting_callback() calls db.base.get_session() internally;
    # point that at our disposable test engine instead of the real
    # DATABASE_URL so this test never touches dev/prod data.
    test_session_factory = sessionmaker(bind=test_engine, future=True)
    monkeypatch.setattr("collector.persistence.get_session", test_session_factory)

    callback = make_persisting_callback(asset_ip="127.0.0.1")
    record = TelemetryRecord(
        asset_id="PLC-001",
        timestamp=datetime.now(timezone.utc),
        temperature=88.4,
        pressure=2.1,
        tank_level_percent=55.0,
        pump_state=PumpState.ON,
        cooling_active=False,
        inlet_open=True,
    )

    callback(record)

    asset_repo = AssetRepository(db_session)
    telemetry_repo = TelemetryRepository(db_session)

    asset = asset_repo.get_by_code("PLC-001")
    assert asset is not None
    assert asset.ip_address == "127.0.0.1"
    assert asset.protocol == "Modbus TCP"

    latest = telemetry_repo.latest_for_asset(asset.id)
    assert latest is not None
    assert latest.temperature == 88.4
    assert latest.pump_state == "ON"
    assert latest.inlet_open is True


def test_persisting_callback_second_call_updates_same_asset(test_engine, monkeypatch, db_session):
    test_session_factory = sessionmaker(bind=test_engine, future=True)
    monkeypatch.setattr("collector.persistence.get_session", test_session_factory)

    callback = make_persisting_callback(asset_ip="127.0.0.1")

    for temp in (70.0, 75.0):
        callback(
            TelemetryRecord(
                asset_id="PLC-001",
                timestamp=datetime.now(timezone.utc),
                temperature=temp,
                pressure=1.0,
                tank_level_percent=50.0,
                pump_state=PumpState.OFF,
                cooling_active=False,
                inlet_open=True,
            )
        )

    asset_repo = AssetRepository(db_session)
    telemetry_repo = TelemetryRepository(db_session)

    assets = asset_repo.list_all()
    assert len(assets) == 1  # still one asset, not duplicated

    recent = telemetry_repo.list_recent(assets[0].id, limit=10)
    assert len(recent) == 2  # two telemetry rows, one per call
