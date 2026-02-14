from __future__ import annotations
"""The OKTE Integration"""
"""Author: Jozef Moravcik"""
"""email: jozef.moravcik@moravcik.eu"""

""" okte.py """

""" Core classes and API functions for OKTE Integration."""

from datetime import datetime, timedelta, time as dt_time
import logging
import struct
import dataclasses
import json
import asyncio
import time
import urllib.request
import urllib.error

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNKNOWN, STATE_UNAVAILABLE, STATE_OK, STATE_PROBLEM
from .const import *

LOGGER = logging.getLogger(__name__)

# Color and styling constants for HTML tables
COLOR_PRICE_HIGH = "#009000"  # Green for high prices
COLOR_PRICE_LOW = "#d08000"  # Orange for low prices
COLOR_PRICE_NEGATIVE = "#d00000"  # Red for negative prices
THRESHOLD_PRICE_HIGH = 20
THRESHOLD_PRICE_LOW = 0
BG_COLOR_TABLE_HEADER_ROW1 = "#4a90e2"
BG_COLOR_TABLE_HEADER_ROW2 = "#f2f2f2"
BG_COLOR_TABLE_HEADER_ROW3 = "#f2f2f2"
TEXT_COLOR_TABLE_HEADER_ROW1 = "#ffffff"
TEXT_COLOR_TABLE_HEADER_ROW2 = "#000000"
TEXT_COLOR_TABLE_HEADER_ROW3 = "#000000"
BORDER_COLOR_HEADER = "#a0a0a0"
BORDER_COLOR_DATA = "#a0a0a0"
PADDING_HEADER_ROW1 = "10px 10px 10px 10px"
PADDING_HEADER_ROW2 = "2px 7px 2px 7px"
PADDING_HEADER_ROW3 = "2px 7px 2px 7px"
PADDING_DATA_ROWS = "1px 7px 1px 7px"
BG_COLOR_TABLE_DATA_ROW_ODD = "#ffffff"
BG_COLOR_TABLE_DATA_ROW_EVEN = "#f5f7ff"

##############################################################################################################################
# API Functions ##############################################################################################################
##############################################################################################################################

def format_local_time(iso_time_str, format_str='%d.%m.%Y %H:%M', hass=None):
    """Format ISO time to local format with timezone conversion."""
    if not iso_time_str:
        return ""
    
    try:
        # Parse UTC time from API
        if iso_time_str.endswith('Z'):
            utc_time = datetime.fromisoformat(iso_time_str.replace('Z', '+00:00'))
        else:
            utc_time = datetime.fromisoformat(iso_time_str)
        
        # Convert to local timezone if hass is available
        if hass:
            try:
                import zoneinfo
                ha_timezone = hass.config.time_zone
                tz = zoneinfo.ZoneInfo(ha_timezone)
                local_time = utc_time.astimezone(tz)
                return local_time.strftime(format_str)
            except (ImportError, Exception) as e:
                LOGGER.debug(f"Could not use Home Assistant timezone, using UTC: {e}")
        
        # Fallback: just format as-is (naive datetime)
        dt_local = utc_time.replace(tzinfo=None)
        return dt_local.strftime(format_str)
        
    except Exception as e:
        LOGGER.warning(f"Error formatting time {iso_time_str}: {e}")
        return str(iso_time_str)


def fetch_okte_data(fetch_days=2, fetch_start_day=None, hass=None):
    """
    Fetch data from OKTE API for specified period.
    
    Args:
        fetch_days (int): Number of days to fetch (default: 2)
        fetch_start_day (str): Start date in format 'DD.MM.YYYY' or None for today (default: None)
        hass: Home Assistant instance for timezone conversion
    
    Returns:
        list: Array of objects with attributes deliveryStart, period, price
    """
    
    # Get current local time with timezone
    if hass:
        try:
            import zoneinfo
            ha_timezone = hass.config.time_zone
            tz = zoneinfo.ZoneInfo(ha_timezone)
            current_local = datetime.now(tz)
        except (ImportError, Exception):
            current_local = datetime.now()
    else:
        current_local = datetime.now()
    
    if fetch_start_day is None:
        start_date = current_local.date()
    else:
        try:
            start_date = datetime.strptime(fetch_start_day, '%d.%m.%Y').date()
        except ValueError:
            LOGGER.error(f"Invalid date format: {fetch_start_day}. Using today's date.")
            start_date = current_local.date()
    
    end_date = start_date + timedelta(days=fetch_days - 1)
    
    delivery_day_from = start_date.strftime('%Y-%m-%d')
    delivery_day_to = end_date.strftime('%Y-%m-%d')
    
    url = f"{OKTE_API_BASE_URL}?deliveryDayFrom={delivery_day_from}&deliveryDayTo={delivery_day_to}"
    
    LOGGER.info(f"OKTE API: Fetching data from: {url}")
    LOGGER.info(f"OKTE API: Period: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')} ({fetch_days} days)")
    
    try:
        request = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Home Assistant OKTE Integration',
                'Accept': 'application/json'
            }
        )
        
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            response_data = response.read().decode('utf-8')
        
        data = json.loads(response_data)
        
        result_array = []
        
        for item in data:
            # Convert deliveryStart from UTC to local time to get correct day
            delivery_start_utc = item.get('deliveryStart')
            delivery_day_local = None
            
            if delivery_start_utc and hass:
                try:
                    import zoneinfo
                    ha_timezone = hass.config.time_zone
                    tz = zoneinfo.ZoneInfo(ha_timezone)
                    
                    # Parse UTC time
                    utc_time = datetime.fromisoformat(delivery_start_utc.replace('Z', '+00:00'))
                    # Convert to local timezone
                    local_time = utc_time.astimezone(tz)
                    # Extract date in local timezone
                    delivery_day_local = local_time.strftime('%Y-%m-%d')
                except Exception as e:
                    LOGGER.debug(f"Error converting time to local: {e}")
                    delivery_day_local = item.get('deliveryDay')
            
            if not delivery_day_local:
                delivery_day_local = item.get('deliveryDay')
            
            record = {
                'deliveryStart': item.get('deliveryStart'),
                'deliveryEnd': item.get('deliveryEnd'),
                'deliveryDayCET': delivery_day_local,
                'HourStartCET': format_local_time(item.get('deliveryStart'), '%H:%M', hass),
                'HourEndCET': format_local_time(item.get('deliveryEnd'), '%H:%M', hass),
                'period': item.get('period'),
                'price': item.get('price')
            }
            result_array.append(record)
        
        LOGGER.info(f"OKTE API: Successfully fetched {len(result_array)} records from API")
        return result_array
        
    except urllib.error.HTTPError as e:
        LOGGER.error(f"OKTE API: HTTP error {e.code}: {e.reason}")
        return []
    except urllib.error.URLError as e:
        LOGGER.error(f"OKTE API: URL error: {e.reason}")
        return []
    except json.JSONDecodeError as e:
        LOGGER.error(f"OKTE API: JSON parsing error: {e}")
        return []
    except Exception as e:
        LOGGER.error(f"OKTE API: Unexpected error: {e}")
        return []


def filter_data_by_date(data, target_date):
    """Filter data for specific date."""
    if not data:
        return []
    
    target_date_str = target_date.strftime('%Y-%m-%d')
    return [record for record in data if record.get('deliveryDayCET') == target_date_str]


def calculate_price_statistics(data):
    """Calculate price statistics from fetched data."""
    if not data:
        return {
            'min_price': None,
            'max_price': None,
            'avg_price': None,
            'count': 0,
            'min_record': None,
            'max_record': None
        }
    
    valid_prices = [record for record in data if record['price'] is not None]
    
    if not valid_prices:
        return {
            'min_price': None,
            'max_price': None,
            'avg_price': None,
            'count': 0,
            'min_record': None,
            'max_record': None
        }
    
    prices = [record['price'] for record in valid_prices]
    min_price = min(prices)
    max_price = max(prices)
    avg_price = sum(prices) / len(prices)
    
    min_record = next(record for record in valid_prices if record['price'] == min_price)
    max_record = next(record for record in valid_prices if record['price'] == max_price)
    
    return {
        'min_price': min_price,
        'max_price': max_price,
        'avg_price': round(avg_price, 2),
        'count': len(valid_prices),
        'min_record': min_record,
        'max_record': max_record
    }


