# ForgeSentinel

An educational, defensive, fully simulated Industrial Control System (ICS/OT)
Cybersecurity Lab. Everything runs locally against a simulated plant — no
real PLCs, no real network targets.

## Milestone 1: Industrial Process Simulator

Pure-Python simulation of a small virtual plant:

- `TANK-001` — a tank with capacity/level/inlet/outlet flow
- `PUMP-001` — drain pump (ON / OFF / FAULT)
- `TEMP-001` — temperature sensor
- `PRESS-001` — pressure sensor
- `PLC-001` — control logic enforcing basic safety rules

No networking, database, or web framework yet — those arrive in later
milestones.

### Run the simulator

```bash
python -m simulator.loop
```

### Run the tests

```bash
python -m pytest
```

## Milestone 4: PostgreSQL persistence

Assets and telemetry are now durably stored in PostgreSQL via
SQLAlchemy models and Alembic migrations.

```bash
cp .env.example .env          # defaults already match docker-compose.yml
docker compose up -d          # starts PostgreSQL on localhost:5432
python -m alembic upgrade head
python -m simulator.modbus.server   # terminal 1
python -m collector.collector       # terminal 2 - now persists to Postgres too
```

## Milestone 5: FastAPI backend

Read-only HTTP API over the asset inventory and telemetry history.

```bash
python -m uvicorn backend.main:app --reload
```

Endpoints (interactive docs at `http://127.0.0.1:8000/docs`):

- `GET /health` - process + database connectivity check
- `GET /api/assets` - list all known assets
- `GET /api/assets/{asset_code}` - one asset, e.g. `/api/assets/PLC-001`
- `GET /api/telemetry?asset_code=PLC-001&limit=100` - recent telemetry, newest first
- `GET /api/telemetry/latest?asset_code=PLC-001` - most recent reading

## Milestone 6: Detection engine

Rule-based detection over live telemetry. Rules 001-003 react to
incoming telemetry; Rule 004 (device offline) is heartbeat-driven -
see `detection/rules/device_offline.py`. Rule 005 (suspicious
configuration change) is intentionally NOT implemented yet - see
`detection/rules/suspicious_configuration_change.py` for why.

```bash
python -m simulator.modbus.server   # terminal 1
python -m collector.collector       # terminal 2 - now logs ALERT lines too
```

All rules debounce: a persisting condition raises exactly one alert
on the transition to "true," not one per poll, and re-arms once the
condition clears.

**Hysteresis, not just debouncing, on Rules 001/002.** Plain
rising-edge debouncing isn't enough when the value oscillates right
around a single threshold - which HIGH_TEMPERATURE genuinely does
here, since PLCController's cooling logic shares the same 90.0C
setpoint this rule alarms on, producing a real ~81C-94C bang-bang
cycle roughly every 3 seconds. Naive edge-triggering reported a fresh
alert on every cycle - dozens a minute for one ongoing excursion, a
textbook ICS "alarm flooding" problem. `_fire_with_hysteresis`
(`detection/rules/base.py`) fixes this with a wide "all clear"
threshold (70.0C for temperature, well below the oscillation floor):
one sustained excursion now raises exactly one OPEN alert, and its
OPEN -> ACKNOWLEDGED -> RESOLVED lifecycle (Milestone 7) is what
tracks "is this still ongoing" from there, not repeated re-firing.

## Milestone 7: Alert management

Alerts from the detection engine are now persisted and manageable
through the API - a full OPEN -> ACKNOWLEDGED -> RESOLVED lifecycle.

```bash
python -m simulator.modbus.server   # terminal 1
python -m collector.collector       # terminal 2 - alerts now persist too
python -m uvicorn backend.main:app --reload   # terminal 3
```

- `GET /api/alerts?status=OPEN&limit=100` - list, optionally filtered by status
- `GET /api/alerts/{id}` - one alert
- `POST /api/alerts/{id}/acknowledge` - OPEN -> ACKNOWLEDGED
- `POST /api/alerts/{id}/resolve` - OPEN or ACKNOWLEDGED -> RESOLVED

