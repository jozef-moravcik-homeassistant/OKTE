"""
OKTE Integration for Home Assistant
Custom integration for fetching and analyzing electricity prices from OKTE Slovakia
*** Specific sensors for OKTE integration ***
*** All Prices (Today + Tomorrow) ***

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


class OkteHourlyPriceSensor(OkteBaseSensor):
    """Sensor - Hodinové ceny - všetky z posledného načítania z OKTE"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "hourly_prices")
        self._attr_name = "Hourly Prices"
        self._attr_icon = "mdi:finance"
#        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = f"{CURRENCY_EURO}/MWh"

    @property
    def native_value(self):
        """Return the current price (ako current_price sensor)."""
        data = self._get_okte_data()
        if not data:
            return None
        
        # Get current time in Home Assistant timezone
        now = datetime.now()
        
        for record in data:
            try:
                if record.get('deliveryStart') and record.get('deliveryEnd'):
                    # Parse delivery times from API (they are in UTC with Z suffix)
                    delivery_start = datetime.fromisoformat(record['deliveryStart'].replace('Z', '+00:00'))
                    delivery_end = datetime.fromisoformat(record['deliveryEnd'].replace('Z', '+00:00'))
                    
                    # Convert to local time for comparison
                    try:
                        import zoneinfo
                        ha_timezone = self.hass.config.time_zone
                        tz = zoneinfo.ZoneInfo(ha_timezone)
                        delivery_start_local = delivery_start.astimezone(tz).replace(tzinfo=None)
                        delivery_end_local = delivery_end.astimezone(tz).replace(tzinfo=None)
                    except ImportError:
                        # Fallback for older Python versions - assume 2 hour offset for CET/CEST
                        from datetime import timedelta
                        delivery_start_local = delivery_start.replace(tzinfo=None) + timedelta(hours=2)
                        delivery_end_local = delivery_end.replace(tzinfo=None) + timedelta(hours=2)
                    
                    # Check if current time falls within this delivery period
                    if delivery_start_local <= now < delivery_end_local:
                        return record.get('price')
                        
            except Exception as e:
                _LOGGER.debug(f"Error processing record for current price: {e}")
                continue
        
        return None

    @property
    def extra_state_attributes(self):
        """Return all hourly data for graphs and display."""
        data = self._get_okte_data()
        if not data:
            return {
                'hourly_data': [],
                'total_hours': 0,
                'date_range': None,
                'prices_list': [],
                'timestamps_list': [],
                'labels_list': []
            }
        
        # Hodinové údaje zoradené podľa času
        hourly_data = []
        valid_records = [record for record in data if record.get('price') is not None and record.get('deliveryStart')]
        
        # Zoraď podľa času
        valid_records.sort(key=lambda x: x.get('deliveryStart', ''))
        
        for record in valid_records:
            try:
                # Parse delivery time
                delivery_start = datetime.fromisoformat(record['deliveryStart'].replace('Z', '+00:00'))
                
                # Convert to local timezone for display
                try:
                    import zoneinfo
                    ha_timezone = self.hass.config.time_zone
                    tz = zoneinfo.ZoneInfo(ha_timezone)
                    delivery_local = delivery_start.astimezone(tz)
                except ImportError:
                    from datetime import timedelta
                    delivery_local = delivery_start + timedelta(hours=2)
                
                hourly_entry = {
                    'time': record['deliveryStart'],  # ISO formát pre grafy
                    'time_local': delivery_local.strftime('%Y-%m-%d %H:%M:%S'),  # Lokálny čas
                    'price': record['price'],
                    'period': record.get('period'),
                    'hour_start': record.get('HourStartCET'),
                    'hour_end': record.get('HourEndCET'),
                    'date': record.get('deliveryDayCET'),
                    'day_name': delivery_local.strftime('%A'),  # Názov dňa
                    'hour_label': f"{record.get('HourStartCET', '')}-{record.get('HourEndCET', '')}",
                    'timestamp': int(delivery_start.timestamp() * 1000)  # Pre ApexCharts
                }
                hourly_data.append(hourly_entry)
                
            except Exception as e:
                _LOGGER.debug(f"Error processing hourly record: {e}")
                continue
        
        # Dodatočné zoznamy pre rôzne typy grafov
        prices_list = [entry['price'] for entry in hourly_data]
        timestamps_list = [entry['time'] for entry in hourly_data]
        labels_list = [entry['hour_label'] for entry in hourly_data]
        
        # Základné štatistiky
        date_range = None
        if hourly_data:
            dates = list(set(entry['date'] for entry in hourly_data if entry['date']))
            if dates:
                dates.sort()
                date_range = f"{dates[0]} - {dates[-1]}" if len(dates) > 1 else dates[0]

        return {
            'hourly_data': hourly_data,
            'total_hours': len(hourly_data),
            'date_range': date_range,
            'prices_list': prices_list,
            'timestamps_list': timestamps_list,
            'labels_list': labels_list,
            'min_price': min(prices_list) if prices_list else None,
            'max_price': max(prices_list) if prices_list else None,
            'avg_price': round(sum(prices_list) / len(prices_list), 2) if prices_list else None
        }

