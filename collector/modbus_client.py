"""
ModbusPLCClient: thin wrapper around pymodbus's synchronous TCP client.

Real-world analogy:
    This is the actual network-facing piece of the collector - the
    part that would, in a real deployment, be pointed at a real PLC's
    IP address. Everything here only knows about "connect / read
    registers / read coils / disconnect" - it has zero knowledge of
    what temperature, pressure, or pump state even mean. That
    knowledge lives in collector/telemetry.py, one layer up.

Why synchronous (not async, unlike the Modbus *server* in Milestone 2):
    The server had to be async because it runs a background updater
    loop *concurrently* with answering client requests, in one
    process. The collector is a simple, independent polling loop -
    connect, read, sleep, repeat - with nothing else it needs to do
    concurrently, so a synchronous client keeps the code simpler
    without giving anything up.

Error handling: real networks fail. A cable gets unplugged, a PLC
reboots, a firewall rule changes. This wrapper never lets a connection
problem raise out into the collector's main loop uncaught - it
surfaces failures as `None` return values so the caller can decide
what "no data this poll" means (later: this is exactly the raw signal
Rule 004, DEVICE_OFFLINE, will be built on).
"""

from __future__ import annotations

import logging

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from simulator.modbus import mapping

logger = logging.getLogger("forgesentinel.collector.modbus_client")


class ModbusPLCClient:
    def __init__(self, host: str, port: int, unit_id: int = 1) -> None:
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self._client = ModbusTcpClient(host, port=port)

    def connect(self) -> bool:
        return self._client.connect()

    def close(self) -> None:
        self._client.close()

    def read_raw(self) -> tuple[list[int], list[bool]] | None:
        """
        Read the full holding-register and coil block in one poll.
        Returns None (rather than raising) on any Modbus-level or
        connection-level failure, so a single bad poll doesn't crash
        the collector loop.
        """
        try:
            hr_result = self._client.read_holding_registers(
                address=0, count=mapping.HOLDING_REGISTER_COUNT, slave=self.unit_id
            )
            if hr_result.isError():
                logger.warning("Modbus error reading holding registers: %s", hr_result)
                return None

            coil_result = self._client.read_coils(
                address=0, count=mapping.COIL_COUNT, slave=self.unit_id
            )
            if coil_result.isError():
                logger.warning("Modbus error reading coils: %s", coil_result)
                return None

            return hr_result.registers, coil_result.bits
        except (ModbusException, OSError) as exc:
            # ModbusException covers pymodbus's own connection/protocol
            # errors; OSError covers raw socket failures (which includes
            # Python's ConnectionError family: refused, reset, aborted).
            logger.warning("Modbus connection error: %s", exc)
            return None