def find_window_cross_days(today_data, tomorrow_data, periods, time_from_str, time_to_str, find_lowest=True, hass=None):
    """
    Find time window with lowest or highest average price across two days.
    Search from today time_from to tomorrow time_to.
    
    Args:
        today_data (list): Array of objects with prices for today
        tomorrow_data (list): Array of objects with prices for tomorrow
        periods (int): Size of time window in periods
        time_from_str (str): Start time in format 'HH:MM' (applied to today)
        time_to_str (str): End time in format 'HH:MM' (applied to tomorrow)
        find_lowest (bool): True for lowest price, False for highest price
        hass: Home Assistant instance for timezone conversion
    
    Returns:
        dict: Information about found time window
    """
    # Convert periods to int
    periods = int(periods)
    
    # Parse time range
    try:
        time_from = datetime.strptime(time_from_str, '%H:%M').time()
        time_to = datetime.strptime(time_to_str, '%H:%M').time()
    except ValueError:
        return {
            'found': False,
            'message': 'Invalid time format',
            'start_time': None,
            'end_time': None,
            'periods': None,
            'min_price': None,
            'max_price': None,
            'avg_price': None,
            'records': []
        }
    
    # Filter and combine data from both days
    combined_data = []
    
    # Add today's data from time_from onwards
    for record in today_data:
        if record['price'] is not None and record['deliveryStart'] is not None and record['HourStartCET'] is not None:
            try:
                period_start_time = datetime.strptime(record['HourStartCET'], '%H:%M').time()
                if period_start_time >= time_from:
                    combined_data.append(record)
            except ValueError:
                continue
    
    # Add tomorrow's data up to time_to
    for record in tomorrow_data:
        if record['price'] is not None and record['deliveryStart'] is not None and record['HourStartCET'] is not None:
            try:
                period_start_time = datetime.strptime(record['HourStartCET'], '%H:%M').time()
                if period_start_time <= time_to:
                    combined_data.append(record)
            except ValueError:
                continue
    
    # Check if we have enough data
    if len(combined_data) < periods:
        return {
            'found': False,
            'message': f'Not enough data for {periods}-period window across both days',
            'start_time': None,
            'end_time': None,
            'periods': periods,
            'min_price': None,
            'max_price': None,
            'avg_price': None,
            'records': []
        }
    
    # Find best window using sliding window approach
    best_window = None
    best_avg_price = None
    
    for i in range(len(combined_data) - periods + 1):
        window_records = combined_data[i:i + periods]
        
        # Calculate window statistics
        prices = [r['price'] for r in window_records]
        avg_price = sum(prices) / len(prices)
        
        # Check if this is better
        if best_window is None:
            best_window = {
                'records': window_records,
                'avg_price': avg_price,
                'min_price': min(prices),
                'max_price': max(prices)
            }
            best_avg_price = avg_price
        elif find_lowest and avg_price < best_avg_price:
            best_window = {
                'records': window_records,
                'avg_price': avg_price,
                'min_price': min(prices),
                'max_price': max(prices)
            }
            best_avg_price = avg_price
        elif not find_lowest and avg_price > best_avg_price:
            best_window = {
                'records': window_records,
                'avg_price': avg_price,
                'min_price': min(prices),
                'max_price': max(prices)
            }
            best_avg_price = avg_price
    
    if best_window:
        # Get start and end times
        start_record = best_window['records'][0]
        end_record = best_window['records'][-1]
        
        # Parse delivery times
        start_utc = datetime.fromisoformat(start_record['deliveryStart'].replace('Z', '+00:00'))
        end_utc = datetime.fromisoformat(end_record['deliveryEnd'].replace('Z', '+00:00'))
        
        # Convert to local timezone
        try:
            import zoneinfo
            ha_timezone = hass.config.time_zone if hass else 'Europe/Bratislava'
            tz = zoneinfo.ZoneInfo(ha_timezone)
            start_local = start_utc.astimezone(tz)
            end_local = end_utc.astimezone(tz)
        except ImportError:
            start_local = start_utc + timedelta(hours=1)
            end_local = end_utc + timedelta(hours=1)
        
        # Format times
        start_time_with_tz = start_local.isoformat()
        end_time_with_tz = end_local.isoformat()
        start_time_utc = f"UTC: {start_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        end_time_utc = f"UTC: {end_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        start_time_local = start_local.strftime('%d.%m.%Y %H:%M')
        end_time_local = end_local.strftime('%d.%m.%Y %H:%M')
        
        # Convert records to old format
        formatted_records = []
        for record in best_window['records']:
            try:
                delivery_start_dt = datetime.fromisoformat(record.get('deliveryStart').replace('Z', '+00:00'))
                delivery_end_dt = datetime.fromisoformat(record.get('deliveryEnd').replace('Z', '+00:00'))
                period_start_utc = delivery_start_dt.strftime('%H:%M')
                period_end_utc = delivery_end_dt.strftime('%H:%M')
            except:
                period_start_utc = record.get('HourStartCET')
                period_end_utc = record.get('HourEndCET')
            
            formatted_record = {
                'price': record.get('price'),
                'period': record.get('period'),
                'delivery_start': record.get('deliveryStart'),
                'delivery_end': record.get('deliveryEnd'),
                'period_start': period_start_utc,
                'period_end': period_end_utc,
                'date': record.get('deliveryDayCET'),
                'time_local': format_local_time(record.get('deliveryStart'), '%d.%m.%Y %H:%M', hass)
            }
            formatted_records.append(formatted_record)
        
        return {
            'found': True,
            'start_time': start_time_with_tz,
            'end_time': end_time_with_tz,
            'start_time_UTC': start_time_utc,
            'end_time_UTC': end_time_utc,
            'start_time_local': start_time_local,
            'end_time_local': end_time_local,
            'periods': periods,
            'min_price': best_window['min_price'],
            'max_price': best_window['max_price'],
            'avg_price': best_window['avg_price'],
            'records': formatted_records
        }
    else:
        return {
            'found': False,
            'message': 'No window found',
            'start_time': None,
            'end_time': None,
            'periods': periods,
            'min_price': None,
            'max_price': None,
            'avg_price': None,
            'records': []
        }


def find_window_in_time_range(data, periods, time_from_str, time_to_str, find_lowest=True, hass=None):
    """
    Find time window with lowest or highest average price within specified time range.
    
    Args:
        data (list): Array of objects with prices
        periods (int): Size of time window in periods
        time_from_str (str): Start time in format 'HH:MM'
        time_to_str (str): End time in format 'HH:MM'
        find_lowest (bool): True for lowest price, False for highest price
        hass: Home Assistant instance for timezone conversion
    
    Returns:
        dict: Information about found time window
    """
    # Convert periods to int in case it's a float
    periods = int(periods)
    
    if not data or len(data) < periods:
        return {
            'found': False,
            'message': f'Not enough data for {periods}-period window',
            'start_time': None,
            'end_time': None,
            'periods': None,
            'min_price': None,
            'max_price': None,
            'avg_price': None,
            'records': []
        }
    
    # Parse time range
    try:
        time_from = datetime.strptime(time_from_str, '%H:%M').time()
        time_to = datetime.strptime(time_to_str, '%H:%M').time()
    except ValueError:
        return {
            'found': False,
            'message': 'Invalid time format',
            'start_time': None,
            'end_time': None,
            'periods': None,
            'min_price': None,
            'max_price': None,
            'avg_price': None,
            'records': []
        }
    
    # Filter valid records
    valid_data = [record for record in data if 
                  record['price'] is not None and 
                  record['deliveryStart'] is not None and 
                  record['HourStartCET'] is not None]
    
    if len(valid_data) < periods:
        return {
            'found': False,
            'message': f'Not enough valid data for {periods}-period window',
            'start_time': None,
            'end_time': None,
            'periods': periods,
            'min_price': None,
            'max_price': None,
            'avg_price': None,
            'records': []
        }
    
    # Filter by time range
    filtered_data = []
    for record in valid_data:
        try:
            period_start_time = datetime.strptime(record['HourStartCET'], '%H:%M').time()
            if time_from <= period_start_time <= time_to:
                filtered_data.append(record)
        except:
            continue
    
    if len(filtered_data) < periods:
        return {
            'found': False,
            'message': f'Not enough data in time range {time_from_str}-{time_to_str}',
            'start_time': None,
            'end_time': None,
            'periods': periods,
            'min_price': None,
            'max_price': None,
            'avg_price': None,
            'records': []
        }
    
    # Sort by deliveryStart
    try:
        filtered_data.sort(key=lambda x: x['deliveryStart'])
    except:
        return {
            'found': False,
            'message': 'Error sorting data by time',
            'start_time': None,
            'end_time': None,
            'periods': periods,
            'min_price': None,
            'max_price': None,
            'avg_price': None,
            'records': []
        }
    
    best_window = None
    best_avg_price = float('inf') if find_lowest else float('-inf')
    
    # Slide window through all possible positions
    for i in range(len(filtered_data) - periods + 1):
        window_data = filtered_data[i:i + periods]
        
        # Check if window is continuous (no gaps)
        is_continuous = True
        for j in range(len(window_data) - 1):
            try:
                end_time = datetime.fromisoformat(window_data[j]['deliveryEnd'].replace('Z', '+00:00'))
                start_time = datetime.fromisoformat(window_data[j + 1]['deliveryStart'].replace('Z', '+00:00'))
                if end_time != start_time:
                    is_continuous = False
                    break
            except:
                is_continuous = False
                break
        
        if not is_continuous:
            continue
        
        # Calculate average price in window
        window_prices = [record['price'] for record in window_data]
        avg_price = sum(window_prices) / len(window_prices)
        
        # Check if this window is better
        if (find_lowest and avg_price < best_avg_price) or (not find_lowest and avg_price > best_avg_price):
            best_avg_price = avg_price
            best_window = {
                'start_time': window_data[0]['deliveryStart'],
                'end_time': window_data[-1]['deliveryEnd'],
                'avg_price': round(avg_price, 2),
                'min_price': min(window_prices),
                'max_price': max(window_prices),
                'records': window_data,
                'total_cost_per_mwh': round(sum(window_prices), 2)
            }
    
    if best_window:
        # Convert start_time and end_time to datetime with timezone
        try:
            import zoneinfo
            if hass:
                ha_timezone = hass.config.time_zone
                tz = zoneinfo.ZoneInfo(ha_timezone)
            else:
                tz = zoneinfo.ZoneInfo('Europe/Bratislava')
        except ImportError:
            # Fallback for older Python
            from datetime import timezone, timedelta
            tz = timezone(timedelta(hours=1))  # CET
        
        # Parse UTC times
        start_utc = datetime.fromisoformat(best_window['start_time'].replace('Z', '+00:00'))
        end_utc = datetime.fromisoformat(best_window['end_time'].replace('Z', '+00:00'))
        
        # Convert to local timezone
        start_local = start_utc.astimezone(tz)
        end_local = end_utc.astimezone(tz)
        
        # Format times
        start_time_with_tz = start_local.isoformat()
        end_time_with_tz = end_local.isoformat()
        start_time_utc = f"UTC: {start_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        end_time_utc = f"UTC: {end_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        start_time_local = start_local.strftime('%d.%m.%Y %H:%M')
        end_time_local = end_local.strftime('%d.%m.%Y %H:%M')
        
        # Convert records to old format (snake_case)
        formatted_records = []
        for record in best_window['records']:
            # Parse delivery times to extract UTC hour
            try:
                delivery_start_dt = datetime.fromisoformat(record.get('deliveryStart').replace('Z', '+00:00'))
                delivery_end_dt = datetime.fromisoformat(record.get('deliveryEnd').replace('Z', '+00:00'))
                period_start_utc = delivery_start_dt.strftime('%H:%M')
                period_end_utc = delivery_end_dt.strftime('%H:%M')
            except:
                period_start_utc = record.get('HourStartCET')
                period_end_utc = record.get('HourEndCET')
            
            formatted_record = {
                'price': record.get('price'),
                'period': record.get('period'),
                'delivery_start': record.get('deliveryStart'),
                'delivery_end': record.get('deliveryEnd'),
                'period_start': period_start_utc,
                'period_end': period_end_utc,
                'date': record.get('deliveryDayCET'),
                'time_local': format_local_time(record.get('deliveryStart'), '%d.%m.%Y %H:%M', hass)
            }
            formatted_records.append(formatted_record)
        
        return {
            'found': True,
            'start_time': start_time_with_tz,
            'end_time': end_time_with_tz,
            'start_time_UTC': start_time_utc,
            'end_time_UTC': end_time_utc,
            'start_time_local': start_time_local,
            'end_time_local': end_time_local,
            'periods': periods,
            'min_price': best_window['min_price'],
            'max_price': best_window['max_price'],
            'avg_price': best_window['avg_price'],
            'records': formatted_records
        }
    else:
        return {
            'found': False,
            'message': 'Could not find suitable continuous time window in specified time range',
            'start_time': None,
            'end_time': None,
            'periods': periods,
            'min_price': None,
            'max_price': None,
            'avg_price': None,
            'records': []
        }


##############################################################################################################################
# Master Device Instance #####################################################################################################
##############################################################################################################################

class OKTE_Master_Instance:
    """Master device instance - handles API communication and stores price data."""

    def __init__(self) -> None:
        self.settings = self.Settings()
        self._is_running = False
        self.hass = None
        self._entry_id = None

        # Storage for sensor states
        self.sensor_states = {
            ENTITY_CONNECTION_STATUS: False,
            ENTITY_LAST_UPDATE: None,
            ENTITY_DATA_COUNT: 0,
            ENTITY_CURRENT_PRICE: None,
            ENTITY_AVERAGE_PRICE_TODAY: None,
            ENTITY_MIN_PRICE_TODAY: None,
            ENTITY_MAX_PRICE_TODAY: None,
            ENTITY_AVERAGE_PRICE_TOMORROW: None,
            ENTITY_MIN_PRICE_TOMORROW: None,
            ENTITY_MAX_PRICE_TOMORROW: None,
            ENTITY_PRICES_TODAY: "OK",  # State will be "OK", data in attributes
            ENTITY_PRICES_TOMORROW: "OK",  # State will be "OK", data in attributes
            ENTITY_HTML_TABLE_TODAY: "OK",  # State will be "OK", data in attributes
            ENTITY_HTML_TABLE_TOMORROW: "OK",  # State will be "OK", data in attributes
            ENTITY_ERROR_CODE: 0,  # Bitmap of error codes, 0 = no errors
        }
        
        # Storage for sensor attributes (for long data like HTML, JSON)
        self.sensor_attributes = {
            ENTITY_CURRENT_PRICE: {},
            ENTITY_MIN_PRICE_TODAY: {},
            ENTITY_MAX_PRICE_TODAY: {},
            ENTITY_MIN_PRICE_TOMORROW: {},
            ENTITY_MAX_PRICE_TOMORROW: {},
            ENTITY_CONNECTION_STATUS: {},
            ENTITY_LAST_UPDATE: {},
            ENTITY_PRICES_TODAY: {},
            ENTITY_PRICES_TOMORROW: {},
            ENTITY_HTML_TABLE_TODAY: {},
            ENTITY_HTML_TABLE_TOMORROW: {},
            ENTITY_ERROR_CODE: {},
        }

        # Price data storage
        self.price_data = {
            'all_data': [],
            'today_data': [],
            'tomorrow_data': [],
            'last_fetch': None
        }
        
        # Retry timer for failed API fetch
        self._retry_timer = None

        # Entity IDs
        self.SENSOR_ENTITY_CONNECTION_STATUS = None
        self.SENSOR_ENTITY_LAST_UPDATE = None
        self.SENSOR_ENTITY_DATA_COUNT = None
        self.SENSOR_ENTITY_ERROR_CODE = None
        self.SENSOR_ENTITY_CURRENT_PRICE = None
        self.SENSOR_ENTITY_AVERAGE_PRICE_TODAY = None
        self.SENSOR_ENTITY_MIN_PRICE_TODAY = None
        self.SENSOR_ENTITY_MAX_PRICE_TODAY = None
        self.SENSOR_ENTITY_AVERAGE_PRICE_TOMORROW = None
        self.SENSOR_ENTITY_MIN_PRICE_TOMORROW = None
        self.SENSOR_ENTITY_MAX_PRICE_TOMORROW = None
        self.SENSOR_ENTITY_PRICES_TODAY = None
        self.SENSOR_ENTITY_PRICES_TOMORROW = None
        self.SENSOR_ENTITY_HTML_TABLE_TODAY = None
        self.SENSOR_ENTITY_HTML_TABLE_TOMORROW = None

    def setup_entity_ids(self):
        """Setup entity IDs after entry_id is set."""
        if self._entry_id:
            from .const import ENTITY_PREFIX
            
            # Master device uses simple prefix: okte_{entity_name}
            self.SENSOR_ENTITY_CONNECTION_STATUS = f"sensor.{ENTITY_PREFIX}_{ENTITY_CONNECTION_STATUS}"
            self.SENSOR_ENTITY_LAST_UPDATE = f"sensor.{ENTITY_PREFIX}_{ENTITY_LAST_UPDATE}"
            self.SENSOR_ENTITY_DATA_COUNT = f"sensor.{ENTITY_PREFIX}_{ENTITY_DATA_COUNT}"
            self.SENSOR_ENTITY_ERROR_CODE = f"sensor.{ENTITY_PREFIX}_{ENTITY_ERROR_CODE}"
            self.SENSOR_ENTITY_CURRENT_PRICE = f"sensor.{ENTITY_PREFIX}_{ENTITY_CURRENT_PRICE}"
            self.SENSOR_ENTITY_AVERAGE_PRICE_TODAY = f"sensor.{ENTITY_PREFIX}_{ENTITY_AVERAGE_PRICE_TODAY}"
            self.SENSOR_ENTITY_MIN_PRICE_TODAY = f"sensor.{ENTITY_PREFIX}_{ENTITY_MIN_PRICE_TODAY}"
            self.SENSOR_ENTITY_MAX_PRICE_TODAY = f"sensor.{ENTITY_PREFIX}_{ENTITY_MAX_PRICE_TODAY}"
            self.SENSOR_ENTITY_AVERAGE_PRICE_TOMORROW = f"sensor.{ENTITY_PREFIX}_{ENTITY_AVERAGE_PRICE_TOMORROW}"
            self.SENSOR_ENTITY_MIN_PRICE_TOMORROW = f"sensor.{ENTITY_PREFIX}_{ENTITY_MIN_PRICE_TOMORROW}"
            self.SENSOR_ENTITY_MAX_PRICE_TOMORROW = f"sensor.{ENTITY_PREFIX}_{ENTITY_MAX_PRICE_TOMORROW}"
            self.SENSOR_ENTITY_PRICES_TODAY = f"sensor.{ENTITY_PREFIX}_{ENTITY_PRICES_TODAY}"
            self.SENSOR_ENTITY_PRICES_TOMORROW = f"sensor.{ENTITY_PREFIX}_{ENTITY_PRICES_TOMORROW}"
            self.SENSOR_ENTITY_HTML_TABLE_TODAY = f"sensor.{ENTITY_PREFIX}_{ENTITY_HTML_TABLE_TODAY}"
            self.SENSOR_ENTITY_HTML_TABLE_TOMORROW = f"sensor.{ENTITY_PREFIX}_{ENTITY_HTML_TABLE_TOMORROW}"

    @dataclasses.dataclass
    class Settings:
        """Settings for master device."""
        fallback_check_interval = DEFAULT_FALLBACK_CHECK_INTERVAL
        
        device_name: str = DEFAULT_DEVICE_NAME
        include_device_name_in_entity: bool = DEFAULT_INCLUDE_DEVICE_NAME_IN_ENTITY
        fetch_time: str = DEFAULT_FETCH_TIME
        fetch_days: int = DEFAULT_FETCH_DAYS

    def system_started(self) -> None:
        """System started callback."""
        try:
            LOGGER.debug(f"Master Device System Started: {self.settings.device_name}")
        except Exception as e:
            LOGGER.error(f"Error during System Started: {e}")

    async def update_current_price(self):
        """Update only current price from already fetched data - no API call."""
        try:
            # Check if we have data
            if not self.price_data.get('all_data'):
                LOGGER.debug("No data available for current price update")
                return
            
            data = self.price_data['all_data']
            current_local_time = self._get_current_local_time()
            current_hour = current_local_time.replace(minute=0, second=0, microsecond=0)
            
            # Find current price record
            current_record = None
            for record in data:
                try:
                    delivery_start = record.get('deliveryStart')
                    if not delivery_start:
                        continue
                    
                    # Parse UTC time and convert to local
                    if delivery_start.endswith('Z'):
                        utc_start = datetime.fromisoformat(delivery_start.replace('Z', '+00:00'))
                    else:
                        utc_start = datetime.fromisoformat(delivery_start)
                    
                    # Convert to local timezone
                    try:
                        import zoneinfo
                        ha_timezone = self.hass.config.time_zone
                        tz = zoneinfo.ZoneInfo(ha_timezone)
                        local_start = utc_start.astimezone(tz)
                    except (ImportError, Exception):
                        local_start = utc_start + timedelta(hours=1)
                    
                    # Compare hours
                    local_start_hour = local_start.replace(minute=0, second=0, microsecond=0)
                    if local_start_hour == current_hour:
                        current_record = record
                        LOGGER.debug(f"Current price updated: {record['price']} EUR/MWh for {local_start.strftime('%H:%M')}")
                        break
                except Exception as e:
                    continue
            
            # Update current price sensor
            self.sensor_states[ENTITY_CURRENT_PRICE] = current_record['price'] if current_record else None
            
            # Update attributes
            if current_record:
                # Get statistics from stored data
                today_data = self.price_data.get('today_data', [])
                tomorrow_data = self.price_data.get('tomorrow_data', [])
                all_data = self.price_data.get('all_data', [])
                
                today_stats = calculate_price_statistics(today_data)
                tomorrow_stats = calculate_price_statistics(tomorrow_data)
                all_stats = calculate_price_statistics(all_data)
                
                self.sensor_attributes[ENTITY_CURRENT_PRICE] = {
                    'period': current_record.get('period'),
                    'period_start': format_local_time(current_record.get('deliveryStart'), '%H:%M', self.hass),
                    'period_end': format_local_time(current_record.get('deliveryEnd'), '%H:%M', self.hass),
                    'total_records': len(all_data),
                    'today_average': today_stats['avg_price'],
                    'tomorrow_average': tomorrow_stats['avg_price'],
                    'price_spread': round(all_stats['max_price'] - all_stats['min_price'], 2) if all_stats['max_price'] and all_stats['min_price'] else None,
                }
            else:
                # No current record found
                today_data = self.price_data.get('today_data', [])
                tomorrow_data = self.price_data.get('tomorrow_data', [])
                all_data = self.price_data.get('all_data', [])
                
                today_stats = calculate_price_statistics(today_data)
                tomorrow_stats = calculate_price_statistics(tomorrow_data)
                all_stats = calculate_price_statistics(all_data)
                
                self.sensor_attributes[ENTITY_CURRENT_PRICE] = {
                    'total_records': len(all_data),
                    'today_average': today_stats['avg_price'],
                    'tomorrow_average': tomorrow_stats['avg_price'],
                    'price_spread': round(all_stats['max_price'] - all_stats['min_price'], 2) if all_stats['max_price'] and all_stats['min_price'] else None,
                }
            
            LOGGER.debug("OKTE API: Current price sensor updated from cached data")
            
        except Exception as e:
            LOGGER.error(f"OKTE API: Error updating current price: {e}")

    async def fetch_and_process_data(self):
        """Fetch data from API and process it."""
        try:
            LOGGER.info("OKTE API: Fetching price data from OKTE API...")
            
            # Fetch data with hass parameter for timezone conversion
            data = await self.hass.async_add_executor_job(
                fetch_okte_data, 
                self.settings.fetch_days, 
                None,
                self.hass
            )
            
            if data:
                self.price_data['all_data'] = data
                self.price_data['last_fetch'] = self._get_current_local_time()
                
                # Filter today and tomorrow data - use local timezone
                current_local_time = self._get_current_local_time()
                today = current_local_time.date()
                tomorrow = today + timedelta(days=1)
                
                LOGGER.debug(f"OKTE API: Filtering data for today: {today.strftime('%Y-%m-%d')} (local timezone)")
                
                self.price_data['today_data'] = filter_data_by_date(data, today)
                self.price_data['tomorrow_data'] = filter_data_by_date(data, tomorrow)
                
                LOGGER.info(f"OKTE API: Successfully fetched {len(data)} records - Today: {len(self.price_data['today_data'])}, Tomorrow: {len(self.price_data['tomorrow_data'])}")
                
                # Calculate statistics
                today_stats = calculate_price_statistics(self.price_data['today_data'])
                tomorrow_stats = calculate_price_statistics(self.price_data['tomorrow_data'])
                
                # Update sensor states
                self.sensor_states[ENTITY_CONNECTION_STATUS] = True
                self.sensor_states[ENTITY_LAST_UPDATE] = current_local_time.isoformat()
                self.sensor_states[ENTITY_DATA_COUNT] = len(data)
                
                # Clear API fetch error bit (bit 0)
                self.sensor_states[ENTITY_ERROR_CODE] = self.sensor_states[ENTITY_ERROR_CODE] & ~1
                
                # Cancel retry timer if it exists (fetch succeeded)
                if self._retry_timer is not None:
                    self._retry_timer()
                    self._retry_timer = None
                    LOGGER.debug("OKTE API: Cancelled retry timer - fetch successful")
                
                # Connection status attributes
                self.sensor_attributes[ENTITY_CONNECTION_STATUS] = {
                    'status': 'Connected',
                    'status_description': 'Last data fetch was successful',
                    'last_attempt': current_local_time.isoformat(),
                }
                
                # Last update attributes
                self.sensor_attributes[ENTITY_LAST_UPDATE] = {
                    'data_records': len(data),
                    'status': 'Data available',
                }
                
                # Today statistics
                self.sensor_states[ENTITY_AVERAGE_PRICE_TODAY] = today_stats['avg_price']
                self.sensor_states[ENTITY_MIN_PRICE_TODAY] = today_stats['min_price']
                self.sensor_states[ENTITY_MAX_PRICE_TODAY] = today_stats['max_price']
                
                # Today min/max price attributes
                if today_stats['min_record']:
                    min_rec = today_stats['min_record']
                    self.sensor_attributes[ENTITY_MIN_PRICE_TODAY] = {
                        'available': True,
                        'time': format_local_time(min_rec.get('deliveryStart'), '%d.%m.%Y %H:%M', self.hass),
                        'period': min_rec.get('period'),
                        'period_start': format_local_time(min_rec.get('deliveryStart'), '%H:%M', self.hass),
                        'period_end': format_local_time(min_rec.get('deliveryEnd'), '%H:%M', self.hass),
                    }
                else:
                    self.sensor_attributes[ENTITY_MIN_PRICE_TODAY] = {
                        'available': False,
                    }
                
                if today_stats['max_record']:
                    max_rec = today_stats['max_record']
                    self.sensor_attributes[ENTITY_MAX_PRICE_TODAY] = {
                        'available': True,
                        'time': format_local_time(max_rec.get('deliveryStart'), '%d.%m.%Y %H:%M', self.hass),
                        'period': max_rec.get('period'),
                        'period_start': format_local_time(max_rec.get('deliveryStart'), '%H:%M', self.hass),
                        'period_end': format_local_time(max_rec.get('deliveryEnd'), '%H:%M', self.hass),
                    }
                else:
                    self.sensor_attributes[ENTITY_MAX_PRICE_TODAY] = {
                        'available': False,
                    }
                
                # Tomorrow statistics
                self.sensor_states[ENTITY_AVERAGE_PRICE_TOMORROW] = tomorrow_stats['avg_price']
                self.sensor_states[ENTITY_MIN_PRICE_TOMORROW] = tomorrow_stats['min_price']
                self.sensor_states[ENTITY_MAX_PRICE_TOMORROW] = tomorrow_stats['max_price']
                
                # Tomorrow min/max price attributes
                if tomorrow_stats['min_record']:
                    min_rec = tomorrow_stats['min_record']
                    self.sensor_attributes[ENTITY_MIN_PRICE_TOMORROW] = {
                        'available': True,
                        'time': format_local_time(min_rec.get('deliveryStart'), '%d.%m.%Y %H:%M', self.hass),
                        'period': min_rec.get('period'),
                        'period_start': format_local_time(min_rec.get('deliveryStart'), '%H:%M', self.hass),
                        'period_end': format_local_time(min_rec.get('deliveryEnd'), '%H:%M', self.hass),
                    }
                else:
                    self.sensor_attributes[ENTITY_MIN_PRICE_TOMORROW] = {
                        'available': False,
                    }
                
                if tomorrow_stats['max_record']:
                    max_rec = tomorrow_stats['max_record']
                    self.sensor_attributes[ENTITY_MAX_PRICE_TOMORROW] = {
                        'available': True,
                        'time': format_local_time(max_rec.get('deliveryStart'), '%d.%m.%Y %H:%M', self.hass),
                        'period': max_rec.get('period'),
                        'period_start': format_local_time(max_rec.get('deliveryStart'), '%H:%M', self.hass),
                        'period_end': format_local_time(max_rec.get('deliveryEnd'), '%H:%M', self.hass),
                    }
                else:
                    self.sensor_attributes[ENTITY_MAX_PRICE_TOMORROW] = {
                        'available': False,
                    }
                
                # Current price - use local timezone
                current_local_time = self._get_current_local_time()
                current_hour = current_local_time.replace(minute=0, second=0, microsecond=0)
                LOGGER.debug(f"Looking for current price at local time: {current_local_time.strftime('%Y-%m-%d %H:%M:%S %Z')}, current_hour: {current_hour.strftime('%H:%M')}")
                current_record = None
                for record in data:
                    try:
                        # Parse UTC time from API and convert to local timezone
                        utc_start = datetime.fromisoformat(record['deliveryStart'].replace('Z', '+00:00'))
                        try:
                            import zoneinfo
                            ha_timezone = self.hass.config.time_zone
                            tz = zoneinfo.ZoneInfo(ha_timezone)
                            local_start = utc_start.astimezone(tz)
                        except ImportError:
                            # Fallback
                            local_start = utc_start + timedelta(hours=1)
                        
                        # Compare hours (ignore minutes/seconds)
                        local_start_hour = local_start.replace(minute=0, second=0, microsecond=0)
                        if local_start_hour == current_hour:
                            current_record = record
                            LOGGER.debug(f"Found current price: {record['price']} EUR/MWh for time slot {local_start.strftime('%H:%M')}")
                            break
                    except Exception as e:
                        LOGGER.debug(f"Error parsing delivery time: {e}")
                        continue
                
                if not current_record:
                    LOGGER.warning(f"No current price found for {current_hour.strftime('%H:%M')}")
                
                self.sensor_states[ENTITY_CURRENT_PRICE] = current_record['price'] if current_record else None
                
                # Calculate overall statistics for current price attributes
                all_stats = calculate_price_statistics(data)
                
                # Current price attributes
                if current_record:
                    self.sensor_attributes[ENTITY_CURRENT_PRICE] = {
                        'period': current_record.get('period'),
                        'period_start': format_local_time(current_record.get('deliveryStart'), '%H:%M', self.hass),
                        'period_end': format_local_time(current_record.get('deliveryEnd'), '%H:%M', self.hass),
                        'total_records': len(data),
                        'today_average': today_stats['avg_price'],
                        'tomorrow_average': tomorrow_stats['avg_price'],
                        'price_spread': round(all_stats['max_price'] - all_stats['min_price'], 2) if all_stats['max_price'] and all_stats['min_price'] else None,
                    }
                else:
                    self.sensor_attributes[ENTITY_CURRENT_PRICE] = {
                        'total_records': len(data),
                        'today_average': today_stats['avg_price'],
                        'tomorrow_average': tomorrow_stats['avg_price'],
                        'price_spread': round(all_stats['max_price'] - all_stats['min_price'], 2) if all_stats['max_price'] and all_stats['min_price'] else None,
                    }
                
                # Prices - create detailed attributes like in original integration
                # Process TODAY data
                today_period_data = []
                today_valid_records = [record for record in self.price_data['today_data'] 
                                      if record.get('price') is not None and record.get('deliveryStart')]
                today_valid_records.sort(key=lambda x: x.get('deliveryStart', ''))
                
                for record in today_valid_records:
                    try:
                        delivery_start = datetime.fromisoformat(record['deliveryStart'].replace('Z', '+00:00'))
                        
                        # Convert to local timezone
                        try:
                            import zoneinfo
                            ha_timezone = self.hass.config.time_zone
                            tz = zoneinfo.ZoneInfo(ha_timezone)
                            delivery_local = delivery_start.astimezone(tz)
                        except ImportError:
                            delivery_local = delivery_start + timedelta(hours=1)
                        
                        period_entry = {
                            'time': record['deliveryStart'],  # ISO format for graphs
                            'time_local': delivery_local.strftime('%Y-%m-%d %H:%M:%S'),
                            'price': record['price'],
                            'period': record.get('period'),
                            'period_start': record.get('HourStartCET'),
                            'period_end': record.get('HourEndCET'),
                            'date': record.get('deliveryDayCET'),
                            'day_name': delivery_local.strftime('%A'),
                            'period_label': f"{record.get('HourStartCET', '')}-{record.get('HourEndCET', '')}",
                            'timestamp': int(delivery_start.timestamp() * 1000)  # For ApexCharts
                        }
                        today_period_data.append(period_entry)
                    except Exception as e:
                        LOGGER.debug(f"Error processing today hourly record: {e}")
                        continue
                
                today_prices_list = [entry['price'] for entry in today_period_data]
                today_timestamps_list = [entry['time'] for entry in today_period_data]
                today_labels_list = [entry['period_label'] for entry in today_period_data]
                
                self.sensor_states[ENTITY_PRICES_TODAY] = len(today_valid_records)
                self.sensor_attributes[ENTITY_PRICES_TODAY] = {
                    'period_data': today_period_data,
                    'periods': len(today_period_data),
                    'date_range': today.strftime('%Y-%m-%d'),
                    'prices_list': today_prices_list,
                    'timestamps_list': today_timestamps_list,
                    'labels_list': today_labels_list,
                    'min_price': min(today_prices_list) if today_prices_list else None,
                    'max_price': max(today_prices_list) if today_prices_list else None,
                    'avg_price': round(sum(today_prices_list) / len(today_prices_list), 2) if today_prices_list else None
                }
                
                # Process TOMORROW data
                tomorrow_period_data = []
                tomorrow_valid_records = [record for record in self.price_data['tomorrow_data']
                                         if record.get('price') is not None and record.get('deliveryStart')]
                tomorrow_valid_records.sort(key=lambda x: x.get('deliveryStart', ''))
                
                for record in tomorrow_valid_records:
                    try:
                        delivery_start = datetime.fromisoformat(record['deliveryStart'].replace('Z', '+00:00'))
                        
                        # Convert to local timezone
                        try:
                            import zoneinfo
                            ha_timezone = self.hass.config.time_zone
                            tz = zoneinfo.ZoneInfo(ha_timezone)
                            delivery_local = delivery_start.astimezone(tz)
                        except ImportError:
                            delivery_local = delivery_start + timedelta(hours=1)
                        
                        period_entry = {
                            'time': record['deliveryStart'],
                            'time_local': delivery_local.strftime('%Y-%m-%d %H:%M:%S'),
                            'price': record['price'],
                            'period': record.get('period'),
                            'period_start': record.get('HourStartCET'),
                            'period_end': record.get('HourEndCET'),
                            'date': record.get('deliveryDayCET'),
                            'day_name': delivery_local.strftime('%A'),
                            'period_label': f"{record.get('HourStartCET', '')}-{record.get('HourEndCET', '')}",
                            'timestamp': int(delivery_start.timestamp() * 1000)
                        }
                        tomorrow_period_data.append(period_entry)
                    except Exception as e:
                        LOGGER.debug(f"Error processing tomorrow hourly record: {e}")
                        continue
                
                tomorrow_prices_list = [entry['price'] for entry in tomorrow_period_data]
                tomorrow_timestamps_list = [entry['time'] for entry in tomorrow_period_data]
                tomorrow_labels_list = [entry['period_label'] for entry in tomorrow_period_data]
                
                self.sensor_states[ENTITY_PRICES_TOMORROW] = len(tomorrow_valid_records)
                self.sensor_attributes[ENTITY_PRICES_TOMORROW] = {
                    'period_data': tomorrow_period_data,
                    'periods': len(tomorrow_period_data),
                    'date_range': tomorrow.strftime('%Y-%m-%d'),
                    'prices_list': tomorrow_prices_list,
                    'timestamps_list': tomorrow_timestamps_list,
                    'labels_list': tomorrow_labels_list,
                    'min_price': min(tomorrow_prices_list) if tomorrow_prices_list else None,
                    'max_price': max(tomorrow_prices_list) if tomorrow_prices_list else None,
                    'avg_price': round(sum(tomorrow_prices_list) / len(tomorrow_prices_list), 2) if tomorrow_prices_list else None
                }
                
                LOGGER.info(f"Set ENTITY_PRICES_TODAY: {len(today_valid_records)} records in attributes")
                LOGGER.info(f"Set ENTITY_PRICES_TOMORROW: {len(tomorrow_valid_records)} records in attributes")
                
                # HTML tables - pass dates to ensure correct formatting
                html_today = self.generate_html_table_today(self.price_data['today_data'], today)
                html_tomorrow = self.generate_html_table_tomorrow(self.price_data['tomorrow_data'], tomorrow)
                
                # Count valid records for today
                today_valid_records = [record for record in self.price_data['today_data'] 
                                      if record.get('price') is not None and record.get('deliveryStart')]
                
                # Count valid records for tomorrow  
                tomorrow_valid_records = [record for record in self.price_data['tomorrow_data']
                                         if record.get('price') is not None and record.get('deliveryStart')]
                
                # Set state to count of records
                self.sensor_states[ENTITY_HTML_TABLE_TODAY] = len(today_valid_records)
                self.sensor_states[ENTITY_HTML_TABLE_TOMORROW] = len(tomorrow_valid_records)
                
                # Set attributes - use local time
                self.sensor_attributes[ENTITY_HTML_TABLE_TODAY] = {
                    'html_table': html_today,
                    'total_records': len(today_valid_records),
                    'date': today.strftime('%d.%m.%Y'),
                    'available': len(today_valid_records) > 0,
                    'last_update': current_local_time.isoformat()
                }
                
                self.sensor_attributes[ENTITY_HTML_TABLE_TOMORROW] = {
                    'html_table': html_tomorrow,
                    'total_records': len(tomorrow_valid_records),
                    'date': tomorrow.strftime('%d.%m.%Y'),
                    'available': len(tomorrow_valid_records) > 0,
                    'last_update': current_local_time.isoformat()
                }
                
                LOGGER.info(f"Set ENTITY_HTML_TABLE_TODAY: {len(html_today)} chars in attributes")
                LOGGER.info(f"Set ENTITY_HTML_TABLE_TOMORROW: {len(html_tomorrow)} chars in attributes")
                
                LOGGER.info(f"Successfully processed {len(data)} price records")
            else:
                self.sensor_states[ENTITY_CONNECTION_STATUS] = False
                LOGGER.error("OKTE API: No data received from API")
                
                # Set API fetch error bit (bit 0)
                self.sensor_states[ENTITY_ERROR_CODE] = self.sensor_states[ENTITY_ERROR_CODE] | 1
                
                # Schedule retry in 1 minute
                self._schedule_retry()
                
                # Connection status attributes - disconnected
                current_local_time = self._get_current_local_time()
                self.sensor_attributes[ENTITY_CONNECTION_STATUS] = {
                    'status': 'Disconnected',
                    'status_description': 'Last data fetch failed',
                    'last_attempt': current_local_time.isoformat(),
                }
                
        except Exception as e:
            self.sensor_states[ENTITY_CONNECTION_STATUS] = False
            LOGGER.error(f"OKTE API: Error fetching data: {e}")
            
            # Set API fetch error bit (bit 0)
            self.sensor_states[ENTITY_ERROR_CODE] = self.sensor_states[ENTITY_ERROR_CODE] | 1
            
            # Schedule retry in 1 minute
            self._schedule_retry()
            
            # Connection status attributes - error
            current_local_time = self._get_current_local_time()
            self.sensor_attributes[ENTITY_CONNECTION_STATUS] = {
                'status': 'Disconnected',
                'status_description': f'Error during data fetch: {str(e)[:100]}',
                'last_attempt': current_local_time.isoformat(),
            }

    def _schedule_retry(self):
        """Schedule retry of API fetch in 1 minute if previous attempt failed."""
        from homeassistant.helpers.event import async_call_later
        
        # Cancel existing retry timer if any
        if self._retry_timer is not None:
            self._retry_timer()
            self._retry_timer = None
        
        # Schedule retry in 60 seconds
        async def retry_fetch(_now=None):
            """Retry API fetch."""
            self._retry_timer = None
            LOGGER.info("OKTE API: Retrying API fetch after previous failure...")
            await self.fetch_and_process_data()
            # Send update signal
            from homeassistant.helpers.dispatcher import async_dispatcher_send
            async_dispatcher_send(self.hass, f"{DOMAIN}_feedback_update_{self._entry_id}")
        
        self._retry_timer = async_call_later(self.hass, 60, retry_fetch)
        LOGGER.info("OKTE API: Scheduled retry in 60 seconds")

    def _get_price_color(self, price):
        """Get color for price based on value."""
        if price is None:
            return ""
        
        if price > THRESHOLD_PRICE_HIGH:
            return COLOR_PRICE_HIGH
        elif price >= THRESHOLD_PRICE_LOW:
            return COLOR_PRICE_LOW
        else:
            return COLOR_PRICE_NEGATIVE
    
    def _get_current_local_time(self):
        """Get current time in Home Assistant's timezone."""
        try:
            import zoneinfo
            ha_timezone = self.hass.config.time_zone
            tz = zoneinfo.ZoneInfo(ha_timezone)
            return datetime.now(tz)
        except ImportError:
            # Fallback - return naive datetime with UTC offset guess
            from datetime import timezone
            utc_now = datetime.now(timezone.utc)
            # Assume CET/CEST (UTC+1/UTC+2) - not ideal but works for most EU
            return utc_now + timedelta(hours=1)
    
    def _convert_to_local_time(self, utc_time_str):
        """Convert UTC time string to local time string."""
        if not utc_time_str:
            return ""
        
        try:
            # Parse UTC time from API (format: 2024-12-28T23:00:00Z)
            utc_time = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
            
            # Convert to local timezone
            try:
                import zoneinfo
                ha_timezone = self.hass.config.time_zone
                tz = zoneinfo.ZoneInfo(ha_timezone)
                local_time = utc_time.astimezone(tz)
            except ImportError:
                # Fallback for older Python versions - assume CET/CEST (UTC+1/UTC+2)
                local_time = utc_time + timedelta(hours=1)  # CET is UTC+1, CEST is UTC+2
                
            return local_time.strftime('%H:%M')
        except Exception as e:
            LOGGER.debug(f"Error converting time {utc_time_str}: {e}")
            return ""
    
    def generate_html_table_today(self, data, date=None):
        """Create HTML table with today's hourly prices."""
        # Get today's date formatted - use provided date or get current local time
        if date:
            today_formatted = date.strftime('%d.%m.%Y')
        else:
            today_formatted = self._get_current_local_time().strftime('%d.%m.%Y')
        
        # Start building HTML table with header (always show)
        html = f"""
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%; max-width: 400px; border-color: {BORDER_COLOR_HEADER};">
            <thead>
                <tr style="background-color: {BG_COLOR_TABLE_HEADER_ROW1}; color: {TEXT_COLOR_TABLE_HEADER_ROW1};">
                    <th colspan="2" style="text-align: center; font-size: 16px; padding: {PADDING_HEADER_ROW1};">
                        Dnešné ceny elektriky OKTE
                    </th>
                </tr>
                <tr style="background-color: {BG_COLOR_TABLE_HEADER_ROW2}; color: {TEXT_COLOR_TABLE_HEADER_ROW2};">
                    <th style="width: auto; max-width: 200px; text-align: center; padding: {PADDING_HEADER_ROW2};">Čas od - do</th>
                    <th style="width: auto; max-width: 200px; text-align: center; padding: {PADDING_HEADER_ROW2};">Cena [€/MWh]</th>
                </tr>
            </thead>
            <tbody>
        """
        
        if not data:
            # No data available - show message
            html += f"""
                <tr>
                    <td colspan="2" style="text-align: center; height: 200px; vertical-align: middle; border: 1px solid {BORDER_COLOR_DATA};">
                        Údaje nie sú k dispozícii
                    </td>
                </tr>
            """
            html += """
            </tbody>
        </table>
        """
            return html
        
        # Filter and sort valid records
        valid_records = [record for record in data if record.get('price') is not None and record.get('deliveryStart')]
        
        if not valid_records:
            # No valid records - show message
            html += f"""
                <tr>
                    <td colspan="2" style="text-align: center; height: 200px; vertical-align: middle; border: 1px solid {BORDER_COLOR_DATA};">
                        Údaje nie sú k dispozícii
                    </td>
                </tr>
            """
            html += """
            </tbody>
        </table>
        """
            return html
        
        valid_records.sort(key=lambda x: x.get('deliveryStart', ''))
        
        # Calculate statistics
        prices = [record['price'] for record in valid_records]
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        
        min_record = next(record for record in valid_records if record['price'] == min_price)
        max_record = next(record for record in valid_records if record['price'] == max_price)
        
        # Add data rows
        row_index = 0
        for record in valid_records:
            # Convert UTC times to local times
            time_from = self._convert_to_local_time(record.get('deliveryStart', ''))
            time_to = self._convert_to_local_time(record.get('deliveryEnd', ''))
            
            # Create time range string
            time_range = f"{time_from} - {time_to}" if time_from and time_to else ""
            
            price = record.get('price', 0)
            
            # Format price to 2 decimal places with € symbol
            price_formatted = f"{price:.2f} €"
            price_color = self._get_price_color(price)
            
            # Determine row background color (alternating)
            row_bg_color = BG_COLOR_TABLE_DATA_ROW_ODD if row_index % 2 == 0 else BG_COLOR_TABLE_DATA_ROW_EVEN
            
            html += f"""
                <tr style="background-color: {row_bg_color};">
                    <td style="width: auto; max-width: 200px; text-align: center; padding: {PADDING_DATA_ROWS};">{time_range}</td>
                    <td style="text-align: right; width: auto; max-width: 200px; color: {price_color}; padding: {PADDING_DATA_ROWS};">{price_formatted}</td>
                </tr>
            """
            row_index += 1
        
        # Add footer with statistics
        min_time_from = self._convert_to_local_time(min_record.get('deliveryStart', ''))
        min_time_to = self._convert_to_local_time(min_record.get('deliveryEnd', ''))
        max_time_from = self._convert_to_local_time(max_record.get('deliveryStart', ''))
        max_time_to = self._convert_to_local_time(max_record.get('deliveryEnd', ''))
        
        html += f"""
            </tbody>
            <tfoot>
                <tr style="background-color: #e8f4f8;">
                    <td colspan="2" style="padding: 10px; font-size: 14px;">
                        <strong>📅 Dátum:</strong> {today_formatted}<br>
                        <strong>📉 Min. cena:</strong> {min_price:.2f} € ({min_time_from}-{min_time_to})<br>
                        <strong>📈 Max. cena:</strong> {max_price:.2f} € ({max_time_from}-{max_time_to})<br>
                        <strong>📊 Priemerná cena:</strong> {avg_price:.2f} €
                    </td>
                </tr>
            </tfoot>
        </table>
        """
        
        return html
    
    def generate_html_table_tomorrow(self, data, date=None):
        """Create HTML table with tomorrow's hourly prices."""
        # Get tomorrow's date formatted - use provided date or calculate from current local time
        if date:
            tomorrow_formatted = date.strftime('%d.%m.%Y')
        else:
            tomorrow = self._get_current_local_time().date() + timedelta(days=1)
            tomorrow_formatted = tomorrow.strftime('%d.%m.%Y')
        
        # Start building HTML table with header (always show)
        html = f"""
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%; max-width: 400px; border-color: {BORDER_COLOR_HEADER};">
            <thead>
                <tr style="background-color: {BG_COLOR_TABLE_HEADER_ROW1}; color: {TEXT_COLOR_TABLE_HEADER_ROW1};">
                    <th colspan="2" style="text-align: center; font-size: 16px; padding: {PADDING_HEADER_ROW1};">
                        Zajtrajšie ceny elektriky OKTE
                    </th>
                </tr>
                <tr style="background-color: {BG_COLOR_TABLE_HEADER_ROW2}; color: {TEXT_COLOR_TABLE_HEADER_ROW2};">
                    <th style="width: auto; max-width: 200px; text-align: center; padding: {PADDING_HEADER_ROW2};">Čas od - do</th>
                    <th style="width: auto; max-width: 200px; text-align: center; padding: {PADDING_HEADER_ROW2};">Cena [€/MWh]</th>
                </tr>
            </thead>
            <tbody>
        """
        
        if not data:
            # No data available - show message
            html += f"""
                <tr>
                    <td colspan="2" style="text-align: center; height: 200px; vertical-align: middle; border: 1px solid {BORDER_COLOR_DATA};">
                        Údaje nie sú k dispozícii
                    </td>
                </tr>
            """
            html += """
            </tbody>
        </table>
        """
            return html
        
        # Filter and sort valid records
        valid_records = [record for record in data if record.get('price') is not None and record.get('deliveryStart')]
        
        if not valid_records:
            # No valid records - show message
            html += f"""
                <tr>
                    <td colspan="2" style="text-align: center; height: 200px; vertical-align: middle; border: 1px solid {BORDER_COLOR_DATA};">
                        Údaje nie sú k dispozícii
                    </td>
                </tr>
            """
            html += """
            </tbody>
        </table>
        """
            return html
        
        valid_records.sort(key=lambda x: x.get('deliveryStart', ''))
        
        # Calculate statistics
        prices = [record['price'] for record in valid_records]
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        
        min_record = next(record for record in valid_records if record['price'] == min_price)
        max_record = next(record for record in valid_records if record['price'] == max_price)
        
        # Add data rows
        row_index = 0
        for record in valid_records:
            # Convert UTC times to local times
            time_from = self._convert_to_local_time(record.get('deliveryStart', ''))
            time_to = self._convert_to_local_time(record.get('deliveryEnd', ''))
            
            # Create time range string
            time_range = f"{time_from} - {time_to}" if time_from and time_to else ""
            
            price = record.get('price', 0)
            
            # Format price to 2 decimal places with € symbol
            price_formatted = f"{price:.2f} €"
            price_color = self._get_price_color(price)
            
            # Determine row background color (alternating)
            row_bg_color = BG_COLOR_TABLE_DATA_ROW_ODD if row_index % 2 == 0 else BG_COLOR_TABLE_DATA_ROW_EVEN
            
            html += f"""
                <tr style="background-color: {row_bg_color};">
                    <td style="width: auto; max-width: 200px; text-align: center; padding: {PADDING_DATA_ROWS};">{time_range}</td>
                    <td style="text-align: right; width: auto; max-width: 200px; color: {price_color}; padding: {PADDING_DATA_ROWS};">{price_formatted}</td>
                </tr>
            """
            row_index += 1
        
        # Add footer with statistics
        min_time_from = self._convert_to_local_time(min_record.get('deliveryStart', ''))
        min_time_to = self._convert_to_local_time(min_record.get('deliveryEnd', ''))
        max_time_from = self._convert_to_local_time(max_record.get('deliveryStart', ''))
        max_time_to = self._convert_to_local_time(max_record.get('deliveryEnd', ''))
        
        html += f"""
            </tbody>
            <tfoot>
                <tr style="background-color: #e8f4f8;">
                    <td colspan="2" style="padding: 10px; font-size: 14px;">
                        <strong>📅 Dátum:</strong> {tomorrow_formatted}<br>
                        <strong>📉 Min. cena:</strong> {min_price:.2f} € ({min_time_from}-{min_time_to})<br>
                        <strong>📈 Max. cena:</strong> {max_price:.2f} € ({max_time_from}-{max_time_to})<br>
                        <strong>📊 Priemerná cena:</strong> {avg_price:.2f} €
                    </td>
                </tr>
            </tfoot>
        </table>
        """
        
        return html

    async def my_controller(self):
        """Main controller logic for Master device."""
        LOGGER.debug("OKTE API: Master controller - updating current price from cache")
        
        if self._is_running:
            LOGGER.debug("OKTE API: Already running, skipping this cycle")
            return
        
        self._is_running = True

        try:
            # Update current price from cached data (no API call)
            await self.update_current_price()
            
        except Exception as e:
            LOGGER.error(f"OKTE API: Error in master controller: {e}")
            return

        finally:
            # Update all sensors via dispatcher
            async_dispatcher_send(self.hass, f"{DOMAIN}_feedback_update_{self._entry_id}")
            self._is_running = False


##############################################################################################################################
# Window Device Instance #####################################################################################################
##############################################################################################################################

class OKTE_Window_Instance:
    """Window device instance - calculates time windows from master device data."""

    def __init__(self) -> None:
        self.settings = self.Settings()
        self._is_running = False
        self.hass = None
        self._entry_id = None

        # Storage for sensor states
        self.sensor_states = {
            ENTITY_LOWEST_PRICE_WINDOW: None,
            ENTITY_LOWEST_PRICE_WINDOW_TODAY: None,
            ENTITY_LOWEST_PRICE_WINDOW_TOMORROW: None,
            ENTITY_HIGHEST_PRICE_WINDOW: None,
            ENTITY_HIGHEST_PRICE_WINDOW_TODAY: None,
            ENTITY_HIGHEST_PRICE_WINDOW_TOMORROW: None,
            ENTITY_DETECTOR_LOWEST_PRICE: False,
            ENTITY_DETECTOR_LOWEST_PRICE_TODAY: False,
            ENTITY_DETECTOR_LOWEST_PRICE_TOMORROW: False,
            ENTITY_DETECTOR_HIGHEST_PRICE: False,
            ENTITY_DETECTOR_HIGHEST_PRICE_TODAY: False,
            ENTITY_DETECTOR_HIGHEST_PRICE_TOMORROW: False,
        }
        
        # Storage for sensor attributes
        self.sensor_attributes = {}
        
        # Optimization: track when calculations are needed
        self._last_calculation_time = None  # Last time we did full calculation
        self._last_master_fetch_time = None  # Last fetch time from master device
        self._last_config_values = None  # Last configuration values for change detection
        
        # Debounce timer for config changes
        self._debounce_timer = None  # Timer handle for debounced calculation

        # Entity IDs
        self.SENSOR_ENTITY_LOWEST_PRICE_WINDOW = None
        self.SENSOR_ENTITY_LOWEST_PRICE_WINDOW_TODAY = None
        self.SENSOR_ENTITY_LOWEST_PRICE_WINDOW_TOMORROW = None
        self.SENSOR_ENTITY_HIGHEST_PRICE_WINDOW = None
        self.SENSOR_ENTITY_HIGHEST_PRICE_WINDOW_TODAY = None
        self.SENSOR_ENTITY_HIGHEST_PRICE_WINDOW_TOMORROW = None
        self.BINARY_SENSOR_ENTITY_DETECTOR_LOWEST_PRICE = None
        self.BINARY_SENSOR_ENTITY_DETECTOR_LOWEST_PRICE_TODAY = None
        self.BINARY_SENSOR_ENTITY_DETECTOR_LOWEST_PRICE_TOMORROW = None
        self.BINARY_SENSOR_ENTITY_DETECTOR_HIGHEST_PRICE = None
        self.BINARY_SENSOR_ENTITY_DETECTOR_HIGHEST_PRICE_TODAY = None
        self.BINARY_SENSOR_ENTITY_DETECTOR_HIGHEST_PRICE_TOMORROW = None

    def setup_entity_ids(self):
        """Setup entity IDs after entry_id is set."""
        if self._entry_id:
            from .const import ENTITY_PREFIX, get_calculator_number_from_name
            
            # Get calculator number from device name
            calculator_number = get_calculator_number_from_name(self.settings.device_name)
            
            # Calculator device uses prefix: okte_N_{entity_name} where N is calculator number
            self.SENSOR_ENTITY_LOWEST_PRICE_WINDOW = f"sensor.{ENTITY_PREFIX}_{calculator_number}_{ENTITY_LOWEST_PRICE_WINDOW}"
            self.SENSOR_ENTITY_LOWEST_PRICE_WINDOW_TODAY = f"sensor.{ENTITY_PREFIX}_{calculator_number}_{ENTITY_LOWEST_PRICE_WINDOW_TODAY}"
            self.SENSOR_ENTITY_LOWEST_PRICE_WINDOW_TOMORROW = f"sensor.{ENTITY_PREFIX}_{calculator_number}_{ENTITY_LOWEST_PRICE_WINDOW_TOMORROW}"
            self.SENSOR_ENTITY_HIGHEST_PRICE_WINDOW = f"sensor.{ENTITY_PREFIX}_{calculator_number}_{ENTITY_HIGHEST_PRICE_WINDOW}"
            self.SENSOR_ENTITY_HIGHEST_PRICE_WINDOW_TODAY = f"sensor.{ENTITY_PREFIX}_{calculator_number}_{ENTITY_HIGHEST_PRICE_WINDOW_TODAY}"
            self.SENSOR_ENTITY_HIGHEST_PRICE_WINDOW_TOMORROW = f"sensor.{ENTITY_PREFIX}_{calculator_number}_{ENTITY_HIGHEST_PRICE_WINDOW_TOMORROW}"
            self.BINARY_SENSOR_ENTITY_DETECTOR_LOWEST_PRICE = f"binary_sensor.{ENTITY_PREFIX}_{calculator_number}_{ENTITY_DETECTOR_LOWEST_PRICE}"
            self.BINARY_SENSOR_ENTITY_DETECTOR_LOWEST_PRICE_TODAY = f"binary_sensor.{ENTITY_PREFIX}_{calculator_number}_{ENTITY_DETECTOR_LOWEST_PRICE_TODAY}"
            self.BINARY_SENSOR_ENTITY_DETECTOR_LOWEST_PRICE_TOMORROW = f"binary_sensor.{ENTITY_PREFIX}_{calculator_number}_{ENTITY_DETECTOR_LOWEST_PRICE_TOMORROW}"
            self.BINARY_SENSOR_ENTITY_DETECTOR_HIGHEST_PRICE = f"binary_sensor.{ENTITY_PREFIX}_{calculator_number}_{ENTITY_DETECTOR_HIGHEST_PRICE}"
            self.BINARY_SENSOR_ENTITY_DETECTOR_HIGHEST_PRICE_TODAY = f"binary_sensor.{ENTITY_PREFIX}_{calculator_number}_{ENTITY_DETECTOR_HIGHEST_PRICE_TODAY}"
            self.BINARY_SENSOR_ENTITY_DETECTOR_HIGHEST_PRICE_TOMORROW = f"binary_sensor.{ENTITY_PREFIX}_{calculator_number}_{ENTITY_DETECTOR_HIGHEST_PRICE_TOMORROW}"
    
    def _get_current_local_time(self):
        """Get current time in Home Assistant's timezone."""
        try:
            import zoneinfo
            ha_timezone = self.hass.config.time_zone
            tz = zoneinfo.ZoneInfo(ha_timezone)
            return datetime.now(tz)
        except ImportError:
            # Fallback - return naive datetime with UTC offset guess
            from datetime import timezone
            utc_now = datetime.now(timezone.utc)
            # Assume CET/CEST (UTC+1/UTC+2) - not ideal but works for most EU
            return utc_now + timedelta(hours=1)

    @dataclasses.dataclass
    class Settings:
        """Settings for window device."""
        fallback_check_interval = DEFAULT_FALLBACK_CHECK_INTERVAL
        
        device_name: str = DEFAULT_DEVICE_NAME
        include_device_name_in_entity: bool = DEFAULT_INCLUDE_DEVICE_NAME_IN_ENTITY
        master_device: str = DEFAULT_MASTER_DEVICE
        window_size: int = DEFAULT_WINDOW_SIZE
        time_from: str = DEFAULT_TIME_FROM
        time_to: str = DEFAULT_TIME_TO

    def schedule_calculation(self, delay: float = None):
        """Schedule calculation with debounce to prevent multiple rapid recalculations.
        
        Args:
            delay: Delay in seconds. If None, uses CALCULATION_DEBOUNCE_DELAY from const.py
        """
        from homeassistant.helpers.event import async_call_later
        from .const import CALCULATION_DEBOUNCE_DELAY
        
        if delay is None:
            delay = CALCULATION_DEBOUNCE_DELAY
        
        # Cancel existing timer if any
        if self._debounce_timer is not None:
            self._debounce_timer()  # Call the cancel function
            self._debounce_timer = None
            LOGGER.debug(f"OKTE Calculation: Cancelled previous debounce timer")
        
        # Schedule new calculation
        async def delayed_calculation(_now=None):
            """Execute calculation after debounce delay."""
            self._debounce_timer = None
            LOGGER.debug(f"OKTE Calculation: Debounce timer expired, running calculation")
            await self.my_controller()
        
        self._debounce_timer = async_call_later(self.hass, delay, delayed_calculation)
        LOGGER.debug(f"OKTE Calculation: Scheduled calculation with {delay}s debounce")

    def system_started(self) -> None:
        """System started callback."""
        try:
            LOGGER.debug(f"Window Device System Started: {self.settings.device_name}")
        except Exception as e:
            LOGGER.error(f"Error during System Started: {e}")

    def get_master_price_data(self):
        """Get price data from master device."""
        try:
            if not self.settings.master_device:
                LOGGER.error("Master device not configured")
                return None
            
            # Find master device entry
            master_entry_id = self.settings.master_device
            LOGGER.debug(f"Looking for master device: {master_entry_id}")
            LOGGER.debug(f"Available DOMAIN entries: {list(self.hass.data.get(DOMAIN, {}).keys())}")
            
            if DOMAIN in self.hass.data and master_entry_id in self.hass.data[DOMAIN]:
                master_instance = self.hass.data[DOMAIN][master_entry_id].get("instance")
                if master_instance:
                    price_data = master_instance.price_data
                    LOGGER.debug(f"Found master price_data with keys: {list(price_data.keys())}")
                    LOGGER.debug(f"Today data records: {len(price_data.get('today_data', []))}")
                    LOGGER.debug(f"Tomorrow data records: {len(price_data.get('tomorrow_data', []))}")
                    return price_data
                else:
                    LOGGER.error(f"Master instance not found in entry {master_entry_id}")
            else:
                LOGGER.error(f"Master device {master_entry_id} not found in hass.data")
            
            return None
            
        except Exception as e:
            LOGGER.error(f"Error getting master price data: {e}", exc_info=True)
            return None

    def is_master_available(self):
        """Check if master device is available."""
        try:
            if not self.settings.master_device:
                return False
            
            master_entry_id = self.settings.master_device
            if DOMAIN in self.hass.data and master_entry_id in self.hass.data[DOMAIN]:
                return True
            
            return False
            
        except Exception as e:
            LOGGER.error(f"Error checking master availability: {e}")
            return False

    async def calculate_windows(self):
        """Calculate time windows from master device data."""
        try:
            # Get current time
            current_local_time = self._get_current_local_time()
            current_15min_period = current_local_time.replace(minute=(current_local_time.minute // 15) * 15, second=0, microsecond=0)
            
            # Get current configuration values FIRST (before any returns)
            current_config = {
                'lowest_window_size': int(self.number_values.get(ENTITY_LOWEST_WINDOW_SIZE, 3)),
                'lowest_time_from': self.time_values.get(ENTITY_LOWEST_TIME_FROM, dt_time(0, 0)),
                'lowest_time_to': self.time_values.get(ENTITY_LOWEST_TIME_TO, dt_time(23, 45)),
                'highest_window_size': int(self.number_values.get(ENTITY_HIGHEST_WINDOW_SIZE, 3)),
                'highest_time_from': self.time_values.get(ENTITY_HIGHEST_TIME_FROM, dt_time(0, 0)),
                'highest_time_to': self.time_values.get(ENTITY_HIGHEST_TIME_TO, dt_time(23, 45)),
            }
            
            # Check if master is available
            if not self.is_master_available():
                LOGGER.warning("OKTE Calculation: Master device not available - sensors will be unavailable")
                # Set all sensors to None to make them unavailable
                self.sensor_states[ENTITY_LOWEST_PRICE_WINDOW] = None
                self.sensor_states[ENTITY_LOWEST_PRICE_WINDOW_TODAY] = None
                self.sensor_states[ENTITY_LOWEST_PRICE_WINDOW_TOMORROW] = None
                self.sensor_states[ENTITY_HIGHEST_PRICE_WINDOW] = None
                self.sensor_states[ENTITY_HIGHEST_PRICE_WINDOW_TODAY] = None
                self.sensor_states[ENTITY_HIGHEST_PRICE_WINDOW_TOMORROW] = None
                self.sensor_states[ENTITY_DETECTOR_LOWEST_PRICE] = False
                self.sensor_states[ENTITY_DETECTOR_LOWEST_PRICE_TODAY] = False
                self.sensor_states[ENTITY_DETECTOR_LOWEST_PRICE_TOMORROW] = False
                self.sensor_states[ENTITY_DETECTOR_HIGHEST_PRICE] = False
                self.sensor_states[ENTITY_DETECTOR_HIGHEST_PRICE_TODAY] = False
                self.sensor_states[ENTITY_DETECTOR_HIGHEST_PRICE_TOMORROW] = False
                
                # Send update signal to reflect unavailable state
                from homeassistant.helpers.dispatcher import async_dispatcher_send
                async_dispatcher_send(self.hass, f"{DOMAIN}_feedback_update_{self._entry_id}")
                return
            
            price_data = self.get_master_price_data()
            if not price_data:
                LOGGER.warning("OKTE Calculation: No price data available from master device")
                # Set all sensors to None to make them unavailable
                self.sensor_states[ENTITY_LOWEST_PRICE_WINDOW] = None
                self.sensor_states[ENTITY_LOWEST_PRICE_WINDOW_TODAY] = None
                self.sensor_states[ENTITY_LOWEST_PRICE_WINDOW_TOMORROW] = None
                self.sensor_states[ENTITY_HIGHEST_PRICE_WINDOW] = None
                self.sensor_states[ENTITY_HIGHEST_PRICE_WINDOW_TODAY] = None
                self.sensor_states[ENTITY_HIGHEST_PRICE_WINDOW_TOMORROW] = None
                self.sensor_states[ENTITY_DETECTOR_LOWEST_PRICE] = False
                self.sensor_states[ENTITY_DETECTOR_LOWEST_PRICE_TODAY] = False
                self.sensor_states[ENTITY_DETECTOR_LOWEST_PRICE_TOMORROW] = False
                self.sensor_states[ENTITY_DETECTOR_HIGHEST_PRICE] = False
                self.sensor_states[ENTITY_DETECTOR_HIGHEST_PRICE_TODAY] = False
                self.sensor_states[ENTITY_DETECTOR_HIGHEST_PRICE_TOMORROW] = False
                
                # Send update signal to reflect unavailable state
                from homeassistant.helpers.dispatcher import async_dispatcher_send
                async_dispatcher_send(self.hass, f"{DOMAIN}_feedback_update_{self._entry_id}")
                return
            
            # Get master's last fetch time
            master_fetch_time = price_data.get('last_fetch')
            
            # Check if full calculation is needed
            need_calculation = False
            reason = []
            
            # First run - always calculate
            if self._last_calculation_time is None:
                need_calculation = True
                reason.append("first run")
            
            # New data from master API
            elif master_fetch_time and master_fetch_time != self._last_master_fetch_time:
                need_calculation = True
                reason.append("new API data")
                self._last_master_fetch_time = master_fetch_time
            
            # Configuration changed
            elif current_config != self._last_config_values:
                need_calculation = True
                reason.append("configuration changed")
                self._last_config_values = current_config
            
            # 15-minute period changed (for detector updates)
            elif self._last_calculation_time and current_15min_period != self._last_calculation_time:
                need_calculation = True
                reason.append("15-min period changed")
            
            # Skip calculation if not needed
            if not need_calculation:
                LOGGER.debug(f"OKTE Calculation: Skipping - no changes detected (last calc: {self._last_calculation_time.strftime('%H:%M:%S') if self._last_calculation_time else 'never'})")
                return
            
            # Perform calculation
            LOGGER.info(f"OKTE Calculation: Running window calculations - Reason: {', '.join(reason)}")
            LOGGER.debug(f"OKTE Calculation: Local time: {current_local_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
            today_data = price_data.get('today_data', [])
            tomorrow_data = price_data.get('tomorrow_data', [])
            
            # Get window settings
            lowest_window_size = current_config['lowest_window_size']
            lowest_time_from = current_config['lowest_time_from'].strftime("%H:%M")
            lowest_time_to = current_config['lowest_time_to'].strftime("%H:%M")
            
            highest_window_size = current_config['highest_window_size']
            highest_time_from = current_config['highest_time_from'].strftime("%H:%M")
            highest_time_to = current_config['highest_time_to'].strftime("%H:%M")
            
            LOGGER.debug(f"OKTE Calculation: Lowest window: size={lowest_window_size}, from={lowest_time_from}, to={lowest_time_to}")
            LOGGER.debug(f"OKTE Calculation: Highest window: size={highest_window_size}, from={highest_time_from}, to={highest_time_to}")
            
            # Calculate lowest price windows
            lowest_today = find_window_in_time_range(
                today_data, 
                lowest_window_size, 
                lowest_time_from, 
                lowest_time_to, 
                find_lowest=True,
                hass=self.hass
            )
            
            lowest_tomorrow = find_window_in_time_range(
                tomorrow_data, 
                lowest_window_size, 
                lowest_time_from, 
                lowest_time_to, 
                find_lowest=True,
                hass=self.hass
            )
            
            # Calculate highest price windows
            highest_today = find_window_in_time_range(
                today_data, 
                highest_window_size, 
                highest_time_from, 
                highest_time_to, 
                find_lowest=False,
                hass=self.hass
            )
            
            highest_tomorrow = find_window_in_time_range(
                tomorrow_data, 
                highest_window_size, 
                highest_time_from, 
                highest_time_to, 
                find_lowest=False,
                hass=self.hass
            )
            
            # Calculate cross-day windows for main sensors (from today time_from to tomorrow time_to)
            lowest_cross_day = find_window_cross_days(
                today_data,
                tomorrow_data,
                lowest_window_size,
                lowest_time_from,
                lowest_time_to,
                find_lowest=True,
                hass=self.hass
            )
            
            highest_cross_day = find_window_cross_days(
                today_data,
                tomorrow_data,
                highest_window_size,
                highest_time_from,
                highest_time_to,
                find_lowest=False,
                hass=self.hass
            )
            
            # Update sensor states
            self.sensor_states[ENTITY_LOWEST_PRICE_WINDOW_TODAY] = json.dumps(lowest_today) if lowest_today['found'] else None
            self.sensor_states[ENTITY_LOWEST_PRICE_WINDOW_TOMORROW] = json.dumps(lowest_tomorrow) if lowest_tomorrow['found'] else None
            self.sensor_states[ENTITY_HIGHEST_PRICE_WINDOW_TODAY] = json.dumps(highest_today) if highest_today['found'] else None
            self.sensor_states[ENTITY_HIGHEST_PRICE_WINDOW_TOMORROW] = json.dumps(highest_tomorrow) if highest_tomorrow['found'] else None
            
            # Update detectors - use local timezone for comparison
            current_local_time = self._get_current_local_time()
            
            # Check if current time is within lowest price window today
            if lowest_today['found']:
                try:
                    # Parse UTC times and convert to local timezone
                    utc_start = datetime.fromisoformat(lowest_today['start_time'].replace('Z', '+00:00'))
                    utc_end = datetime.fromisoformat(lowest_today['end_time'].replace('Z', '+00:00'))
                    
                    try:
                        import zoneinfo
                        ha_timezone = self.hass.config.time_zone
                        tz = zoneinfo.ZoneInfo(ha_timezone)
                        local_start = utc_start.astimezone(tz)
                        local_end = utc_end.astimezone(tz)
                    except ImportError:
                        local_start = utc_start + timedelta(hours=1)
                        local_end = utc_end + timedelta(hours=1)
                    
                    self.sensor_states[ENTITY_DETECTOR_LOWEST_PRICE_TODAY] = local_start <= current_local_time < local_end
                except Exception as e:
                    LOGGER.debug(f"Error checking lowest price window today: {e}")
                    self.sensor_states[ENTITY_DETECTOR_LOWEST_PRICE_TODAY] = False
            else:
                self.sensor_states[ENTITY_DETECTOR_LOWEST_PRICE_TODAY] = False
            
            # Check if current time is within highest price window today
            if highest_today['found']:
                try:
                    utc_start = datetime.fromisoformat(highest_today['start_time'].replace('Z', '+00:00'))
                    utc_end = datetime.fromisoformat(highest_today['end_time'].replace('Z', '+00:00'))
                    
                    try:
                        import zoneinfo
                        ha_timezone = self.hass.config.time_zone
                        tz = zoneinfo.ZoneInfo(ha_timezone)
                        local_start = utc_start.astimezone(tz)
                        local_end = utc_end.astimezone(tz)
                    except ImportError:
                        local_start = utc_start + timedelta(hours=1)
                        local_end = utc_end + timedelta(hours=1)
                    
                    self.sensor_states[ENTITY_DETECTOR_HIGHEST_PRICE_TODAY] = local_start <= current_local_time < local_end
                except Exception as e:
                    LOGGER.debug(f"Error checking highest price window today: {e}")
                    self.sensor_states[ENTITY_DETECTOR_HIGHEST_PRICE_TODAY] = False
            else:
                self.sensor_states[ENTITY_DETECTOR_HIGHEST_PRICE_TODAY] = False
            
            # Check if current time is within lowest price window tomorrow
            if lowest_tomorrow['found']:
                try:
                    utc_start = datetime.fromisoformat(lowest_tomorrow['start_time'].replace('Z', '+00:00'))
                    utc_end = datetime.fromisoformat(lowest_tomorrow['end_time'].replace('Z', '+00:00'))
                    
                    try:
                        import zoneinfo
                        ha_timezone = self.hass.config.time_zone
                        tz = zoneinfo.ZoneInfo(ha_timezone)
                        local_start = utc_start.astimezone(tz)
                        local_end = utc_end.astimezone(tz)
                    except ImportError:
                        local_start = utc_start + timedelta(hours=1)
                        local_end = utc_end + timedelta(hours=1)
                    
                    self.sensor_states[ENTITY_DETECTOR_LOWEST_PRICE_TOMORROW] = local_start <= current_local_time < local_end
                except Exception as e:
                    LOGGER.debug(f"Error checking lowest price window tomorrow: {e}")
                    self.sensor_states[ENTITY_DETECTOR_LOWEST_PRICE_TOMORROW] = False
            else:
                self.sensor_states[ENTITY_DETECTOR_LOWEST_PRICE_TOMORROW] = False
            
            # Check if current time is within highest price window tomorrow
            if highest_tomorrow['found']:
                try:
                    utc_start = datetime.fromisoformat(highest_tomorrow['start_time'].replace('Z', '+00:00'))
                    utc_end = datetime.fromisoformat(highest_tomorrow['end_time'].replace('Z', '+00:00'))
                    
                    try:
                        import zoneinfo
                        ha_timezone = self.hass.config.time_zone
                        tz = zoneinfo.ZoneInfo(ha_timezone)
                        local_start = utc_start.astimezone(tz)
                        local_end = utc_end.astimezone(tz)
                    except ImportError:
                        local_start = utc_start + timedelta(hours=1)
                        local_end = utc_end + timedelta(hours=1)
                    
                    self.sensor_states[ENTITY_DETECTOR_HIGHEST_PRICE_TOMORROW] = local_start <= current_local_time < local_end
                except Exception as e:
                    LOGGER.debug(f"Error checking highest price window tomorrow: {e}")
                    self.sensor_states[ENTITY_DETECTOR_HIGHEST_PRICE_TOMORROW] = False
            else:
                self.sensor_states[ENTITY_DETECTOR_HIGHEST_PRICE_TOMORROW] = False
            
            # Update general sensors (without today/tomorrow) - use cross-day windows
            # These search from today time_from to tomorrow time_to
            
            # LOWEST_PRICE_WINDOW - cross-day search result
            if lowest_cross_day['found']:
                self.sensor_states[ENTITY_LOWEST_PRICE_WINDOW] = json.dumps(lowest_cross_day)
                
                # Check if current time is within this window for detector
                try:
                    utc_start = datetime.fromisoformat(lowest_cross_day['start_time'].replace('Z', '+00:00'))
                    utc_end = datetime.fromisoformat(lowest_cross_day['end_time'].replace('Z', '+00:00'))
                    
                    try:
                        import zoneinfo
                        ha_timezone = self.hass.config.time_zone
                        tz = zoneinfo.ZoneInfo(ha_timezone)
                        local_start = utc_start.astimezone(tz)
                        local_end = utc_end.astimezone(tz)
                    except ImportError:
                        local_start = utc_start + timedelta(hours=1)
                        local_end = utc_end + timedelta(hours=1)
                    
                    self.sensor_states[ENTITY_DETECTOR_LOWEST_PRICE] = local_start <= current_local_time < local_end
                except Exception as e:
                    LOGGER.debug(f"Error checking lowest price window detector: {e}")
                    self.sensor_states[ENTITY_DETECTOR_LOWEST_PRICE] = False
            else:
                self.sensor_states[ENTITY_LOWEST_PRICE_WINDOW] = None
                self.sensor_states[ENTITY_DETECTOR_LOWEST_PRICE] = False
            
            # HIGHEST_PRICE_WINDOW - cross-day search result
            if highest_cross_day['found']:
                self.sensor_states[ENTITY_HIGHEST_PRICE_WINDOW] = json.dumps(highest_cross_day)
                
                # Check if current time is within this window for detector
                try:
                    utc_start = datetime.fromisoformat(highest_cross_day['start_time'].replace('Z', '+00:00'))
                    utc_end = datetime.fromisoformat(highest_cross_day['end_time'].replace('Z', '+00:00'))
                    
                    try:
                        import zoneinfo
                        ha_timezone = self.hass.config.time_zone
                        tz = zoneinfo.ZoneInfo(ha_timezone)
                        local_start = utc_start.astimezone(tz)
                        local_end = utc_end.astimezone(tz)
                    except ImportError:
                        local_start = utc_start + timedelta(hours=1)
                        local_end = utc_end + timedelta(hours=1)
                    
                    self.sensor_states[ENTITY_DETECTOR_HIGHEST_PRICE] = local_start <= current_local_time < local_end
                except Exception as e:
                    LOGGER.debug(f"Error checking highest price window detector: {e}")
                    self.sensor_states[ENTITY_DETECTOR_HIGHEST_PRICE] = False
            else:
                self.sensor_states[ENTITY_HIGHEST_PRICE_WINDOW] = None
                self.sensor_states[ENTITY_DETECTOR_HIGHEST_PRICE] = False
            
            # Store calculation time for optimization
            self._last_calculation_time = current_15min_period
            
            LOGGER.info(f"OKTE Calculation: Window calculations completed successfully")
            
            # Send update signal to refresh all sensors with new values
            from homeassistant.helpers.dispatcher import async_dispatcher_send
            async_dispatcher_send(self.hass, f"{DOMAIN}_feedback_update_{self._entry_id}")
            LOGGER.debug(f"OKTE Calculation: Sent update signal to refresh sensors")
            
        except Exception as e:
            LOGGER.error(f"OKTE Calculation: Error calculating windows: {e}")
            # On error, set all sensors to unavailable
            self.sensor_states[ENTITY_LOWEST_PRICE_WINDOW] = None
            self.sensor_states[ENTITY_LOWEST_PRICE_WINDOW_TODAY] = None
            self.sensor_states[ENTITY_LOWEST_PRICE_WINDOW_TOMORROW] = None
            self.sensor_states[ENTITY_HIGHEST_PRICE_WINDOW] = None
            self.sensor_states[ENTITY_HIGHEST_PRICE_WINDOW_TODAY] = None
            self.sensor_states[ENTITY_HIGHEST_PRICE_WINDOW_TOMORROW] = None
            self.sensor_states[ENTITY_DETECTOR_LOWEST_PRICE] = False
            self.sensor_states[ENTITY_DETECTOR_LOWEST_PRICE_TODAY] = False
            self.sensor_states[ENTITY_DETECTOR_LOWEST_PRICE_TOMORROW] = False
            self.sensor_states[ENTITY_DETECTOR_HIGHEST_PRICE] = False
            self.sensor_states[ENTITY_DETECTOR_HIGHEST_PRICE_TODAY] = False
            self.sensor_states[ENTITY_DETECTOR_HIGHEST_PRICE_TOMORROW] = False
            
            # Send update signal even on error to reflect unavailable state
            from homeassistant.helpers.dispatcher import async_dispatcher_send
            async_dispatcher_send(self.hass, f"{DOMAIN}_feedback_update_{self._entry_id}")
            LOGGER.debug(f"OKTE Calculation: Sent update signal after error")

    async def my_controller(self):
        """Main controller logic for Window device."""
        LOGGER.debug("OKTE Calculation: Window controller - checking if calculation needed")
        
        if self._is_running:
            LOGGER.debug("OKTE Calculation: Already running, skipping this cycle")
            return
        
        self._is_running = True

        try:
            # Calculate windows (optimized - skips if not needed)
            await self.calculate_windows()
            
        except Exception as e:
            LOGGER.error(f"OKTE Calculation: Error in window controller: {e}")
            return

        finally:
            # Update all sensors via dispatcher
            async_dispatcher_send(self.hass, f"{DOMAIN}_feedback_update_{self._entry_id}")
            self._is_running = False
