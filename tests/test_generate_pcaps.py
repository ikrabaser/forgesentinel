"""
Checks the byte-level correctness of network-security/generate_pcaps.py
without needing Docker/Suricata/Zeek at all - a pure Python
regression test for the one piece of custom logic in this milestone
(everything else is off-the-shelf tooling, config, or docs).

Decodes the raw Modbus TCP ADUs the same way a real Modbus master
would, and cross-checks register values against the actual
mapping.decode_scaled()/decode_pump_state() functions the simulator
uses - so if mapping.py's scaling or addresses ever change, this test
would catch the pcaps silently going stale/unrealistic.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from scapy.all import Raw, rdpcap

from simulator.modbus import mapping
from simulator.process.pump import PumpState

REPO_ROOT = Path(__file__).parent.parent
PCAPS_DIR = REPO_ROOT / "network-security" / "pcaps"


def _load_generator_module():
    spec = importlib.util.spec_from_file_location(
        "generate_pcaps", REPO_ROOT / "network-security" / "generate_pcaps.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_pcaps"] = module
    spec.loader.exec_module(module)
    return module


def _adus(pcap_path: Path) -> list[bytes]:
    """Every TCP segment's raw payload, in order - each one is one Modbus TCP ADU."""
    packets = rdpcap(str(pcap_path))
    return [bytes(p[Raw].load) for p in packets if p.haslayer(Raw)]


def _parse_mbap(adu: bytes) -> tuple[int, int, int, bytes]:
    transaction_id = int.from_bytes(adu[0:2], "big")
    protocol_id = int.from_bytes(adu[2:4], "big")
    unit_id = adu[6]
    pdu = adu[7:]
    return transaction_id, protocol_id, unit_id, pdu


def test_generator_produces_both_pcap_files(tmp_path, monkeypatch):
    module = _load_generator_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path)
    tmp_path.mkdir(exist_ok=True)

    module.build_benign_pcap()
    module.build_malicious_write_pcap()

    assert (tmp_path / "benign-traffic.pcap").exists()
    assert (tmp_path / "malicious-write.pcap").exists()


def test_benign_pcap_matches_a_real_collector_poll(tmp_path, monkeypatch):
    module = _load_generator_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path)
    tmp_path.mkdir(exist_ok=True)
    module.build_benign_pcap()

    adus = _adus(tmp_path / "benign-traffic.pcap")
    assert len(adus) == 4  # read-HR request/response, read-coils request/response

    _, protocol_id, unit_id, request_pdu = _parse_mbap(adus[0])
    assert protocol_id == 0
    assert unit_id == 1
    assert request_pdu[0] == 0x03  # read holding registers
    assert int.from_bytes(request_pdu[1:3], "big") == mapping.HR_TEMPERATURE  # starts at register 0
    assert int.from_bytes(request_pdu[3:5], "big") == mapping.HOLDING_REGISTER_COUNT

    _, _, _, response_pdu = _parse_mbap(adus[1])
    byte_count = response_pdu[1]
    values = [
        int.from_bytes(response_pdu[2 + i : 4 + i], "big") for i in range(0, byte_count, 2)
    ]
    assert mapping.decode_scaled(values[mapping.HR_TEMPERATURE]) == 87.62
    assert mapping.decode_scaled(values[mapping.HR_PRESSURE]) == 2.10
    assert mapping.decode_scaled(values[mapping.HR_TANK_LEVEL]) == 45.5
    assert mapping.decode_pump_state(values[mapping.HR_PUMP_STATE]) == PumpState.ON

    _, _, _, coil_request_pdu = _parse_mbap(adus[2])
    assert coil_request_pdu[0] == 0x01  # read coils
    assert int.from_bytes(coil_request_pdu[1:3], "big") == mapping.COIL_COOLING_ACTIVE

    _, _, _, coil_response_pdu = _parse_mbap(adus[3])
    coil_byte = coil_response_pdu[2]
    assert (coil_byte >> mapping.COIL_COOLING_ACTIVE) & 1 == 0  # cooling off
    assert (coil_byte >> mapping.COIL_INLET_OPEN) & 1 == 1  # inlet open


def test_malicious_pcap_contains_writes_no_legitimate_client_would_send(tmp_path, monkeypatch):
    module = _load_generator_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path)
    tmp_path.mkdir(exist_ok=True)
    module.build_malicious_write_pcap()

    adus = _adus(tmp_path / "malicious-write.pcap")
    assert len(adus) == 4  # write-single request/response, write-multiple request/response

    _, _, unit_id, write_single_pdu = _parse_mbap(adus[0])
    assert unit_id == 1
    assert write_single_pdu[0] == 0x06  # write single register
    assert int.from_bytes(write_single_pdu[1:3], "big") == mapping.HR_PUMP_STATE
    assert int.from_bytes(write_single_pdu[3:5], "big") == mapping.encode_pump_state(PumpState.OFF)

    _, _, _, write_multi_pdu = _parse_mbap(adus[2])
    assert write_multi_pdu[0] == 0x10  # write multiple registers
    assert int.from_bytes(write_multi_pdu[1:3], "big") == mapping.HR_TEMPERATURE
    assert int.from_bytes(write_multi_pdu[3:5], "big") == 2  # overwrites temperature + pressure
