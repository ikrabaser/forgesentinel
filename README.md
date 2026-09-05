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
configuration change) is event-driven from the Modbus server's write
path, not telemetry - see the "Rule 005" note under Milestone 15 below.

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
(`detection/rules/suspicious_configuration_change.py`, implemented in
Milestone 15/later): Modbus has no authentication, so any client's
write command is inherently suspicious here - a signal the network
layer can express trivially (`modbus: access write`) without needing
any application-layer state at all, independent of whether the
application-layer rule is watching.

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

## Milestone 13: MQTT (push vs. pull)

The Modbus server now ALSO publishes every tick over MQTT
(Mosquitto), so the exact same `Plant` state reaches the outside world
through two fundamentally different protocol philosophies at once:
Modbus's pull ("ask me and I'll answer") and MQTT's push ("I'll tell
you the moment something changes"). See
`simulator/mqtt/publisher.py`'s docstring for the retain/QoS reasoning.

```bash
docker compose up -d mosquitto
python -m simulator.modbus.server   # now publishes to MQTT too

# in another terminal, watch it live (needs the paho-mqtt package):
python -c "
import paho.mqtt.client as mqtt
c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
c.on_message = lambda _c, _u, m: print(m.topic, m.payload.decode())
c.connect('127.0.0.1', 1883)
c.subscribe('forgesentinel/PLC-001/telemetry')
c.loop_forever()
"
```

**Verified live:** started the Modbus server with MQTT publishing on,
confirmed the same tick's temperature matches (within each protocol's
own rounding) between a real Modbus read and a live MQTT subscription
- see `tests/test_modbus_server_mqtt.py`.

## Milestone 14: AI Incident Analyst

Claude explains alerts - it never controls the plant. See
`detection/ai_analyst.py`'s docstring: the module imports nothing from
`simulator/` and references no Modbus/MQTT client, so there is no code
path here that could write to the plant even if the model "wanted" to.
It reads an alert plus the 10 minutes of telemetry leading up to it,
and returns a structured `summary` / `possible_causes` /
`recommended_actions` - always investigation steps a human takes, never
a control command.

```bash
# .env: set ANTHROPIC_API_KEY=sk-ant-... (get one at https://console.anthropic.com)
docker compose up -d redis
celery -A tasks.celery_app worker --loglevel=info   # terminal 1
uvicorn backend.main:app --reload                    # terminal 2

curl -X POST http://127.0.0.1:8000/api/incidents/analyze/1
# -> {"task_id": "...", "status": "PENDING"}
curl http://127.0.0.1:8000/api/incidents/tasks/<task_id>
# -> {"status": "SUCCESS", "result": {"summary": "...", "possible_causes": [...], "recommended_actions": [...]}}
curl "http://127.0.0.1:8000/api/incidents?alert_id=1"   # persisted history for that alert
```

Every test in this milestone mocks the Claude call (see
`tests/test_incident_analysis_task.py` /
`tests/test_backend_incidents_api.py`) - no API key is required to run
the suite. **Live end-to-end verification requires your own
`ANTHROPIC_API_KEY`** and has not been run in this environment.

**Dashboard integration:** each row on the Alerts page has an expand
chevron that reveals `IncidentAnalysisPanel` - "Analyze with AI"
requests an analysis, polls the Celery task to completion, and renders
the result in place (with a "Re-analyze" option and a persisted-history
lookup, so re-opening an alert reuses a prior run instead of re-paying
for a fresh one). The disclaimer under every result restates the same
rule as the backend: AI-generated analysis for human review only, it
does not act on the plant.

## Milestone 15: Audit logging

An append-only "who did what, when" record - distinct from Telemetry
(physical process state) and Alert (detection findings). Nothing
outside `AuditLogRepository.record()` can create an entry, and there
is no update/delete method at all: an audit log an application can
quietly edit isn't a trustworthy one.

Two sources feed it:

1. **API actions** - `POST /api/alerts/{id}/acknowledge`, `/resolve`,
   and `POST /api/incidents/analyze/{id}` each write an entry
   (`actor="api-client"` - there's no authentication yet, so this is
   an honest placeholder, not a real principal, until a future auth
   milestone).
2. **Modbus write requests** - `detection/rules/suspicious_configuration_change.py`
   named this exact gap as its own prerequisite: *"a write-audit path
   on the Modbus server, logging every FC06/16 request"*.
   `AuditingSlaveContext` (`simulator/modbus/server.py`) does exactly
   that - and only that: our own simulator writes registers every tick
   using fc=3/1 (the "read" function codes, by pymodbus convention), so
   only a genuine external FC06/FC16 write ever reaches the audit log,
   never our own internal state refresh.

**Rule 005 (SUSPICIOUS_CONFIGURATION_CHANGE) is now implemented**,
built directly on top of this audit path: every genuine external write
`AuditingSlaveContext` observes also raises a CRITICAL alert via
`simulator/modbus/audit.py` - our collector never writes, so any write
is unauthorized by construction. Unlike Rules 001-003, it has no
debounce state: a write is a discrete event, not a continuous value
that can hover near a threshold, so every occurrence gets its own
alert. It runs on its own event trigger, not through
`DetectionEngine`/`build_default_engine` - see that function's
docstring for why.

