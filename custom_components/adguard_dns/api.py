from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import API_BASE_URL


class AdGuardDnsApiError(Exception):
    """Base API error."""


class AdGuardDnsAuthError(AdGuardDnsApiError):
    """Authentication error."""


class AdGuardDnsClient:
    """AdGuard DNS API client."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        self._session = session
        self._headers = {
            "Authorization": f"ApiKey {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """Make an API request."""
        url = f"{API_BASE_URL}{path}"

        try:
            async with self._session.request(
                method,
                url,
                headers=self._headers,
                json=json,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status in (401, 403):
                    raise AdGuardDnsAuthError(f"Auth failed: HTTP {resp.status}")

                if resp.status >= 400:
                    text = await resp.text()
                    raise AdGuardDnsApiError(f"HTTP {resp.status}: {text}")

                if resp.content_type and "json" in resp.content_type:
                    return await resp.json()

                return await resp.text()

        except asyncio.TimeoutError as err:
            raise AdGuardDnsApiError("Request timed out") from err
        except aiohttp.ClientError as err:
            raise AdGuardDnsApiError(str(err)) from err

    async def async_list_devices(self) -> list[dict[str, Any]]:
        """Return all devices visible to this API key."""
        data = await self._request("GET", "/devices")
        return data if isinstance(data, list) else []

    async def async_get_device(self, device_id: str) -> dict[str, Any]:
        """Return a single device payload."""
        data = await self._request("GET", f"/devices/{device_id}")
        return data if isinstance(data, dict) else {}

    async def async_test_auth(self) -> list[dict[str, Any]]:
        """Simple auth test used by config flow."""
        return await self.async_list_devices()

    def extract_protection_state(self, device_data: dict[str, Any]) -> bool:
        """
        Extract protection state from a device payload.

        Based on the working REST sensor:
        value_json.settings.protection_enabled
        """
        return bool(device_data.get("settings", {}).get("protection_enabled", False))

    async def async_set_protection(self, device_id: str, enabled: bool) -> None:
        """
        Enable/disable DNS protection.

        Based on the working REST command:
        PUT /devices/{device_id}/settings
        {"protection_enabled": true/false}
        """
        await self._request(
            "PUT",
            f"/devices/{device_id}/settings",
            json={"protection_enabled": enabled},
        )