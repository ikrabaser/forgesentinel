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

## Security boundary

This is a local training lab only. It never targets real industrial
facilities, public IP addresses, or third-party systems.