class OkteCurrentPriceSensor(OkteBaseSensor):
    """Sensor - Aktuálna cena"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "current_price")
        self._attr_name = "Current Price"
        self._attr_icon = "mdi:currency-eur"
#        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = f"{CURRENCY_EURO}/MWh"

    @property
    def native_value(self):
        """Return the current price."""
        data = self._get_okte_data()
        if not data:
            return None
        
        # Get current time in Home Assistant timezone
        now = datetime.now()
        
        for record in data:
            try:
                if record.get('deliveryStart') and record.get('deliveryEnd'):
                    # Parse delivery times from API (they are in UTC with Z suffix)
                    delivery_start = datetime.fromisoformat(record['deliveryStart'].replace('Z', '+00:00'))
                    delivery_end = datetime.fromisoformat(record['deliveryEnd'].replace('Z', '+00:00'))
                    
                    # Convert to local time for comparison
                    try:
                        import zoneinfo
                        ha_timezone = self.hass.config.time_zone
                        tz = zoneinfo.ZoneInfo(ha_timezone)
                        delivery_start_local = delivery_start.astimezone(tz).replace(tzinfo=None)
                        delivery_end_local = delivery_end.astimezone(tz).replace(tzinfo=None)
                    except ImportError:
                        # Fallback for older Python versions - assume 2 hour offset for CET/CEST
                        from datetime import timedelta
                        delivery_start_local = delivery_start.replace(tzinfo=None) + timedelta(hours=2)
                        delivery_end_local = delivery_end.replace(tzinfo=None) + timedelta(hours=2)
                    
                    # Check if current time falls within this delivery period
                    if delivery_start_local <= now < delivery_end_local:
                        return record.get('price')
                        
            except Exception as e:
                _LOGGER.debug(f"Error processing record for current price: {e}")
                continue
        
        return None

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        data = self._get_okte_data()
        if not data:
            return {}
        
        # Get current time in Home Assistant timezone
        now = datetime.now()
        
        for record in data:
            try:
                if record.get('deliveryStart') and record.get('deliveryEnd'):
                    # Parse delivery times from API (they are in UTC with Z suffix)
                    delivery_start = datetime.fromisoformat(record['deliveryStart'].replace('Z', '+00:00'))
                    delivery_end = datetime.fromisoformat(record['deliveryEnd'].replace('Z', '+00:00'))
                    
                    # Convert to local time for comparison
                    try:
                        import zoneinfo
                        ha_timezone = self.hass.config.time_zone
                        tz = zoneinfo.ZoneInfo(ha_timezone)
                        delivery_start_local = delivery_start.astimezone(tz).replace(tzinfo=None)
                        delivery_end_local = delivery_end.astimezone(tz).replace(tzinfo=None)
                    except ImportError:
                        # Fallback for older Python versions - assume 2 hour offset for CET/CEST
                        from datetime import timedelta
                        delivery_start_local = delivery_start.replace(tzinfo=None) + timedelta(hours=2)
                        delivery_end_local = delivery_end.replace(tzinfo=None) + timedelta(hours=2)
                    
                    # Check if current time falls within this delivery period
                    if delivery_start_local <= now < delivery_end_local:
                        return {
                            "period": record.get('period'),
                            "delivery_start": format_local_time(record.get('deliveryStart'), '%d.%m.%Y %H:%M'),
                            "delivery_end": format_local_time(record.get('deliveryEnd'), '%H:%M'),
                        }
            except Exception as e:
                _LOGGER.debug(f"Error processing record for current price attributes: {e}")
                continue
        
        return {}

class OkteAveragePriceSensor(OkteBaseSensor):
    """Sensor - Priemerná cena"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "average_price")
        self._attr_name = "Average Price"
        self._attr_icon = "mdi:currency-eur"
