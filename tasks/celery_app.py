"""
Celery application instance + periodic task schedule (Celery Beat).

Why Celery (and Redis as its broker) now, not earlier:
    Two concrete needs neither FastAPI's request/response cycle nor
    the collector's synchronous per-telemetry callbacks can satisfy:

    1. DEVICE_OFFLINE detection (tasks/heartbeat.py) has to keep
       running even if the collector process itself has crashed - the
       one failure mode a timer *inside* the collector could never
       notice (a dead process can't run its own watchdog). Celery Beat
       schedules this task independently, in its own worker process,
       reading Postgres's Asset.last_seen column regardless of whether
       the collector that writes it is still alive.
    2. Report generation (tasks/reports.py) can be slow. A FastAPI
       route handling it synchronously would block the HTTP response
       for however long that takes; Celery lets a route hand the work
       off immediately and return a task id the client polls.

Redis's role here is narrow and specific: it's Celery's message broker
(how the API process tells a worker process "run this task") and
result backend (where a task's return value is stored so something
can later ask "is it done, what did it return"). It is NOT a database
substitute - Postgres remains the system of record for
assets/telemetry/alerts. Broker and result backend point at different
Redis logical databases (0 and 1) purely so `redis-cli` inspection of
one doesn't mix task messages with stored results - both still live in
the one Redis container docker-compose.yml runs.
"""

from __future__ import annotations

import os

from celery import Celery

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = os.environ.get("REDIS_PORT", "6379")
BROKER_URL = os.environ.get("CELERY_BROKER_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}/0")
RESULT_BACKEND_URL = os.environ.get(
    "CELERY_RESULT_BACKEND", f"redis://{REDIS_HOST}:{REDIS_PORT}/1"
)

celery_app = Celery(
    "forgesentinel",
    broker=BROKER_URL,
    backend=RESULT_BACKEND_URL,
    include=["tasks.heartbeat", "tasks.reports"],
)

celery_app.conf.timezone = "UTC"
celery_app.conf.broker_connection_retry_on_startup = True
celery_app.conf.beat_schedule = {
    "check-device-offline": {
        "task": "tasks.check_device_offline",
        "schedule": 5.0,  # seconds - independent of, and slower than, the 1s telemetry poll
    },
}
