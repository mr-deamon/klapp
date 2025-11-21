"""Sensor platform for KLAPP integration."""
from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KLAPP sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    async_add_entities([KlappMessageSensor(coordinator, entry)])


class KlappMessageSensor(CoordinatorEntity, SensorEntity):
    """Representation of a KLAPP message sensor."""

    _attr_has_entity_name = True
    _attr_name = "Unread Messages"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_unread_messages"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "KLAPP",
            "manufacturer": "KLAPP",
            "model": "Message Service",
        }

    @property
    def native_value(self) -> int:
        """Return the number of unread messages."""
        if self.coordinator.data:
            return len(self.coordinator.data)
        return 0

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}
        
        # Get the most recent message
        if len(self.coordinator.data) > 0:
            latest = self.coordinator.data[0]
            
            subject = latest.get("subject", "")
            body = ""
            message_id = latest.get("id", "")
            sent_at = latest.get("sent_at", "")
            
            # Extract body from replies if available
            replies = latest.get("replies", [])
            if replies and len(replies) > 0:
                body = replies[0].get("body_html", "")
            
            return {
                "latest_subject": subject,
                "latest_body": body,
                "latest_id": message_id,
                "latest_sent_at": sent_at,
                "total_unread": len(self.coordinator.data),
                "messages": [
                    {
                        "id": msg.get("id"),
                        "subject": msg.get("subject"),
                        "sent_at": msg.get("sent_at"),
                    }
                    for msg in self.coordinator.data
                ],
            }
        
        return {"total_unread": 0}

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        if self.native_value and self.native_value > 0:
            return "mdi:email-alert"
        return "mdi:email"
