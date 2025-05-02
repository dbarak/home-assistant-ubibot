"""Ubibot sensor."""

from datetime import datetime
import logging
import threading
import requests

from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from . import CONF_CHANNEL
from .const import SENSOR_TYPES, MODELS

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Ubibot sensor setup."""
    _LOGGER.debug("Setting up UbiBot platform with config: %s", config)
    api_key = config.get(CONF_API_KEY)
    channel = config.get(CONF_CHANNEL)
    scan_interval = config.get(CONF_SCAN_INTERVAL)
    _LOGGER.debug("Account key: %s, Channel: %s, Scan interval: %s", api_key, channel, scan_interval)

    ubibot_data = UbibotData(api_key, channel, scan_interval)

    for sensor_type in SENSOR_TYPES:
        _LOGGER.debug("Adding sensor for type: %s", sensor_type)
        add_devices([UbibotSensor(sensor_type, channel, ubibot_data)])


class UbibotSensor(SensorEntity):
    """Representation of a UbiBot field as a sensor."""

    def __init__(self, sensor_type, channel, ubibot_data):
        """Initialize the sensor."""
        self._type = sensor_type
        self._channel = channel
        self._ubibot_data = ubibot_data
        _LOGGER.debug("Initializing sensor '%s' for channel '%s'", sensor_type, channel)

        # Grab the most recent value from feeds
        feeds = self._ubibot_data.data.get("feeds", [])
        self._state = next(
            (entry[SENSOR_TYPES[self._type]["field"]] for entry in feeds
             if SENSOR_TYPES[self._type]["field"] in entry),
            None
        )
        _LOGGER.debug("Initial state for %s: %s", self._type, self._state)

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

    def update(self):
        """Fetch new state data for the sensor."""
        _LOGGER.debug("Updating sensor '%s'", self._type)
        self._ubibot_data.update()
        feeds = self._ubibot_data.data.get("feeds", [])
        new_state = next(
            (entry[SENSOR_TYPES[self._type]["field"]] for entry in feeds
             if SENSOR_TYPES[self._type]["field"] in entry),
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

    # Point to feeds.json endpoint
    URL = "https://webapi.ubibot.com/channels/{0}/feeds.json?account_key={1}"

    def __init__(self, account_key, channel, scan_interval):
        """
        :param account_key: Ubibot Account Key
        :param channel: Channel ID
        :param scan_interval: refresh interval in seconds
        """
        self.account_key = account_key
        self.channel = channel
        self.scan_interval = scan_interval
        self.last_refresh = datetime(2000, 1, 1)
        self.data = {}
        self._update_in_progress = threading.Lock()
        self.update()

    def update(self):
        """Get data from Ubibot API."""
        # Throttle by scan_interval (seconds)
        if datetime.now() < self.last_refresh + timedelta(seconds=self.scan_interval) \
           or not self._update_in_progress.acquire(False):
            return
        try:
            url = UbibotData.URL.format(self.channel, self.account_key)
            _LOGGER.debug("Fetching UbiBot URL: %s", url)
            r = requests.get(url)
            _LOGGER.debug("Received status code: %s", r.status_code)
            if r.status_code == 200:
                try:
                    self.data = r.json()
                    _LOGGER.debug("Fetched data keys: %s", list(self.data.keys()))
                except ValueError as e:
                    _LOGGER.error("Error parsing UbiBot JSON: %s", e)
            else:
                _LOGGER.error("Ubibot API error: %s", r.status_code)
            self.last_refresh = datetime.now()
            _LOGGER.debug("Next allowed refresh after: %s", self.last_refresh + timedelta(seconds=self.scan_interval))
        finally:
            self._update_in_progress.release()
