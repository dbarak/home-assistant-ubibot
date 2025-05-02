# custom_components/ubibot/sensor.py
"""
Ubibot WS1 custom sensor platform.

  • Fetches the latest feed via the Ubibot Web API  
  • Creates one SensorEntity per field (temperature, humidity, etc.)  
  • Groups them under a single "Ubibot WS1 Channel <channel>" device
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

# Default polling interval: 15 minutes
DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)

# The YAML block remains `platform: ubibot`
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required("platform"): "ubibot",
        vol.Required("account_key"): cv.string,
        vol.Required("channel"): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
    }
)


async def async_setup_platform(hass, config, async_add_entities: AddEntitiesCallback, discovery_info=None):
    """Set up the Ubibot WS1 sensor platform from YAML configuration."""
    account_key = config["account_key"]
    channel = config["channel"]
    scan_interval = config[CONF_SCAN_INTERVAL]

    async def async_fetch_data():
        """Fetch JSON data from the Ubibot API."""
        url = (
            f"https://webapi.ubibot.com/channels/{channel}/feeds.json"
            f"?account_key={account_key}&results=1"
        )
        try:
            async with async_timeout.timeout(10):
                session = async_get_clientsession(hass)
                resp = await session.get(url)
                resp.raise_for_status()
                return await resp.json()
        except Exception as err:
            raise UpdateFailed(f"Error fetching Ubibot WS1 data: {err}")

    # Coordinator handles polling & caching
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"ubibot_ws1_{channel}",
        update_method=async_fetch_data,
        update_interval=scan_interval,
    )

    # Fetch initial data so entities have something to display right away
    await coordinator.async_config_entry_first_refresh()

    # Map the API fields to human-friendly names & units
    field_map = {
        "field1": {"label": "Temperature", "unit": "°C"},
        "field2": {"label": "Humidity", "unit": "%"},
        "field3": {"label": "Light", "unit": "lux"},
        "field4": {"label": "Voltage", "unit": "V"},
        "field5": {"label": "WiFi RSSI", "unit": "dBm"},
        "field6": {"label": "Vibration Index", "unit": None},
        "field7": {"label": "Knocks", "unit": None},
        "field8": {"label": "External Temperature", "unit": "°C"},
    }

    # Create one sensor per field
    entities = [
        UbibotWS1Sensor(coordinator, channel, field, meta["label"], meta["unit"])
        for field, meta in field_map.items()
    ]

    async_add_entities(entities)


class UbibotWS1Sensor(CoordinatorEntity, SensorEntity):
    """A SensorEntity for a single Ubibot WS1 field."""

    def __init__(self, coordinator, channel, field, label, unit):
        """Initialize the sensor and its device info."""
        super().__init__(coordinator)
        self._field = field
        # Prefix all sensor names with "Ubibot WS1"
        self._attr_name = f"Ubibot WS1 {label}"
        self._attr_unique_id = f"ubibot_ws1_{channel}_{field}"
        self._attr_unit_of_measurement = unit
        # Group under a single device named "Ubibot WS1 Channel <channel>"
        self._attr_device_info = {
            "identifiers": {("ubibot_ws1", channel)},
            "name": f"Ubibot WS1 Channel {channel}",
            "manufacturer": "Ubibot",
            "model": "Web API",
        }

    @property
    def state(self):
        """Return the latest value for this field, or None if unavailable."""
        data = self.coordinator.data or {}
        feeds = data.get("feeds", [])
        if not feeds:
            return None
        latest = feeds[-1]
        return latest.get(self._field)

    @property
    def extra_state_attributes(self):
        """Expose some of the API metadata as attributes."""
        data = self.coordinator.data or {}
        return {
            "server_time": data.get("server_time"),
            "start": data.get("start"),
            "end": data.get("end"),
        }
