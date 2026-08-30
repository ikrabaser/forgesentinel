"""
Generates synthetic Modbus TCP .pcap files for Suricata/Zeek to
analyze offline.

Why synthetic/offline PCAPs instead of live-capturing the collector's
real traffic:
    Suricata and Zeek run here as Docker containers. On Windows,
    Docker Desktop containers cannot see host loopback traffic (there
    is no Linux-style "host networking" on Windows, and the
    collector/simulator talk over 127.0.0.1) - live-sniffing our own
    Modbus traffic from inside a container is not practical on this
    platform. Working from a captured .pcap file instead is not a
    workaround or a downgrade, though: it's how a huge amount of real
    security analysis actually happens (an analyst is handed a
    capture from an incident, not a live tap), so this is a legitimate
    and common workflow to practice, not a simulation of one.

Byte layout matches simulator/modbus/mapping.py exactly (unit id 1,
holding registers 0-3 = temperature/pressure/tank_level/pump_state,
coils 0-1 = cooling_active/inlet_open, SCALE=100) so the "benign"
capture is a faithful replay of what the real collector/simulator
exchange, not an invented approximation.
"""

from __future__ import annotations

from pathlib import Path

from scapy.all import IP, TCP, Ether, Raw, wrpcap

OUT_DIR = Path(__file__).parent / "pcaps"
MODBUS_PORT = 5020  # this lab's port - the standard is 502, ours differs (see Milestone 2)

PLC_IP = "10.10.0.10"
COLLECTOR_IP = "10.10.0.20"
ATTACKER_IP = "10.10.0.99"


def _tcp_stream(src_ip: str, dst_ip: str, sport: int, dport: int, exchanges: list[bytes]) -> list:
    """
    Build a minimal but real TCP stream: SYN/SYN-ACK/ACK handshake,
    then each entry in `exchanges` alternates client->server,
    server->client as a PSH/ACK segment carrying one Modbus TCP ADU.
    """
    packets = []
    seq_c, seq_s = 1000, 5000

    packets.append(Ether() / IP(src=src_ip, dst=dst_ip) / TCP(sport=sport, dport=dport, flags="S", seq=seq_c))
    seq_c += 1
    packets.append(
        Ether() / IP(src=dst_ip, dst=src_ip) / TCP(sport=dport, dport=sport, flags="SA", seq=seq_s, ack=seq_c)
    )
    seq_s += 1
    packets.append(Ether() / IP(src=src_ip, dst=dst_ip) / TCP(sport=sport, dport=dport, flags="A", seq=seq_c, ack=seq_s))

    for i, adu in enumerate(exchanges):
        is_request = i % 2 == 0
        if is_request:
            packets.append(
                Ether()
                / IP(src=src_ip, dst=dst_ip)
                / TCP(sport=sport, dport=dport, flags="PA", seq=seq_c, ack=seq_s)
                / Raw(load=adu)
            )
            seq_c += len(adu)
        else:
            packets.append(
                Ether()
                / IP(src=dst_ip, dst=src_ip)
                / TCP(sport=dport, dport=sport, flags="PA", seq=seq_s, ack=seq_c)
                / Raw(load=adu)
            )
            seq_s += len(adu)

    return packets


def _mbap(transaction_id: int, unit_id: int, pdu: bytes) -> bytes:
    """Modbus TCP framing: transaction id, protocol id (always 0), length, unit id, then the PDU."""
    length = 1 + len(pdu)  # unit id byte + PDU
    return transaction_id.to_bytes(2, "big") + b"\x00\x00" + length.to_bytes(2, "big") + bytes([unit_id]) + pdu


def build_benign_pcap() -> None:
    """
    One real collector poll cycle: read holding registers 0-3
    (temperature=87.62C, pressure=2.10bar, tank_level=45.5%,
    pump_state=ON), then read coils 0-1 (cooling=off, inlet=open) -
    exactly the two calls collector/modbus_client.py makes every poll.
    """
    read_hr_request = _mbap(1, 1, bytes([0x03, 0x00, 0x00, 0x00, 0x04]))
    hr_values = [8762, 210, 4550, 1]  # temp, pressure, tank_level (all x100), pump_state=ON
    hr_payload = b"".join(v.to_bytes(2, "big") for v in hr_values)
    read_hr_response = _mbap(1, 1, bytes([0x03, len(hr_payload)]) + hr_payload)

    read_coils_request = _mbap(2, 1, bytes([0x01, 0x00, 0x00, 0x00, 0x02]))
    # bit0=cooling_active(0), bit1=inlet_open(1) -> 0b10 = 0x02
    read_coils_response = _mbap(2, 1, bytes([0x01, 0x01, 0x02]))

    packets = _tcp_stream(
        COLLECTOR_IP,
        PLC_IP,
        sport=51000,
        dport=MODBUS_PORT,
        exchanges=[read_hr_request, read_hr_response, read_coils_request, read_coils_response],
    )
    wrpcap(str(OUT_DIR / "benign-traffic.pcap"), packets)


def build_malicious_write_pcap() -> None:
    """
    An external client (not the collector - a different source IP)
    directly writing Modbus registers: exactly the attack Rule 005's
    docstring (detection/rules/suspicious_configuration_change.py)
    describes as undetectable at the application layer with what we
    have today, because Modbus itself has no authentication - ANY
    client reaching the port can do this, which is precisely why a
    network-layer rule (not a value-based one) is the right tool here.

    Two attacks in one capture:
      1. FC06 write single register: force HR_PUMP_STATE (register 3)
         to 0 (OFF) - directly overriding the PLC's own control logic
         from outside it entirely.
      2. FC16 write multiple registers: overwrite HR_TEMPERATURE and
         HR_PRESSURE (registers 0-1) with 0 - spoofing sensor readings,
         the same "hide the real value" pattern used in real ICS
         attacks (e.g. Stuxnet's PLC value spoofing).
    """
    write_single_request = _mbap(10, 1, bytes([0x06, 0x00, 0x03, 0x00, 0x00]))
    write_single_response = _mbap(10, 1, bytes([0x06, 0x00, 0x03, 0x00, 0x00]))  # FC06 echoes the request

    write_multi_payload = (0).to_bytes(2, "big") + (0).to_bytes(2, "big")
    write_multi_request = _mbap(
        11, 1, bytes([0x10, 0x00, 0x00, 0x00, 0x02, len(write_multi_payload)]) + write_multi_payload
    )
    write_multi_response = _mbap(11, 1, bytes([0x10, 0x00, 0x00, 0x00, 0x02]))

    packets = _tcp_stream(
        ATTACKER_IP,
        PLC_IP,
        sport=45000,
        dport=MODBUS_PORT,
        exchanges=[
            write_single_request,
            write_single_response,
            write_multi_request,
            write_multi_response,
        ],
    )
    wrpcap(str(OUT_DIR / "malicious-write.pcap"), packets)


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    build_benign_pcap()
    build_malicious_write_pcap()
    print(f"Wrote {OUT_DIR / 'benign-traffic.pcap'}")
    print(f"Wrote {OUT_DIR / 'malicious-write.pcap'}")
