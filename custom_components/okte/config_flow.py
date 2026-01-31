"""
OKTE Integration for Home Assistant
Custom integration for fetching and analyzing electricity prices from OKTE Slovakia
*** Config flow for OKTE integration ***

Author: Jozef Moravcik
email: jozef.moravcik@moravcik.eu
"""

import logging
import voluptuous as vol
from datetime import time

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    DEFAULT_CHEAPEST_TIME_WINDOW_PERIOD,
    DEFAULT_MOST_EXPENSIVE_TIME_WINDOW_PERIOD,
    DEFAULT_FETCH_TIME,
    CONF_MOST_EXPENSIVE_TIME_WINDOW_PERIOD,
    CONF_CHEAPEST_TIME_WINDOW_PERIOD,
    CONF_FETCH_TIME,
)

_LOGGER = logging.getLogger(__name__)


def validate_time_format(value):
    """Validate time format HH:MM."""
    try:
        time_obj = time.fromisoformat(value)
        return value
    except ValueError:
        raise vol.Invalid("Invalid time format. Use HH:MM (e.g., 14:00)")


class OkteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OKTE."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate time format
            try:
                validate_time_format(user_input[CONF_FETCH_TIME])
            except vol.Invalid:
                errors[CONF_FETCH_TIME] = "invalid_time"
            
            if not errors:
                # Check if already configured
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                
                # Create entry without name
                return self.async_create_entry(
                    title="OKTE Slovakia",
                    data=user_input,
                )

        # Show form - time is first, removed name
        data_schema = vol.Schema({
            vol.Optional(CONF_FETCH_TIME, default=DEFAULT_FETCH_TIME): str,
            vol.Optional(CONF_CHEAPEST_TIME_WINDOW_PERIOD, default=DEFAULT_CHEAPEST_TIME_WINDOW_PERIOD): cv.positive_int,
            vol.Optional(CONF_MOST_EXPENSIVE_TIME_WINDOW_PERIOD, default=DEFAULT_MOST_EXPENSIVE_TIME_WINDOW_PERIOD): cv.positive_int,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get options flow."""
        return OkteOptionsFlowHandler(config_entry)


class OkteOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for OKTE."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        # Removed deprecated explicit config_entry assignment
        super().__init__()

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}
        
        if user_input is not None:
            # Validate time format
            try:
                validate_time_format(user_input[CONF_FETCH_TIME])
            except vol.Invalid:
                errors[CONF_FETCH_TIME] = "invalid_time"
            
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        # Access config_entry through self.config_entry (inherited from OptionsFlow)
        options_schema = vol.Schema({
            vol.Optional(
                CONF_FETCH_TIME,
                default=self.config_entry.options.get(CONF_FETCH_TIME,
                    self.config_entry.data.get(CONF_FETCH_TIME, DEFAULT_FETCH_TIME))
            ): str,
            vol.Optional(
                CONF_CHEAPEST_TIME_WINDOW_PERIOD,
                default=self.config_entry.options.get(CONF_CHEAPEST_TIME_WINDOW_PERIOD, 
                    self.config_entry.data.get(CONF_CHEAPEST_TIME_WINDOW_PERIOD, DEFAULT_CHEAPEST_TIME_WINDOW_PERIOD))
            ): cv.positive_int,
            vol.Optional(
                CONF_MOST_EXPENSIVE_TIME_WINDOW_PERIOD,
                default=self.config_entry.options.get(CONF_MOST_EXPENSIVE_TIME_WINDOW_PERIOD,
                    self.config_entry.data.get(CONF_MOST_EXPENSIVE_TIME_WINDOW_PERIOD, DEFAULT_MOST_EXPENSIVE_TIME_WINDOW_PERIOD))
            ): cv.positive_int,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
        )