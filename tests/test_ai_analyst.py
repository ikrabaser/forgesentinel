from datetime import datetime, timezone

from detection.ai_analyst import (
    AlertContext,
    AssetContext,
    TelemetrySample,
    build_incident_prompt,
)


def _alert(**overrides) -> AlertContext:
    defaults = dict(
        rule_id="RULE-001",
        severity="HIGH",
        title="High temperature",
        description="Temperature 94.3C exceeds the 90.0C safe threshold.",
        status="OPEN",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return AlertContext(**defaults)


def _asset(**overrides) -> AssetContext:
    defaults = dict(asset_code="PLC-001", asset_type="PLC", status="ONLINE")
    defaults.update(overrides)
    return AssetContext(**defaults)


def _sample(**overrides) -> TelemetrySample:
    defaults = dict(
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        temperature=72.0,
        pressure=2.0,
        tank_level_percent=50.0,
        pump_state="ON",
        cooling_active=False,
        inlet_open=True,
    )
    defaults.update(overrides)
    return TelemetrySample(**defaults)


def test_prompt_includes_alert_and_asset_details():
    prompt = build_incident_prompt(_alert(), _asset(), [])

    assert "PLC-001" in prompt
    assert "RULE-001" in prompt
    assert "High temperature" in prompt
    assert "HIGH" in prompt
    assert "94.3C exceeds the 90.0C safe threshold" in prompt


def test_prompt_handles_empty_telemetry_history():
    prompt = build_incident_prompt(_alert(), _asset(), [])

    assert "none available" in prompt.lower()


def test_prompt_renders_telemetry_trend_oldest_first():
    history = [
        _sample(temperature=72.0, pressure=1.8, tank_level_percent=40.0, pump_state="OFF"),
        _sample(temperature=78.0, pressure=1.9, tank_level_percent=45.0, pump_state="OFF"),
        _sample(temperature=91.0, pressure=2.1, tank_level_percent=52.0, pump_state="ON"),
    ]
    prompt = build_incident_prompt(_alert(), _asset(), history)

    assert "72.0C -> 78.0C -> 91.0C" in prompt
    assert "1.80bar -> 1.90bar -> 2.10bar" in prompt
    assert "40.0% -> 45.0% -> 52.0%" in prompt
    assert "OFF -> OFF -> ON" in prompt


def test_module_has_no_control_capability_by_construction():
    """
    Architectural guarantee, not just a prompting convention: this
    module must not import anything that could write to the plant
    (simulator/, the Modbus client, the MQTT publisher). If someone
    later adds such an import, this test catches it - "AI may only
    analyze/explain/recommend" should be enforced by what code CAN
    run, not only by what the system prompt asks it not to do.
    """
    import detection.ai_analyst as module

    source = open(module.__file__, encoding="utf-8").read()
    assert "import simulator" not in source
    assert "from simulator" not in source
    assert "ModbusPLCClient" not in source
    assert "MqttPublisher" not in source
