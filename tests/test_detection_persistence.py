from datetime import datetime, timezone

from sqlalchemy.orm import sessionmaker

from db.repository import AlertRepository, AssetRepository
from detection.models import Alert, AlertSeverity
from detection.persistence import make_persisting_alert_sink


def test_persisting_alert_sink_writes_alert_for_known_asset(test_engine, monkeypatch, db_session):
    test_session_factory = sessionmaker(bind=test_engine, future=True)
    monkeypatch.setattr("detection.persistence.get_session", test_session_factory)

    AssetRepository(db_session).upsert_seen(
        asset_code="PLC-001", name="PLC-001", asset_type="PLC", seen_at=datetime.now(timezone.utc)
    )
    db_session.commit()

    sink = make_persisting_alert_sink()
    sink(
        Alert(
            rule_id="RULE-001",
            asset_id="PLC-001",
            severity=AlertSeverity.HIGH,
            title="High temperature",
            description="Temperature 95.0C exceeds threshold",
            created_at=datetime.now(timezone.utc),
        )
    )

    asset = AssetRepository(db_session).get_by_code("PLC-001")
    alerts = AlertRepository(db_session).list_all()
    assert len(alerts) == 1
    assert alerts[0].asset_id == asset.id
    assert alerts[0].rule_id == "RULE-001"
    assert alerts[0].severity == "HIGH"
    assert alerts[0].status == "OPEN"


def test_persisting_alert_sink_drops_alert_for_unknown_asset(test_engine, monkeypatch, db_session):
    test_session_factory = sessionmaker(bind=test_engine, future=True)
    monkeypatch.setattr("detection.persistence.get_session", test_session_factory)

    sink = make_persisting_alert_sink()
    # No asset has ever been upserted - this should not raise, just
    # log a warning and skip persisting.
    sink(
        Alert(
            rule_id="RULE-001",
            asset_id="NEVER-SEEN",
            severity=AlertSeverity.HIGH,
            title="High temperature",
            description="d",
            created_at=datetime.now(timezone.utc),
        )
    )

    assert AlertRepository(db_session).list_all() == []
