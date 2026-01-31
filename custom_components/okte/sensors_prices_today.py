"""
OKTE Integration for Home Assistant
Custom integration for fetching and analyzing electricity prices from OKTE Slovakia
*** Specific sensors for OKTE integration ***
*** Prices Today only ***

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


class OkteHourlyPriceTodaySensor(OkteBaseSensor):
    """Sensor - Hodinové ceny - dnešné z posledného načítania z OKTE"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "hourly_prices_today")
        self._attr_name = "Hourly Prices Today"
        self._attr_icon = "mdi:finance"
#        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = f"{CURRENCY_EURO}/MWh"

    @property
    def native_value(self):
        """Return current price if it's today."""
        today_data = self._filter_data_by_date(datetime.now().date())
        if not today_data:
            return None
        
        # Nájdi aktuálnu cenu pre dnes
        now = datetime.now()
        for record in today_data:
            try:
                if record.get('deliveryStart') and record.get('deliveryEnd'):
                    delivery_start = datetime.fromisoformat(record['deliveryStart'].replace('Z', '+00:00'))
                    delivery_end = datetime.fromisoformat(record['deliveryEnd'].replace('Z', '+00:00'))
                    
                    try:
                        import zoneinfo
                        ha_timezone = self.hass.config.time_zone
                        tz = zoneinfo.ZoneInfo(ha_timezone)
                        delivery_start_local = delivery_start.astimezone(tz).replace(tzinfo=None)
                        delivery_end_local = delivery_end.astimezone(tz).replace(tzinfo=None)
                    except ImportError:
                        from datetime import timedelta
                        delivery_start_local = delivery_start.replace(tzinfo=None) + timedelta(hours=2)
                        delivery_end_local = delivery_end.replace(tzinfo=None) + timedelta(hours=2)
                    
                    if delivery_start_local <= now < delivery_end_local:
                        return record.get('price')
            except:
                continue
        
        # Ak nie je aktuálna hodina, vráť priemer za dnes
        valid_prices = [r['price'] for r in today_data if r.get('price') is not None]
        return round(sum(valid_prices) / len(valid_prices), 2) if valid_prices else None

    @property
    def extra_state_attributes(self):
        """Return today's hourly data."""
        today_data = self._filter_data_by_date(datetime.now().date())
        if not today_data:
            return {'hourly_data': [], 'total_hours': 0}
        
        # Priprav dnešné hodinové údaje
        hourly_data = []
        valid_records = [record for record in today_data if record.get('price') is not None]
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
            'prices_list': prices,
            'min_price': min(prices) if prices else None,
            'max_price': max(prices) if prices else None,
            'avg_price': round(sum(prices) / len(prices), 2) if prices else None
        }

class OkteMinPriceTodaySensor(OkteBaseSensor):
    """Sensor - Dnešná Minimálna cena"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "minimum_price_today")
        self._attr_name = "Minimum Price Today"
        self._attr_icon = "mdi:trending-down"
#        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = f"{CURRENCY_EURO}/MWh"

    @property
    def native_value(self):
        """Return the minimum price for today."""
        today_stats = self._get_today_statistics()
        return today_stats.get('min_price') if today_stats else None

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        today_stats = self._get_today_statistics()
        if not today_stats or not today_stats.get('min_record'):
            return {}
        
        min_record = today_stats['min_record']
        return {
            "time": format_local_time(min_record.get('deliveryStart'), '%d.%m.%Y %H:%M'),
            "period": min_record.get('period'),
            "hour_start": format_local_time(min_record.get('deliveryStart'), '%H:%M'),
            "hour_end": format_local_time(min_record.get('deliveryEnd'), '%H:%M'),
        }

class OkteMinPriceTimeTodaySensor(OkteBaseSensor):
    """Sensor - Čas kedy je dnešná cena minimálna"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "minimum_price_today_time")
        self._attr_name = "Minimum Price Time Today"
        self._attr_icon = "mdi:clock-time-eight"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        """Return the time of minimum price today."""
        today_stats = self._get_today_statistics()
        if not today_stats or not today_stats.get('min_record'):
            return None
        
        min_record = today_stats['min_record']
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
                    from datetime import timedelta, timezone
                    local_offset = timedelta(hours=2)  # CET/CEST
                    tz_offset = timezone(local_offset)
                    return delivery_time.astimezone(tz_offset)
            except:
                pass
        return None

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        today_stats = self._get_today_statistics()
        if not today_stats or not today_stats.get('min_record'):
            return {}
        
        min_record = today_stats['min_record']
        return {
            'available': True,
            "price": today_stats.get('min_price'),
            "period": min_record.get('period'),
            "hour_start": format_local_time(min_record.get('deliveryStart'), '%H:%M'),
            "hour_end": format_local_time(min_record.get('deliveryEnd'), '%H:%M'),
        }

class OkteMaxPriceTodaySensor(OkteBaseSensor):
    """Sensor - Dnešná Maximálna cena"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "maximum_price_today")
        self._attr_name = "Maximum Price Today"
        self._attr_icon = "mdi:trending-up"
#        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = f"{CURRENCY_EURO}/MWh"

    @property
    def native_value(self):
        """Return the maximum price for today."""
        today_stats = self._get_today_statistics()
        return today_stats.get('max_price') if today_stats else None

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        today_stats = self._get_today_statistics()
        if not today_stats or not today_stats.get('max_record'):
            return {}
        
        max_record = today_stats['max_record']
        return {
            "time": format_local_time(max_record.get('deliveryStart'), '%d.%m.%Y %H:%M'),
            "period": max_record.get('period'),
            "hour_start": format_local_time(max_record.get('deliveryStart'), '%H:%M'),
            "hour_end": format_local_time(max_record.get('deliveryEnd'), '%H:%M'),
        }

class OkteMaxPriceTimeTodaySensor(OkteBaseSensor):
    """Sensor - Čas kedy je dnešná cena maximálna"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "maximum_price_today_time")
        self._attr_name = "Maximum Price Time Today"
        self._attr_icon = "mdi:clock-time-four"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        """Return the time of maximum price today."""
        today_stats = self._get_today_statistics()
        if not today_stats or not today_stats.get('max_record'):
            return None
        
        max_record = today_stats['max_record']
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
                    from datetime import timedelta, timezone
                    local_offset = timedelta(hours=2)  # CET/CEST
                    tz_offset = timezone(local_offset)
                    return delivery_time.astimezone(tz_offset)
            except:
                pass
        return None

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        today_stats = self._get_today_statistics()
        if not today_stats or not today_stats.get('max_record'):
            return {}
        
        max_record = today_stats['max_record']
        return {
            "price": today_stats.get('max_price'),
            "period": max_record.get('period'),
            "hour_start": format_local_time(max_record.get('deliveryStart'), '%H:%M'),
            "hour_end": format_local_time(max_record.get('deliveryEnd'), '%H:%M'),
        }