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
)

_LOGGER = logging.getLogger(__name__)

# Default polling interval: 15 minutes
DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)

# Configuration schema for configuration.yaml
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required("platform"): "ubibot",
        vol.Required("account_key"): cv.string,
        vol.Required("channel"): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
    }
)

async def async_setup_platform(hass, config, async_add_entities: AddEntitiesCallback, discovery_info=None):
    """Set up the Ubibot sensor platform."""
    account_key = config["account_key"]
    channel = config["channel"]
    scan_interval = config[CONF_SCAN_INTERVAL]

    # Helper to fetch JSON from Ubibot
    async def async_fetch_data():
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
            raise UpdateFailed(f"Error fetching Ubibot data: {err}")

    # Coordinator will handle polling and caching
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="ubibot",
        update_method=async_fetch_data,
        update_interval=scan_interval,
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Map JSON fields to sensor metadata
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

    # Create one entity per field
    entities = [
        UbibotSensor(coordinator, channel, field, meta["label"], meta["unit"])
        for field, meta in field_map.items()
    ]

    async_add_entities(entities)


class UbibotSensor(SensorEntity):
    """Representation of a single Ubibot field as a Home Assistant sensor."""

    def __init__(self, coordinator, channel, field, label, unit):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._channel = channel
        self._field = field
        self._attr_name = f"Ubibot {label}"
        self._attr_unique_id = f"ubibot_{channel}_{field}"
        self._attr_unit_of_measurement = unit

    @property
    def state(self):
        """Return the latest value for this field, or None if unavailable."""
        data = self.coordinator.data
        feeds = data.get("feeds") if data else None
        if not feeds:
            return None
        # feeds is a list from oldest→newest; take the last element
        latest = feeds[-1]
        return latest.get(self._field)

    @property
    def extra_state_attributes(self):
        """Add some metadata from the API response."""
        data = self.coordinator.data or {}
        return {
            "server_time": data.get("server_time"),
            "start": data.get("start"),
            "end": data.get("end"),
        }

    async def async_update(self):
        """Request the coordinator to refresh data."""
        await self.coordinator.async_request_refresh()
