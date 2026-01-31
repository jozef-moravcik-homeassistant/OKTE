"""
OKTE Integration for Home Assistant
Custom integration for fetching and analyzing electricity prices from OKTE Slovakia
*** Analysis sensors for OKTE integration - Time Windows ***

Author: Jozef Moravcik
email: jozef.moravcik@moravcik.eu
"""

import logging
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant

from .base import OkteBaseSensor
from .okte import format_local_time

_LOGGER = logging.getLogger(__name__)


class OkteMostExpensiveTimeWindowSensor(OkteBaseSensor):
    """Sensor - Najdrahšie časové okno"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "most_expensive_time_window")
        self._attr_name = "Most Expensive Time Window"
        self._attr_icon = "mdi:clock-time-four"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_native_unit_of_measurement = f"{CURRENCY_EURO}/MWh"

    @property
    def native_value(self):
        """Return the average price of most expensive time window."""
        most_expensive_window = self._get_most_expensive_window()
        if not most_expensive_window or not most_expensive_window.get('found'):
            return None
        return most_expensive_window.get('found')

    @property
    def available(self):
        """Return if sensor is available."""
        most_expensive_window = self._get_most_expensive_window()
        return most_expensive_window is not None

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        most_expensive_window = self._get_most_expensive_window()
        
        if not most_expensive_window:
            return {
                'found': False,
                'message': 'No data available',
                'start_time': None,
                'end_time': None,
                'window_hours': None,
                'min_price': None,
                'max_price': None,
                'avg_price': None,
                'records': []
            }
        
        if not most_expensive_window.get('found'):
            return {
                'found': False,
                'message': most_expensive_window.get('message', 'Window not found'),
                'start_time': None,
                'end_time': None,
                'window_hours': most_expensive_window.get('window_hours'),
                'min_price': None,
                'max_price': None,
                'avg_price': None,
                'records': []
            }
        
        # Priprav records s lokálnymi časmi
        formatted_records = []
        if most_expensive_window.get('records'):
            for record in most_expensive_window['records']:
                formatted_record = {
                    'price': record.get('price'),
                    'period': record.get('period'),
                    'delivery_start': record.get('deliveryStart'),
                    'delivery_end': record.get('deliveryEnd'),
                    'hour_start': record.get('HourStartCET'),
                    'hour_end': record.get('HourEndCET'),
                    'date': record.get('deliveryDayCET'),
                    'time_local': format_local_time(record.get('deliveryStart'), '%d.%m.%Y %H:%M')
                }
                formatted_records.append(formatted_record)
        
        # Convert start and end times to local timezone datetime objects
        start_time_local_dt = None
        end_time_local_dt = None
        
        if most_expensive_window.get('start_time'):
            try:
                start_time_utc = datetime.fromisoformat(most_expensive_window['start_time'].replace('Z', '+00:00'))
                try:
                    import zoneinfo
                    ha_timezone = self.hass.config.time_zone
                    tz = zoneinfo.ZoneInfo(ha_timezone)
                    start_time_local_dt = start_time_utc.astimezone(tz)
                except ImportError:
                    from datetime import timedelta, timezone
                    local_offset = timedelta(hours=2)  # CET/CEST
                    tz_offset = timezone(local_offset)
                    start_time_local_dt = start_time_utc.astimezone(tz_offset)
            except:
                pass
        
        if most_expensive_window.get('end_time'):
            try:
                end_time_utc = datetime.fromisoformat(most_expensive_window['end_time'].replace('Z', '+00:00'))
                try:
                    import zoneinfo
                    ha_timezone = self.hass.config.time_zone
                    tz = zoneinfo.ZoneInfo(ha_timezone)
                    end_time_local_dt = end_time_utc.astimezone(tz)
                except ImportError:
                    from datetime import timedelta, timezone
                    local_offset = timedelta(hours=2)  # CET/CEST
                    tz_offset = timezone(local_offset)
                    end_time_local_dt = end_time_utc.astimezone(tz_offset)
            except:
                pass

        # Get original UTC times from the first and last record
        start_time_utc_str = None
        end_time_utc_str = None
        
        if most_expensive_window.get('records'):
            records = most_expensive_window['records']
            if len(records) > 0:
                start_time_utc_str = records[0].get('deliveryStart')  # Original UTC from API
                end_time_utc_str = records[-1].get('deliveryEnd')     # Original UTC from API

        return {
            'found': True,
            'start_time': start_time_local_dt,
            'end_time': end_time_local_dt,
            'start_time_UTC': f"UTC: {start_time_utc_str}" if start_time_utc_str else None,
            'end_time_UTC': f"UTC: {end_time_utc_str}" if end_time_utc_str else None,
            'start_time_local': start_time_local_dt.strftime('%d.%m.%Y %H:%M') if start_time_local_dt else None,
            'end_time_local': end_time_local_dt.strftime('%d.%m.%Y %H:%M') if end_time_local_dt else None,
            'window_hours': most_expensive_window.get('window_hours'),
            'min_price': most_expensive_window.get('min_price'),
            'max_price': most_expensive_window.get('max_price'),
            'avg_price': most_expensive_window.get('avg_price'),
            'records': formatted_records
        }

    def set_window_hours(self, max_window_hours: int):
        """Set custom window hours for analysis."""
        from .const import DOMAIN
        from .okte import find_most_expensive_time_window
        
        if DOMAIN not in self.hass.data:
            _LOGGER.debug("OKTE domain data not available")
            return False
        
        try:
            # Get current data
            data = self.hass.data[DOMAIN].get("data", [])
            if not data:
                _LOGGER.debug("No OKTE data available for analysis")
                return False
            
            # Calculate new most expensive window with custom hours
            most_expensive_window = find_most_expensive_time_window(data, max_window_hours)
            
            # Update stored window
            self.hass.data[DOMAIN]["most_expensive_window"] = most_expensive_window
            
            # Trigger sensor update
            self.async_write_ha_state()
            
            _LOGGER.debug(f"Updated most expensive time window analysis with {max_window_hours} hours")
            return True
            
        except Exception as e:
            _LOGGER.error(f"Error setting window hours for most expensive window: {e}")
            return False

class OkteMostExpensiveTimeWindowTodaySensor(OkteBaseSensor):
    """Sensor - Najdrahšie časové okno dnes"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "most_expensive_time_window_today")
        self._attr_name = "Most Expensive Time Window Today"
        self._attr_icon = "mdi:clock-time-four"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_native_unit_of_measurement = f"{CURRENCY_EURO}/MWh"

    @property
    def native_value(self):
        """Return the average price of most expensive time window today."""
        today_window = self._get_most_expensive_window_today()
        if not today_window or not today_window.get('found'):
            return None
        return today_window.get('found')

    @property
    def available(self):
        """Return if sensor is available."""
        return True  # Sensor is always available, but found can be false

    def _get_most_expensive_window_today(self):
        """Get most expensive window for today only."""
        from datetime import datetime
        from .okte import find_most_expensive_time_window
        from .const import DOMAIN
        
        # Get today's data
        today_data = self._filter_data_by_date(datetime.now().date())
        
        if not today_data:
            return {
                'found': False,
                'message': 'No data available for today'
            }
        
        # Get window hours from config
        max_window_hours = 5  # default
        if DOMAIN in self.hass.data:
            coordinator = self.hass.data[DOMAIN].get("coordinator")
            if coordinator:
                max_window_hours = coordinator._get_max_window_hours()
        
        # Find most expensive window in today's data
        return find_most_expensive_time_window(today_data, max_window_hours)

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        today_window = self._get_most_expensive_window_today()
        
        if not today_window:
            return {
                'found': False,
                'message': 'No data available for today',
                'start_time': None,
                'end_time': None,
                'window_hours': None,
                'min_price': None,
                'max_price': None,
                'avg_price': None,
                'records': []
            }
        
        if not today_window.get('found'):
            return {
                'found': False,
                'message': today_window.get('message', 'Window not found for today'),
                'start_time': None,
                'end_time': None,
                'window_hours': today_window.get('window_hours'),
                'min_price': None,
                'max_price': None,
                'avg_price': None,
                'records': [],
            }
        
        # Priprav records s lokálnymi časmi
        formatted_records = []
        if today_window.get('records'):
            for record in today_window['records']:
                formatted_record = {
                    'price': record.get('price'),
                    'period': record.get('period'),
                    'delivery_start': record.get('deliveryStart'),
                    'delivery_end': record.get('deliveryEnd'),
                    'hour_start': record.get('HourStartCET'),
                    'hour_end': record.get('HourEndCET'),
                    'date': record.get('deliveryDayCET'),
                    'time_local': format_local_time(record.get('deliveryStart'), '%d.%m.%Y %H:%M')
                }
                formatted_records.append(formatted_record)
        
        # Convert start and end times to local timezone datetime objects
        start_time_local_dt = None
        end_time_local_dt = None
        
        if today_window.get('start_time'):
            try:
                start_time_utc = datetime.fromisoformat(today_window['start_time'].replace('Z', '+00:00'))
                try:
                    import zoneinfo
                    ha_timezone = self.hass.config.time_zone
                    tz = zoneinfo.ZoneInfo(ha_timezone)
                    start_time_local_dt = start_time_utc.astimezone(tz)
                except ImportError:
                    from datetime import timedelta, timezone
                    local_offset = timedelta(hours=2)  # CET/CEST
                    tz_offset = timezone(local_offset)
                    start_time_local_dt = start_time_utc.astimezone(tz_offset)
            except:
                pass
        
        if today_window.get('end_time'):
            try:
                end_time_utc = datetime.fromisoformat(today_window['end_time'].replace('Z', '+00:00'))
                try:
                    import zoneinfo
                    ha_timezone = self.hass.config.time_zone
                    tz = zoneinfo.ZoneInfo(ha_timezone)
                    end_time_local_dt = end_time_utc.astimezone(tz)
                except ImportError:
                    from datetime import timedelta, timezone
                    local_offset = timedelta(hours=2)  # CET/CEST
                    tz_offset = timezone(local_offset)
                    end_time_local_dt = end_time_utc.astimezone(tz_offset)
            except:
                pass

        # Get original UTC times from the first and last record
        start_time_utc_str = None
        end_time_utc_str = None
        
        if today_window.get('records'):
            records = today_window['records']
            if len(records) > 0:
                start_time_utc_str = records[0].get('deliveryStart')  # Original UTC from API
                end_time_utc_str = records[-1].get('deliveryEnd')     # Original UTC from API

        return {
            'found': True,
            'start_time': start_time_local_dt,
            'end_time': end_time_local_dt,
            'start_time_UTC': f"UTC: {start_time_utc_str}" if start_time_utc_str else None,
            'end_time_UTC': f"UTC: {end_time_utc_str}" if end_time_utc_str else None,
            'start_time_local': start_time_local_dt.strftime('%d.%m.%Y %H:%M') if start_time_local_dt else None,
            'end_time_local': end_time_local_dt.strftime('%d.%m.%Y %H:%M') if end_time_local_dt else None,
            'window_hours': today_window.get('window_hours'),
            'min_price': today_window.get('min_price'),
            'max_price': today_window.get('max_price'),
            'avg_price': today_window.get('avg_price'),
            'records': formatted_records
        }

    def set_window_hours(self, max_window_hours: int):
        """Set custom window hours for today's analysis."""
        try:
            # Trigger sensor update with new window hours
            self.async_write_ha_state()
            _LOGGER.debug(f"Updated today's most expensive time window analysis with {max_window_hours} hours")
            return True
        except Exception as e:
            _LOGGER.error(f"Error setting window hours for today's most expensive window: {e}")
            return False

