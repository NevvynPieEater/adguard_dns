from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
import aiohttp

from .const import DOMAIN, PLATFORMS
from .api import AdGuardDnsClient
from .services import async_setup_services


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    session = aiohttp.ClientSession()

    client = AdGuardDnsClient(session, entry.data["api_key"])

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "device_id": entry.data["device_id"],
    }

    await async_setup_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)