**Verified live:** sent a real `write_register(0, 9999)` - it produced
exactly one `RULE-005` CRITICAL "Suspicious configuration change"
alert visible at `GET /api/alerts`, alongside the corresponding
`MODBUS_WRITE` audit-log entry.

```bash
python -m simulator.modbus.server   # now audits genuine writes
python -m uvicorn backend.main:app --reload
```

- `GET /api/audit-log?action=MODBUS_WRITE&resource_type=plc&limit=100`

**Verified live:** sent a real `write_register(0, 4200)` from a Modbus
client - it showed up as a single `MODBUS_WRITE` entry
(`function_name: WRITE_SINGLE_REGISTER`) in `/api/audit-log`, with zero
pollution from the thousands of internal fc=3 updates the simulator's
own tick loop makes.

**Known gap:** the Modbus write entries don't capture the writing
client's source IP - pymodbus's single-shared-context server model
doesn't expose per-connection info to `setValues()` without deeper
protocol-layer surgery. Documented, not silently missing.

## Dashboard: Audit Log page + loading/polish pass

The dashboard's frontend caught up to Milestone 15 and picked up a
round of UI fixes that applied across the whole app, not just one
page:

- **Audit Log page** (`/audit-log`) - filterable by action/resource
  type, polled every 4s (no live WebSocket push for audit entries by
  design - see the page's own comment on why extending
  `backend/broadcaster.py` for one monitoring page isn't worth the
  coupling yet). Rows with details expand in place to show the raw
  JSON, with a copy-to-clipboard button. Newly-arrived rows (since the
  last poll) get a brief accent-tinted flash - fast attack, slow decay
  - so a fresh entry is noticeable without needing a toast.
- **Loading skeletons everywhere a table fetches data.** Real gap:
  Assets and Alerts tracked no loading state at all before this - an
  empty result and "still fetching" rendered identically. `TableSkeleton`
  (shimmer bars, deterministically varied widths) and `StatCardSkeleton`
  now cover Overview, Live Telemetry, Assets, Alerts, and Audit Log.
- **Per-asset-type icons** in the Assets table (Cpu/Droplet/Pump/
  Thermometer/Gauge, mirroring `db/models.py`'s `AssetType` enum) and a
  **color-key legend** on the Live Telemetry chart (temperature vs.
  pressure line color).

```bash
cd frontend && npm run build   # tsc -b && vite build - verified clean
```

## Milestone 16: Multi-asset simulation

Still fully simulated - this doesn't connect to real hardware. What it
does: the whole stack scales past one hard-coded PLC-001, and a real
bug that hard-coding caused gets fixed along the way.

A real bug this surfaced: `collector/persistence.py`'s `ASSET_NAME`
was the literal string `"PLC-001"`, harmless with exactly one asset in
the system, wrong the moment a second one exists - every asset would
display the name "PLC-001" regardless of which it actually was. Now
defaults to the asset's own code.

`PLANT_PROFILES` (`simulator/loop.py`) lets a second simulated asset be
a genuinely different process, not a PLC-001 clone on a different
port - `cooling-loop` runs smaller/faster, cooler, with a tighter
pressure ceiling. Both the Modbus server and the collector read their
target/asset/port from environment variables now (defaulted to
reproduce single-asset behavior exactly):

```bash
# Terminal 1-3: PLC-001, exactly as every earlier milestone
python -m simulator.modbus.server
python -m collector.collector
python -m uvicorn backend.main:app --reload

# Terminal 4-5: PLC-002, a second simulated asset
MODBUS_ASSET_ID=PLC-002 MODBUS_PORT=5021 PLANT_PROFILE=cooling-loop \
  python -m simulator.modbus.server
COLLECTOR_ASSET_ID=PLC-002 COLLECTOR_PORT=5021 COLLECTOR_METRICS_PORT=9101 \
  python -m collector.collector
```

The Live Telemetry page picks up a tab picker automatically once more
than one asset exists - verified live switching between PLC-001 and
PLC-002 correctly swaps the stat cards, chart data, and Y-axis scale.

**`scripts/seed_history.py`** backfills realistic historical telemetry
+ alerts so the dashboard doesn't open empty on a fresh database -
using the SAME `Plant`/`PLCController`/`DetectionEngine` machinery the
live system runs, fast-forwarded and stamped with past timestamps, not
random numbers standing in for real ones:

```bash
python -m scripts.seed_history --asset PLC-001 --hours 48 --reset
python -m scripts.seed_history --asset PLC-002 --profile cooling-loop --hours 48 --reset
```

Two real bugs its own test suite caught before either was committed:
(1) the detection engine was only evaluated once per 5-minute
*persisted* sample instead of every simulated tick, which let a full
excursion-and-recovery cycle happen between evaluations and inflated a
48h backfill to 73 alerts instead of the ~1 the real hysteresis-fixed
system produces; (2) the backfill loop's boundary could stamp its last
window's telemetry with timestamps technically in the future. Both
fixed; `tests/test_seed_history.py` asserts against regressing either.

## Security boundary

This is a local training lab only. It never targets real industrial
facilities, public IP addresses, or third-party systems.
