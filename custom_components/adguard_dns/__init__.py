from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import ConfigEntryNotReady

from .api import AdGuardDnsApiError, AdGuardDnsAuthError, AdGuardDnsClient
from .const import CONF_API_KEY, DOMAIN, MANAGER_KEY, PLATFORMS
from .coordinator import AdGuardDnsCoordinator
from .services import async_setup_services, async_unload_services


async def async_setup(hass: HomeAssistant, config) -> bool:
    """Set up the AdGuard DNS integration (global)."""
    hass.data.setdefault(DOMAIN, {})

    # ✅ THIS is what registers your services (fixes your error)
    await async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AdGuard DNS from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    api = AdGuardDnsClient(session, entry.data[CONF_API_KEY])
    coordinator = AdGuardDnsCoordinator(hass, api)

    try:
        # ✅ Initial data load
        await coordinator.async_config_entry_first_refresh()

    except AdGuardDnsAuthError as err:
        raise ConfigEntryNotReady(f"Authentication failed: {err}") from err

    except AdGuardDnsApiError as err:
        raise ConfigEntryNotReady(f"Cannot connect to AdGuard DNS: {err}") from err

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    # ✅ Restore any 30-min timers after restart
    manager = hass.data[DOMAIN].get(MANAGER_KEY)
    if manager:
        await manager.async_restore_schedules()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

        # ✅ Only remove services if no entries left
        remaining_entries = [
            k for k in hass.data.get(DOMAIN, {}) if k != MANAGER_KEY
        ]

        if not remaining_entries:
            await async_unload_services(hass)

    return unload_ok