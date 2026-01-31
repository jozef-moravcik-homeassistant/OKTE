"""
OKTE Integration for Home Assistant
Custom integration for fetching and analyzing electricity prices from OKTE Slovakia
*** Core OKTE functions for fetching and analyzing electricity price data ***

Author: Jozef Moravcik
email: jozef.moravcik@moravcik.eu
"""

import logging
import urllib.request
import urllib.error
import json
from datetime import datetime, timedelta, timezone

from .const import (
    DEFAULT_MOST_EXPENSIVE_TIME_WINDOW_PERIOD,
    DEFAULT_CHEAPEST_TIME_WINDOW_PERIOD,
    DEFAULT_WINDOW_COUNT,
    OKTE_API_BASE_URL,
    REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


def format_local_time(iso_time_str, format_str='%d.%m.%Y %H:%M'):
    """
    Format ISO time to local format
    
    Args:
        iso_time_str (str): ISO time format
        format_str (str): Output format
    
    Returns:
        str: Formatted time
    """
    if not iso_time_str:
        return ""
    
    try:
        # Parse ISO format with timezone
        if iso_time_str.endswith('Z'):
            dt = datetime.fromisoformat(iso_time_str.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(iso_time_str)
        
        # Convert to local time (remove timezone info for local display)
        dt_local = dt.replace(tzinfo=None)
        
        return dt_local.strftime(format_str)
    except Exception as e:
        _LOGGER.warning(f"Error formatting time {iso_time_str}: {e}")
        return str(iso_time_str)


def fetch_okte_data(fetch_days=1, fetch_start_day=None):
    """
    Fetch data from OKTE API for specified period
    
    Args:
        fetch_days (int): Number of days to fetch (default: 1)
        fetch_start_day (str): Start date in format 'DD.MM.YYYY' or None for today (default: None)
    
    Returns:
        list: Array of objects with attributes deliveryStart, period, price
    """
    
    # Determine start date
    if fetch_start_day is None:
        start_date = datetime.now()
    else:
        try:
            # Parse date in DD.MM.YYYY format
            start_date = datetime.strptime(fetch_start_day, '%d.%m.%Y')
        except ValueError:
            try:
                # Try parsing in DD.M.YYYY format
                start_date = datetime.strptime(fetch_start_day, '%d.%m.%Y')
            except ValueError:
                _LOGGER.error(f"Invalid date format: {fetch_start_day}. Using today's date.")
                start_date = datetime.now()
    
    # Calculate end date
    end_date = start_date + timedelta(days=fetch_days - 1)
    
    # Format dates to required format (YYYY-MM-DD)
    delivery_day_from = start_date.strftime('%Y-%m-%d')
    delivery_day_to = end_date.strftime('%Y-%m-%d')
    
    # Create URL with dynamic dates
    url = f"{OKTE_API_BASE_URL}?deliveryDayFrom={delivery_day_from}&deliveryDayTo={delivery_day_to}"
    
    _LOGGER.info(f"Fetching data from: {url}")
    _LOGGER.info(f"Period: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')} ({fetch_days} days)")
    
    try:
        # Create HTTP request with headers
        request = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Home Assistant OKTE Integration',
                'Accept': 'application/json'
            }
        )
        
        # HTTP GET request
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            # Read response
            response_data = response.read().decode('utf-8')
        
        # Parse JSON response
        data = json.loads(response_data)
        
        # Create array with required attributes
        result_array = []
        
        for item in data:
            # Extract required attributes
            record = {
                'deliveryStart': item.get('deliveryStart'),
                'deliveryEnd': item.get('deliveryEnd'),
                'deliveryDayCET': item.get('deliveryDay'),
                'HourStartCET': format_local_time(item.get('deliveryStart'), '%H:%M'),
                'HourEndCET': format_local_time(item.get('deliveryEnd'), '%H:%M'),
                'period': item.get('period'),
                'price': item.get('price')
            }
            result_array.append(record)
        
        _LOGGER.info(f"Fetched {len(result_array)} records")
        return result_array
        
    except urllib.error.HTTPError as e:
        _LOGGER.error(f"HTTP error {e.code}: {e.reason}")
        return []
    except urllib.error.URLError as e:
        _LOGGER.error(f"URL error: {e.reason}")
        return []
    except json.JSONDecodeError as e:
        _LOGGER.error(f"JSON parsing error: {e}")
        return []
    except Exception as e:
        _LOGGER.error(f"Unexpected error: {e}")
        return []


