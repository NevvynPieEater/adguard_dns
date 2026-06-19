from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AdGuardDnsApiError
from .const import CONF_DEVICE_ID, CONF_MODE, DOMAIN, MANAGER_KEY, MODE_SINGLE_DEVICE


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime["coordinator"]
    api = runtime["api"]

    devices = coordinator.data.get("devices", [])

    if entry.data.get(CONF_MODE) == MODE_SINGLE_DEVICE:
        wanted = entry.data.get(CONF_DEVICE_ID)
        devices = [d for d in devices if d.get("id") == wanted]

    entities = [
        AdGuardDnsProtectionSwitch(hass, coordinator, api, entry.entry_id, device)
        for device in devices
        if device.get("id")
    ]

    async_add_entities(entities)


class AdGuardDnsProtectionSwitch(CoordinatorEntity, SwitchEntity):
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_has_entity_name = True

    def __init__(
        self,
        hass,
        coordinator,
        api,
        entry_id: str,
        device: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self.hass = hass
        self.api = api
        self.entry_id = entry_id
        self.device_id = device["id"]
        self._fallback_name = device.get("name") or self.device_id
        self._attr_unique_id = f"adguard_dns_{self.device_id}_protection"
        self._attr_name = "Protection"

    @property
    def icon(self):
        return "mdi:shield-check" if self.is_on else "mdi:shield-off"

    @property
    def device_info(self):
        return {
            "identifiers": {("adguard_dns", self.device_id)},
            "name": self._fallback_name,
            "manufacturer": "AdGuard DNS",
            "model": "DNS Device",
        }

    @property
    def available(self) -> bool:
        return self._device_data is not None

    @property
    def _device_data(self) -> dict[str, Any] | None:
        for item in self.coordinator.data.get("devices", []):
            if item.get("id") == self.device_id:
                return item
        return None

    @property
    def is_on(self) -> bool:
        data = self._device_data
        if not data:
            return False
        return self.api.extract_protection_state(data)

    @property
    def extra_state_attributes(self):
        data = self._device_data or {}
        attrs = {
            "device_id": self.device_id,
        }

        for key in ("name", "server_id", "created_at", "updated_at", "auto_device"):
            if key in data:
                attrs[key] = data[key]

        manager = self.hass.data.get(DOMAIN, {}).get(MANAGER_KEY)
        if manager:
            expires = (
                manager._data.get("temporary_disables", {})
                .get(self.entry_id, {})
                .get(self.device_id)
            )
            if expires:
                attrs["temporarily_disabled_until"] = expires

        return attrs

    async def async_turn_on(self, **kwargs):
        try:
            await self.api.async_set_protection(self.device_id, True)

            manager = self.hass.data.get(DOMAIN, {}).get(MANAGER_KEY)
            if manager:
                await manager.async_clear_temporary_disable(self.entry_id, self.device_id)

            await self.coordinator.async_request_refresh()
        except AdGuardDnsApiError as err:
            raise HomeAssistantError(f"Failed to enable protection: {err}") from err

    async def async_turn_off(self, **kwargs):
        try:
            await self.api.async_set_protection(self.device_id, False)

            # Manual off should cancel any pending automatic re-enable schedule
            manager = self.hass.data.get(DOMAIN, {}).get(MANAGER_KEY)
            if manager:
                await manager.async_clear_temporary_disable(self.entry_id, self.device_id)

            await self.coordinator.async_request_refresh()
        except AdGuardDnsApiError as err:
            raise HomeAssistantError(f"Failed to disable protection: {err}") from err