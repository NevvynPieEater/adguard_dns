from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    SERVICE_ENABLE_PROTECTION,
    SERVICE_DISABLE_PROTECTION,
    SERVICE_DISABLE_FOR_30_MINUTES,
)

_LOGGER = logging.getLogger(__name__)


class AdGuardDnsServiceManager:
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._store = Store(hass, 1, "adguard_dns_storage")
        self._data = {}

    async def async_load(self):
        self._data = await self._store.async_load() or {}

    async def async_save(self):
        await self._store.async_save(self._data)

    async def async_enable(self, entry_id):
        entry = self.hass.data[DOMAIN][entry_id]
        await entry["client"].async_set_protection(entry["device_id"], True)

    async def async_disable(self, entry_id):
        entry = self.hass.data[DOMAIN][entry_id]
        await entry["client"].async_set_protection(entry["device_id"], False)

    async def async_disable_temporarily(self, entry_id):
        await self.async_disable(entry_id)

    async def async_setup(self):
        async def enable(call: ServiceCall):
            for entry_id in self.hass.data[DOMAIN]:
                await self.async_enable(entry_id)

        async def disable(call: ServiceCall):
            for entry_id in self.hass.data[DOMAIN]:
                await self.async_disable(entry_id)

        async def disable_30(call: ServiceCall):
            for entry_id in self.hass.data[DOMAIN]:
                await self.async_disable_temporarily(entry_id)

        self.hass.services.async_register(DOMAIN, SERVICE_ENABLE_PROTECTION, enable)
        self.hass.services.async_register(DOMAIN, SERVICE_DISABLE_PROTECTION, disable)
        self.hass.services.async_register(DOMAIN, SERVICE_DISABLE_FOR_30_MINUTES, disable_30)


async def async_setup_services(hass: HomeAssistant):
    manager = AdGuardDnsServiceManager(hass)
    await manager.async_load()
    await manager.async_setup()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["manager"] = manager