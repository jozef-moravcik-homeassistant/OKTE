"""
OKTE Integration for Home Assistant
Custom integration for fetching and analyzing electricity prices from OKTE Slovakia
*** Base classes for OKTE sensors ***

Author: Jozef Moravcik
email: jozef.moravcik@moravcik.eu
"""

import logging
from datetime import datetime, timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .okte import format_local_time

_LOGGER = logging.getLogger(__name__)


class OkteBaseSensor(SensorEntity):
    """Base class for OKTE sensors."""

    def __init__(self, hass: HomeAssistant, sensor_type: str):
        """Initialize the sensor."""
        self.hass = hass
        self._sensor_type = sensor_type
        self._attr_unique_id = f"okte_{sensor_type}"
        self._attr_has_entity_name = True
        
        # Listen for data updates
        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_data_updated",
                self._handle_data_update
            )
        )
        
    async def _handle_data_update(self, event):
        """Handle data update event."""
        _LOGGER.debug(f"Sensor {self._attr_unique_id} received data update")
        self.async_write_ha_state()
        
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
        """Return if sensor is available."""
        # All sensors are available if domain data exists
        return DOMAIN in self.hass.data

    def _get_okte_data(self):
        """Get OKTE data from hass.data."""
        if DOMAIN not in self.hass.data:
            return None
        return self.hass.data[DOMAIN].get("data", [])

    def _get_statistics(self):
        """Get statistics from hass.data."""
        if DOMAIN not in self.hass.data:
            return None
        return self.hass.data[DOMAIN].get("statistics", {})

    def _get_cheapest_window(self):
        """Get cheapest window from hass.data."""
        if DOMAIN not in self.hass.data:
            return None
        return self.hass.data[DOMAIN].get("cheapest_window", {})

    def _get_most_expensive_window(self):
        """Get most expensive window from hass.data."""
        if DOMAIN not in self.hass.data:
            return None
        return self.hass.data[DOMAIN].get("most_expensive_window", {})

    def _get_today_statistics(self):
        """Get statistics for today only."""
        data = self._get_okte_data()
        if not data:
            return None
        
        # Get today's date
        today = datetime.now().date()
        
        # Filter data for today only
        today_data = []
        for record in data:
            try:
                if record.get('deliveryStart'):
                    delivery_time = datetime.fromisoformat(record['deliveryStart'].replace('Z', '+00:00'))
                    # Convert to local time for date comparison
                    try:
                        import zoneinfo
                        ha_timezone = self.hass.config.time_zone
                        tz = zoneinfo.ZoneInfo(ha_timezone)
                        delivery_local = delivery_time.astimezone(tz)
                    except ImportError:
                        # Fallback for older Python versions
                        delivery_local = delivery_time + timedelta(hours=2)  # CET/CEST offset
                    
                    if delivery_local.date() == today:
                        today_data.append(record)
            except:
                continue
        
        if not today_data:
            return {
                'min_price': None,
                'max_price': None,
                'min_record': None,
                'max_record': None,
                'count': 0
            }
        
        # Calculate today's statistics
        valid_prices = [record for record in today_data if record['price'] is not None]
        
        if not valid_prices:
            return {
                'min_price': None,
                'max_price': None,
                'min_record': None,
                'max_record': None,
                'count': 0
            }
        
        prices = [record['price'] for record in valid_prices]
        min_price = min(prices)
        max_price = max(prices)
        
        min_record = next(record for record in valid_prices if record['price'] == min_price)
        max_record = next(record for record in valid_prices if record['price'] == max_price)
        
        return {
            'min_price': min_price,
            'max_price': max_price,
            'min_record': min_record,
            'max_record': max_record,
            'count': len(valid_prices)
        }

    def _filter_data_by_date(self, target_date):
        """Filter data for specific date."""
        data = self._get_okte_data()
        if not data:
            return []
        
        filtered_data = []
        for record in data:
            try:
                if record.get('deliveryStart'):
                    delivery_time = datetime.fromisoformat(record['deliveryStart'].replace('Z', '+00:00'))
                    # Convert to local time for date comparison
                    try:
                        import zoneinfo
                        ha_timezone = self.hass.config.time_zone
                        tz = zoneinfo.ZoneInfo(ha_timezone)
                        delivery_local = delivery_time.astimezone(tz)
                    except ImportError:
                        # Fallback for older Python versions
                        delivery_local = delivery_time + timedelta(hours=2)  # CET/CEST offset
                    
                    if delivery_local.date() == target_date:
                        filtered_data.append(record)
            except:
                continue
        
        return filtered_data