# custom_components/ubibot/sensor.py
"""
Ubibot WS1 dynamic sensor platform (most‐recent per field, with °F conversion).

  • Fetches the last 50 feed entries via the Ubibot Web API  
  • Reads channel["fieldX"] to determine which sensors to create  
  • For each field, sorts all feeds by created_at and returns the first
    (most recent) entry that contains that field  
  • Converts field1 & field8 from °C to °F  
  • Groups sensors under one "Ubibot WS1 Channel <channel>" device
"""

import logging
from datetime import timedelta

import async_timeout
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
    CoordinatorEntity,
)

_LOGGER = logging.getLogger(__name__)
DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required("platform"): "ubibot",
        vol.Required("account_key"): cv.string,
        vol.Required("channel"): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
    }
)

# Units: field1 & field8 now °F; others unchanged
_UNITS = {
    "field1": "°F",   # Temperature → converted
    "field2": "%",    # Humidity
    "field3": "lux",  # Light
    "field4": "V",    # Voltage
    "field5": "dBm",  # WiFi RSSI
    "field6": None,   # Vibration Index
    "field7": None,   # Knocks
    "field8": "°F",   # External Temperature Probe → converted
}


async def async_setup_platform(hass, config, async_add_entities: AddEntitiesCallback, discovery_info=None):
    """Set up Ubibot WS1 sensors from YAML."""
    account_key = config["account_key"]
    channel = config["channel"]
    scan_interval = config[CONF_SCAN_INTERVAL]

    async def async_fetch_data():
        """Fetch the last 50 feeds from Ubibot."""
        url = (
            f"https://webapi.ubibot.com/channels/{channel}/feeds.json"
            f"?account_key={account_key}&results=50"
        )
        try:
            async with async_timeout.timeout(10):
                session = async_get_clientsession(hass)
                resp = await session.get(url)
                resp.raise_for_status()
                return await resp.json()
        except Exception as err:
            raise UpdateFailed(f"Error fetching Ubibot WS1 data: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"ubibot_ws1_{channel}",
        update_method=async_fetch_data,
        update_interval=scan_interval,
    )

    # Initial data fetch
    await coordinator.async_config_entry_first_refresh()

    data = coordinator.data or {}
    channel_info = data.get("channel", {})

    # Only create sensors for fields that have a non-empty label
    field_map = {
        key: label
        for key, label in channel_info.items()
        if key.startswith("field") and label
    }

    entities = []
    for field_key, label in field_map.items():
        entities.append(
            UbibotWS1Sensor(
                coordinator,
                channel,
                field_key,
                label,
                _UNITS.get(field_key),
            )
        )

    async_add_entities(entities)


class UbibotWS1Sensor(CoordinatorEntity, SensorEntity):
    """Sensor for a single Ubibot WS1 field (with optional conversion)."""

    def __init__(self, coordinator, channel, field, label, unit):
        """Initialize sensor and device grouping."""
        super().__init__(coordinator)
        self._field = field
        self._attr_name = f"Ubibot WS1 {label}"
        self._attr_unique_id = f"ubibot_ws1_{channel}_{field}"
        self._attr_unit_of_measurement = unit
        self._attr_device_info = {
            "identifiers": {("ubibot_ws1", channel)},
            "name": f"Ubibot WS1 Channel {channel}",
            "manufacturer": "Ubibot",
            "model": "Web API",
        }

    @property
    def state(self):
        """Return the most recent value for this field, converting if needed."""
        data = self.coordinator.data or {}
        feeds = data.get("feeds", [])
        if not feeds:
            return None

        # Sort feeds chronologically by created_at
        try:
            sorted_feeds = sorted(feeds, key=lambda e: e.get("created_at", ""))
        except Exception:
            sorted_feeds = feeds

        # Walk from newest → oldest looking for our field
        for entry in reversed(sorted_feeds):
            if self._field in entry:
                value = entry[self._field]
                # Convert Celsius → Fahrenheit for field1 & field8
                if self._field in ("field1", "field8") and isinstance(value, (int, float)):
                    value = value * 9.0 / 5.0 + 32.0
                return value

        return None

    @property
    def extra_state_attributes(self):
        """Expose API metadata as attributes."""
        data = self.coordinator.data or {}
        return {
            "server_time": data.get("server_time"),
            "start": data.get("start"),
            "end": data.get("end"),
        }
