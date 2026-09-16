"""Select Sabiana Fancoil: velocità ventola e modalità Estate/Inverno."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CLIMATE, FAN_SPEED
from .coordinator import SabianaCoordinator
from .entity import SabianaEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinators: dict[str, SabianaCoordinator] = entry.runtime_data["coordinators"]
    for subentry_id, coordinator in coordinators.items():
        async_add_entities(
            [
                FanSpeedSelect(coordinator, subentry_id),
                SeasonSelect(coordinator, subentry_id),
            ],
            config_subentry_id=subentry_id,
        )


class FanSpeedSelect(SabianaEntity, SelectEntity):
    _attr_unique_id_suffix = "fan_speed"
    _attr_name = "Velocità Ventola"
    _attr_options = list(FAN_SPEED.options)

    def __init__(self, coordinator: SabianaCoordinator, subentry_id: str) -> None:
        super().__init__(coordinator, subentry_id)
        self._attr_unique_id = f"{subentry_id}_fan_speed"

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data
        if data.get("fan_auto") == 1:
            return "Automatico"
        if data.get("fan_min") == 1:
            return "Minimo"
        if data.get("fan_med") == 1:
            return "Medio"
        if data.get("fan_max") == 1:
            return "Massimo"
        return None

    async def async_select_option(self, option: str) -> None:
        value = {"Automatico": 0, "Minimo": 1, "Medio": 2, "Massimo": 3}[option]
        await self.coordinator.async_write_register(FAN_SPEED.command_address, value)


class SeasonSelect(SabianaEntity, SelectEntity):
    _attr_name = "Modalità"
    _attr_options = ["Estate", "Inverno"]

    def __init__(self, coordinator: SabianaCoordinator, subentry_id: str) -> None:
        super().__init__(coordinator, subentry_id)
        self._attr_unique_id = f"{subentry_id}_modalita"

    @property
    def current_option(self) -> str | None:
        season = self.coordinator.data.get("climate_season")
        if season == 0:
            return "Estate"
        if season == 1:
            return "Inverno"
        return None

    async def async_select_option(self, option: str) -> None:
        value = {"Estate": 0, "Inverno": 1}[option]
        await self.coordinator.async_write_register(CLIMATE.mode_write_address, value)
