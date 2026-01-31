"""
OKTE Integration for Home Assistant
Custom integration for fetching and analyzing electricity prices from OKTE Slovakia
*** OKTE button for Home Assistant ***

Author: Jozef Moravcik
email: jozef.moravcik@moravcik.eu
"""

import logging
from datetime import datetime

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, DEFAULT_FETCH_DAYS
from .okte import (
    fetch_okte_data,
    calculate_price_statistics,
    find_cheapest_time_window,
    find_most_expensive_time_window,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OKTE button from a config entry."""
    buttons = [
        OkteFetchDataButton(hass),
    ]
    
    async_add_entities(buttons)


class OkteFetchDataButton(ButtonEntity):
    """Button for manually fetching OKTE data."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the button."""
        self.hass = hass
        self._attr_unique_id = "okte_fetch_data"
        self.entity_id = "button.okte_fetch_data"
        self._attr_name = "Fetch Data"
        self._attr_icon = "mdi:download"
        
        self._attr_has_entity_name = True
#        self._attr_translation_key = "fetch_data"
#        self._attr_name = None

        # Set name based on language
        language = hass.config.language
        if language == "sk":
            self._attr_name = "Import z OKTE"
        else:
            self._attr_name = "Import from OKTE"




    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, "okte_main")},
            "name": "OKTE - Electricity Price Monitor",
            "manufacturer": "Jozef Moravcik",
            "model": "Electricity Price Monitor",
            "sw_version": "1.0.0",
        }

    @property
    def available(self):
        """Return if button is available."""
        return DOMAIN in self.hass.data

    async def async_press(self) -> None:
        """Handle button press."""
        _LOGGER.debug("Manual OKTE data fetch triggered via button")
        
        try:
            # Get coordinator to access configuration
            coordinator = self.hass.data[DOMAIN].get("coordinator")
            if not coordinator:
                _LOGGER.error("OKTE coordinator not found")
                return
            
            # Get configuration values
            max_window_hours = coordinator._get_max_window_hours()
            min_window_hours = coordinator._get_min_window_hours()
            fetch_days = DEFAULT_FETCH_DAYS
            
            # Fetch data in executor to avoid blocking
            data = await self.hass.async_add_executor_job(
                fetch_okte_data, fetch_days, None
            )
            
            if data:
                # Calculate statistics
                statistics = await self.hass.async_add_executor_job(
                    calculate_price_statistics, data
                )
                
                # Find cheapest window
                cheapest_window = await self.hass.async_add_executor_job(
                    find_cheapest_time_window, data, min_window_hours
                )
                
                # Find most expensive window
                most_expensive_window = await self.hass.async_add_executor_job(
                    find_most_expensive_time_window, data, max_window_hours
                )
                
                # Store data
                self.hass.data[DOMAIN]["data"] = data
                self.hass.data[DOMAIN]["statistics"] = statistics
                self.hass.data[DOMAIN]["cheapest_window"] = cheapest_window
                self.hass.data[DOMAIN]["most_expensive_window"] = most_expensive_window
                self.hass.data[DOMAIN]["last_update"] = datetime.now()
                self.hass.data[DOMAIN]["connection_status"] = True  # Success
                
                _LOGGER.debug(f"Manual fetch via button completed: {len(data)} records")
                
                # Fire event
                self.hass.bus.async_fire(f"{DOMAIN}_data_updated", {
                    "records": len(data),
                    "timestamp": datetime.now().isoformat(),
                    "manual": True,
                    "triggered_by": "button"
                })
                
                # Update all sensors after button press
                coordinator = self.hass.data[DOMAIN]["coordinator"]
                await coordinator._update_sensors()
            else:
                _LOGGER.warning("Manual fetch via button failed - no data received")
                self.hass.data[DOMAIN]["connection_status"] = False  # Failed
                
        except Exception as e:
            _LOGGER.error(f"Error in manual data fetch via button: {e}")
            self.hass.data[DOMAIN]["connection_status"] = False  # Failed