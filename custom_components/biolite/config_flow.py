"""Config flow for BioLite Backup."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BioliteApiClient, BioliteApiError, BioliteAuthError
from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class BioliteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BioLite Backup."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = BioliteApiClient(session, user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            try:
                await client._login()  # noqa: SLF001 -- validating credentials only
                node_id = await client.async_get_node_id()
            except BioliteAuthError:
                errors["base"] = "invalid_auth"
            except (BioliteApiError, HomeAssistantError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(node_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )
