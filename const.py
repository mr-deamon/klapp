"""Constants for the KLAPP integration."""

from datetime import timedelta

DOMAIN = "klapp"

CONF_SCAN_INTERVAL = "scan_interval"

# Default scan interval for DataUpdateCoordinator
SCAN_INTERVAL = timedelta(minutes=5)

# Default number of days to look back when querying unread messages
DEFAULT_LOOKBACK_DAYS = 3
