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

## Security boundary

This is a local training lab only. It never targets real industrial
facilities, public IP addresses, or third-party systems.
