from __future__ import annotations
"""The OKTE Integration"""
"""Author: Jozef Moravcik"""
"""email: jozef.moravcik@moravcik.eu"""

""" config_flow.py """

""" Config flow for OKTE Integration."""

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TimeSelector,
)
import homeassistant.helpers.config_validation as cv

from .okte import OKTE_Master_Instance, OKTE_Window_Instance
from .const import *

LOGGER = logging.getLogger(__name__)

class OkteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._data = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step - automatically select device type based on existing configuration."""
        # Check existing devices
        existing_entries = self.hass.config_entries.async_entries(DOMAIN)
        has_master = any(
            entry.data.get(CONF_DEVICE_TYPE) == DEVICE_TYPE_MASTER 
            for entry in existing_entries
        )
        
        # Automatically select device type:
        # - If no Master exists -> configure Master
        # - If Master exists -> configure Window
        if not has_master:
            # No Master device, automatically configure Master
            self._data[CONF_DEVICE_TYPE] = DEVICE_TYPE_MASTER
            return await self.async_step_master_parameters(user_input)
        else:
            # Master exists, automatically configure Window
            self._data[CONF_DEVICE_TYPE] = DEVICE_TYPE_CALCULATOR
            return await self.async_step_window_parameters(user_input)

    async def async_step_import(self, import_data=None):
        """Handle import of the Master device from configuration.yaml."""
        from datetime import time as dt_time

        import_data = dict(import_data or {})
        fetch_time = import_data.get(CONF_FETCH_TIME, DEFAULT_FETCH_TIME)
        if isinstance(fetch_time, dt_time):
            fetch_time = f"{fetch_time.hour:02d}:{fetch_time.minute:02d}"

        await self.async_set_unique_id(f"{DOMAIN}_master")
        self._abort_if_unique_id_configured()

        device_name = "OKTE Master"
        return self.async_create_entry(
            title=device_name,
            data={
                CONF_DEVICE_TYPE: DEVICE_TYPE_MASTER,
                CONF_DEVICE_NAME: device_name,
                CONF_INCLUDE_DEVICE_NAME_IN_ENTITY: import_data.get(
                    CONF_INCLUDE_DEVICE_NAME_IN_ENTITY, DEFAULT_INCLUDE_DEVICE_NAME_IN_ENTITY
                ),
                CONF_FETCH_TIME: fetch_time,
            },
        )

    async def async_step_master_parameters(self, user_input=None):
        """Handle Master device parameters."""
        errors = {}

        if user_input is not None:
            # Convert time object to string with seconds=0 (TimeSelector returns time object)
            from datetime import time as dt_time
            if CONF_FETCH_TIME in user_input and isinstance(user_input[CONF_FETCH_TIME], dt_time):
                time_obj = user_input[CONF_FETCH_TIME]
                # Convert to string HH:MM format (seconds always 0)
                user_input[CONF_FETCH_TIME] = f"{time_obj.hour:02d}:{time_obj.minute:02d}"
            
            # IMPORTANT: Preserve CONF_DEVICE_TYPE before update
            device_type = self._data.get(CONF_DEVICE_TYPE)
            
            # Master device always has fixed name "OKTE Master"
            device_name = "OKTE Master"
            self._data[CONF_DEVICE_NAME] = device_name
            self._data.update(user_input)
            
            # Restore CONF_DEVICE_TYPE (it was set in async_step_user)
            if device_type:
                self._data[CONF_DEVICE_TYPE] = device_type
            
            unique_id = f"{DOMAIN}_master"
            
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            
            LOGGER.info(f"Creating Master entry with data: {self._data}")
            
            return self.async_create_entry(
                title=device_name,
                data=self._data,
            )

        # Master device configuration - NO device_name field, NO fetch_days field
        # Convert DEFAULT_FETCH_TIME string to time object
        from datetime import time as dt_time
        default_time_parts = DEFAULT_FETCH_TIME.split(':')
        default_time = dt_time(int(default_time_parts[0]), int(default_time_parts[1]))
        
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_INCLUDE_DEVICE_NAME_IN_ENTITY,
                    default=DEFAULT_INCLUDE_DEVICE_NAME_IN_ENTITY,
                ): cv.boolean,
                vol.Required(
                    CONF_FETCH_TIME,
                    default=default_time,
                ): TimeSelector(config={}),
            }
        )

        return self.async_show_form(
            step_id="master_parameters",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_window_parameters(self, user_input=None):
        """Handle Window device parameters."""
        errors = {}

        if user_input is not None:
            # IMPORTANT: Preserve CONF_DEVICE_TYPE before update
            device_type = self._data.get(CONF_DEVICE_TYPE)
            
            self._data.update(user_input)
            
            # Restore CONF_DEVICE_TYPE (it was set in async_step_user)
            if device_type:
                self._data[CONF_DEVICE_TYPE] = device_type
            
            # Get master device entry_id automatically
            existing_entries = self.hass.config_entries.async_entries(DOMAIN)
            master_entry = next(
                (entry for entry in existing_entries if entry.data.get(CONF_DEVICE_TYPE) == DEVICE_TYPE_MASTER),
                None
            )
            
            if not master_entry:
                return self.async_abort(reason="no_master_device")
            
            # Store master_device entry_id automatically
            self._data[CONF_MASTER_DEVICE] = master_entry.entry_id
            
            # Get next available calculator number
            from .const import get_next_calculator_number
            calculator_number = get_next_calculator_number(self.hass)
            device_name = f"Calculator {calculator_number}"
            self._data[CONF_DEVICE_NAME] = device_name
            
            unique_id = f"{DOMAIN}_calculator_{calculator_number}"
            
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            
            LOGGER.info(f"Creating Calculator entry with data: {self._data}")
            
            return self.async_create_entry(
                title=device_name,
                data=self._data,
            )

        # Check if master device exists
        existing_entries = self.hass.config_entries.async_entries(DOMAIN)
        has_master = any(
            entry.data.get(CONF_DEVICE_TYPE) == DEVICE_TYPE_MASTER 
            for entry in existing_entries
        )
        
        if not has_master:
            return self.async_abort(reason="no_master_device")

        # Calculator device configuration - only prefix checkbox
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_INCLUDE_DEVICE_NAME_IN_ENTITY,
                    default=DEFAULT_INCLUDE_DEVICE_NAME_IN_ENTITY,
                ): cv.boolean,
            }
        )

        return self.async_show_form(
            step_id="window_parameters",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OkteOptionsFlowHandler()


class OkteOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for OKTE."""

    def __init__(self):
        """Initialize options flow."""
        super().__init__()
        self._data = {}

    async def async_step_init(self, user_input=None):
        """Handle the initial step of options flow."""
        device_type = self.config_entry.data.get(CONF_DEVICE_TYPE, DEVICE_TYPE_MASTER)
        
        if device_type == DEVICE_TYPE_MASTER:
            return await self.async_step_master_parameters(user_input)
        else:
            return await self.async_step_window_parameters(user_input)

    async def async_step_master_parameters(self, user_input=None):
        """Handle Master device parameters in options."""
        errors = {}

        if user_input is not None:
            # Convert time object to string with seconds=0 (TimeSelector returns time object)
            from datetime import time as dt_time
            if CONF_FETCH_TIME in user_input and isinstance(user_input[CONF_FETCH_TIME], dt_time):
                time_obj = user_input[CONF_FETCH_TIME]
                # Convert to string HH:MM format (seconds always 0)
                user_input[CONF_FETCH_TIME] = f"{time_obj.hour:02d}:{time_obj.minute:02d}"
            
            # Keep stored entity values (window sizes, times, switches) - merge instead of replace
            return self.async_create_entry(title="", data={**self.config_entry.options, **user_input})

        # Get current values
        current_include_device_name = self.config_entry.options.get(
            CONF_INCLUDE_DEVICE_NAME_IN_ENTITY,
            self.config_entry.data.get(CONF_INCLUDE_DEVICE_NAME_IN_ENTITY, DEFAULT_INCLUDE_DEVICE_NAME_IN_ENTITY)
        )
        current_fetch_time_str = self.config_entry.options.get(
            CONF_FETCH_TIME,
            self.config_entry.data.get(CONF_FETCH_TIME, DEFAULT_FETCH_TIME)
        )
        
        # Convert string time to time object
        from datetime import time as dt_time
        if isinstance(current_fetch_time_str, str):
            time_parts = current_fetch_time_str.split(':')
            current_fetch_time = dt_time(int(time_parts[0]), int(time_parts[1]))
        else:
            current_fetch_time = current_fetch_time_str

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_INCLUDE_DEVICE_NAME_IN_ENTITY,
                    default=current_include_device_name,
                ): cv.boolean,
                vol.Required(
                    CONF_FETCH_TIME,
                    default=current_fetch_time,
                ): TimeSelector(config={}),
            }
        )

        return self.async_show_form(
            step_id="master_parameters", 
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_window_parameters(self, user_input=None):
        """Handle Window device parameters in options."""
        errors = {}

        if user_input is not None:
            # Keep stored entity values (window sizes, times, switches) - merge instead of replace
            return self.async_create_entry(title="", data={**self.config_entry.options, **user_input})

        # Get current values
        current_include_device_name = self.config_entry.options.get(
            CONF_INCLUDE_DEVICE_NAME_IN_ENTITY,
            self.config_entry.data.get(CONF_INCLUDE_DEVICE_NAME_IN_ENTITY, DEFAULT_INCLUDE_DEVICE_NAME_IN_ENTITY)
        )

        # Note: Master device selector is NOT shown - it cannot be changed
        # Note: Device name is NOT shown - it cannot be changed
        # Note: Window size, time from, time to are now separate number entities
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_INCLUDE_DEVICE_NAME_IN_ENTITY,
                    default=current_include_device_name,
                ): cv.boolean,
            }
        )

        return self.async_show_form(
            step_id="window_parameters", 
            data_schema=data_schema,
            errors=errors,
        )
