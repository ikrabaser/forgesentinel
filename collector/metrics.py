"""
Application metrics for the collector process, exposed for Prometheus
to scrape - NOT to be confused with the industrial telemetry the
collector also produces (temperature, pressure, tank level), which
lives in Postgres and answers "is the physical process healthy".
These metrics answer a different question: "is the collector software
itself healthy" - is it actually reaching the PLC, how often is it
failing. An operator watching a Grafana panel for
forgesentinel_collector_errors_total climbing is diagnosing the
collector, not the plant.

The collector isn't an HTTP server (it's a polling loop), so unlike
the FastAPI backend it can't just add a route - start_metrics_server()
runs prometheus_client's own tiny built-in HTTP server on a separate
port (default 9100) for Prometheus to scrape independently of
whatever the collector's main loop is doing.
"""

from __future__ import annotations

from prometheus_client import Counter, start_http_server

MODBUS_REQUESTS_TOTAL = Counter(
    "forgesentinel_modbus_requests_total",
    "Total Modbus TCP read attempts made by the collector.",
)

COLLECTOR_ERRORS_TOTAL = Counter(
    "forgesentinel_collector_errors_total",
    "Total failed connection/read attempts (transient or otherwise).",
)


def start_metrics_server(port: int = 9100) -> None:
    start_http_server(port)
