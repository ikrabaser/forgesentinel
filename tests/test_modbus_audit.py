from datetime import datetime, timezone

from sqlalchemy.orm import sessionmaker

from db.repository import AlertRepository, AssetRepository, AuditLogRepository
from simulator.modbus.audit import record_modbus_write


def _patch_sessions(test_engine, monkeypatch):
    """
    record_modbus_write touches two adapters, each resolving get_session
    from its OWN module's namespace at call time (see
    detection/persistence.py's docstring) - both must be patched, or
    one half of the call would quietly hit the real dev database.
    """
    test_session_factory = sessionmaker(bind=test_engine, future=True)
    monkeypatch.setattr("simulator.modbus.audit.get_session", test_session_factory)
    monkeypatch.setattr("detection.persistence.get_session", test_session_factory)


def test_record_modbus_write_persists_audit_entry(test_engine, monkeypatch, db_session):
    _patch_sessions(test_engine, monkeypatch)

    record_modbus_write("PLC-001", function_code=6, address=0, values=[1])

    entries = AuditLogRepository(db_session).list_recent()
    assert len(entries) == 1
    assert entries[0].actor == "modbus-client"
    assert entries[0].action == "MODBUS_WRITE"
    assert entries[0].resource_type == "plc"
    assert entries[0].resource_id == "PLC-001"
    assert entries[0].details == {
        "function_code": 6,
        "function_name": "WRITE_SINGLE_REGISTER",
        "address": 0,
        "values": [1],
    }


def test_record_modbus_write_unknown_function_code_falls_back_to_number(
    test_engine, monkeypatch, db_session
):
    _patch_sessions(test_engine, monkeypatch)

    record_modbus_write("PLC-001", function_code=99, address=0, values=[1])

    entries = AuditLogRepository(db_session).list_recent()
    assert entries[0].details["function_name"] == "99"


def test_record_modbus_write_raises_rule_005_alert_for_known_asset(
    test_engine, monkeypatch, db_session
):
    _patch_sessions(test_engine, monkeypatch)
    AssetRepository(db_session).upsert_seen(
        asset_code="PLC-001", name="PLC-001", asset_type="PLC", seen_at=datetime.now(timezone.utc)
    )
    db_session.commit()

    record_modbus_write("PLC-001", function_code=6, address=0, values=[4200])

    alerts = AlertRepository(db_session).list_all()
    assert len(alerts) == 1
    assert alerts[0].rule_id == "RULE-005"
    assert alerts[0].severity == "CRITICAL"
    assert "WRITE_SINGLE_REGISTER" in alerts[0].description


def test_record_modbus_write_skips_alert_for_unknown_asset(test_engine, monkeypatch, db_session):
    _patch_sessions(test_engine, monkeypatch)
    # No asset upserted - mirrors make_persisting_alert_sink's existing
    # "drop it, log a warning, don't crash" behavior for this case.

    record_modbus_write("NEVER-SEEN", function_code=6, address=0, values=[1])

    assert AlertRepository(db_session).list_all() == []
    # The audit log entry itself still gets written regardless -
    # these are two independent concerns.
    assert len(AuditLogRepository(db_session).list_recent()) == 1
