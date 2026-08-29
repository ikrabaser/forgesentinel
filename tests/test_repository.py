from datetime import datetime, timedelta, timezone

from db.models import AssetStatus
from db.repository import AssetRepository, TelemetryRepository


def test_upsert_seen_creates_asset_on_first_sighting(db_session):
    repo = AssetRepository(db_session)
    seen_at = datetime.now(timezone.utc)

    asset = repo.upsert_seen(
        asset_code="PLC-001", name="PLC-001", asset_type="PLC", seen_at=seen_at
    )
    db_session.commit()

    assert asset.id is not None
    assert asset.asset_code == "PLC-001"
    assert asset.status == AssetStatus.ONLINE.value
    assert asset.first_seen == seen_at
    assert asset.last_seen == seen_at


def test_upsert_seen_updates_existing_asset_without_duplicating(db_session):
    repo = AssetRepository(db_session)
    first_seen = datetime.now(timezone.utc)
    later = first_seen + timedelta(minutes=5)

    repo.upsert_seen(asset_code="PLC-001", name="PLC-001", asset_type="PLC", seen_at=first_seen)
    repo.upsert_seen(asset_code="PLC-001", name="PLC-001", asset_type="PLC", seen_at=later)
    db_session.commit()

    all_assets = repo.list_all()
    assert len(all_assets) == 1  # no duplicate row was created
    assert all_assets[0].first_seen == first_seen  # first_seen never moves
    assert all_assets[0].last_seen == later  # last_seen advances


def test_get_by_code_returns_none_when_missing(db_session):
    repo = AssetRepository(db_session)
    assert repo.get_by_code("DOES-NOT-EXIST") is None


def test_telemetry_add_and_latest_for_asset(db_session):
    asset_repo = AssetRepository(db_session)
    telemetry_repo = TelemetryRepository(db_session)

    asset = asset_repo.upsert_seen(
        asset_code="PLC-001", name="PLC-001", asset_type="PLC", seen_at=datetime.now(timezone.utc)
    )
    db_session.flush()

    older = datetime.now(timezone.utc) - timedelta(minutes=1)
    newer = datetime.now(timezone.utc)

    telemetry_repo.add(
        asset_id=asset.id,
        timestamp=older,
        temperature=80.0,
        pressure=2.0,
        tank_level_percent=40.0,
        pump_state="ON",
        cooling_active=False,
        inlet_open=True,
    )
    telemetry_repo.add(
        asset_id=asset.id,
        timestamp=newer,
        temperature=91.0,
        pressure=2.4,
        tank_level_percent=42.0,
        pump_state="ON",
        cooling_active=True,
        inlet_open=True,
    )
    db_session.commit()

    latest = telemetry_repo.latest_for_asset(asset.id)
    assert latest is not None
    assert latest.timestamp == newer
    assert latest.temperature == 91.0

    recent = telemetry_repo.list_recent(asset.id, limit=10)
    assert len(recent) == 2
    assert recent[0].timestamp == newer  # newest first


def test_telemetry_latest_for_asset_returns_none_when_no_rows(db_session):
    asset_repo = AssetRepository(db_session)
    telemetry_repo = TelemetryRepository(db_session)

    asset = asset_repo.upsert_seen(
        asset_code="PLC-001", name="PLC-001", asset_type="PLC", seen_at=datetime.now(timezone.utc)
    )
    db_session.commit()

    assert telemetry_repo.latest_for_asset(asset.id) is None
