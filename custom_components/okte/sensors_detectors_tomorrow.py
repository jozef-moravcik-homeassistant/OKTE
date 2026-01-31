"""
OKTE Integration for Home Assistant
Custom integration for fetching and analyzing electricity prices from OKTE Slovakia
*** Detector sensors for OKTE integration - Time Window Detectors for Tomorrow's data only ***

Author: Jozef Moravcik
email: jozef.moravcik@moravcik.eu
"""

import logging
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change
from homeassistant.const import STATE_ON, STATE_OFF

from .base import OkteBaseSensor
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class OkteCheapestTimeWindowTomorrowDetectorSensor(OkteBaseSensor):
    """Sensor - Detektor najlacnejšieho časového okna pre zajtrajšie dáta"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "cheapest_time_window_tomorrow_detector")
        self._attr_name = "Cheapest Time Window Tomorrow Detector"
        self._attr_icon = "mdi:clock-check"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = ["true", "false"]
        self._state = False
        
        # Schedule hourly checks at the top of each hour (00:00)
        async_track_time_change(
            self.hass, 
            self._hourly_update,
            minute=0,  # Spustí sa vždy o 0. minúte
            second=0   # a 0. sekunde každej hodiny
        )
        
        # Listen for force update events
        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_detectors_update",
                self._handle_force_update
            )
        )
        
        # Listen for force update events (alternative)
        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_force_update",
                self._handle_force_update
            )
        )

    @property
    def native_value(self):
        """Return true/false state."""
        return True if self._state else False

    @property
    def state(self):
        """Return true/false state."""
        return True if self._state else False

    @property
    def is_on(self):
        """Return True if currently in cheapest time window."""
        return self._state

    async def _handle_force_update(self, event):
        """Handle force update event for immediate detector refresh."""
        _LOGGER.debug("Force update received for cheapest time window tomorrow detector")
        self._update_detector_state()
        self.async_write_ha_state()

    async def _hourly_update(self, now):
        """Update sensor state every hour at the top of the hour."""
        _LOGGER.debug("Hourly update triggered for cheapest time window tomorrow detector")
        self._update_detector_state()
        self.async_write_ha_state()

    async def _handle_data_update(self, event):
        """Handle data update event."""
        _LOGGER.debug("Data update received for cheapest time window tomorrow detector")
        self._update_detector_state()
        await super()._handle_data_update(event)

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Initial state update
        self._update_detector_state()

    def _get_cheapest_window_tomorrow(self):
        """Get cheapest window for tomorrow only."""
        from datetime import datetime, timedelta
        from .okte import find_cheapest_time_window
        from .const import DOMAIN
        
        # Get tomorrow's data
        tomorrow = datetime.now().date() + timedelta(days=1)
        tomorrow_data = self._filter_data_by_date(tomorrow)
        
        if not tomorrow_data:
            return {
                'found': False,
                'message': 'No data available for tomorrow'
            }
        
        # Get window hours from config
        min_window_hours = 5  # default
        if DOMAIN in self.hass.data:
            coordinator = self.hass.data[DOMAIN].get("coordinator")
            if coordinator:
                min_window_hours = coordinator._get_min_window_hours()
        
        # Find cheapest window in tomorrow's data
        return find_cheapest_time_window(tomorrow_data, min_window_hours)

    def _update_detector_state(self):
        """Update the detector state based on current time and cheapest window for tomorrow."""
        try:
            cheapest_window = self._get_cheapest_window_tomorrow()
            
            if not cheapest_window or not cheapest_window.get('found'):
                self._state = False
                return
            
            start_time_attr = cheapest_window.get('start_time')
            end_time_attr = cheapest_window.get('end_time')
            
            if not start_time_attr or not end_time_attr:
                self._state = False
                return
            
            # Parse start and end times
            try:
                if isinstance(start_time_attr, datetime):
                    start_time = start_time_attr
                else:
                    start_time = datetime.fromisoformat(start_time_attr.replace('Z', '+00:00'))
                
                if isinstance(end_time_attr, datetime):
                    end_time = end_time_attr
                else:
                    end_time = datetime.fromisoformat(end_time_attr.replace('Z', '+00:00'))
                
                # Convert to local time for comparison
                try:
                    import zoneinfo
                    ha_timezone = self.hass.config.time_zone
                    tz = zoneinfo.ZoneInfo(ha_timezone)
                    start_time_local = start_time.astimezone(tz).replace(tzinfo=None)
                    end_time_local = end_time.astimezone(tz).replace(tzinfo=None)
                except ImportError:
                    from datetime import timedelta
                    start_time_local = start_time.replace(tzinfo=None) + timedelta(hours=2)
                    end_time_local = end_time.replace(tzinfo=None) + timedelta(hours=2)
                
                # Get current time
                now = datetime.now()
                
                # Check if current time is within the cheapest window
                self._state = start_time_local <= now < end_time_local
                
                _LOGGER.debug(f"Cheapest window detector tomorrow: {start_time_local} <= {now} < {end_time_local} = {self._state}")
                
            except Exception as e:
                _LOGGER.warning(f"Error parsing cheapest window times: {e}")
                self._state = False
                
        except Exception as e:
            _LOGGER.warning(f"Error updating cheapest window detector state: {e}")
            self._state = False

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        cheapest_window = self._get_cheapest_window_tomorrow()
        
        attrs = {
            'state': self._state,
            'last_check': datetime.now().isoformat(),
        }
        
        if cheapest_window and cheapest_window.get('found'):
            attrs.update({
                'window_found': True,
                'window_start': cheapest_window.get('start_time'),
                'window_end': cheapest_window.get('end_time'),
                'avg_price': cheapest_window.get('avg_price'),
                'window_hours': cheapest_window.get('window_hours'),
            })
        else:
            attrs.update({
                'window_found': False,
                'window_start': None,
                'window_end': None,
                'avg_price': None,
                'window_hours': None,
            })
        
        return attrs


class OkteMostExpensiveTimeWindowTomorrowDetectorSensor(OkteBaseSensor):
    """Sensor - Detektor najdrahšieho časového okna zajtrajšie dáta"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "most_expensive_time_window_tomorrow_detector")
        self._attr_name = "Most Expensive Time Window Tomorrow Detector"
        self._attr_icon = "mdi:clock-check"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = ["true", "false"]
        self._state = False
        
        # Schedule hourly checks at the top of each hour (00:00)
        async_track_time_change(
            self.hass, 
            self._hourly_update,
            minute=0,  # Spustí sa vždy o 0. minúte
            second=0   # a 0. sekunde každej hodiny
        )
        
        # Listen for force update events
        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_detectors_update",
                self._handle_force_update
            )
        )
        
        # Listen for force update events (alternative)
        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_force_update",
                self._handle_force_update
            )
        )

    @property
    def native_value(self):
        """Return true/false state."""
        return True if self._state else False

    @property
    def state(self):
        """Return true/false state."""
        return True if self._state else False

    @property
    def is_on(self):
        """Return True if currently in most expensive time window."""
        return self._state

    async def _handle_force_update(self, event):
        """Handle force update event for immediate detector refresh."""
        _LOGGER.debug("Force update received for most expensive time window tomorrow detector")
        self._update_detector_state()
        self.async_write_ha_state()

    async def _hourly_update(self, now):
        """Update sensor state every hour at the top of the hour."""
        _LOGGER.debug("Hourly update triggered for most expensive time window tomorrow detector")
        self._update_detector_state()
        self.async_write_ha_state()

    async def _handle_data_update(self, event):
        """Handle data update event."""
        _LOGGER.debug("Data update received for most expensive time window tomorrow detector")
        self._update_detector_state()
        await super()._handle_data_update(event)

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Initial state update
        self._update_detector_state()

    def _get_most_expensive_window_tomorrow(self):
        """Get most expensive window for tomorrow only."""
        from datetime import datetime, timedelta
        from .okte import find_most_expensive_time_window
        from .const import DOMAIN
        
        # Get tomorrow's data
        tomorrow = datetime.now().date() + timedelta(days=1)
        tomorrow_data = self._filter_data_by_date(tomorrow)
        
        if not tomorrow_data:
            return {
                'found': False,
                'message': 'No data available for tomorrow'
            }
        
        # Get window hours from config
        max_window_hours = 5  # default
        if DOMAIN in self.hass.data:
            coordinator = self.hass.data[DOMAIN].get("coordinator")
            if coordinator:
                max_window_hours = coordinator._get_max_window_hours()
        
        # Find most expensive window in tomorrow's data
        return find_most_expensive_time_window(tomorrow_data, max_window_hours)

    def _update_detector_state(self):
        """Update the detector state based on current time and most expensive window for tomorrow."""
        try:
            most_expensive_window = self._get_most_expensive_window_tomorrow()
            
            if not most_expensive_window or not most_expensive_window.get('found'):
                self._state = False
                return
            
            start_time_attr = most_expensive_window.get('start_time')
            end_time_attr = most_expensive_window.get('end_time')
            
            if not start_time_attr or not end_time_attr:
                self._state = False
                return
            
            # Parse start and end times
            try:
                if isinstance(start_time_attr, datetime):
                    start_time = start_time_attr
                else:
                    start_time = datetime.fromisoformat(start_time_attr.replace('Z', '+00:00'))
                
                if isinstance(end_time_attr, datetime):
                    end_time = end_time_attr
                else:
                    end_time = datetime.fromisoformat(end_time_attr.replace('Z', '+00:00'))
                
                # Convert to local time for comparison
                try:
                    import zoneinfo
                    ha_timezone = self.hass.config.time_zone
                    tz = zoneinfo.ZoneInfo(ha_timezone)
                    start_time_local = start_time.astimezone(tz).replace(tzinfo=None)
                    end_time_local = end_time.astimezone(tz).replace(tzinfo=None)
                except ImportError:
                    from datetime import timedelta
                    start_time_local = start_time.replace(tzinfo=None) + timedelta(hours=2)
                    end_time_local = end_time.replace(tzinfo=None) + timedelta(hours=2)
                
                # Get current time
                now = datetime.now()
                
                # Check if current time is within the most expensive window
                self._state = start_time_local <= now < end_time_local
                
                _LOGGER.debug(f"Most expensive window detector tomorrow: {start_time_local} <= {now} < {end_time_local} = {self._state}")
                
            except Exception as e:
                _LOGGER.warning(f"Error parsing most expensive window times: {e}")
                self._state = False
                
        except Exception as e:
            _LOGGER.warning(f"Error updating most expensive window detector state: {e}")
            self._state = False

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        most_expensive_window = self._get_most_expensive_window_tomorrow()
        
        attrs = {
            'state': self._state,
            'last_check': datetime.now().isoformat(),
        }
        
        if most_expensive_window and most_expensive_window.get('found'):
            attrs.update({
                'window_found': True,
                'window_start': most_expensive_window.get('start_time'),
                'window_end': most_expensive_window.get('end_time'),
                'avg_price': most_expensive_window.get('avg_price'),
                'window_hours': most_expensive_window.get('window_hours'),
            })
        else:
            attrs.update({
                'window_found': False,
                'window_start': None,
                'window_end': None,
                'avg_price': None,
                'window_hours': None,
            })
        
        return attrs