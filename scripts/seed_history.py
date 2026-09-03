"""
Seed historical telemetry + alerts for a "lived-in" demo, without
inventing a single fake number.

Why this is simulation, not mock data: every value here comes from
running the SAME Plant/PLCController/DetectionEngine machinery the
live simulator and collector use - just fast-forwarded and stamped
with past timestamps instead of running in real time and stamped
"now". A reviewer reading the code gets the identical physics
(tank/pump/sensor dynamics, PLC safety thresholds, debounced alert
rules) that produced the numbers - nothing here is a random.uniform()
call standing in for a real value.

Usage (PowerShell or Git Bash), run from the project root:

    python -m scripts.seed_history                     # default: PLC-001, 24h
    python -m scripts.seed_history --hours 48
    python -m scripts.seed_history --asset PLC-002 --profile cooling-loop --hours 24
    python -m scripts.seed_history --reset              # wipe this asset's existing
                                                          # telemetry/alerts first

Not idempotent by default - re-running without --reset appends a
second backfilled history on top of whatever's already there. Meant to
be run once per asset against a fresh (or --reset) database, not on a
schedule.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from collector.telemetry import TelemetryRecord
from db.base import get_session
from db.models import Alert as AlertRow
from db.models import Telemetry as TelemetryRow
from db.repository import AlertRepository, AssetRepository, TelemetryRepository
from detection.engine import build_default_engine
from simulator.loop import PLANT_PROFILES, Plant

DEFAULT_INTERVAL_MINUTES = 5
# Real ticks are 1s apart; backfilling at that resolution for 24h+
# would be 86400+ rows for no benefit to a dashboard that plots ~50
# points at a time. The simulation itself still advances continuously
# (SIM_TICKS_PER_SAMPLE steps between each persisted point) - only
# what we RECORD is downsampled, the same way a real historian's
# polling interval is coarser than a PLC's own scan cycle.
SIM_TICKS_PER_SAMPLE = 60


def _reset_asset_history(session, asset_repo: AssetRepository, asset_id: str) -> None:
    asset = asset_repo.get_by_code(asset_id)
    if asset is None:
        return
    session.execute(delete(AlertRow).where(AlertRow.asset_id == asset.id))
    session.execute(delete(TelemetryRow).where(TelemetryRow.asset_id == asset.id))
    session.commit()
    print(f"Reset: cleared existing telemetry/alerts for {asset_id}")


def seed(asset_id: str, profile: str, hours: int, reset: bool) -> None:
    if profile not in PLANT_PROFILES:
        raise SystemExit(f"Unknown profile '{profile}' - choices: {', '.join(PLANT_PROFILES)}")

    plant = Plant(PLANT_PROFILES[profile])
    engine = build_default_engine()  # heartbeat rule unused here - see module docstring

    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours)
    sample_every = timedelta(minutes=DEFAULT_INTERVAL_MINUTES)

    session = get_session()
    try:
        asset_repo = AssetRepository(session)
        telemetry_repo = TelemetryRepository(session)
        alert_repo = AlertRepository(session)

        if reset:
            _reset_asset_history(session, asset_repo, asset_id)

        asset = asset_repo.upsert_seen(
            asset_code=asset_id,
            name=asset_id,
            asset_type="PLC",
            seen_at=start,
            protocol="Modbus TCP",
            ip_address="127.0.0.1",
        )
        session.commit()

        current_ts = start
        telemetry_rows = 0
        alerts_raised: list[tuple[datetime, object]] = []
        tick_spacing = sample_every / SIM_TICKS_PER_SAMPLE

        # Bounded so the LAST window's final sub-tick (current_ts +
        # sample_every, in the limit) still lands at or before `now` -
        # `current_ts <= now` alone lets that last window's
        # interpolated sub-tick timestamps run past `now`, seeding
        # telemetry that's technically from the future.
        while current_ts + sample_every <= now:
            # Run the DETECTION ENGINE on every simulated tick (each
            # with its own interpolated timestamp), not just once per
            # persisted sample - the debounce/hysteresis rules
            # (detection/rules/base.py) need to see the continuous
            # trajectory to behave correctly. Evaluating only at the
            # 5-minute sample points would let the process swing
            # through a full excursion-and-recovery cycle *between*
            # two evaluations, making hysteresis re-arm far more often
            # than the real collector (which polls every ~1s) ever
            # would - inflating alert counts into something unrealistic.
            for i in range(SIM_TICKS_PER_SAMPLE):
                readings = plant.step()
                decision = plant.last_decision
                assert decision is not None
                tick_ts = current_ts + tick_spacing * i

                record = TelemetryRecord(
                    asset_id=asset_id,
                    timestamp=tick_ts,
                    temperature=readings.temperature,
                    pressure=readings.pressure,
                    tank_level_percent=readings.tank_level_percent,
                    pump_state=readings.pump_state,
                    cooling_active=decision.cooling_active,
                    inlet_open=decision.inlet_open,
                )
                for alert in engine.process_telemetry(record):
                    alerts_raised.append((tick_ts, alert))

                if i == SIM_TICKS_PER_SAMPLE - 1:
                    # Only the LAST tick of each window gets persisted
                    # as a Telemetry row - downsampling what we RECORD,
                    # not what the engine EVALUATES. Same relationship
                    # a real historian's polling interval has to a
                    # PLC's own (much faster) scan cycle.
                    telemetry_repo.add(
                        asset_id=asset.id,
                        timestamp=record.timestamp,
                        temperature=record.temperature,
                        pressure=record.pressure,
                        tank_level_percent=record.tank_level_percent,
                        pump_state=record.pump_state.value,
                        cooling_active=record.cooling_active,
                        inlet_open=record.inlet_open,
                    )
                    telemetry_rows += 1

            current_ts += sample_every

        asset_repo.upsert_seen(
            asset_code=asset_id,
            name=asset_id,
            asset_type="PLC",
            seen_at=now,
            protocol="Modbus TCP",
            ip_address="127.0.0.1",
        )

        # A realistic "lived-in" history isn't all-OPEN: resolve every
        # raised alert except the single most recent one, so the
        # dashboard still has at least one live, actionable item.
        resolved_count = 0
        for i, (ts, alert) in enumerate(alerts_raised):
            row = alert_repo.create(
                asset_id=asset.id,
                rule_id=alert.rule_id,
                severity=alert.severity.value,
                title=alert.title,
                description=alert.description,
                created_at=ts,
            )
            if i < len(alerts_raised) - 1:
                alert_repo.acknowledge(row.id, ts + timedelta(minutes=6))
                alert_repo.resolve(row.id, ts + timedelta(minutes=22))
                resolved_count += 1

        session.commit()
        left_open = len(alerts_raised) - resolved_count
        print(
            f"Seeded {asset_id} ({profile}): {telemetry_rows} telemetry rows over {hours}h, "
            f"{len(alerts_raised)} alerts raised ({resolved_count} resolved, {left_open} left open)"
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", default="PLC-001", help="Asset code to seed (default: PLC-001)")
    parser.add_argument(
        "--profile", default="default", help=f"Plant profile - choices: {', '.join(PLANT_PROFILES)}"
    )
    parser.add_argument("--hours", type=int, default=24, help="Hours of history to backfill (default: 24)")
    parser.add_argument(
        "--reset", action="store_true", help="Delete this asset's existing telemetry/alerts first"
    )
    args = parser.parse_args()

    seed(asset_id=args.asset, profile=args.profile, hours=args.hours, reset=args.reset)
