from __future__ import annotations

DOMAIN = "adguard_dns"

CONF_API_KEY = "api_key"
CONF_MODE = "mode"
CONF_DEVICE_ID = "device_id"

MODE_ALL_DEVICES = "all"
MODE_SINGLE_DEVICE = "single"

SERVICE_ENABLE_PROTECTION = "enable_protection"
SERVICE_DISABLE_PROTECTION = "disable_protection"
SERVICE_DISABLE_FOR_30_MINUTES = "disable_for_30_minutes"

ATTR_ENTRY_ID = "entry_id"
ATTR_DEVICE_ID = "device_id"

DEFAULT_SCAN_INTERVAL = 60

API_BASE_URL = "https://api.adguard-dns.io/oapi/v1"

PLATFORMS = ["switch"]

STORAGE_VERSION = 1
STORAGE_KEY = "adguard_dns_storage"

MANAGER_KEY = "manager"