from sqlalchemy.orm import sessionmaker

from db.repository import AuditLogRepository
from simulator.modbus.audit import record_modbus_write


def test_record_modbus_write_persists_entry(test_engine, monkeypatch, db_session):
    test_session_factory = sessionmaker(bind=test_engine, future=True)
    monkeypatch.setattr("simulator.modbus.audit.get_session", test_session_factory)

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
    test_session_factory = sessionmaker(bind=test_engine, future=True)
    monkeypatch.setattr("simulator.modbus.audit.get_session", test_session_factory)

    record_modbus_write("PLC-001", function_code=99, address=0, values=[1])

    entries = AuditLogRepository(db_session).list_recent()
    assert entries[0].details["function_name"] == "99"
