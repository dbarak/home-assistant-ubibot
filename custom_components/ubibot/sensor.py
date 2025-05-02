"""Ubibot sensor."""

import logging
import threading
from datetime import datetime, timedelta
import requests

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import SensorStateClass

from .const import (
    CONF_ACCOUNT_KEY, CONF_CHANNEL_ID, CONF_SCAN_INTERVAL,
    SENSOR_TYPES, MODELS
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities, discovery_info=None
):
    """Set up the UbiBot sensors via YAML."""
    _LOGGER.debug("Setting up UbiBot platform with config: %s", config)
    account_key = config[DOMAIN][CONF_ACCOUNT_KEY]
    channel_id = config[DOMAIN][CONF_CHANNEL_ID]
    scan_interval = config[DOMAIN][CONF_SCAN_INTERVAL]

    ubibot_data = UbibotData(account_key, channel_id, scan_interval)
    # Initial fetch off the event loop
    await hass.async_add_executor_job(ubibot_data.update)

    entities = [
        UbibotSensor(hass, sensor_type, channel_id, ubibot_data)
        for sensor_type in SENSOR_TYPES
    ]
    async_add_entities(entities)

class UbibotSensor(Entity):
    """Representation of a UbiBot field as a sensor."""

    def __init__(
        self, hass: HomeAssistant, sensor_type: str, channel_id: str, ubibot_data
    ):
        self.hass = hass
        self._type = sensor_type
        self._channel = channel_id
        self._ubibot_data = ubibot_data
        self._state = None

    @property
    def name(self):
        return f"Ubibot - {self._channel} - {self._type}"

    @property
    def native_value(self):
        return self._state

    @property
    def device_class(self):
        return SENSOR_TYPES[self._type]["class"]

    @property
    def native_unit_of_measurement(self):
        return SENSOR_TYPES[self._type]["unit"]

    @property
        def icon(self):
        return SENSOR_TYPES[self._type]["icon"]

    @property
    def unique_id(self) -> str:
        return f"{self._channel}_{self._type}"

    async def async_update(self):
        """Fetch new state data asynchronously."""
        _LOGGER.debug("Updating sensor '%s'", self._type)
        await self.hass.async_add_executor_job(self._ubibot_data.update)
        feeds = self._ubibot_data.data.get("feeds", [])
        new_state = next(
            (
                entry[SENSOR_TYPES[self._type]["field"]]
                for entry in feeds
                if SENSOR_TYPES[self._type]["field"] in entry
            ),
            None
        )
        _LOGGER.debug("New state for %s: %s", self._type, new_state)
        self._state = new_state

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def device_info(self):
        data = self._ubibot_data.data.get("channel", {})
        return {
            "identifiers": {("ubibot", data.get("device_id"))},
            "name": data.get("name"),
            "manufacturer": "UbiBot",
            "model": MODELS.get(data.get("device_id"), data.get("device_id")),
        }

class UbibotData:
    """Ubibot data object."""

    URL = "https://webapi.ubibot.com/channels/{0}/feeds.json?account_key={1}"

    def __init__(
        self, account_key: str, channel_id: str, scan_interval: int
    ):
        self.account_key = account_key
        self.channel = channel_id
        self.scan_interval = scan_interval
        self.last_refresh = None
        self.data = {}
        self._lock = threading.Lock()

    def update(self):
        """Get data from UbiBot API."""
        if (
            self.last_refresh
            and datetime.now() < self.last_refresh + timedelta(seconds=self.scan_interval)
        ):
            return
        if not self._lock.acquire(False):
            return
        try:
            url = self.URL.format(self.channel, self.account_key)
            _LOGGER.debug("Fetching UbiBot URL: %s", url)
            response = requests.get(url, timeout=10)
            _LOGGER.debug("Received status code: %s", response.status_code)
            if response.status_code == 200:
                try:
                    self.data = response.json()
                    _LOGGER.debug("Fetched data keys: %s", list(self.data.keys()))
                except ValueError as e:
                    _LOGGER.error("Error parsing UbiBot JSON: %s", e)
            else:
                _LOGGER.error("Ubibot API error: %s", response.status_code)
            self.last_refresh = datetime.now()
        finally:
            self._lock.release()
