from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class AdGuardDnsCoordinator(DataUpdateCoordinator):
    """Data update coordinator for AdGuard DNS."""

    def __init__(self, hass, api) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="AdGuard DNS",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api

    async def _async_update_data(self):
        """Fetch data from AdGuard DNS API."""
        try:
            devices = await self.api.async_list_devices()
            return {"devices": devices}
        except Exception as err:
            raise UpdateFailed(f"Error communicating with AdGuard DNS: {err}") from err