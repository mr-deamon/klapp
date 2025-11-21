"""The KLAPP integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, DEFAULT_LOOKBACK_DAYS, SCAN_INTERVAL
from .klapp_api import KlappAPI, KlappAuthError, KlappConnectionError

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]



async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up KLAPP from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    api = KlappAPI(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        lookback_days=DEFAULT_LOOKBACK_DAYS,
    )

    coordinator = KlappDataUpdateCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    async def handle_mark_as_read(call):
        """Handle the mark_as_read service call."""
        message_id = call.data.get("message_id")
        try:
            await api.mark_message_as_read(message_id)
            await coordinator.async_request_refresh()
        except KlappAuthError as err:
            _LOGGER.error("Authentication error marking message as read: %s", err)
        except KlappConnectionError as err:
            _LOGGER.error("Connection error marking message as read: %s", err)

    hass.services.async_register(DOMAIN, "mark_as_read", handle_mark_as_read)

    async def handle_mark_all_read(call):
        """Handle the mark_all_read service call."""
        try:
            data = coordinator.data or []
            message_ids = [msg.get("id") for msg in data if msg.get("id")]
            if not message_ids:
                _LOGGER.debug("KLAPP mark_all_read: no unread messages to mark.")
                return
            await api.mark_messages_as_read(message_ids)
            _LOGGER.info("KLAPP: Marked %d messages as read", len(message_ids))
            await coordinator.async_request_refresh()
        except KlappAuthError as err:
            _LOGGER.error("Authentication error marking messages as read: %s", err)
        except KlappConnectionError as err:
            _LOGGER.error("Connection error marking messages as read: %s", err)

    hass.services.async_register(DOMAIN, "mark_all_read", handle_mark_all_read)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class KlappDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching KLAPP data."""

    def __init__(self, hass: HomeAssistant, api: KlappAPI) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            return await self.api.get_unread_messages()
        except KlappAuthError as err:
            raise UpdateFailed(f"Authentication error: {err}") from err
        except KlappConnectionError as err:
            raise UpdateFailed(f"Connection error: {err}") from err
