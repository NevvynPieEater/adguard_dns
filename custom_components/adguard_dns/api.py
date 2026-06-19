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
        data = await self._request("GET", "/devices")
        return data if isinstance(data, list) else []

    async def async_get_device(self, device_id: str) -> dict[str, Any]:
        data = await self._request("GET", f"/devices/{device_id}")
        return data if isinstance(data, dict) else {}

    async def async_test_auth(self) -> list[dict[str, Any]]:
        return await self.async_list_devices()

    def _search_bool_field(self, obj: Any, candidate_fields: tuple[str, ...]) -> bool | None:
        if isinstance(obj, dict):
            for field in candidate_fields:
                if field in obj and isinstance(obj[field], bool):
                    return obj[field]
            for value in obj.values():
                found = self._search_bool_field(value, candidate_fields)
                if found is not None:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = self._search_bool_field(item, candidate_fields)
                if found is not None:
                    return found
        return None

    def extract_protection_state(self, device_data: dict[str, Any]) -> bool:
        """
        Best-effort protection state detection.

        The public API docs clearly show the device endpoints, but the field name
        for the protection toggle is not explicit in the snippets I verified.
        So this checks a few likely candidates.
        """
        candidates = (
            "protection_enabled",
            "enabled",
            "protection",
            "dns_filtering_enabled",
            "filtering_enabled",
        )
