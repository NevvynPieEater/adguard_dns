from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [AdGuardDnsSwitch(data["client"], data["device_id"])],
        True,
    )


class AdGuardDnsSwitch(SwitchEntity):
    def __init__(self, client, device_id):
        self._client = client
        self._device_id = device_id
        self._is_on = False
        self._attr_name = "AdGuard DNS Protection"

    async def async_update(self):
        data = await self._client.async_get_device(self._device_id)
        self._is_on = self._client.extract_protection_state(data)

    @property
    def is_on(self):
        return self._is_on

    async def async_turn_on(self, **kwargs):
        await self._client.async_set_protection(self._device_id, True)
        self._is_on = True

    async def async_turn_off(self, **kwargs):
        await self._client.async_set_protection(self._device_id, False)
        self._is_on = False