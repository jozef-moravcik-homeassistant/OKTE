"""
OKTE Integration for Home Assistant
Custom integration for fetching and analyzing electricity prices from OKTE Slovakia
*** Specific sensors for OKTE integration ***
*** Prices Tomorrow only ***

Author: Jozef Moravcik
email: jozef.moravcik@moravcik.eu
"""

import logging
from datetime import datetime, timedelta, timezone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant

from .base import OkteBaseSensor
from .okte import format_local_time

_LOGGER = logging.getLogger(__name__)


class OkteHourlyPriceTomorrowSensor(OkteBaseSensor):
    """Sensor - Hodinové ceny - zajtrajšie z posledného načítania z OKTE"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "hourly_prices_tomorrow")
        self._attr_name = "Hourly Prices Tomorrow"
        self._attr_icon = "mdi:finance"
#        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = f"{CURRENCY_EURO}/MWh"

    @property
    def native_value(self):
        """Return average price for tomorrow."""
        tomorrow = datetime.now().date() + timedelta(days=1)
        tomorrow_data = self._filter_data_by_date(tomorrow)
        
        if not tomorrow_data:
            return None
        
        valid_prices = [r['price'] for r in tomorrow_data if r.get('price') is not None]
        return round(sum(valid_prices) / len(valid_prices), 2) if valid_prices else None

    @property
    def extra_state_attributes(self):
        """Return tomorrow's hourly data."""
        tomorrow = datetime.now().date() + timedelta(days=1)
        tomorrow_data = self._filter_data_by_date(tomorrow)
        
        if not tomorrow_data:
            return {'hourly_data': [], 'total_hours': 0, 'available': False}
        
        # Priprav zajtrajšie hodinové údaje
        hourly_data = []
        valid_records = [record for record in tomorrow_data if record.get('price') is not None]
        valid_records.sort(key=lambda x: x.get('deliveryStart', ''))
        
        for record in valid_records:
            hourly_entry = {
                'time': record['deliveryStart'],
                'price': record['price'],
                'hour_start': record.get('HourStartCET'),
                'hour_end': record.get('HourEndCET'),
                'hour_label': f"{record.get('HourStartCET', '')}-{record.get('HourEndCET', '')}"
            }
            hourly_data.append(hourly_entry)
        
        prices = [entry['price'] for entry in hourly_data]
        
        return {
            'hourly_data': hourly_data,
            'total_hours': len(hourly_data),
            'available': len(hourly_data) > 0,
            'prices_list': prices,
            'min_price': min(prices) if prices else None,
            'max_price': max(prices) if prices else None,
            'avg_price': round(sum(prices) / len(prices), 2) if prices else None
        }

class OkteMinPriceTomorrowSensor(OkteBaseSensor):
    """Sensor - Zajtrajšia Minimálna cena"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "minimum_price_tomorrow")
        self._attr_name = "Minimum Price Tomorrow"
        self._attr_icon = "mdi:trending-down"
#        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = f"{CURRENCY_EURO}/MWh"

    @property
    def native_value(self):
        """Return the minimum price for tomorrow."""
        tomorrow = datetime.now().date() + timedelta(days=1)
        tomorrow_data = self._filter_data_by_date(tomorrow)
        
        if not tomorrow_data:
            return None
        
        valid_prices = [r['price'] for r in tomorrow_data if r.get('price') is not None]
        return min(valid_prices) if valid_prices else None

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        tomorrow = datetime.now().date() + timedelta(days=1)
        tomorrow_data = self._filter_data_by_date(tomorrow)
        
        if not tomorrow_data:
            return {'available': False}
        
        valid_records = [record for record in tomorrow_data if record.get('price') is not None]
        if not valid_records:
            return {'available': False}
        
        prices = [record['price'] for record in valid_records]
        min_price = min(prices)
        min_record = next(record for record in valid_records if record['price'] == min_price)
        
        return {
            'available': True,
            'time': format_local_time(min_record.get('deliveryStart'), '%d.%m.%Y %H:%M'),
            'period': min_record.get('period'),
            'hour_start': format_local_time(min_record.get('deliveryStart'), '%H:%M'),
            'hour_end': format_local_time(min_record.get('deliveryEnd'), '%H:%M'),
        }

class OkteMinPriceTimeTomorrowSensor(OkteBaseSensor):
    """Sensor - Čas kedy je zajtrajšia cena minimálna"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "minimum_price_tomorrow_time")
        self._attr_name = "Minimum Price Time Tomorrow"
        self._attr_icon = "mdi:clock-time-eight"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        """Return the time of minimum price tomorrow."""
        tomorrow = datetime.now().date() + timedelta(days=1)
        tomorrow_data = self._filter_data_by_date(tomorrow)
        
        if not tomorrow_data:
            return None
        
        valid_records = [record for record in tomorrow_data if record.get('price') is not None]
        if not valid_records:
            return None
        
        prices = [record['price'] for record in valid_records]
        min_price = min(prices)
        min_record = next(record for record in valid_records if record['price'] == min_price)
        
        if min_record.get('deliveryStart'):
            try:
                delivery_time = datetime.fromisoformat(min_record['deliveryStart'].replace('Z', '+00:00'))
                # Convert to local time with timezone
                try:
                    import zoneinfo
                    ha_timezone = self.hass.config.time_zone
                    tz = zoneinfo.ZoneInfo(ha_timezone)
                    return delivery_time.astimezone(tz)
                except ImportError:
                    local_offset = timedelta(hours=2)  # CET/CEST
                    tz_offset = timezone(local_offset)
                    return delivery_time.astimezone(tz_offset)
            except:
                pass
        return None

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        tomorrow = datetime.now().date() + timedelta(days=1)
        tomorrow_data = self._filter_data_by_date(tomorrow)
        
        if not tomorrow_data:
            return {'available': False}
        
        valid_records = [record for record in tomorrow_data if record.get('price') is not None]
        if not valid_records:
            return {'available': False}
        
        prices = [record['price'] for record in valid_records]
        min_price = min(prices)
        min_record = next(record for record in valid_records if record['price'] == min_price)
        
        return {
            'available': True,
            'price': min_price,
            'period': min_record.get('period'),
            'hour_start': format_local_time(min_record.get('deliveryStart'), '%H:%M'),
            'hour_end': format_local_time(min_record.get('deliveryEnd'), '%H:%M'),
        }