def calculate_price_statistics(data):
    """
    Calculate price statistics from fetched data
    
    Args:
        data (list): Array of objects with prices
    
    Returns:
        dict: Dictionary with statistics (min, max, avg, count)
    """
    if not data:
        return {
            'min_price': None,
            'max_price': None,
            'avg_price': None,
            'count': 0,
            'min_record': None,
            'max_record': None
        }
    
    # Filter valid prices (not None)
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
    
    # Calculate statistics
    prices = [record['price'] for record in valid_prices]
    min_price = min(prices)
    max_price = max(prices)
    avg_price = sum(prices) / len(prices)
    
    # Find records with min/max price
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


def find_cheapest_time_window(data, window_hours=DEFAULT_CHEAPEST_TIME_WINDOW_PERIOD):
    """
    Find time window with lowest average price
    
    Args:
        data (list): Array of objects with prices
        window_hours (int): Size of time window in hours
    
    Returns:
        dict: Information about cheapest time window
    """
    if not data or len(data) < window_hours:
        return {
            'found': False,
            'message': f'Not enough data for {window_hours}-hour window'
        }
    
    # Filter valid records and sort by time
    valid_data = [record for record in data if record['price'] is not None and record['deliveryStart'] is not None and record['deliveryEnd'] is not None and record['deliveryDayCET'] is not None and record['HourStartCET'] is not None and record['HourEndCET'] is not None]
    
    if len(valid_data) < window_hours:
        return {
            'found': False,
            'message': f'Not enough valid data for {window_hours}-hour window'
        }
    
    # Sort by deliveryStart
    try:
        valid_data.sort(key=lambda x: x['deliveryStart'])
    except:
        return {
            'found': False,
            'message': 'Error sorting data by time'
        }
    
    best_window = None
    best_avg_price = float('inf')
    
    # Slide window through all possible positions
    for i in range(len(valid_data) - window_hours + 1):
        window_data = valid_data[i:i + window_hours]
        
        # Calculate average price in window
        window_prices = [record['price'] for record in window_data]
        avg_price = sum(window_prices) / len(window_prices)
        
        # If this window is better, save it
        if avg_price < best_avg_price:
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
        return {
            'found': True,
            'window_hours': window_hours,
            'start_time': best_window['start_time'],
            'end_time': best_window['end_time'],
            'avg_price': best_window['avg_price'],
            'min_price': best_window['min_price'],
            'max_price': best_window['max_price'],
            'total_cost_per_mwh': best_window['total_cost_per_mwh'],
            'records': best_window['records'],
            'savings_vs_daily_avg': None  # Will be calculated later if needed
        }
    else:
        return {
            'found': False,
            'message': 'Could not find suitable time window'
        }


def find_most_expensive_time_window(data, window_hours=DEFAULT_MOST_EXPENSIVE_TIME_WINDOW_PERIOD):
    """
    Find time window with highest average price
    
    Args:
        data (list): Array of objects with prices
        window_hours (int): Size of time window in hours
    
    Returns:
        dict: Information about most expensive time window
    """
    if not data or len(data) < window_hours:
        return {
            'found': False,
            'message': f'Not enough data for {window_hours}-hour window'
        }
    
    # Filter valid records and sort by time
    valid_data = [record for record in data if record['price'] is not None and record['deliveryStart'] is not None and record['deliveryEnd'] is not None and record['deliveryDayCET'] is not None and record['HourStartCET'] is not None and record['HourEndCET'] is not None]
    
    if len(valid_data) < window_hours:
        return {
            'found': False,
            'message': f'Not enough valid data for {window_hours}-hour window'
        }
    
    # Sort by deliveryStart
    try:
        valid_data.sort(key=lambda x: x['deliveryStart'])
    except:
        return {
            'found': False,
            'message': 'Error sorting data by time'
        }
    
    worst_window = None
    worst_avg_price = float('-inf')
    
    # Slide window through all possible positions
    for i in range(len(valid_data) - window_hours + 1):
        window_data = valid_data[i:i + window_hours]
        
        # Calculate average price in window
        window_prices = [record['price'] for record in window_data]
        avg_price = sum(window_prices) / len(window_prices)
        
        # If this window is more expensive, save it
        if avg_price > worst_avg_price:
            worst_avg_price = avg_price
            worst_window = {
                'start_time': window_data[0]['deliveryStart'],
                'end_time': window_data[-1]['deliveryEnd'],
                'avg_price': round(avg_price, 2),
                'min_price': min(window_prices),
                'max_price': max(window_prices),
                'records': window_data,
                'total_cost_per_mwh': round(sum(window_prices), 2)
            }
    
    if worst_window:
        return {
            'found': True,
            'window_hours': window_hours,
            'start_time': worst_window['start_time'],
            'end_time': worst_window['end_time'],
            'avg_price': worst_window['avg_price'],
            'min_price': worst_window['min_price'],
            'max_price': worst_window['max_price'],
            'total_cost_per_mwh': worst_window['total_cost_per_mwh'],
            'records': worst_window['records'],
            'extra_cost_vs_daily_avg': None  # Will be calculated later if needed
        }
    else:
        return {
            'found': False,
            'message': 'Could not find suitable time window'
        }


