"""Entità base comune a sensor/switch/select/climate."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SabianaCoordinator


class SabianaEntity(CoordinatorEntity[SabianaCoordinator]):
    """Base: raggruppa ogni entità sotto un dispositivo 'Fancoil <stanza>'."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SabianaCoordinator, subentry_id: str) -> None:
        super().__init__(coordinator)
        self._subentry_id = subentry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=f"Fancoil {coordinator.room_name}",
            manufacturer="Sabiana",
            model="Fancoil (Cassette/FanCoil serie MB EXT)",
        )
