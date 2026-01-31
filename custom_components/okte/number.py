"""
OKTE Integration for Home Assistant
Custom integration for fetching and analyzing electricity prices from OKTE Slovakia
*** OKTE number entities for Home Assistant ***

Author: Jozef Moravcik
email: jozef.moravcik@moravcik.eu
"""

import logging
from datetime import datetime

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import (
    DOMAIN, 
    CONF_CHEAPEST_TIME_WINDOW_PERIOD,
    CONF_MOST_EXPENSIVE_TIME_WINDOW_PERIOD,
    DEFAULT_CHEAPEST_TIME_WINDOW_PERIOD,
    DEFAULT_MOST_EXPENSIVE_TIME_WINDOW_PERIOD
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OKTE number entities from a config entry."""
    number_entities = [
        OkteCheapestWindowHoursNumber(hass),
        OkteMostExpensiveWindowHoursNumber(hass),
    ]
    
    async_add_entities(number_entities)


class OkteCheapestWindowHoursNumber(NumberEntity):
    """Number entity for setting cheapest time window hours."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the number entity."""
        self.hass = hass
        self._attr_unique_id = "okte_cheapest_window_hours"
        self.entity_id = "number.okte_cheapest_window_hours"
        self._attr_icon = "mdi:clock-time-eight"
        self._attr_native_min_value = 1
        self._attr_native_max_value = 24
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = "h"

        self._attr_has_entity_name = True
        # self._attr_name = None
        # self._attr_translation_key = "cheapest_window_hours"

        # Set name based on language
        language = hass.config.language
        if language == "sk":
            self._attr_name = "Najlacnejšie hodiny"
        else:
            self._attr_name = "Cheapest Hours"

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, "okte_main")},
            "name": "OKTE",
            "manufacturer": "OKTE",
            "model": "Electricity Price Monitor",
            "sw_version": "1.0.0",
        }

    @property
    def available(self):
        """Return if number entity is available."""
        return DOMAIN in self.hass.data

    @property
    def native_value(self):
        """Return the current value."""
        if DOMAIN not in self.hass.data:
            return DEFAULT_CHEAPEST_TIME_WINDOW_PERIOD
        
        # Get current value from configuration
        coordinator = self.hass.data[DOMAIN].get("coordinator")
        if coordinator:
            return coordinator._get_min_window_hours()
        
        # Fallback to default
        return DEFAULT_CHEAPEST_TIME_WINDOW_PERIOD

    async def async_set_native_value(self, value: float) -> None:
        """Set new value for cheapest window hours."""
        window_hours = int(value)
        
        _LOGGER.debug(f"Setting cheapest window hours to: {window_hours}")
        
        try:
            # Call the service to update the configuration
            await self.hass.services.async_call(
                DOMAIN,
                "set_cheapest_window_hours",
                {"window_hours": window_hours},
                blocking=True
            )
            
            # Force state update
            self.async_write_ha_state()
            
        except Exception as e:
            _LOGGER.error(f"Error setting cheapest window hours: {e}")

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        coordinator = self.hass.data[DOMAIN].get("coordinator") if DOMAIN in self.hass.data else None
        current_value = coordinator._get_min_window_hours() if coordinator else DEFAULT_CHEAPEST_TIME_WINDOW_PERIOD
        
        return {
            "description": "Počet hodín pre výpočet najlacnejšieho časového okna",
            "current_setting": current_value,
            "service_name": "set_cheapest_window_hours",
            "min_value": 1,
            "max_value": 24
        }


class OkteMostExpensiveWindowHoursNumber(NumberEntity):
    """Number entity for setting most expensive time window hours."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the number entity."""
        self.hass = hass
        self._attr_unique_id = "okte_most_expensive_window_hours"
        self.entity_id = "number.okte_most_expensive_window_hours"
        self._attr_icon = "mdi:clock-time-four"
        self._attr_native_min_value = 1
        self._attr_native_max_value = 24
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = "h"

        self._attr_has_entity_name = True
        # self._attr_name = None
        # self._attr_translation_key = "most_expensive_window_hours"

        # Set name based on language
        language = hass.config.language
        if language == "sk":
            self._attr_name = "Najdrahšie hodiny"
        else:
            self._attr_name = "Expensive Hours"

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, "okte_main")},
            "name": "OKTE",
            "manufacturer": "OKTE",
            "model": "Electricity Price Monitor",
            "sw_version": "1.0.0",
        }

    @property
    def available(self):
        """Return if number entity is available."""
        return DOMAIN in self.hass.data

    @property
    def native_value(self):
        """Return the current value."""
        if DOMAIN not in self.hass.data:
            return DEFAULT_MOST_EXPENSIVE_TIME_WINDOW_PERIOD
        
        # Get current value from configuration
        coordinator = self.hass.data[DOMAIN].get("coordinator")
        if coordinator:
            return coordinator._get_max_window_hours()
        
        # Fallback to default
        return DEFAULT_MOST_EXPENSIVE_TIME_WINDOW_PERIOD

    async def async_set_native_value(self, value: float) -> None:
        """Set new value for most expensive window hours."""
        window_hours = int(value)
        
        _LOGGER.debug(f"Setting most expensive window hours to: {window_hours}")
        
        try:
            # Call the service to update the configuration
            await self.hass.services.async_call(
                DOMAIN,
                "set_most_expensive_window_hours",
                {"window_hours": window_hours},
                blocking=True
            )
            
            # Force state update
            self.async_write_ha_state()
            
        except Exception as e:
            _LOGGER.error(f"Error setting most expensive window hours: {e}")

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        coordinator = self.hass.data[DOMAIN].get("coordinator") if DOMAIN in self.hass.data else None
        current_value = coordinator._get_max_window_hours() if coordinator else DEFAULT_MOST_EXPENSIVE_TIME_WINDOW_PERIOD
        
        return {
            "description": "Počet hodín pre výpočet najdrahšieho časového okna",
            "current_setting": current_value,
            "service_name": "set_most_expensive_window_hours",
            "min_value": 1,
            "max_value": 24
        }