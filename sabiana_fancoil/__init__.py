"""Integrazione Sabiana Fancoil.

Un config entry = un bus RS485 (una porta seriale, un client Modbus
condiviso). Ogni fancoil collegato al bus è una config subentry
("fancoil"), aggiunta dall'utente inserendo solo il numero di slave e
un nome stanza. Ad ogni subentry corrisponde un dispositivo HA e un
SabianaCoordinator dedicato (vedi coordinator.py).
"""
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
    """Crea il client Modbus condiviso e un coordinator per ogni fancoil già aggiunto."""
    # Import qui, non in cima al file: pymodbus viene installato da HA solo
    # dopo aver letto "requirements" dal manifest, al primo avvio dopo
    # l'installazione della custom integration.
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
            f"Impossibile aprire la porta seriale {entry.data[CONF_PORT]} per il bus Sabiana"
        )

    bus = ModbusBus(client=client, lock=asyncio.Lock())

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

    entry.runtime_data = {"bus": bus, "coordinators": coordinators}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Se l'utente aggiunge o rimuove un fancoil dall'interfaccia, la cosa
    # più semplice e sicura in questa prima versione è ricaricare l'intero
    # config entry: il bus viene rimontato e i coordinator ricreati per
    # tutte le subentry correnti. Comporta una breve interruzione di TUTTI
    # i fancoil quando se ne aggiunge uno nuovo, accettabile per un'operazione
    # rara come "aggiungi un fancoil".
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        bus: ModbusBus = entry.runtime_data["bus"]
        bus.client.close()
    return unloaded
