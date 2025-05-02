# custom_components/ubibot/sensor.py
"""
Ubibot WS1 dynamic sensor platform (latest‐only).

  • Fetches the single most recent feed entry via the Ubibot Web API  
  • Reads channel["fieldX"] to determine which sensors to create  
  • For each field, grabs the value from that one latest entry  
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

# Optional: define units for known fields
_UNITS = {
    "field1": "°C",  # Temperature
    "field2": "%",   # Humidity
    "field3": "lux", # Light
    "field4": "V",   # Voltage
    "field5": "dBm", # WIFI RSSI
    "field6": None,  # Vibration Index
    "field7": None,  # Knocks
    "field8": "°C",  # External Temperature Probe
}


async def async_setup_platform(hass, config, async_add_entities: AddEntitiesCallback, discovery_info=None):
    """Set up the Ubibot WS1 sensor platform from YAML."""
    account_key = config["account_key"]
    channel = config["channel"]
    scan_interval = config[CONF_SCAN_INTERVAL]

    async def async_fetch_data():
        """Fetch only the single most recent feed entry from Ubibot."""
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

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"ubibot_ws1_{channel}",
        update_method=async_fetch_data,
        update_interval=scan_interval,
    )

    # Initial fetch to get channel metadata
    await coordinator.async_config_entry_first_refresh()

    data = coordinator.data or {}
    channel_info = data.get("channel", {})

    # Determine which fields are defined (non-empty) in the channel metadata
    field_map = {
        key: label
        for key, label in channel_info.items()
        if key.startswith("field") and label
    }

    # Create a sensor for each defined field
    entities = [
        UbibotWS1Sensor(coordinator, channel, field_key, label, _UNITS.get(field_key))
        for field_key, label in field_map.items()
    ]

    async_add_entities(entities)


class UbibotWS1Sensor(CoordinatorEntity, SensorEntity):
    """A SensorEntity for a single Ubibot WS1 field (latest‐only)."""

    def __init__(self, coordinator, channel, field, label, unit):
        """Initialize the sensor."""
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
        """Return the value for this field from the single latest feed."""
        data = self.coordinator.data or {}
        feeds = data.get("feeds", [])
        if not feeds:
            return None
        latest = feeds[0]  # only one entry
        return latest.get(self._field)

    @property
    def extra_state_attributes(self):
        """Expose API metadata as attributes."""
        data = self.coordinator.data or {}
        return {
            "server_time": data.get("server_time"),
            "start": data.get("start"),
            "end": data.get("end"),
            "last_entry_date": data.get("channel", {}).get("last_entry_date"),
        }
