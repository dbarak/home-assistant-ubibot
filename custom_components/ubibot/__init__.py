"""UbiBot integration."""
import voluptuous as vol
from homeassistant.const import CONF_SCAN_INTERVAL
import homeassistant.helpers.config_validation as cv
from .const import CONF_ACCOUNT_KEY, CONF_CHANNEL_ID, DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_ACCOUNT_KEY): cv.string,
                vol.Required(CONF_CHANNEL_ID): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=900): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)
