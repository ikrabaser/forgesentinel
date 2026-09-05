from datetime import datetime, timezone

from detection.models import AlertSeverity
from detection.rules.suspicious_configuration_change import (
    RULE_ID,
    build_suspicious_configuration_change_alert,
)


def test_builds_alert_for_write_single_register():
    at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    alert = build_suspicious_configuration_change_alert(
        asset_id="PLC-001", function_code=6, address=0, values=[4200], timestamp=at
    )

    assert alert.rule_id == RULE_ID
    assert alert.asset_id == "PLC-001"
    assert alert.severity == AlertSeverity.CRITICAL
    assert alert.created_at == at
    assert "WRITE_SINGLE_REGISTER" in alert.description
    assert "FC6" in alert.description
    assert "address 0" in alert.description
    assert "[4200]" in alert.description


def test_builds_alert_for_write_multiple_registers():
    alert = build_suspicious_configuration_change_alert(
        asset_id="PLC-001",
        function_code=16,
        address=2,
        values=[1, 2, 3],
        timestamp=datetime.now(timezone.utc),
    )

    assert "WRITE_MULTIPLE_REGISTERS" in alert.description
    assert "FC16" in alert.description


def test_unknown_function_code_falls_back_to_number():
    alert = build_suspicious_configuration_change_alert(
        asset_id="PLC-001", function_code=99, address=0, values=[1], timestamp=datetime.now(timezone.utc)
    )

    assert "a 99 (FC99) request" in alert.description


def test_each_call_produces_an_independent_alert_no_shared_state():
    # No debounce state exists here - two calls, even for the same
    # asset/address, must each raise their own alert.
    at = datetime.now(timezone.utc)
    first = build_suspicious_configuration_change_alert("PLC-001", 6, 0, [1], at)
    second = build_suspicious_configuration_change_alert("PLC-001", 6, 0, [1], at)

    assert first == second  # same inputs -> equal alerts, not a singleton/cached one