def find_multiple_expensive_windows(data, window_hours=DEFAULT_MOST_EXPENSIVE_TIME_WINDOW_PERIOD, count=DEFAULT_WINDOW_COUNT):
    """
    Find multiple most expensive time windows
    
    Args:
        data (list): Array of objects with prices
        window_hours (int): Size of time window in hours
        count (int): Number of windows to find
    
    Returns:
        list: List of most expensive windows
    """
    if not data or len(data) < window_hours:
        return []
    
    valid_data = [record for record in data if record['price'] is not None and record['deliveryStart'] is not None and record['deliveryEnd'] is not None and record['deliveryDayCET'] is not None and record['HourStartCET'] is not None and record['HourEndCET'] is not None]
    
    if len(valid_data) < window_hours:
        return []
    
    try:
        valid_data.sort(key=lambda x: x['deliveryStart'])
    except:
        return []
    
    windows = []
    
    # Find all possible windows
    for i in range(len(valid_data) - window_hours + 1):
        window_data = valid_data[i:i + window_hours]
        window_prices = [record['price'] for record in window_data]
        avg_price = sum(window_prices) / len(window_prices)
        
        windows.append({
            'start_time': window_data[0]['deliveryStart'],
            'end_time': window_data[-1]['deliveryEnd'],
            'avg_price': round(avg_price, 2),
            'records': window_data
        })
    
    # Sort by average price (from most expensive) and return top N
    windows.sort(key=lambda x: x['avg_price'], reverse=True)
    return windows[:count]


def find_multiple_cheap_windows(data, window_hours=DEFAULT_CHEAPEST_TIME_WINDOW_PERIOD, count=DEFAULT_WINDOW_COUNT):
    """
    Find multiple cheapest time windows
    
    Args:
        data (list): Array of objects with prices
        window_hours (int): Size of time window in hours
        count (int): Number of windows to find
    
    Returns:
        list: List of cheapest windows
    """
    if not data or len(data) < window_hours:
        return []
    
    valid_data = [record for record in data if record['price'] is not None and record['deliveryStart'] is not None and record['deliveryEnd'] is not None and record['deliveryDayCET'] is not None and record['HourStartCET'] is not None and record['HourEndCET'] is not None]
    
    if len(valid_data) < window_hours:
        return []
    
    try:
        valid_data.sort(key=lambda x: x['deliveryStart'])
    except:
        return []
    
    windows = []
    
    # Find all possible windows
    for i in range(len(valid_data) - window_hours + 1):
        window_data = valid_data[i:i + window_hours]
        window_prices = [record['price'] for record in window_data]
        avg_price = sum(window_prices) / len(window_prices)
        
        windows.append({
            'start_time': window_data[0]['deliveryStart'],
            'end_time': window_data[-1]['deliveryEnd'],
            'avg_price': round(avg_price, 2),
            'records': window_data
        })
    
    # Sort by average price and return top N
    windows.sort(key=lambda x: x['avg_price'])
    return windows[:count]


