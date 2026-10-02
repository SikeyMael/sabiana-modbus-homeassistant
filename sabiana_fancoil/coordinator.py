\"\"\"Coordinator for a single Sabiana fancoil.

Architecture: ONE shared serial Modbus client for the entire
RS485 bus (created once at the config entry level, the \"hub\"), and ONE
DataUpdateCoordinator for each configured fancoil (a subentry).
Each coordinator, when updating, acquires the shared bus lock,
performs all necessary reads for its own slave, and releases
the lock. This avoids collisions on the bus (RS485 is half-duplex: two
simultaneous requests from different slaves cause errors) while
leaving each fancoil free to fail/update without blocking
the others.
\"\"\"
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CLIMATE, FAN_SPEED, INTER_MESSAGE_DELAY, SENSORS, SWITCHES

_LOGGER = logging.getLogger(__name__)

# \"Base\" polling interval: some registers (hysteresis, hardware model)
# are read less frequently thanks to the scan_interval field
# of individual SensorDef, handled internally below.
DEFAULT_UPDATE_INTERVAL = timedelta(seconds=30)


@dataclass
class ModbusBus:
    \"\"\"Modbus client + lock, shared by all fancoils on the same serial port.\"\"\"

    client: Any  # pymodbus.client.AsyncModbusSerialClient
    lock: asyncio.Lock


class SabianaCoordinator(DataUpdateCoordinator[dict[str, int]]):
    \"\"\"Periodically reads all registers of ONE fancoil (one slave).\"\"\"

    def __init__(self, hass: HomeAssistant, bus: ModbusBus, slave: int, room_name: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f\"Sabiana Fancoil {room_name} (slave {slave})\",
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self._bus = bus
        self.slave = slave
        self.room_name = room_name
        self._cycle_count = 0

    async def _ensure_connected(self) -> None:
        \"\"\"Checks the serial connection and attempts reconnection if necessary.\"\"\"
        if not getattr(self._bus.client, \"connected\", False):
            _LOGGER.warning(\"Modbus client disconnected, attempting bus reconnection...\")
            try:
                await self._bus.client.connect()
            except Exception as err:
                _LOGGER.error(\"Reconnection attempt failed: %s\", err)

    async def _read_holding(self, address: int) -> int:
        \"\"\"Reads a single holding register, serialized on the bus lock.\"\"\"
        async with self._bus.lock:
            await self._ensure_connected()
            result = await self._bus.client.read_holding_registers(
                address=address, count=1, device_id=self.slave
            )
            await asyncio.sleep(INTER_MESSAGE_DELAY)
        if result.isError():
            raise UpdateFailed(
                f\"Modbus error reading address {address} on slave {self.slave}: {result}\"
            )
        value = result.registers[0]
        # Protocol \"sig16\" registers are signed integers: pymodbus
        # always returns a raw uint16, must be reinterpreted manually.
        if value >= 32768:
            value -= 65536
        return value

    async def _write_holding(self, address: int, value: int) -> None:
        async with self._bus.lock:
            await self._ensure_connected()
            result = await self._bus.client.write_register(
                address=address, value=value, device_id=self.slave
            )
            await asyncio.sleep(INTER_MESSAGE_DELAY)
        if result.isError():
            raise UpdateFailed(
                f\"Modbus error writing {value} to address {address}, slave {self.slave}: {result}\"
            )

    async def async_write_register(self, address: int, value: int) -> None:
        \"\"\"Public API used by entities (switch/select/climate) for writing.\"\"\"
        await self._write_holding(address, value)
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, int]:
        self._cycle_count += 1
        data: dict[str, int] = {}

        for sensor in SENSORS:
            # Respect the \"slow\" scan_interval of diagnostic registers,
            # without creating a separate coordinator for each.
            cycles_needed = max(1, sensor.scan_interval // DEFAULT_UPDATE_INTERVAL.seconds)
            if self._cycle_count == 1 or self._cycle_count % cycles_needed == 0:
                data[sensor.key] = await self._read_holding(sensor.address)
            elif self.data and sensor.key in self.data:
                data[sensor.key] = self.data[sensor.key]

        for switch in SWITCHES:
            addr = switch.verify_address or switch.write_address
            data[switch.key] = await self._read_holding(addr)

        data[\"climate_current_temp\"] = await self._read_holding(CLIMATE.current_temp_address)
        data[\"climate_season\"] = await self._read_holding(CLIMATE.season_state_address)
        data[\"climate_setpoint_estate\"] = await self._read_holding(CLIMATE.setpoint_estate_address)
        data[\"climate_setpoint_inverno\"] = await self._read_holding(CLIMATE.setpoint_inverno_address)
        data[\"climate_power\"] = await self._read_holding(CLIMATE.power_state_address)

        data[\"fan_auto\"] = await self._read_holding(FAN_SPEED.auto_state_address)
        data[\"fan_min\"] = await self._read_holding(FAN_SPEED.min_state_address)
        data[\"fan_med\"] = await self._read_holding(FAN_SPEED.med_state_address)
        data[\"fan_max\"] = await self._read_holding(FAN_SPEED.max_state_address)

        return data
