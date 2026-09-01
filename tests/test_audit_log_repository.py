from datetime import datetime, timedelta, timezone

from db.repository import AuditLogRepository


def test_record_creates_entry(db_session):
    repo = AuditLogRepository(db_session)
    at = datetime.now(timezone.utc)

    entry = repo.record(
        actor="api-client",
        action="ALERT_ACKNOWLEDGED",
        resource_type="alert",
        resource_id="1",
        timestamp=at,
        details={"previous_status": "OPEN"},
    )
    db_session.commit()

    assert entry.id is not None
    assert entry.actor == "api-client"
    assert entry.action == "ALERT_ACKNOWLEDGED"
    assert entry.details == {"previous_status": "OPEN"}


def test_record_without_details(db_session):
    repo = AuditLogRepository(db_session)
    entry = repo.record(
        actor="modbus-client",
        action="MODBUS_WRITE",
        resource_type="plc",
        resource_id="PLC-001",
        timestamp=datetime.now(timezone.utc),
    )
    db_session.commit()

    assert entry.details is None


def test_list_recent_orders_newest_first(db_session):
    repo = AuditLogRepository(db_session)
    base = datetime.now(timezone.utc)

    older = repo.record(
        actor="api-client",
        action="ALERT_ACKNOWLEDGED",
        resource_type="alert",
        resource_id="1",
        timestamp=base,
    )
    newer = repo.record(
        actor="api-client",
        action="ALERT_RESOLVED",
        resource_type="alert",
        resource_id="1",
        timestamp=base + timedelta(seconds=1),
    )
    db_session.commit()

    entries = repo.list_recent()
    assert [e.id for e in entries] == [newer.id, older.id]


def test_list_recent_filters_by_action_and_resource_type(db_session):
    repo = AuditLogRepository(db_session)
    now = datetime.now(timezone.utc)

    repo.record(
        actor="api-client", action="ALERT_ACKNOWLEDGED", resource_type="alert",
        resource_id="1", timestamp=now,
    )
    write_entry = repo.record(
        actor="modbus-client", action="MODBUS_WRITE", resource_type="plc",
        resource_id="PLC-001", timestamp=now,
    )
    db_session.commit()

    writes_only = repo.list_recent(action="MODBUS_WRITE")
    assert [e.id for e in writes_only] == [write_entry.id]

    plc_only = repo.list_recent(resource_type="plc")
    assert [e.id for e in plc_only] == [write_entry.id]


def test_list_recent_respects_limit(db_session):
    repo = AuditLogRepository(db_session)
    now = datetime.now(timezone.utc)
    for i in range(5):
        repo.record(
            actor="api-client", action="ALERT_ACKNOWLEDGED", resource_type="alert",
            resource_id=str(i), timestamp=now + timedelta(seconds=i),
        )
    db_session.commit()

    assert len(repo.list_recent(limit=2)) == 2
