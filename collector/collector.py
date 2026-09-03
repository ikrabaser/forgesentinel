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

from collector.metrics import COLLECTOR_ERRORS_TOTAL, MODBUS_REQUESTS_TOTAL
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
                    COLLECTOR_ERRORS_TOTAL.inc()
                    time.sleep(poll_seconds)
                    continue

            MODBUS_REQUESTS_TOTAL.inc()
            raw = client.read_raw()
            if raw is None:
                # Could be a transient error or a dropped connection;
                # force a reconnect attempt on the next iteration.
                COLLECTOR_ERRORS_TOTAL.inc()
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


def _compose(*callbacks: TelemetryCallback) -> TelemetryCallback:
    """Run several TelemetryCallbacks in order for every record."""

    def _combined(record: TelemetryRecord) -> None:
        for callback in callbacks:
            callback(record)

    return _combined


def _make_detecting_callback(engine, alert_sink) -> TelemetryCallback:
    """
    Run every telemetry record through the detection engine, log every
    alert produced, and hand it to alert_sink (Milestone 7: persists
    to Postgres via detection.persistence.make_persisting_alert_sink).
    """
    detection_logger = logging.getLogger("forgesentinel.detection")

    def _callback(record: TelemetryRecord) -> None:
        for alert in engine.process_telemetry(record):
            detection_logger.warning(
                "ALERT [%s] %s severity=%s asset=%s :: %s",
                alert.rule_id,
                alert.title,
                alert.severity.value,
                alert.asset_id,
                alert.description,
            )
            alert_sink(alert)

    return _callback


if __name__ == "__main__":
    import os

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    # Milestone 4: persist every polled record to Postgres in addition
    # to logging it. Milestone 6: also run it through the detection
    # engine. Milestone 7: persist every alert too. Imports are local
    # to __main__ so `collector.py` can still be imported/tested
    # (Milestone 3 style) by anything that doesn't need the DB or
    # detection engine.
    from collector.metrics import start_metrics_server
    from collector.persistence import make_persisting_callback
    from detection.engine import build_default_engine
    from detection.persistence import make_persisting_alert_sink

    # Milestone 16 (multi-asset): every knob a second collector
    # instance needs is an env var defaulted to reproduce Milestone
    # 3-15's single-collector behavior exactly. Running the collector
    # for the PLC-002 example in simulator/modbus/server.py's own
    # __main__ comment is then:
    #   COLLECTOR_ASSET_ID=PLC-002 COLLECTOR_PORT=5021 COLLECTOR_METRICS_PORT=9101 \\
    #     python -m collector.collector
    target_host = os.environ.get("COLLECTOR_HOST", "127.0.0.1")
    target_port = int(os.environ.get("COLLECTOR_PORT", "5020"))
    asset_id = os.environ.get("COLLECTOR_ASSET_ID", DEFAULT_ASSET_ID)
    # Distinct default per likely-second-instance so two collectors
    # started with only COLLECTOR_ASSET_ID/COLLECTOR_PORT set don't
    # also collide on the metrics port by accident.
    metrics_port = int(os.environ.get("COLLECTOR_METRICS_PORT", "9100"))

    # Milestone 11: expose forgesentinel_modbus_requests_total /
    # forgesentinel_collector_errors_total on their own tiny HTTP
    # server for Prometheus to scrape - separate from anything the
    # collector loop itself is doing.
    start_metrics_server(port=metrics_port)

    engine = build_default_engine(expected_poll_interval_seconds=DEFAULT_POLL_SECONDS)

    run_collector(
        host=target_host,
        port=target_port,
        asset_id=asset_id,
        on_telemetry=_compose(
            log_telemetry,
            make_persisting_callback(asset_ip=target_host),
            _make_detecting_callback(engine, make_persisting_alert_sink()),
        ),
    )