Both actions are no-ops (don't overwrite timestamps) if the alert is
already past that state.

## Milestone 8: WebSocket live telemetry

The backend now pushes new telemetry and alerts to connected clients
over `WS /ws/live`, no polling from the browser required. A background
task (`backend/broadcaster.py`) checks Postgres once a second and
broadcasts anything new - see that file's docstring for why polling
the database (not a true collector-to-backend push) is the right call
right now, without reaching for Redis/Celery early.

```bash
python -m simulator.modbus.server
python -m collector.collector
python -m uvicorn backend.main:app --reload
```

```python
import asyncio, websockets, json

async def main():
    async with websockets.connect("ws://127.0.0.1:8000/ws/live") as ws:
        while True:
            print(json.loads(await ws.recv()))

asyncio.run(main())
```

## Milestone 9: React OT SOC dashboard

A dark, technical "security operations center" dashboard - Overview,
Live Telemetry (animated chart), Alerts (filter + acknowledge/resolve),
and Assets - built with React, TypeScript, Vite, Tailwind CSS,
Recharts, and Framer Motion for live-data animation (pulsing status
dots, animated numbers, alert toasts, smooth page transitions).

```bash
# terminal 1-3: the usual backend stack
python -m simulator.modbus.server
python -m collector.collector
python -m uvicorn backend.main:app --reload

# terminal 4: frontend dev server (proxies /api and /ws to :8000)
cd frontend
npm install
npm run dev
```

Then open the printed `http://localhost:<port>/` URL.

## Milestone 10: Redis + Celery

Two concrete gaps neither FastAPI's request/response cycle nor the
collector's synchronous per-telemetry callbacks could fill:

1. **DEVICE_OFFLINE (Rule 004) never actually ran.** It existed and
   was tested since Milestone 6, but nothing called it on a timer. A
   timer *inside* the collector process couldn't fix this properly
   either - it would die along with the very process it's supposed to
   notice has died. `tasks/heartbeat.py` runs as a Celery Beat
   schedule (every 5s), in its own worker process, reading Postgres's
   `Asset.last_seen` - independent of whether the collector is alive.
2. **Report generation** (`tasks/reports.py`) can be slow. A FastAPI
   route running it synchronously would block the HTTP response;
   instead the route hands it to a Celery worker and returns
   immediately with a task id to poll.

Redis is Celery's broker + result backend only - Postgres remains the
system of record.

```bash
docker compose up -d          # now also starts redis
python -m alembic upgrade head

# terminal 1-3: the usual backend stack (simulator, collector, API)

# terminal 4
celery -A tasks.celery_app worker --loglevel=info --pool=solo   # --pool=solo: Windows

# terminal 5
celery -A tasks.celery_app beat --loglevel=info
```

- `POST /api/reports/{asset_code}` -> `202 {"task_id": ..., "status": "PENDING"}`
- `GET /api/reports/{task_id}` -> `{"status": "SUCCESS", "result": {...}}`

**Verified live:** killed the collector process outright while the
worker/beat kept running - Celery Beat noticed the stale `last_seen`
and raised exactly one CRITICAL `DEVICE_OFFLINE` alert on its own,
with no further duplicates on later ticks.

## Milestone 11: Prometheus + Grafana

**Application monitoring vs. industrial telemetry - deliberately kept
separate.** Postgres's telemetry table answers "is the physical
process healthy" (temperature, pressure, tank level) and drives
business logic (the detection engine). Prometheus answers a different
question - "is the ForgeSentinel *software* healthy" (assets online,
open alerts, Modbus request/error rates) - for a human watching a
Grafana panel, not for the application to branch on. Mixing the two
would mean using a short-retention operational metrics store for
long-term business data, or vice versa.

The collector isn't an HTTP server, so it can't just add a `/metrics`
route like the backend does - `collector/metrics.py` runs
prometheus_client's own tiny HTTP server on a separate port (9100).

```bash
docker compose up -d   # now also starts prometheus (:9090) and grafana (:3000)
```

- Backend: `GET /metrics` (port 8000) - `forgesentinel_active_assets`,
  `forgesentinel_alerts_total{status=...}`,
  `forgesentinel_critical_alerts_total` (Gauges, recomputed fresh from
  Postgres on every scrape - correct even if the backend ever runs as
  more than one worker process).
- Collector: `GET :9100/metrics` - `forgesentinel_modbus_requests_total`,
  `forgesentinel_collector_errors_total` (Counters, incremented as the
  poll loop runs).
- Grafana (`http://localhost:3000`, `admin` / `$GRAFANA_ADMIN_PASSWORD`
  from `.env`, default `forgesentinel`) auto-provisions the Prometheus
  datasource and a "ForgeSentinel - Application Health" dashboard on
  first start - no manual click-through setup, so the whole
  observability stack is reproducible from the repo alone.

## Milestone 12: Network security integration

A network-layer (packet-level) view alongside the application-layer
detection engine - Suricata (rule-based) and Zeek (passive protocol
logging), both reading a synthetic Modbus TCP `.pcap` rather than
live-sniffing (Docker Desktop on Windows can't see host loopback
traffic - see `network-security/README.md` for the full reasoning).

This is deliberately the network-layer complement to Rule 005
(`detection/rules/suspicious_configuration_change.py`), which
documented exactly why it couldn't be built at the application layer:
Modbus has no authentication, so any client's write command is
inherently suspicious here - a rule the network layer can express
trivially (`modbus: access write`) without needing to know what value
was written or why.

```bash
python network-security/generate_pcaps.py
docker compose --profile analysis run --rm suricata
docker compose --profile analysis run --rm zeek
```

Full walkthrough (including a Wireshark manual-inspection guide) in
[network-security/README.md](network-security/README.md).

**Verified live:** Suricata raised all 4 expected alerts against the
malicious capture and zero against the benign one; Zeek's
`modbus.log` correctly decoded both write function codes with the
right source/destination/transaction ids.

## Security boundary

This is a local training lab only. It never targets real industrial
facilities, public IP addresses, or third-party systems.
