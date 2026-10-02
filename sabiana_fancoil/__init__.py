\"\"\"Sabiana Fancoil integration.

A config entry = an RS485 bus (a serial port, a shared Modbus client).
Each fancoil connected to the bus is a config subentry (\"fancoil\"),
added by the user by entering only the slave number and a room name.
Each subentry corresponds to an HA device and a dedicated SabianaCoordinator
(see coordinator.py).
\"\"\"
from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_PORT,
    CONF_ROOM_NAME,
    CONF_SLAVE,
    DOMAIN,
    SERIAL_BAUDRATE,
    SERIAL_BYTESIZE,
    SERIAL_PARITY,
    SERIAL_STOPBITS,
    SUBENTRY_TYPE_FANCOIL,
)
from .coordinator import ModbusBus, SabianaCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.CLIMATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    \"\"\"Create the shared Modbus client and a coordinator for each added fancoil.\"\"\"
    # Imported here, not at the top of the file: pymodbus is installed by HA only
    # after reading \"requirements\" from the manifest, on the first start after
    # installing the custom integration.
    from pymodbus.client import AsyncModbusSerialClient

    client = AsyncModbusSerialClient(
        entry.data[CONF_PORT],
        baudrate=SERIAL_BAUDRATE,
        bytesize=SERIAL_BYTESIZE,
        parity=SERIAL_PARITY,
        stopbits=SERIAL_STOPBITS,
        timeout=3,
    )
    connected = await client.connect()
    if not connected:
        raise ConnectionError(
            f\"Unable to open serial port {entry.data[CONF_PORT]} for Sabiana bus\"
        )

    bus = ModbusBus(client=client, lock=asyncio.Lock())

    try:
        coordinators: dict[str, SabianaCoordinator] = {}
        for subentry_id, subentry in entry.subentries.items():
            if subentry.subentry_type != SUBENTRY_TYPE_FANCOIL:
                continue
            coordinator = SabianaCoordinator(
                hass,
                bus,
                slave=subentry.data[CONF_SLAVE],
                room_name=subentry.data[CONF_ROOM_NAME],
            )
            await coordinator.async_config_entry_first_refresh()
            coordinators[subentry_id] = coordinator

        entry.runtime_data = {\"bus\": bus, \"coordinators\": coordinators}

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    except Exception:
        if hasattr(client, \"close\"):
            if asyncio.iscoroutinefunction(client.close):
                await client.close()
            else:
                client.close()
        raise

    # If the user adds or removes a fancoil from the UI, reloading the entire
    # config entry is the simplest and safest approach: the bus is remounted
    # and coordinators are recreated for all current subentries. This causes
    # a brief interruption of ALL fancoils when a new one is added, which is
    # acceptable for a rare operation like \"add a fancoil\".
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and entry.runtime_data and \"bus\" in entry.runtime_data:
        bus: ModbusBus = entry.runtime_data[\"bus\"]
        if bus and bus.client:
            if hasattr(bus.client, \"close\"):
                if asyncio.iscoroutinefunction(bus.client.close):
                    await bus.client.close()
                else:
                    bus.client.close()
    return unloaded
