"""
Tests for TelemetryBroadcaster's polling logic, run against the
disposable test database directly (session_factory injected) - no
FastAPI app, no WebSocket, no lifespan involved. This isolates "does
the broadcaster correctly detect new rows and avoid repeating them"
from "does the WebSocket plumbing deliver messages," which is covered
separately in test_websocket.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import sessionmaker

from backend.broadcaster import TelemetryBroadcaster
from backend.websocket_manager import ConnectionManager
from db.repository import AlertRepository, AssetRepository, TelemetryRepository


def make_broadcaster(test_engine) -> TelemetryBroadcaster:
    session_factory = sessionmaker(bind=test_engine, future=True)
    return TelemetryBroadcaster(
        connection_manager=ConnectionManager(), session_factory=session_factory, poll_seconds=1.0
    )


def test_poll_once_reports_new_telemetry_once(test_engine, db_session):
    asset = AssetRepository(db_session).upsert_seen(
        asset_code="PLC-001", name="PLC-001", asset_type="PLC", seen_at=datetime.now(timezone.utc)
    )
    db_session.flush()
    TelemetryRepository(db_session).add(
        asset_id=asset.id,
        timestamp=datetime.now(timezone.utc),
        temperature=80.0,
        pressure=2.0,
        tank_level_percent=50.0,
        pump_state="ON",
        cooling_active=False,
        inlet_open=True,
    )
    db_session.commit()

    broadcaster = make_broadcaster(test_engine)

    first_poll = broadcaster._poll_once()
    assert len(first_poll) == 1
    assert first_poll[0]["type"] == "telemetry"
    assert first_poll[0]["asset_code"] == "PLC-001"
    assert first_poll[0]["temperature"] == 80.0

    second_poll = broadcaster._poll_once()
    assert second_poll == []  # no new row - nothing to report again


def test_poll_once_reports_only_the_new_row_after_an_update(test_engine, db_session):
    asset = AssetRepository(db_session).upsert_seen(
        asset_code="PLC-001", name="PLC-001", asset_type="PLC", seen_at=datetime.now(timezone.utc)
    )
    db_session.flush()
    telemetry_repo = TelemetryRepository(db_session)
    telemetry_repo.add(
        asset_id=asset.id,
        timestamp=datetime.now(timezone.utc),
        temperature=80.0,
        pressure=2.0,
        tank_level_percent=50.0,
        pump_state="ON",
        cooling_active=False,
        inlet_open=True,
    )
    db_session.commit()

    broadcaster = make_broadcaster(test_engine)
    broadcaster._poll_once()  # consume the first row

    telemetry_repo.add(
        asset_id=asset.id,
        timestamp=datetime.now(timezone.utc),
        temperature=91.0,
        pressure=2.4,
        tank_level_percent=52.0,
        pump_state="ON",
        cooling_active=True,
        inlet_open=True,
    )
    db_session.commit()

    second_poll = broadcaster._poll_once()
    assert len(second_poll) == 1
    assert second_poll[0]["temperature"] == 91.0


def test_poll_once_reports_new_alerts(test_engine, db_session):
    asset = AssetRepository(db_session).upsert_seen(
        asset_code="PLC-001", name="PLC-001", asset_type="PLC", seen_at=datetime.now(timezone.utc)
    )
    db_session.flush()
    AlertRepository(db_session).create(
        asset_id=asset.id,
        rule_id="RULE-001",
        severity="HIGH",
        title="High temperature",
        description="d",
        created_at=datetime.now(timezone.utc),
    )
    db_session.commit()

    broadcaster = make_broadcaster(test_engine)
    poll = broadcaster._poll_once()

    alert_messages = [m for m in poll if m["type"] == "alert"]
    assert len(alert_messages) == 1
    assert alert_messages[0]["rule_id"] == "RULE-001"

    assert broadcaster._poll_once() == []  # not repeated


def test_poll_once_returns_empty_list_when_nothing_exists(test_engine, db_session):
    # db_session is requested (even though unused directly) purely to
    # get its truncate-before-yield behavior, so this test doesn't
    # depend on running before/after any test that left rows behind.
    broadcaster = make_broadcaster(test_engine)
    assert broadcaster._poll_once() == []