class OkteMaxPriceTomorrowSensor(OkteBaseSensor):
    """Sensor - Zajtrajšia Maximálna cena"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "maximum_price_tomorrow")
        self._attr_name = "Maximum Price Tomorrow"
        self._attr_icon = "mdi:trending-up"
#        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = f"{CURRENCY_EURO}/MWh"

    @property
    def native_value(self):
        """Return the maximum price for tomorrow."""
        tomorrow = datetime.now().date() + timedelta(days=1)
        tomorrow_data = self._filter_data_by_date(tomorrow)
        
        if not tomorrow_data:
            return None
        
        valid_prices = [r['price'] for r in tomorrow_data if r.get('price') is not None]
        return max(valid_prices) if valid_prices else None

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        tomorrow = datetime.now().date() + timedelta(days=1)
        tomorrow_data = self._filter_data_by_date(tomorrow)
        
        if not tomorrow_data:
            return {'available': False}
        
        valid_records = [record for record in tomorrow_data if record.get('price') is not None]
        if not valid_records:
            return {'available': False}
        
        prices = [record['price'] for record in valid_records]
        max_price = max(prices)
        max_record = next(record for record in valid_records if record['price'] == max_price)
        
        return {
            'available': True,
            'time': format_local_time(max_record.get('deliveryStart'), '%d.%m.%Y %H:%M'),
            'period': max_record.get('period'),
            'hour_start': format_local_time(max_record.get('deliveryStart'), '%H:%M'),
            'hour_end': format_local_time(max_record.get('deliveryEnd'), '%H:%M'),
        }

class OkteMaxPriceTimeTomorrowSensor(OkteBaseSensor):
    """Sensor - Čas kedy je zajtrajšia cena maximálna"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "maximum_price_tomorrow_time")
        self._attr_name = "Maximum Price Time Tomorrow"
        self._attr_icon = "mdi:clock-time-four"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        """Return the time of maximum price tomorrow."""
        tomorrow = datetime.now().date() + timedelta(days=1)
        tomorrow_data = self._filter_data_by_date(tomorrow)
        
        if not tomorrow_data:
            return None
        
        valid_records = [record for record in tomorrow_data if record.get('price') is not None]
        if not valid_records:
            return None
        
        prices = [record['price'] for record in valid_records]
        max_price = max(prices)
        max_record = next(record for record in valid_records if record['price'] == max_price)
        
        if max_record.get('deliveryStart'):
            try:
                delivery_time = datetime.fromisoformat(max_record['deliveryStart'].replace('Z', '+00:00'))
                # Convert to local time with timezone
                try:
                    import zoneinfo
                    ha_timezone = self.hass.config.time_zone
                    tz = zoneinfo.ZoneInfo(ha_timezone)
                    return delivery_time.astimezone(tz)
                except ImportError:
                    local_offset = timedelta(hours=2)  # CET/CEST
                    tz_offset = timezone(local_offset)
                    return delivery_time.astimezone(tz_offset)
            except:
                pass
        return None

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        tomorrow = datetime.now().date() + timedelta(days=1)
        tomorrow_data = self._filter_data_by_date(tomorrow)
        
        if not tomorrow_data:
            return {'available': False}
        
        valid_records = [record for record in tomorrow_data if record.get('price') is not None]
        if not valid_records:
            return {'available': False}
        
        prices = [record['price'] for record in valid_records]
        max_price = max(prices)
        max_record = next(record for record in valid_records if record['price'] == max_price)
        
        return {
            'available': True,
            'price': max_price,
            'period': max_record.get('period'),
            'hour_start': format_local_time(max_record.get('deliveryStart'), '%H:%M'),
            'hour_end': format_local_time(max_record.get('deliveryEnd'), '%H:%M'),
        }