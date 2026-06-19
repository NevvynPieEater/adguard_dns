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
    """Set up the AdGuard DNS integration (global setup)."""
    hass.data.setdefault(DOMAIN, {})

    # Register services once
    await async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AdGuard DNS from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    api = AdGuardDnsClient(session, entry.data[CONF_API_KEY])
    coordinator = AdGuardDnsCoordinator(hass, api)

    try:
        await coordinator.async_config_entry_first_refresh()
    except AdGuardDnsAuthError as err:
        raise ConfigEntryNotReady(f"Authentication failed: {err}") from err
    except AdGuardDnsApiError as err:
        raise ConfigEntryNotReady(f"Could not connect to AdGuard DNS: {err}") from err

    # Store runtime data
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    # Try restoring any scheduled re-enable operations
    manager = hass.data[DOMAIN].get(MANAGER_KEY)
    if manager:
        await manager.async_restore_schedules()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

        # If no more real entries remain, remove services
        active_entries = [
            key for key in hass.data.get(DOMAIN, {}).keys()
            if key != MANAGER_KEY
        ]

        if not active_entries:
            await async_unload_services(hass)

    return unload_ok