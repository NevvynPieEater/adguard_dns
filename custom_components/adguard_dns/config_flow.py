from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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
    """Handle a config flow for AdGuard DNS."""

    VERSION = 1

    def __init__(self) -> None:
        self._user_input: dict[str, Any] = {}
        self._devices: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the first step: API key + mode."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = AdGuardDnsClient(session, user_input[CONF_API_KEY])

            try:
                devices = await api.async_test_auth()
            except AdGuardDnsAuthError:
                errors["base"] = "invalid_auth"
            except AdGuardDnsApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during AdGuard DNS auth")
                errors["base"] = "unknown"
            else:
                self._user_input = user_input
                self._devices = devices

                if user_input[CONF_MODE] == MODE_ALL_DEVICES:
                    return self.async_create_entry(
                        title="AdGuard DNS",
                        data={
                            CONF_API_KEY: user_input[CONF_API_KEY],
                            CONF_MODE: MODE_ALL_DEVICES,
                        },
                    )

                return await self.async_step_device()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Required(CONF_MODE, default=MODE_ALL_DEVICES): vol.In(
                    [MODE_ALL_DEVICES, MODE_SINGLE_DEVICE]
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the device selection step for single-device mode."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_device_id = user_input[CONF_DEVICE_ID]

            selected = next(
                (d for d in self._devices if d.get("id") == selected_device_id),
                None,
            )

            title = (
                f"AdGuard DNS ({selected.get('name', selected_device_id)})"
                if selected
                else "AdGuard DNS"
            )

            return self.async_create_entry(
                title=title,
                data={
                    CONF_API_KEY: self._user_input[CONF_API_KEY],
                    CONF_MODE: MODE_SINGLE_DEVICE,
                    CONF_DEVICE_ID: selected_device_id,
                },
            )

        device_options: dict[str, str] = {}
        for index, device in enumerate(self._devices):
            device_id = device.get("id")
            if not device_id:
                continue

            device_name = (
                device.get("name")
                or device.get("hostname")
                or device.get("human_id")
                or f"Device {index + 1}"
            )
            device_options[device_id] = f"{device_name} ({device_id})"

        if not device_options:
            errors["base"] = "no_devices"
            return self.async_show_form(
                step_id="device",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE_ID): vol.In(device_options),
            }
        )

        return self.async_show_form(
            step_id="device",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow."""
        return AdGuardDnsOptionsFlow(config_entry)


class AdGuardDnsOptionsFlow(config_entries.OptionsFlow):
    """AdGuard DNS options flow."""

    def __init__(self, config_entry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """No options yet."""
        return self.async_create_entry(title="", data={})