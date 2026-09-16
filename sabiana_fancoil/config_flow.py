"""Config flow per Sabiana Fancoil."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_PORT, CONF_ROOM_NAME, CONF_SLAVE, DOMAIN, SUBENTRY_TYPE_FANCOIL


class SabianaFancoilConfigFlow(ConfigFlow, domain=DOMAIN):
    """Flow per il bus/hub Sabiana (una porta seriale)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_PORT])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Sabiana ({user_input[CONF_PORT]})",
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_PORT): selector.TextSelector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_TYPE_FANCOIL: FancoilSubentryFlowHandler}


class FancoilSubentryFlowHandler(ConfigSubentryFlow):
    """Sotto-flow 'Aggiungi fancoil': slave + nome stanza, nient'altro."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            slave = user_input[CONF_SLAVE]
            parent_entry = self._get_entry()
            already_used = {
                sub.data[CONF_SLAVE] for sub in parent_entry.subentries.values()
            }
            if slave in already_used:
                errors[CONF_SLAVE] = "slave_already_used"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_ROOM_NAME],
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_ROOM_NAME): selector.TextSelector(),
                vol.Required(CONF_SLAVE): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=60, mode="box")
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
