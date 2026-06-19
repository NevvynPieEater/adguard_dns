from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_DEVICE_ID,
    ATTR_ENTRY_ID,
    CONF_DEVICE_ID,
    CONF_MODE,
    DOMAIN,
    MANAGER_KEY,
    MODE_SINGLE_DEVICE,
    SERVICE_DISABLE_FOR_30_MINUTES,
    SERVICE_DISABLE_PROTECTION,
    SERVICE_ENABLE_PROTECTION,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): str,
        vol.Optional(ATTR_DEVICE_ID): str,
    }
)

DEFAULT_DISABLE_DURATION = timedelta(minutes=30)


class AdGuardDnsServiceManager:
    """Manage AdGuard DNS service actions and timed re-enable state."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] = {"temporary_disables": {}}
        self._unsubs: dict[str, Any] = {}

    async def async_load(self) -> None:
        """Load persisted temporary disable state."""
        data = await self._store.async_load()
        if isinstance(data, dict):
            self._data = data
        self._data.setdefault("temporary_disables", {})

    async def async_save(self) -> None:
        """Persist temporary disable state."""
        await self._store.async_save(self._data)

    def _entry_runtimes(self) -> list[tuple[str, dict[str, Any]]]:
        """Return active runtime entries for this integration."""
        domain_data = self.hass.data.get(DOMAIN, {})
        return [
            (entry_id, runtime)
            for entry_id, runtime in domain_data.items()
            if entry_id != MANAGER_KEY and isinstance(runtime, dict)
        ]

    def _target_entries(self, entry_id: str | None) -> list[tuple[str, dict[str, Any]]]:
        """Filter runtime entries by entry_id if provided."""
        entries = self._entry_runtimes()
        if entry_id:
            return [(eid, runtime) for eid, runtime in entries if eid == entry_id]
        return entries

    async def _resolve_targets(
        self,
        entry_id: str | None,
        device_id: str | None,
    ) -> list[tuple[str, str, Any, Any]]:
        """Resolve target devices across active entries."""
        targets: list[tuple[str, str, Any, Any]] = []

        for eid, runtime in self._target_entries(entry_id):
            coordinator = runtime["coordinator"]
            api = runtime["api"]
            devices = coordinator.data.get("devices", [])

            config_entry = next(
                (ce for ce in self.hass.config_entries.async_entries(DOMAIN) if ce.entry_id == eid),
                None,
            )

            if config_entry is not None and config_entry.data.get(CONF_MODE) == MODE_SINGLE_DEVICE:
                configured_device_id = config_entry.data.get(CONF_DEVICE_ID)
                devices = [d for d in devices if d.get("id") == configured_device_id]

            if device_id:
                devices = [d for d in devices if d.get("id") == device_id]

            for device in devices:
                did = device.get("id")
                if did:
                    targets.append((eid, did, api, coordinator))

        return targets

    def _cancel_schedule(self, entry_id: str, device_id: str) -> None:
        """Cancel an existing scheduled re-enable callback if present."""
        key = f"{entry_id}:{device_id}"
        unsub = self._unsubs.pop(key, None)
        if unsub:
            unsub()

    async def async_clear_temporary_disable(self, entry_id: str, device_id: str) -> None:
        """Clear persisted temporary disable state and any scheduled callback."""
        self._cancel_schedule(entry_id, device_id)

        entry_map = self._data.setdefault("temporary_disables", {}).get(entry_id)
        if isinstance(entry_map, dict) and device_id in entry_map:
            entry_map.pop(device_id, None)
            if not entry_map:
                self._data["temporary_disables"].pop(entry_id, None)
            await self.async_save()

    async def async_enable(self, entry_id: str | None, device_id: str | None) -> None:
        """Enable protection for resolved targets."""
        targets = await self._resolve_targets(entry_id, device_id)

        for eid, did, api, coordinator in targets:
            await api.async_set_protection(did, True)
            await coordinator.async_request_refresh()
            await self.async_clear_temporary_disable(eid, did)

    async def async_disable(self, entry_id: str | None, device_id: str | None) -> None:
        """Disable protection for resolved targets."""
        targets = await self._resolve_targets(entry_id, device_id)

        for eid, did, api, coordinator in targets:
            await api.async_set_protection(did, False)
            await coordinator.async_request_refresh()
            await self.async_clear_temporary_disable(eid, did)

    def _schedule_reenable(self, entry_id: str, device_id: str, when_utc) -> None:
        """Schedule a re-enable at a specific UTC datetime."""
        key = f"{entry_id}:{device_id}"
        self._cancel_schedule(entry_id, device_id)

        async def _reenable(_now) -> None:
            _LOGGER.info(
                "Re-enabling AdGuard DNS protection for entry %s device %s",
                entry_id,
                device_id,
            )
            try:
                await self.async_enable(entry_id, device_id)
            except Exception as err:
                _LOGGER.error(
                    "Failed to re-enable protection for entry %s device %s: %s",
                    entry_id,
                    device_id,
                    err,
                )

        self._unsubs[key] = async_track_point_in_utc_time(self.hass, _reenable, when_utc)

    async def async_disable_temporarily(
        self,
        entry_id: str | None,
        device_id: str | None,
        duration: timedelta = DEFAULT_DISABLE_DURATION,
    ) -> None:
        """Disable protection temporarily, then automatically re-enable."""
        targets = await self._resolve_targets(entry_id, device_id)
        expires = dt_util.utcnow() + duration

        for eid, did, api, coordinator in targets:
            await api.async_set_protection(did, False)
            await coordinator.async_request_refresh()

            self._data.setdefault("temporary_disables", {})
            self._data["temporary_disables"].setdefault(eid, {})
            self._data["temporary_disables"][eid][did] = expires.isoformat()

            self._schedule_reenable(eid, did, expires)

        await self.async_save()

    async def async_restore_schedules(self) -> None:
        """Restore temporary disable windows after restart."""
        now = dt_util.utcnow()
        tmp = self._data.get("temporary_disables", {})

        for entry_id, devices in list(tmp.items()):
            if not isinstance(devices, dict):
                continue

            for device_id, expires_iso in list(devices.items()):
                try:
                    expires = dt_util.parse_datetime(expires_iso)
                except Exception:
                    expires = None

                if expires is None:
                    continue

                if expires <= now:
                    try:
                        await self.async_enable(entry_id, device_id)
                    except Exception as err:
                        _LOGGER.error(
                            "Failed restoring expired temporary disable for entry %s device %s: %s",
                            entry_id,
                            device_id,
                            err,
                        )
                else:
                    self._schedule_reenable(entry_id, device_id, expires)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration services once."""
    hass.data.setdefault(DOMAIN, {})

    if MANAGER_KEY in hass.data[DOMAIN]:
        return

    manager = AdGuardDnsServiceManager(hass)
    await manager.async_load()
    hass.data[DOMAIN][MANAGER_KEY] = manager

    async def handle_enable(call: ServiceCall) -> None:
        await manager.async_enable(
            call.data.get(ATTR_ENTRY_ID),
            call.data.get(ATTR_DEVICE_ID),
        )

    async def handle_disable(call: ServiceCall) -> None:
        await manager.async_disable(
            call.data.get(ATTR_ENTRY_ID),
            call.data.get(ATTR_DEVICE_ID),
        )

    async def handle_disable_30(call: ServiceCall) -> None:
        await manager.async_disable_temporarily(
            call.data.get(ATTR_ENTRY_ID),
            call.data.get(ATTR_DEVICE_ID),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ENABLE_PROTECTION,
        handle_enable,
        schema=SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DISABLE_PROTECTION,
        handle_disable,
        schema=SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DISABLE_FOR_30_MINUTES,
        handle_disable_30,
        schema=SERVICE_SCHEMA,
    )

    await manager.async_restore_schedules()


async def async_unload_services(hass: HomeAssistant) -> None:
    """Remove integration services."""
    if hass.services.has_service(DOMAIN, SERVICE_ENABLE_PROTECTION):
        hass.services.async_remove(DOMAIN, SERVICE_ENABLE_PROTECTION)

    if hass.services.has_service(DOMAIN, SERVICE_DISABLE_PROTECTION):
        hass.services.async_remove(DOMAIN, SERVICE_DISABLE_PROTECTION)

    if hass.services.has_service(DOMAIN, SERVICE_DISABLE_FOR_30_MINUTES):
        hass.services.async_remove(DOMAIN, SERVICE_DISABLE_FOR_30_MINUTES)