from __future__ import annotations

DOMAIN = "adguard_dns"
PLATFORMS = ["switch"]

CONF_API_KEY = "api_key"
CONF_MODE = "mode"
CONF_DEVICE_ID = "device_id"

MODE_ALL_DEVICES = "all_devices"
MODE_SINGLE_DEVICE = "single_device"

DEFAULT_SCAN_INTERVAL = 30
API_BASE_URL = "https://api.adguard-dns.io/oapi/v1"

SERVICE_ENABLE_PROTECTION = "enable_protection"
SERVICE_DISABLE_PROTECTION = "disable_protection"
SERVICE_DISABLE_FOR_30_MINUTES = "disable_for_30_minutes"

ATTR_ENTRY_ID = "entry_id"
ATTR_DEVICE_ID = "device_id"

STORAGE_KEY = f"{DOMAIN}_runtime"
STORAGE_VERSION = 1

MANAGER_KEY = "service_manager"