def print_price_statistics(data, title="Price Statistics"):
    """
    Print price statistics using logger
    
    Args:
        data (list): Array of objects with prices
        title (str): Title for statistics
    """
    _LOGGER.info(f"📊 {title}")
    _LOGGER.info("=" * 40)
    
    stats = calculate_price_statistics(data)
    
    if stats['count'] == 0:
        _LOGGER.info("❌ No valid data for analysis")
        return
    
    _LOGGER.info(f"📈 Highest price: {stats['max_price']} €/MWh")
    _LOGGER.info(f"📉 Lowest price: {stats['min_price']} €/MWh")
    _LOGGER.info(f"📊 Average price: {stats['avg_price']} €/MWh")
    _LOGGER.info(f"🔢 Number of records: {stats['count']}")
    
    # Price spread
    price_spread = stats['max_price'] - stats['min_price']
    _LOGGER.info(f"📏 Price spread: {round(price_spread, 2)} €/MWh")
    
    # Information about cheapest hour
    if stats['min_record']:
        min_time = format_local_time(stats['min_record']['deliveryStart'], '%d.%m.%Y %H:%M')
        _LOGGER.info(f"⏰ Cheapest hour: {min_time}")
    
    # Information about most expensive hour
    if stats['max_record']:
        max_time = format_local_time(stats['max_record']['deliveryStart'], '%d.%m.%Y %H:%M')
        _LOGGER.info(f"⏰ Most expensive hour: {max_time}")


def print_cheapest_window(data, window_hours=DEFAULT_CHEAPEST_TIME_WINDOW_PERIOD):
    """
    Print information about cheapest time window using logger
    
    Args:
        data (list): Array of objects with prices
        window_hours (int): Size of time window in hours
    """
    result = find_cheapest_time_window(data, window_hours)
    
    _LOGGER.info(f"🕐 Cheapest {window_hours}-hour window")
    _LOGGER.info("=" * 40)
    
    if not result['found']:
        _LOGGER.info(f"❌ {result['message']}")
        return
    
    # Format time
    try:
        start_str = format_local_time(result['start_time'], '%d.%m.%Y %H:%M')
        end_str = format_local_time(result['end_time'], '%H:%M')
    except:
        start_str = result['start_time']
        end_str = result['end_time']
    
    _LOGGER.info(f"⏰ Time window: {start_str} - {end_str}")
    _LOGGER.info(f"💰 Average price: {result['avg_price']} €/MWh")
    _LOGGER.info(f"📉 Lowest price in window: {result['min_price']} €/MWh")
    _LOGGER.info(f"📈 Highest price in window: {result['max_price']} €/MWh")
    _LOGGER.info(f"🧮 Total cost for {window_hours}h: {result['total_cost_per_mwh']} €/MWh")
    
    # Calculate savings vs daily average
    daily_stats = calculate_price_statistics(data)
    if daily_stats['avg_price'] and result['avg_price']:
        savings = daily_stats['avg_price'] - result['avg_price']
        savings_percent = (savings / daily_stats['avg_price']) * 100
        _LOGGER.info(f"💡 Savings vs average: {round(savings, 2)} €/MWh ({round(savings_percent, 1)}%)")


def print_most_expensive_window(data, window_hours=DEFAULT_MOST_EXPENSIVE_TIME_WINDOW_PERIOD):
    """
    Print information about most expensive time window using logger
    
    Args:
        data (list): Array of objects with prices
        window_hours (int): Size of time window in hours
    """
    result = find_most_expensive_time_window(data, window_hours)
    
    _LOGGER.info(f"🕐 Most expensive {window_hours}-hour window")
    _LOGGER.info("=" * 40)
    
    if not result['found']:
        _LOGGER.info(f"❌ {result['message']}")
        return
    
    # Format time
    try:
        start_str = format_local_time(result['start_time'], '%d.%m.%Y %H:%M')
        end_str = format_local_time(result['end_time'], '%H:%M')
    except:
        start_str = result['start_time']
        end_str = result['end_time']
    
    _LOGGER.info(f"⏰ Time window: {start_str} - {end_str}")
    _LOGGER.info(f"💰 Average price: {result['avg_price']} €/MWh")
    _LOGGER.info(f"📉 Lowest price in window: {result['min_price']} €/MWh")
    _LOGGER.info(f"📈 Highest price in window: {result['max_price']} €/MWh")
    _LOGGER.info(f"🧮 Total cost for {window_hours}h: {result['total_cost_per_mwh']} €/MWh")
    
    # Calculate extra costs vs daily average
    daily_stats = calculate_price_statistics(data)
    if daily_stats['avg_price'] and result['avg_price']:
        extra_cost = result['avg_price'] - daily_stats['avg_price']
        extra_percent = (extra_cost / daily_stats['avg_price']) * 100
        _LOGGER.info(f"⚠️ Extra cost vs average: {round(extra_cost, 2)} €/MWh ({round(extra_percent, 1)}%)")