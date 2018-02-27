"""
Support Xiaomi Philips Eyecare Smart Lamp 2

"""
import logging
import asyncio
from functools import partial
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.light import (
    PLATFORM_SCHEMA, ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light, )

from homeassistant.const import (CONF_NAME, CONF_HOST, CONF_TOKEN, )
from homeassistant.exceptions import PlatformNotReady

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Xiaomi Philips Eyecare Smart Lamp 2'
PLATFORM = 'xiaomi_eyecare_lamp'
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

REQUIREMENTS = ['python-miio==0.3.0']

SUCCESS = ['ok']
ATTR_MODEL = 'model'
FW_VER = 'fw_ver'
HW_VER = 'hw_ver'

# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the light from config."""
    from miio import PhilipsEyecare, DeviceException
    if PLATFORM not in hass.data:
        hass.data[PLATFORM] = {}

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)

    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

    try:
        light = PhilipsEyecare(host, token)
        device_info = light.info()
        _LOGGER.info("%s %s %s initialized",
                     device_info.raw['model'],
                     device_info.raw['fw_ver'],
                     device_info.raw['hw_ver'])

        desklamp = PhilipsEyecareLamp(name, light, device_info)
        hass.data[PLATFORM][host] = desklamp
    except DeviceException:
        raise PlatformNotReady

    async_add_devices([desklamp], update_before_add=True)

class PhilipsEyecareLamp(Light):
    """Representation of an Yeelight Desk Lamp."""

    def __init__(self, name, light, device_info):
        """Initialize the light device."""
        self._name = name
        self._device_info = device_info

        self._brightness = None
        # self._ambstatus = None
        # self._ambvalue = None

        self._light = light
        self._state = None
        self._state_attrs = {
            ATTR_MODEL: self._device_info.raw['model'],
            FW_VER: self._device_info.raw['fw_ver'],
            HW_VER: self._device_info.raw['hw_ver']
        }

    @property
    def should_poll(self):
        """Poll the light."""
        return True

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def available(self):
        """Return true when state is known."""
        return self._state is not None

    # @property
    # def ambient(self):
    #     """Return true when state is known."""
    #     return self._ambvalue

    # @property
    # def ambient_brightness(self):
    #     """Return true when state is known."""
    #     return self._ambstatus is not None



    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def supported_features(self):
        """Return the supported features."""
        return SUPPORT_BRIGHTNESS

    @asyncio.coroutine
    def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a light command handling error messages."""
        from miio import DeviceException
        try:
            result = yield from self.hass.async_add_job(
                partial(func, *args, **kwargs))

            _LOGGER.debug("Response received from light: %s", result)

            return result == SUCCESS
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            return False

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            percent_brightness = int(100 * brightness / 255)

            _LOGGER.debug(
                "Setting brightness: %s %s%%",
                self.brightness, percent_brightness)

            result = yield from self._try_command(
                "Setting brightness failed: %s",
                self._light.set_brightness, percent_brightness)

            if result:
                self._brightness = brightness

        # if ATTR_AMBIENT_BRIGHTNESS in kwargs:
        #     ambient = kwargs[ATTR_AMBIENT_BRIGHTNESS]
        #     percent_ambient = int(100 * ambient / 255)

        #     _LOGGER.debug(
        #         "Setting ambient brightness: %s %s%%",
        #         self._ambvalue, percent_ambient)

        #     result = yield from self._try_command(
        #         "Setting ambient brightness failed: %s",
        #         self._light.set_ambient_brightness, percent_ambient)

        #     if result:
        #         self._ambvalue = ambient

        result = yield from self._try_command(
            "Turning the light on failed.", self._light.on)

        if result:
            self._state = True

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the light off."""
        result = yield from self._try_command(
            "Turning the light off failed.", self._light.off)

        if result:
            self._state = True

    @asyncio.coroutine
    def async_update(self):
        """Fetch state from the device."""
        from miio import DeviceException
        try:
            state = yield from self.hass.async_add_job(self._light.status)
            _LOGGER.debug("Got new state: %s", state)

            self._state = state.is_on
            self._brightness = int(255 * 0.01 * state.brightness)
            # self._ambvalue = int(255 * 0.01 * state.ambvalue)

        except DeviceException as ex:
            _LOGGER.error("Got exception while fetching the state: %s", ex)
