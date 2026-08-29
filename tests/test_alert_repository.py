from datetime import datetime, timedelta, timezone

from db.repository import AlertRepository, AssetRepository


def _make_asset(db_session):
    asset = AssetRepository(db_session).upsert_seen(
        asset_code="PLC-001", name="PLC-001", asset_type="PLC", seen_at=datetime.now(timezone.utc)
    )
    db_session.flush()
    return asset


def test_create_alert_defaults_to_open(db_session):
    asset = _make_asset(db_session)
    created_at = datetime.now(timezone.utc)

    alert = AlertRepository(db_session).create(
        asset_id=asset.id,
        rule_id="RULE-001",
        severity="HIGH",
        title="High temperature",
        description="Temperature exceeds threshold",
        created_at=created_at,
    )
    db_session.commit()

    assert alert.id is not None
    assert alert.status == "OPEN"
    assert alert.acknowledged_at is None
    assert alert.resolved_at is None


def test_get_returns_none_when_missing(db_session):
    assert AlertRepository(db_session).get(999999) is None


def test_list_all_orders_newest_first_and_filters_by_status(db_session):
    asset = _make_asset(db_session)
    repo = AlertRepository(db_session)
    base = datetime.now(timezone.utc)

    older = repo.create(
        asset_id=asset.id,
        rule_id="RULE-001",
        severity="HIGH",
        title="older",
        description="d",
        created_at=base,
    )
    newer = repo.create(
        asset_id=asset.id,
        rule_id="RULE-002",
        severity="CRITICAL",
        title="newer",
        description="d",
        created_at=base + timedelta(seconds=1),
    )
    db_session.commit()

    all_alerts = repo.list_all()
    assert [a.id for a in all_alerts] == [newer.id, older.id]

    repo.acknowledge(older.id, base + timedelta(seconds=2))
    db_session.commit()

    open_only = repo.list_all(status="OPEN")
    assert [a.id for a in open_only] == [newer.id]

    ack_only = repo.list_all(status="ACKNOWLEDGED")
    assert [a.id for a in ack_only] == [older.id]


def test_acknowledge_transitions_open_to_acknowledged(db_session):
    asset = _make_asset(db_session)
    repo = AlertRepository(db_session)
    alert = repo.create(
        asset_id=asset.id,
        rule_id="RULE-001",
        severity="HIGH",
        title="t",
        description="d",
        created_at=datetime.now(timezone.utc),
    )
    db_session.commit()

    at = datetime.now(timezone.utc)
    acknowledged = repo.acknowledge(alert.id, at)
    db_session.commit()

    assert acknowledged.status == "ACKNOWLEDGED"
    assert acknowledged.acknowledged_at == at


def test_acknowledge_is_noop_when_already_resolved(db_session):
    asset = _make_asset(db_session)
    repo = AlertRepository(db_session)
    alert = repo.create(
        asset_id=asset.id,
        rule_id="RULE-001",
        severity="HIGH",
        title="t",
        description="d",
        created_at=datetime.now(timezone.utc),
    )
    resolved_at = datetime.now(timezone.utc)
    repo.resolve(alert.id, resolved_at)
    db_session.commit()

    later_attempt = datetime.now(timezone.utc) + timedelta(minutes=5)
    result = repo.acknowledge(alert.id, later_attempt)
    db_session.commit()

    # Still RESOLVED - acknowledging a resolved alert must not revive it
    # or overwrite resolved_at/acknowledged_at.
    assert result.status == "RESOLVED"
    assert result.acknowledged_at is None
    assert result.resolved_at == resolved_at


def test_resolve_valid_from_open_and_from_acknowledged(db_session):
    asset = _make_asset(db_session)
    repo = AlertRepository(db_session)

    direct = repo.create(
        asset_id=asset.id,
        rule_id="RULE-001",
        severity="HIGH",
        title="t",
        description="d",
        created_at=datetime.now(timezone.utc),
    )
    via_ack = repo.create(
        asset_id=asset.id,
        rule_id="RULE-002",
        severity="HIGH",
        title="t2",
        description="d",
        created_at=datetime.now(timezone.utc),
    )
    db_session.commit()

    repo.acknowledge(via_ack.id, datetime.now(timezone.utc))
    db_session.commit()

    resolved_direct = repo.resolve(direct.id, datetime.now(timezone.utc))
    resolved_via_ack = repo.resolve(via_ack.id, datetime.now(timezone.utc))
    db_session.commit()

    assert resolved_direct.status == "RESOLVED"
    assert resolved_via_ack.status == "RESOLVED"


def test_resolve_is_noop_when_already_resolved(db_session):
    asset = _make_asset(db_session)
    repo = AlertRepository(db_session)
    alert = repo.create(
        asset_id=asset.id,
        rule_id="RULE-001",
        severity="HIGH",
        title="t",
        description="d",
        created_at=datetime.now(timezone.utc),
    )
    first_resolved_at = datetime.now(timezone.utc)
    repo.resolve(alert.id, first_resolved_at)
    db_session.commit()

    second_attempt = datetime.now(timezone.utc) + timedelta(minutes=5)
    result = repo.resolve(alert.id, second_attempt)
    db_session.commit()

    assert result.resolved_at == first_resolved_at  # unchanged


def test_acknowledge_and_resolve_return_none_for_missing_alert(db_session):
    repo = AlertRepository(db_session)
    assert repo.acknowledge(999999, datetime.now(timezone.utc)) is None
    assert repo.resolve(999999, datetime.now(timezone.utc)) is None
