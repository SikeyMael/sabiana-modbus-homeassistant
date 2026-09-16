"""Sensori Sabiana Fancoil, generati dal catalogo centrale SENSORS."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SENSORS, SensorDef
from .coordinator import SabianaCoordinator
from .entity import SabianaEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinators: dict[str, SabianaCoordinator] = entry.runtime_data["coordinators"]
    for subentry_id, coordinator in coordinators.items():
        entities = [
            SabianaSensor(coordinator, subentry_id, definition) for definition in SENSORS
        ]
        async_add_entities(entities, config_subentry_id=subentry_id)


class SabianaSensor(SabianaEntity, SensorEntity):
    def __init__(
        self, coordinator: SabianaCoordinator, subentry_id: str, definition: SensorDef
    ) -> None:
        super().__init__(coordinator, subentry_id)
        self._definition = definition
        self._attr_unique_id = f"{subentry_id}_{definition.key}"
        self._attr_name = definition.name
        self._attr_native_unit_of_measurement = definition.unit
        self._attr_entity_category = definition.entity_category
        self._attr_suggested_display_precision = definition.precision

    @property
    def native_value(self) -> float | int | None:
        raw = self.coordinator.data.get(self._definition.key)
        if raw is None:
            return None
        return round(raw * self._definition.scale, self._definition.precision or 2)
