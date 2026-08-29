"""
Modbus register/coil mapping: pure encode/decode functions, no
networking, no pymodbus imports. Kept separate from server.py so the
mapping logic (the actual engineering decisions - which value goes
where, how it's scaled) can be unit tested without spinning up a TCP
server.

--- Why "holding registers" and "coils", and why they differ ---

Modbus defines four data tables, distinguished by whether they're
read-only vs read/write, and whether they hold a single bit or a
16-bit word:

    Coils            (1 bit,  read/write)  - function codes 1 (read), 5/15 (write)
    Discrete Inputs  (1 bit,  read-only)   - function code 2
    Input Registers  (16-bit, read-only)   - function code 4
    Holding Registers(16-bit, read/write)  - function codes 3 (read), 6/16 (write)

We only use Coils and Holding Registers here: coils for values that
are genuinely a single ON/OFF state, holding registers for anything
numeric (a temperature reading can't fit in 1 bit) - discrete
inputs/input registers exist for read-only sensor-style data, but we
model our sensors as holding registers too since nothing in this lab
depends on the read-only distinction yet.

--- Why PUMP STATE is a holding register, not a coil (deviation from
    the original spec's "Coil 0 -> Pump state") ---

A coil is a single bit: it can only represent two states (0/1). Our
Pump has THREE states (OFF/ON/FAULT). Forcing a 3-state value into 1
bit would silently lose information - exactly the kind of thing this
project's rules say we must never do. So pump state lives in a
holding register instead, encoded as a small integer enum. Cooling
and inlet-valve state are genuinely binary (a valve/relay is either
energized or not), so those stay as coils.

--- Why values are scaled integers, not floats ---

A Modbus register is a 16-bit UNSIGNED integer (0-65535). There is no
native floating-point register type in the base protocol. To carry a
value like 87.62 degrees C, we multiply by a fixed SCALE (100) before
writing, and divide by SCALE after reading: 87.62 * 100 = 8762, which
fits in 16 bits. This is a universal real-world Modbus pattern -
always check a device's manual for its scaling factor, because it is
not standardized and differs per vendor/register.

--- Addressing: human-readable vs protocol (zero-based) ---

Historically Modbus documentation uses a human-readable 1-based
convention with a table-identifying prefix, e.g. "40001" for the
first holding register (4xxxx), "00001" for the first coil (0xxxx).
On the wire, however, the actual PROTOCOL address sent in a Modbus
TCP request is zero-based: holding register "40001" is protocol
address 0, "40002" is protocol address 1, and so on.

This module uses protocol (zero-based) addresses directly, and the
server is configured with zero_mode=True precisely so that the
address you pass to pymodbus's API is the same protocol address you
see here - no hidden +1 offset. We call this out explicitly because
silently mixing the two conventions is one of the most common real
Modbus integration bugs.
"""

from __future__ import annotations

from simulator.process.pump import PumpState

# --- Holding register addresses (protocol/zero-based) ---
HR_TEMPERATURE = 0  # traditionally documented as "40001"
HR_PRESSURE = 1  # "40002"
HR_TANK_LEVEL = 2  # "40003"
HR_PUMP_STATE = 3  # "40004"

HOLDING_REGISTER_COUNT = 4

# --- Coil addresses (protocol/zero-based) ---
COIL_COOLING_ACTIVE = 0  # traditionally documented as "00001"
COIL_INLET_OPEN = 1  # "00002"

COIL_COUNT = 2

# Fixed-point scaling factor applied to all numeric readings before
# they're stored as 16-bit unsigned integers.
SCALE = 100

# Max value a single Modbus register can hold.
UINT16_MAX = 65535

PUMP_STATE_TO_CODE: dict[PumpState, int] = {
    PumpState.OFF: 0,
    PumpState.ON: 1,
    PumpState.FAULT: 2,
}
CODE_TO_PUMP_STATE: dict[int, PumpState] = {v: k for k, v in PUMP_STATE_TO_CODE.items()}


def encode_scaled(value: float) -> int:
    """
    Convert a float reading into a 16-bit unsigned integer register
    value. Clamped to [0, UINT16_MAX] because a real Modbus register
    literally cannot represent anything outside that range - clamping
    here (rather than raising) mirrors how a real analog-to-digital
    conversion on a physical device saturates at its rail voltage
    instead of crashing.
    """
    scaled = round(value * SCALE)
    return max(0, min(UINT16_MAX, scaled))


def decode_scaled(register_value: int) -> float:
    """Inverse of encode_scaled: raw register integer -> real-world float."""
    return register_value / SCALE


def encode_pump_state(state: PumpState) -> int:
    return PUMP_STATE_TO_CODE[state]


def decode_pump_state(code: int) -> PumpState:
    if code not in CODE_TO_PUMP_STATE:
        raise ValueError(f"unknown pump state code: {code}")
    return CODE_TO_PUMP_STATE[code]


def build_holding_registers(
    temperature: float, pressure: float, tank_level_percent: float, pump_state: PumpState
) -> list[int]:
    """Build the full holding-register block in address order (0..3)."""
    registers = [0] * HOLDING_REGISTER_COUNT
    registers[HR_TEMPERATURE] = encode_scaled(temperature)
    registers[HR_PRESSURE] = encode_scaled(pressure)
    registers[HR_TANK_LEVEL] = encode_scaled(tank_level_percent)
    registers[HR_PUMP_STATE] = encode_pump_state(pump_state)
    return registers


def build_coils(cooling_active: bool, inlet_open: bool) -> list[bool]:
    """Build the full coil block in address order (0..1)."""
    coils = [False] * COIL_COUNT
    coils[COIL_COOLING_ACTIVE] = cooling_active
    coils[COIL_INLET_OPEN] = inlet_open
    return coils
