"""Climate Sabiana Fancoil.

FIX rispetto alla configurazione YAML originale: il registro
target_temp_register non è più fissato staticamente sul setpoint
Estate. Ad ogni lettura/scrittura, l'entità controlla il registro
"Stato Stagione impostata" (0x1013) e usa il setpoint Estate (0x102D)
o Inverno (0x102E) di conseguenza. Non serve più cambiare nulla a
mano quando si passa stagione.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CLIMATE, FAN_SPEED
from .coordinator import SabianaCoordinator
from .entity import SabianaEntity

FAN_MODE_MAP = {"Automatico": 0, "Minimo": 1, "Medio": 2, "Massimo": 3}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinators: dict[str, SabianaCoordinator] = entry.runtime_data["coordinators"]
    for subentry_id, coordinator in coordinators.items():
        async_add_entities([SabianaClimate(coordinator, subentry_id)], config_subentry_id=subentry_id)


class SabianaClimate(SabianaEntity, ClimateEntity):
    _attr_name = None  # usa il nome del dispositivo (has_entity_name)
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL]
    _attr_fan_modes = list(FAN_MODE_MAP.keys())
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_min_temp = CLIMATE.min_temp
    _attr_max_temp = CLIMATE.max_temp
    _attr_target_temperature_step = CLIMATE.temp_step

    def __init__(self, coordinator: SabianaCoordinator, subentry_id: str) -> None:
        super().__init__(coordinator, subentry_id)
        self._attr_unique_id = f"{subentry_id}_climate"

    def _is_winter(self) -> bool:
        return self.coordinator.data.get("climate_season") == 1

    @property
    def current_temperature(self) -> float | None:
        raw = self.coordinator.data.get("climate_current_temp")
        return None if raw is None else raw / 10

    @property
    def target_temperature(self) -> float | None:
        key = "climate_setpoint_inverno" if self._is_winter() else "climate_setpoint_estate"
        raw = self.coordinator.data.get(key)
        return None if raw is None else raw / 10

    @property
    def hvac_mode(self) -> HVACMode:
        if self.coordinator.data.get("climate_power") != 1:
            return HVACMode.OFF
        return HVACMode.HEAT if self._is_winter() else HVACMode.COOL

    @property
    def fan_mode(self) -> str | None:
        data = self.coordinator.data
        for name, value in FAN_MODE_MAP.items():
            key = {0: "fan_auto", 1: "fan_min", 2: "fan_med", 3: "fan_max"}[value]
            if data.get(key) == 1:
                return name
        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        address = (
            CLIMATE.setpoint_inverno_address if self._is_winter() else CLIMATE.setpoint_estate_address
        )
        await self.coordinator.async_write_register(address, round(temperature * 10))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_write_register(CLIMATE.power_write_address, 0)
            return
        mode_value = 1 if hvac_mode == HVACMode.HEAT else 0
        await self.coordinator.async_write_register(CLIMATE.mode_write_address, mode_value)
        await self.coordinator.async_write_register(CLIMATE.power_write_address, 1)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        await self.coordinator.async_write_register(
            FAN_SPEED.command_address, FAN_MODE_MAP[fan_mode]
        )
