from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import HomeAssistantError

from .api import AdGuardDnsApiError, AdGuardDnsAuthError, AdGuardDnsClient
from .const import (
    CONF_API_KEY,
    CONF_DEVICE_ID,
    CONF_MODE,
    DOMAIN,
    MODE_ALL_DEVICES,
    MODE_SINGLE_DEVICE,
)

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate invalid auth."""


class AdGuardDnsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._user_input: dict[str, Any] = {}
        self._devices: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                session = async_get_clientsession(self.hass)
                api = AdGuardDnsClient(session, user_input[CONF_API_KEY])
                devices = await api.async_test_auth()

                self._user_input = user_input
                self._devices = devices

                await self.async_set_unique_id(f"adguard_dns_{hash(user_input[CONF_API_KEY])}")
                self._abort_if_unique_id_configured()

                if user_input[CONF_MODE] == MODE_SINGLE_DEVICE:
                    return await self.async_step_device()

                return self.async_create_entry(
                    title="AdGuard DNS",
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_MODE: user_input[CONF_MODE],
                    },
                )

            except AdGuardDnsAuthError:
                errors["base"] = "invalid_auth"
            except AdGuardDnsApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Required(CONF_MODE, default=MODE_ALL_DEVICES): vol.In(
                    [MODE_ALL_DEVICES, MODE_SINGLE_DEVICE]
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_device(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            picked_id = user_input[CONF_DEVICE_ID]
            picked = next((d for d in self._devices if d.get("id") == picked_id), None)
            title = f"AdGuard DNS ({picked.get('name', picked_id)})" if picked else "AdGuard DNS"

            return self.async_create_entry(
                title=title,
                data={
                    CONF_API_KEY: self._user_input[CONF_API_KEY],
                    CONF_MODE: MODE_SINGLE_DEVICE,
                    CONF_DEVICE_ID: picked_id,
                },
            )

        options = {
            d.get("id", f"unknown_{idx}"): d.get("name", d.get("id", f"Device {idx + 1}"))
            for idx, d in enumerate(self._devices)
            if d.get("id")
        }

        if not options:
            errors["base"] = "no_devices"
            return self.async_show_form(
                step_id="device",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE_ID): vol.In(options),
            }
        )

        return self.async_show_form(step_id="device", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AdGuardDnsOptionsFlow(config_entry)


class AdGuardDnsOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        return self.async_create_entry(title="", data={})