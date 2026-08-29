"""
Collector: the polling loop entry point. Connects to a Modbus TCP PLC,
polls it on an interval, decodes each poll into a TelemetryRecord, and
hands each record to a callback.

Milestone 3 scope: no database, no detection engine yet - this
process just proves telemetry can be reliably pulled off the wire and
turned into structured records. The default callback logs each
record; Milestone 4 will replace/extend that callback with database
persistence.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from collector.modbus_client import ModbusPLCClient
from collector.telemetry import TelemetryRecord, decode_telemetry

logger = logging.getLogger("forgesentinel.collector")

DEFAULT_ASSET_ID = "PLC-001"
DEFAULT_POLL_SECONDS = 1.0

TelemetryCallback = Callable[[TelemetryRecord], None]


def log_telemetry(record: TelemetryRecord) -> None:
    """Default callback: log each telemetry record like a real historian tail would."""
    logger.info(
        "asset=%s temp=%6.2fC pressure=%5.2fbar level=%5.1f%% pump=%s cooling=%s inlet=%s",
        record.asset_id,
        record.temperature,
        record.pressure,
        record.tank_level_percent,
        record.pump_state.value,
        record.cooling_active,
        record.inlet_open,
    )


def run_collector(
    host: str,
    port: int,
    asset_id: str = DEFAULT_ASSET_ID,
    poll_seconds: float = DEFAULT_POLL_SECONDS,
    max_polls: int | None = None,
    on_telemetry: TelemetryCallback = log_telemetry,
) -> None:
    """
    Run the collector loop. Blocks forever unless max_polls is given
    (used by tests / short manual runs to avoid an infinite loop).

    max_polls bounds the number of loop ITERATIONS (connection
    attempts), not just successful reads - otherwise a PLC that never
    comes back online would make this loop never terminate even with
    max_polls set, since a failed attempt would never count toward the
    limit.

    Reconnects automatically if the initial connect fails or a poll
    reports a connection problem - this mirrors how a real collector
    must tolerate a PLC being briefly unreachable rather than crashing
    outright.
    """
    client = ModbusPLCClient(host=host, port=port)
    logger.info("Collector starting: target=%s:%d asset_id=%s", host, port, asset_id)

    attempts = 0
    connected = client.connect()
    if not connected:
        logger.warning("Initial connection to %s:%d failed; will keep retrying", host, port)

    try:
        while max_polls is None or attempts < max_polls:
            attempts += 1

            if not connected:
                connected = client.connect()
                if not connected:
                    time.sleep(poll_seconds)
                    continue

            raw = client.read_raw()
            if raw is None:
                # Could be a transient error or a dropped connection;
                # force a reconnect attempt on the next iteration.
                connected = False
                time.sleep(poll_seconds)
                continue

            holding_registers, coils = raw
            record = decode_telemetry(
                asset_id=asset_id, holding_registers=holding_registers, coils=coils
            )
            on_telemetry(record)

            time.sleep(poll_seconds)
    finally:
        client.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    run_collector(host="127.0.0.1", port=5020)
