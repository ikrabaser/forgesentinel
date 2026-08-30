# Milestone 12: Network Security Integration

Two things live here: a script that generates synthetic Modbus TCP
`.pcap` files, and configs that point Suricata/Zeek at them.

## Why synthetic PCAPs, not live capture

Suricata and Zeek run as Docker containers here. On Windows, Docker
Desktop containers cannot see host loopback traffic - there's no
Linux-style host networking, and the collector/simulator talk over
`127.0.0.1:5020`. Live-sniffing our own lab traffic from inside a
container isn't practical on this platform.

Working from a captured `.pcap` instead isn't a downgrade - it's a
completely standard security workflow (an analyst is usually handed a
capture from an incident, not a live tap). `generate_pcaps.py` builds
the ADUs byte-for-byte from `simulator/modbus/mapping.py`'s real
addresses/scaling, so the "benign" capture is a faithful replay of an
actual collector poll, not an invented approximation.

## The attack scenario

Modbus TCP has no authentication (see
`detection/rules/suspicious_configuration_change.py` for the full
reasoning) - any client that reaches the port can send a write
command and our PLC will honor it. `malicious-write.pcap` simulates
exactly that: an external client (not the collector) sending:

- **FC06** (write single register) forcing `HR_PUMP_STATE` to OFF -
  directly overriding the PLC's control logic from outside it.
- **FC16** (write multiple registers) zeroing `HR_TEMPERATURE` and
  `HR_PRESSURE` - spoofing sensor readings, the same "hide the real
  value" pattern real ICS attacks use (e.g. Stuxnet's PLC spoofing).

This is the network-layer detection Rule 005 couldn't be built at the
application layer: at the wire level we don't need to know whether a
value "looks wrong" - the mere presence of a write function code from
any client is itself the anomaly, since nothing in this lab is a
legitimate writer today.

## Run it

```bash
# Git Bash
python -m pip install -r requirements.txt   # scapy, if not already installed
python network-security/generate_pcaps.py

docker compose --profile analysis run --rm suricata
cat network-security/suricata/logs/fast.log

docker compose --profile analysis run --rm zeek
cat network-security/zeek/logs/modbus.log
```

Expected `fast.log`: 4 alerts (write access, FC06, FC16 x1 generic +
1 specific each) - all from `10.10.0.99` (the "attacker"), none from
`10.10.0.20` (the collector). Re-run Suricata against
`benign-traffic.pcap` (swap the `-r` path via `docker compose
--profile analysis run --rm --entrypoint "" suricata suricata -r
/pcaps/benign-traffic.pcap ...`, same flags as `docker-compose.yml`'s
entrypoint) and confirm zero alerts - a rule that never fires on real
traffic is as important to verify as one that fires on an attack.

Expected `modbus.log`: 4 rows, `WRITE_SINGLE_REGISTER` and
`WRITE_MULTIPLE_REGISTERS`, each REQ/RESP, from `10.10.0.99:45000` to
`10.10.0.10:5020` - Zeek's passive, no-rules-needed record of exactly
what happened, complementing Suricata's active alerting.

## Wireshark (manual inspection)

Not something to script - open either `.pcap` in Wireshark directly
(`network-security/pcaps/malicious-write.pcap`) and:

1. Apply the display filter `tcp.port == 5020` to isolate this lab's
   Modbus traffic from anything else in a real capture.
2. If Wireshark doesn't recognize it as Modbus automatically
   (its default Modbus port is 502, ours is 5020): right-click a
   packet -> **Decode As...** -> set port 5020 to protocol
   `Modbus/TCP`.
3. Look at the decoded **Function Code** field per packet: `6` = Write
   Single Register, `16` = Write Multiple Registers - the exact
   pattern the Suricata rules and Zeek's `modbus.log` both flagged.