class OkteMostExpensiveTimeWindowTomorrowSensor(OkteBaseSensor):
    """Sensor - Najdrahšie časové okno zajtra"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "most_expensive_time_window_tomorrow")
        self._attr_name = "Most Expensive Time Window Tomorrow"
        self._attr_icon = "mdi:clock-time-four"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_native_unit_of_measurement = f"{CURRENCY_EURO}/MWh"

    @property
    def native_value(self):
        """Return the average price of most expensive time window tomorrow."""
        tomorrow_window = self._get_most_expensive_window_tomorrow()
        if not tomorrow_window or not tomorrow_window.get('found'):
            return None
        return tomorrow_window.get('found')

    @property
    def available(self):
        """Return if sensor is available."""
        return True  # Sensor is always available, but found can be false

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

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        tomorrow_window = self._get_most_expensive_window_tomorrow()
        
        if not tomorrow_window:
            return {
                'found': False,
                'message': 'No data available for tomorrow',
                'start_time': None,
                'end_time': None,
                'window_hours': None,
                'min_price': None,
                'max_price': None,
                'avg_price': None,
                'records': [],
            }
        
        if not tomorrow_window.get('found'):
            return {
                'found': False,
                'message': tomorrow_window.get('message', 'Window not found for tomorrow'),
                'start_time': None,
                'end_time': None,
                'window_hours': tomorrow_window.get('window_hours'),
                'min_price': None,
                'max_price': None,
                'avg_price': None,
                'records': [],
            }
        
        # Priprav records s lokálnymi časmi
        formatted_records = []
        if tomorrow_window.get('records'):
            for record in tomorrow_window['records']:
                formatted_record = {
                    'price': record.get('price'),
                    'period': record.get('period'),
                    'delivery_start': record.get('deliveryStart'),
                    'delivery_end': record.get('deliveryEnd'),
                    'hour_start': record.get('HourStartCET'),
                    'hour_end': record.get('HourEndCET'),
                    'date': record.get('deliveryDayCET'),
                    'time_local': format_local_time(record.get('deliveryStart'), '%d.%m.%Y %H:%M')
                }
                formatted_records.append(formatted_record)
        
        # Convert start and end times to local timezone datetime objects
        start_time_local_dt = None
        end_time_local_dt = None
        
        if tomorrow_window.get('start_time'):
            try:
                start_time_utc = datetime.fromisoformat(tomorrow_window['start_time'].replace('Z', '+00:00'))
                try:
                    import zoneinfo
                    ha_timezone = self.hass.config.time_zone
                    tz = zoneinfo.ZoneInfo(ha_timezone)
                    start_time_local_dt = start_time_utc.astimezone(tz)
                except ImportError:
                    from datetime import timedelta, timezone
                    local_offset = timedelta(hours=2)  # CET/CEST
                    tz_offset = timezone(local_offset)
                    start_time_local_dt = start_time_utc.astimezone(tz_offset)
            except:
                pass
        
        if tomorrow_window.get('end_time'):
            try:
                end_time_utc = datetime.fromisoformat(tomorrow_window['end_time'].replace('Z', '+00:00'))
                try:
                    import zoneinfo
                    ha_timezone = self.hass.config.time_zone
                    tz = zoneinfo.ZoneInfo(ha_timezone)
                    end_time_local_dt = end_time_utc.astimezone(tz)
                except ImportError:
                    from datetime import timedelta, timezone
                    local_offset = timedelta(hours=2)  # CET/CEST
                    tz_offset = timezone(local_offset)
                    end_time_local_dt = end_time_utc.astimezone(tz_offset)
            except:
                pass

        # Get original UTC times from the first and last record
        start_time_utc_str = None
        end_time_utc_str = None
        
        if tomorrow_window.get('records'):
            records = tomorrow_window['records']
            if len(records) > 0:
                start_time_utc_str = records[0].get('deliveryStart')  # Original UTC from API
                end_time_utc_str = records[-1].get('deliveryEnd')     # Original UTC from API

        return {
            'found': True,
            'start_time': start_time_local_dt,
            'end_time': end_time_local_dt,
            'start_time_UTC': f"UTC: {start_time_utc_str}" if start_time_utc_str else None,
            'end_time_UTC': f"UTC: {end_time_utc_str}" if end_time_utc_str else None,
            'start_time_local': start_time_local_dt.strftime('%d.%m.%Y %H:%M') if start_time_local_dt else None,
            'end_time_local': end_time_local_dt.strftime('%d.%m.%Y %H:%M') if end_time_local_dt else None,
            'window_hours': tomorrow_window.get('window_hours'),
            'min_price': tomorrow_window.get('min_price'),
            'max_price': tomorrow_window.get('max_price'),
            'avg_price': tomorrow_window.get('avg_price'),
            'records': formatted_records
        }

    def set_window_hours(self, max_window_hours: int):
        """Set custom window hours for tomorrow's analysis."""
        try:
            # Trigger sensor update with new window hours
            self.async_write_ha_state()
            _LOGGER.debug(f"Updated tomorrow's most expensive time window analysis with {max_window_hours} hours")
            return True
        except Exception as e:
            _LOGGER.error(f"Error setting window hours for tomorrow's most expensive window: {e}")
            return False