#        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = f"{CURRENCY_EURO}/MWh"

    @property
    def native_value(self):
        """Return the average price."""
        stats = self._get_statistics()
        return stats.get('avg_price') if stats else None

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        stats = self._get_statistics()
        data = self._get_okte_data()
        
        if not stats or not data:
            return {}
        
        # Počítaj štatistiky pre dnešok a zajtra
        today_stats = self._get_today_statistics()
        
        from datetime import timedelta
        tomorrow = datetime.now().date() + timedelta(days=1)
        tomorrow_data = self._filter_data_by_date(tomorrow)
        tomorrow_prices = [r['price'] for r in tomorrow_data if r.get('price') is not None]
        tomorrow_avg = round(sum(tomorrow_prices) / len(tomorrow_prices), 2) if tomorrow_prices else None
        
        attrs = {
            'total_records': stats.get('count', 0),
            'today_average': None,
            'tomorrow_average': tomorrow_avg,
            'price_spread': round(stats['max_price'] - stats['min_price'], 2) if stats.get('max_price') and stats.get('min_price') else None
        }
        
        if today_stats and today_stats.get('count', 0) > 0:
            today_prices = [r['price'] for r in self._filter_data_by_date(datetime.now().date()) if r.get('price') is not None]
            attrs['today_average'] = round(sum(today_prices) / len(today_prices), 2) if today_prices else None
        
        return attrs

class OkteMinPriceSensor(OkteBaseSensor):
    """Sensor - Minimálna cena"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "min_price")
        self._attr_name = "Minimum Price"
        self._attr_icon = "mdi:trending-down"
#        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = f"{CURRENCY_EURO}/MWh"

    @property
    def native_value(self):
        """Return the minimum price."""
        stats = self._get_statistics()
        return stats.get('min_price') if stats else None

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        stats = self._get_statistics()
        if not stats or not stats.get('min_record'):
            return {}
        
        min_record = stats['min_record']
        return {
            "time": format_local_time(min_record.get('deliveryStart'), '%d.%m.%Y %H:%M'),
            "period": min_record.get('period'),
            "hour_start": format_local_time(min_record.get('deliveryStart'), '%H:%M'),
            "hour_end": format_local_time(min_record.get('deliveryEnd'), '%H:%M'),
        }

class OkteMinPriceTimeSensor(OkteBaseSensor):
    """Sensor - Čas kedy je cena minimálna"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "minimum_price_time")
        self._attr_name = "Minimum Price Time"
        self._attr_icon = "mdi:clock-time-eight"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        """Return the time of minimum price."""
        stats = self._get_statistics()
        if not stats or not stats.get('min_record'):
            return None
        
        min_record = stats['min_record']
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
        stats = self._get_statistics()
        if not stats or not stats.get('min_record'):
            return {}
        
        min_record = stats['min_record']
        return {
            "price": stats.get('min_price'),
            "period": min_record.get('period'),
            "hour_start": format_local_time(min_record.get('deliveryStart'), '%H:%M'),
            "hour_end": format_local_time(min_record.get('deliveryEnd'), '%H:%M'),
        }

class OkteMaxPriceSensor(OkteBaseSensor):
    """Sensor - Maximálna cena"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "max_price")
        self._attr_name = "Maximum Price"
        self._attr_icon = "mdi:trending-up"
#        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = f"{CURRENCY_EURO}/MWh"

    @property
    def native_value(self):
        """Return the maximum price."""
        stats = self._get_statistics()
        return stats.get('max_price') if stats else None

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        stats = self._get_statistics()
        if not stats or not stats.get('max_record'):
            return {}
        
        max_record = stats['max_record']
        return {
            "time": format_local_time(max_record.get('deliveryStart'), '%d.%m.%Y %H:%M'),
            "period": max_record.get('period'),
            "hour_start": format_local_time(max_record.get('deliveryStart'), '%H:%M'),
            "hour_end": format_local_time(max_record.get('deliveryEnd'), '%H:%M'),
        }

class OkteMaxPriceTimeSensor(OkteBaseSensor):
    """Sensor - Čas kedy je cena maximálna"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "maximum_price_time")
        self._attr_name = "Maximum Price Time"
        self._attr_icon = "mdi:clock-time-four"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        """Return the time of maximum price."""
        stats = self._get_statistics()
        if not stats or not stats.get('max_record'):
            return None
        
        max_record = stats['max_record']
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
        stats = self._get_statistics()
        if not stats or not stats.get('max_record'):
            return {}
        
        max_record = stats['max_record']
        return {
            "price": stats.get('max_price'),
            "period": max_record.get('period'),
            "hour_start": format_local_time(max_record.get('deliveryStart'), '%H:%M'),
            "hour_end": format_local_time(max_record.get('deliveryEnd'), '%H:%M'),
        }