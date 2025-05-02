# custom_components/ubibot/sensor.py
"""
Ubibot custom sensor platform.

  • Fetches the latest feed via the Ubibot Web API  
  • Creates one SensorEntity per field (temperature, humidity, etc.)  
  • Groups them under a single "Ubibot Channel <channel>" device
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


async def async_setup_platform(hass, config, async_add_entities: AddEntitiesCallback, discovery_info=None):
    """Set up the Ubibot sensor platform from YAML configuration."""
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
                r = await session.get(url)
                r.raise_for_status()
                return await r.json()
        except Exception as err:
            raise UpdateFailed(f"Error fetching Ubibot data: {err}")

    # Coordinator handles polling & caching
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"ubibot_{channel}",
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
        UbibotSensor(coordinator, channel, field, meta["label"], meta["unit"])
        for field, meta in field_map.items()
    ]

    async_add_entities(entities)


class UbibotSensor(CoordinatorEntity, SensorEntity):
    """A SensorEntity for a single Ubibot field."""

    def __init__(self, coordinator, channel, field, label, unit):
        """Initialize the sensor and its device info."""
        super().__init__(coordinator)
        self._field = field
        self._attr_name = f"Ubibot {label}"
        self._attr_unique_id = f"ubibot_{channel}_{field}"
        self._attr_unit_of_measurement = unit
        # This groups all your Ubibot sensors under one device in the UI:
        self._attr_device_info = {
            "identifiers": {("ubibot", channel)},
            "name": f"Ubibot Channel {channel}",
            "manufacturer": "Ubibot",
            "model": "Web API",
        }

    @property
    def state(self):
        """Return the latest value for this field, or None."""
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
