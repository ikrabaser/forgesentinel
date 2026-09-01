"""
AI Incident Analyst: given an alert and the telemetry history around
it, asks Claude to explain PLAUSIBLE causes and recommend
investigation steps.

ARCHITECTURAL RULE (see the project's own root instructions): AI here
may only ANALYZE, EXPLAIN, and RECOMMEND - it must never directly
control the PLC. This file enforces that by construction, not just by
convention: it has no import of anything in simulator/, no reference
to PLCController or the Modbus/MQTT clients, and its only possible
effect is returning a structured IncidentAnalysis a human reads. There
is no code path here that could write to a register even if the model
"wanted" it to - the capability simply isn't wired in.

Split into a pure prompt-builder (testable without any API access, no
`anthropic` import needed) and a thin client wrapper (the only
function that actually calls Claude), the same separation already
used throughout this codebase (mapping.py vs server.py, payload.py vs
publisher.py, persistence.py adapters, ...).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel

MODEL = "claude-opus-5"

SYSTEM_PROMPT = """\
You are a defensive OT/ICS security incident analyst assisting a human \
operator at a simulated industrial plant (ForgeSentinel). You explain \
PLAUSIBLE causes for an alert and recommend concrete next steps, using \
the alert and telemetry history you are given.

Rules you must always follow:
- This is a local, fully simulated training lab - never a real industrial \
facility, and nothing you say will be executed automatically.
- You NEVER issue, imply, or word a direct control command to a PLC or \
actuator (e.g. "turn the pump off", "close the inlet valve"). Every \
recommended action must be something a HUMAN does to investigate - read a \
gauge, check a log, review a configuration history, inspect a physical \
component - never an action that itself changes process state.
- Reference the specific numbers, timestamps, and state transitions you were \
given; do not give generic textbook advice that ignores the actual data.
- If the evidence genuinely doesn't point to a clear cause, say that \
explicitly rather than guessing with false confidence.
"""


class IncidentAnalysis(BaseModel):
    summary: str
    possible_causes: list[str]
    recommended_actions: list[str]


@dataclass
class AlertContext:
    rule_id: str
    severity: str
    title: str
    description: str
    status: str
    created_at: datetime


@dataclass
class AssetContext:
    asset_code: str
    asset_type: str
    status: str


@dataclass
class TelemetrySample:
    timestamp: datetime
    temperature: float
    pressure: float
    tank_level_percent: float
    pump_state: str
    cooling_active: bool
    inlet_open: bool


def build_incident_prompt(
    alert: AlertContext,
    asset: AssetContext,
    telemetry_history: list[TelemetrySample],
) -> str:
    """
    Render the alert + asset + telemetry history into the user-turn
    text sent to Claude. Pure string building - no network, no SDK -
    so every case (empty history, single-sample history, long
    history) is unit-testable without an API key.

    telemetry_history is expected oldest-first, matching how a human
    analyst would read a trend ("72 -> 78 -> 91 -> 108C"), per the
    project's own example incident format.
    """
    lines = [
        f"Asset: {asset.asset_code} ({asset.asset_type}, currently {asset.status})",
        "",
        f"Alert: [{alert.rule_id}] {alert.title}",
        f"Severity: {alert.severity}",
        f"Status: {alert.status}",
        f"Raised at: {alert.created_at.isoformat()}",
        f"Description: {alert.description}",
        "",
    ]

    if telemetry_history:
        lines.append(f"Recent telemetry history ({len(telemetry_history)} samples, oldest first):")
        temps = " -> ".join(f"{s.temperature:.1f}C" for s in telemetry_history)
        pressures = " -> ".join(f"{s.pressure:.2f}bar" for s in telemetry_history)
        levels = " -> ".join(f"{s.tank_level_percent:.1f}%" for s in telemetry_history)
        pumps = " -> ".join(s.pump_state for s in telemetry_history)
        lines.append(f"  Temperature: {temps}")
        lines.append(f"  Pressure:    {pressures}")
        lines.append(f"  Tank level:  {levels}")
        lines.append(f"  Pump state:  {pumps}")
    else:
        lines.append("Recent telemetry history: none available.")

    lines.append("")
    lines.append(
        "Analyze this alert. Identify plausible causes grounded in the data above, "
        "and recommend concrete investigation steps a human operator should take next."
    )

    return "\n".join(lines)


def analyze_incident(
    client,  # anthropic.Anthropic - typed loosely so tests can pass a fake
    alert: AlertContext,
    asset: AssetContext,
    telemetry_history: list[TelemetrySample],
) -> IncidentAnalysis:
    """
    The one function in this file that talks to Claude. Uses
    structured outputs (output_format=IncidentAnalysis) so the result
    is a validated Pydantic instance, not a text blob we hope is JSON.
    """
    prompt = build_incident_prompt(alert, asset, telemetry_history)

    response = client.messages.parse(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        output_format=IncidentAnalysis,
    )
    return response.parsed_output
