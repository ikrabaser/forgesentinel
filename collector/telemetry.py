"""
TelemetryRecord: the structured, decoded representation of one poll of
PLC-001's state.

Real-world analogy:
    This is the boundary where raw, protocol-specific bytes (Modbus
    register integers, coil bits) become a domain object the rest of
    the system can reason about ("temperature is 87.6C") without
    knowing anything about Modbus. Every OT collector has an
    equivalent translation layer - it's what lets the same downstream
    code (storage, detection, dashboards) work regardless of whether
    the data arrived via Modbus, OPC UA, or MQTT.

This module is deliberately pure (no networking) so the decode logic
can be unit tested against known register/coil values without a live
server.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from simulator.modbus import mapping
from simulator.process.pump import PumpState


@dataclass(frozen=True)
class TelemetryRecord:
    asset_id: str
    timestamp: datetime
    temperature: float
    pressure: float
    tank_level_percent: float
    pump_state: PumpState
    cooling_active: bool
    inlet_open: bool


def decode_telemetry(
    asset_id: str,
    holding_registers: list[int],
    coils: list[bool],
    timestamp: datetime | None = None,
) -> TelemetryRecord:
    """
    Turn raw Modbus data (as returned by a read_holding_registers /
    read_coils call) into a TelemetryRecord.

    holding_registers must be at least mapping.HOLDING_REGISTER_COUNT
    long, and cover addresses starting at 0 (i.e. it's exactly what
    you get back from `read_holding_registers(address=0, count=...)`).
    Same for coils.
    """
    if len(holding_registers) < mapping.HOLDING_REGISTER_COUNT:
        raise ValueError(
            f"expected at least {mapping.HOLDING_REGISTER_COUNT} holding registers, "
            f"got {len(holding_registers)}"
        )
    if len(coils) < mapping.COIL_COUNT:
        raise ValueError(f"expected at least {mapping.COIL_COUNT} coils, got {len(coils)}")

    return TelemetryRecord(
        asset_id=asset_id,
        timestamp=timestamp or datetime.now(timezone.utc),
        temperature=mapping.decode_scaled(holding_registers[mapping.HR_TEMPERATURE]),
        pressure=mapping.decode_scaled(holding_registers[mapping.HR_PRESSURE]),
        tank_level_percent=mapping.decode_scaled(holding_registers[mapping.HR_TANK_LEVEL]),
        pump_state=mapping.decode_pump_state(holding_registers[mapping.HR_PUMP_STATE]),
        cooling_active=bool(coils[mapping.COIL_COOLING_ACTIVE]),
        inlet_open=bool(coils[mapping.COIL_INLET_OPEN]),
    )
