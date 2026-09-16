"""Switch Sabiana Fancoil, generati dal catalogo centrale SWITCHES."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SWITCHES, SwitchDef
from .coordinator import SabianaCoordinator
from .entity import SabianaEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinators: dict[str, SabianaCoordinator] = entry.runtime_data["coordinators"]
    for subentry_id, coordinator in coordinators.items():
        entities = [
            SabianaSwitch(coordinator, subentry_id, definition) for definition in SWITCHES
        ]
        async_add_entities(entities, config_subentry_id=subentry_id)


class SabianaSwitch(SabianaEntity, SwitchEntity):
    def __init__(
        self, coordinator: SabianaCoordinator, subentry_id: str, definition: SwitchDef
    ) -> None:
        super().__init__(coordinator, subentry_id)
        self._definition = definition
        self._attr_unique_id = f"{subentry_id}_{definition.key}"
        self._attr_name = definition.name
        self._attr_entity_category = definition.entity_category

    @property
    def is_on(self) -> bool | None:
        raw = self.coordinator.data.get(self._definition.key)
        if raw is None:
            return None
        return raw == self._definition.command_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_write_register(
            self._definition.write_address, self._definition.command_on
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_write_register(
            self._definition.write_address, self._definition.command_off
        )
