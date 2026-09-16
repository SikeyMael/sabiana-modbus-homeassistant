"""Coordinator per un singolo fancoil Sabiana.

Architettura scelta: UN client Modbus seriale condiviso per l'intero
bus RS485 (creato una volta a livello di config entry, il "hub"), e UN
DataUpdateCoordinator per ciascun fancoil configurato (una subentry).
Ogni coordinator, quando aggiorna, acquisisce il lock condiviso del
bus, esegue tutte le letture necessarie per il proprio slave e rilascia
il lock. Questo evita collisioni sul bus (RS485 è half-duplex: due
richieste in contemporanea da slave diversi lo mandano in errore) pur
lasciando ogni fancoil libero di fallire/aggiornarsi senza bloccare
gli altri.
"""
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

# Intervallo di polling "base": alcuni registri (isteresi, modello
# hardware) vengono comunque letti più di rado grazie al campo
# scan_interval del singolo SensorDef, gestito internamente qui sotto.
DEFAULT_UPDATE_INTERVAL = timedelta(seconds=30)


@dataclass
class ModbusBus:
    """Client Modbus + lock, condivisi da tutti i fancoil sulla stessa porta seriale."""

    client: Any  # pymodbus.client.AsyncModbusSerialClient
    lock: asyncio.Lock


class SabianaCoordinator(DataUpdateCoordinator[dict[str, int]]):
    """Legge periodicamente tutti i registri di UN fancoil (uno slave)."""

    def __init__(self, hass: HomeAssistant, bus: ModbusBus, slave: int, room_name: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"Sabiana Fancoil {room_name} (slave {slave})",
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self._bus = bus
        self.slave = slave
        self.room_name = room_name
        self._cycle_count = 0

    async def _read_holding(self, address: int) -> int:
        """Legge un singolo holding register, serializzato sul lock del bus."""
        async with self._bus.lock:
            result = await self._bus.client.read_holding_registers(
                address=address, count=1, device_id=self.slave
            )
            await asyncio.sleep(INTER_MESSAGE_DELAY)
        if result.isError():
            raise UpdateFailed(
                f"Errore Modbus leggendo indirizzo {address} su slave {self.slave}: {result}"
            )
        value = result.registers[0]
        # I registri "sig16" del protocollo sono interi con segno: pymodbus
        # restituisce sempre un uint16 grezzo, va reinterpretato manualmente.
        if value >= 32768:
            value -= 65536
        return value

    async def _write_holding(self, address: int, value: int) -> None:
        async with self._bus.lock:
            result = await self._bus.client.write_register(
                address=address, value=value, device_id=self.slave
            )
            await asyncio.sleep(INTER_MESSAGE_DELAY)
        if result.isError():
            raise UpdateFailed(
                f"Errore Modbus scrivendo {value} su indirizzo {address}, slave {self.slave}: {result}"
            )

    async def async_write_register(self, address: int, value: int) -> None:
        """API pubblica usata dalle entità (switch/select/climate) per scrivere."""
        await self._write_holding(address, value)
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, int]:
        self._cycle_count += 1
        data: dict[str, int] = {}

        for sensor in SENSORS:
            # Rispetta lo scan_interval "lento" dei registri diagnostici,
            # senza per questo creare un coordinator separato per ciascuno.
            cycles_needed = max(1, sensor.scan_interval // DEFAULT_UPDATE_INTERVAL.seconds)
            if self._cycle_count == 1 or self._cycle_count % cycles_needed == 0:
                data[sensor.key] = await self._read_holding(sensor.address)
            elif self.data and sensor.key in self.data:
                data[sensor.key] = self.data[sensor.key]

        for switch in SWITCHES:
            addr = switch.verify_address or switch.write_address
            data[switch.key] = await self._read_holding(addr)

        data["climate_current_temp"] = await self._read_holding(CLIMATE.current_temp_address)
        data["climate_season"] = await self._read_holding(CLIMATE.season_state_address)
        data["climate_setpoint_estate"] = await self._read_holding(CLIMATE.setpoint_estate_address)
        data["climate_setpoint_inverno"] = await self._read_holding(CLIMATE.setpoint_inverno_address)
        data["climate_power"] = await self._read_holding(CLIMATE.power_state_address)

        data["fan_auto"] = await self._read_holding(FAN_SPEED.auto_state_address)
        data["fan_min"] = await self._read_holding(FAN_SPEED.min_state_address)
        data["fan_med"] = await self._read_holding(FAN_SPEED.med_state_address)
        data["fan_max"] = await self._read_holding(FAN_SPEED.max_state_address)

        return data
