from __future__ import annotations
"""The OKTE Integration"""
"""Author: Jozef Moravcik"""
"""email: jozef.moravcik@moravcik.eu"""

""" okte.py """

""" Core classes and API functions for OKTE Integration."""

import asyncio
import dataclasses
import json
import logging
import statistics as py_statistics
from datetime import datetime, timedelta, timezone, time as dt_time

import aiohttp

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store

from .const import (
    CALCULATION_DEBOUNCE_DELAY,
    DEFAULT_DATA_FAILOVER_MODE,
    DEFAULT_DEVICE_NAME,
    DEFAULT_FAILOVER_DAYS,
    DEFAULT_FAILOVER_WEEKS,
    DEFAULT_FETCH_DAYS,
    DEFAULT_FETCH_TIME,
    DEFAULT_MASTER_DEVICE,
    DEFAULT_PRICE_UNIT,
    DEFAULT_TIME_FROM,
    DEFAULT_TIME_TO,
    DEFAULT_WINDOW_SIZE,
    DOMAIN,
    ENTITY_AVERAGE_PRICE_TODAY,
    ENTITY_AVERAGE_PRICE_TOMORROW,
    ENTITY_CONNECTION_STATUS,
    ENTITY_CURRENT_PRICE,
    ENTITY_DATA_COUNT,
    ENTITY_DETECTOR_HIGHEST_PRICE,
    ENTITY_DETECTOR_HIGHEST_PRICE_TODAY,
    ENTITY_DETECTOR_LOWEST_PRICE,
    ENTITY_DETECTOR_LOWEST_PRICE_TODAY,
    ENTITY_ERROR_CODE,
    ENTITY_FAILOVER_DATA,
    ENTITY_HIGHEST_PRICE_WINDOW,
    ENTITY_HIGHEST_PRICE_WINDOW_TODAY,
    ENTITY_HIGHEST_PRICE_WINDOW_TOMORROW,
    ENTITY_HIGHEST_TIME_FROM,
    ENTITY_HIGHEST_TIME_TO,
    ENTITY_HIGHEST_WINDOW_SIZE,
    ENTITY_HTML_TABLE_TODAY,
    ENTITY_HTML_TABLE_TOMORROW,
    ENTITY_LAST_UPDATE,
    ENTITY_LOWEST_PRICE_WINDOW,
    ENTITY_LOWEST_PRICE_WINDOW_TODAY,
    ENTITY_LOWEST_PRICE_WINDOW_TOMORROW,
    ENTITY_LOWEST_TIME_FROM,
    ENTITY_LOWEST_TIME_TO,
    ENTITY_LOWEST_WINDOW_SIZE,
    ENTITY_MAX_PRICE_TODAY,
    ENTITY_MAX_PRICE_TOMORROW,
    ENTITY_MIN_PRICE_TODAY,
    ENTITY_MIN_PRICE_TOMORROW,
    ENTITY_PREFIX,
    ENTITY_PRICES_TODAY,
    ENTITY_PRICES_TOMORROW,
    FAILOVER_HISTORY_KEEP_DAYS,
    FAILOVER_MODE_ALL_DAYS,
    FAILOVER_MODE_WEEKDAYS,
    FAILOVER_STATISTICS_DAYS,
    FETCH_RETRY_INTERVAL,
    MARKET_TIMEZONE,
    OKTE_API_BASE_URL,
    PRICE_UNIT_EUR_KWH,
    PRICE_UNIT_LABELS,
    REQUEST_TIMEOUT,
    SIGNAL_FEEDBACK_UPDATE,
    SIGNAL_MASTER_DATA_UPDATED,
    STATE_FALSE,
    STATE_TRUE,
    TOMORROW_RETRY_INTERVAL,
    get_calculator_number_from_name,
)

LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1


def get_prices_store(hass, entry_id):
    """Return Store used to persist downloaded price data."""
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}_{entry_id}_prices")

# Color and styling constants for HTML tables
COLOR_PRICE_HIGH = "#009000"  # Green for high prices
COLOR_PRICE_LOW = "#d08000"  # Orange for low prices
COLOR_PRICE_NEGATIVE = "#d00000"  # Red for negative prices
THRESHOLD_PRICE_HIGH = 20
THRESHOLD_PRICE_LOW = 0
BG_COLOR_TABLE_HEADER_ROW1 = "#4a90e2"
BG_COLOR_TABLE_HEADER_ROW2 = "#f2f2f2"
TEXT_COLOR_TABLE_HEADER_ROW1 = "#ffffff"
TEXT_COLOR_TABLE_HEADER_ROW2 = "#000000"
BORDER_COLOR_HEADER = "#a0a0a0"
BORDER_COLOR_DATA = "#a0a0a0"
PADDING_HEADER_ROW1 = "10px 10px 10px 10px"
PADDING_HEADER_ROW2 = "2px 7px 2px 7px"
PADDING_DATA_ROWS = "1px 7px 1px 7px"
BG_COLOR_TABLE_DATA_ROW_ODD = "#ffffff"
BG_COLOR_TABLE_DATA_ROW_EVEN = "#f5f7ff"

##############################################################################################################################
# Helper functions ###########################################################################################################
##############################################################################################################################

def parse_utc(iso_time_str):
    """Parse an ISO UTC time string from the API ('...Z') to an aware datetime."""
    return datetime.fromisoformat(iso_time_str.replace('Z', '+00:00'))


def to_market_time(iso_time_str):
    """Convert an ISO UTC time string to an aware datetime in market (Slovak) time."""
    return parse_utc(iso_time_str).astimezone(MARKET_TIMEZONE)


def format_market_time(iso_time_str, format_str='%d.%m.%Y %H:%M'):
    """Format an ISO UTC time string in market (Slovak) time. Empty string for missing/invalid input."""
    if not iso_time_str:
        return ""
    try:
        return to_market_time(iso_time_str).strftime(format_str)
    except (TypeError, ValueError) as e:
        LOGGER.debug("Error formatting time %s: %s", iso_time_str, e)
        return ""


def is_valid_record(record):
    """True when a price record has a price and a delivery start."""
    return record.get('price') is not None and bool(record.get('deliveryStart'))


def build_period_entries(records):
    """Convert price records to the 'period_data' structure used by the prices sensors."""
    entries = []
    for record in sorted((r for r in records if is_valid_record(r)), key=lambda x: x['deliveryStart']):
        try:
            delivery_start = parse_utc(record['deliveryStart'])
        except (TypeError, ValueError):
            continue
        delivery_local = delivery_start.astimezone(MARKET_TIMEZONE)
        entries.append({
            'time': record['deliveryStart'],  # ISO format for graphs
            'time_local': delivery_local.strftime('%Y-%m-%d %H:%M:%S'),
            'price': record['price'],
            'period': record.get('period'),
            'period_start': record.get('HourStartCET'),
            'period_end': record.get('HourEndCET'),
            'date': record.get('deliveryDayCET'),
            'day_name': delivery_local.strftime('%A'),
            'period_label': f"{record.get('HourStartCET', '')}-{record.get('HourEndCET', '')}",
            'timestamp': int(delivery_start.timestamp() * 1000),  # For ApexCharts
        })
    return entries


def find_record_at(records, moment):
    """Return the record whose delivery interval contains the aware datetime 'moment' (or None)."""
    for record in records:
        try:
            if parse_utc(record['deliveryStart']) <= moment < parse_utc(record['deliveryEnd']):
                return record
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    return None


##############################################################################################################################
# API Functions ##############################################################################################################
##############################################################################################################################

async def async_fetch_okte_data(hass, fetch_days=2, start_date=None):
    """
    Fetch day-ahead market results from the OKTE API.

    Args:
        hass: Home Assistant instance (its shared aiohttp session is used)
        fetch_days (int): Number of days to fetch (default: 2 = today and tomorrow)
        start_date (date): First market day to fetch, None for today (market time)

    Returns:
        list: price records, empty list on any error
    """
    if start_date is None:
        start_date = datetime.now(MARKET_TIMEZONE).date()
    end_date = start_date + timedelta(days=fetch_days - 1)

    url = f"{OKTE_API_BASE_URL}?deliveryDayFrom={start_date:%Y-%m-%d}&deliveryDayTo={end_date:%Y-%m-%d}"
    LOGGER.debug("OKTE API: Fetching data from %s", url)

    session = async_get_clientsession(hass)
    try:
        async with session.get(
            url,
            headers={'User-Agent': 'Home Assistant OKTE Integration', 'Accept': 'application/json'},
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        ) as response:
            response.raise_for_status()
            data = await response.json(content_type=None)
    except aiohttp.ClientResponseError as e:
        LOGGER.error("OKTE API: HTTP error %s: %s", e.status, e.message)
        return []
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        LOGGER.error("OKTE API: Connection error: %s", e or type(e).__name__)
        return []
    except ValueError as e:
        LOGGER.error("OKTE API: JSON parsing error: %s", e)
        return []

    if not isinstance(data, list):
        LOGGER.error("OKTE API: Unexpected response format")
        return []

    result = []
    for item in data:
        delivery_start = item.get('deliveryStart')
        delivery_end = item.get('deliveryEnd')
        try:
            delivery_day = to_market_time(delivery_start).strftime('%Y-%m-%d')
        except (TypeError, ValueError, AttributeError):
            delivery_day = item.get('deliveryDay')
        result.append({
            'deliveryStart': delivery_start,
            'deliveryEnd': delivery_end,
            'deliveryDayCET': delivery_day,
            'HourStartCET': format_market_time(delivery_start, '%H:%M'),
            'HourEndCET': format_market_time(delivery_end, '%H:%M'),
            'period': item.get('period'),
            'price': item.get('price'),
        })

    LOGGER.debug("OKTE API: Successfully fetched %d records", len(result))
    return result


def filter_data_by_date(data, target_date):
    """Filter data for specific market day."""
    if not data:
        return []
    target_date_str = target_date.strftime('%Y-%m-%d')
    return [record for record in data if record.get('deliveryDayCET') == target_date_str]


def calculate_price_statistics(data):
    """Calculate price statistics from fetched data."""
    valid_prices = [record for record in (data or []) if record.get('price') is not None]
    if not valid_prices:
        return {
            'min_price': None,
            'max_price': None,
            'avg_price': None,
            'count': 0,
            'min_record': None,
            'max_record': None,
        }

    prices = [record['price'] for record in valid_prices]
    min_price = min(prices)
    max_price = max(prices)
    return {
        'min_price': min_price,
        'max_price': max_price,
        'avg_price': round(sum(prices) / len(prices), 2),
        'count': len(valid_prices),
        'min_record': next(record for record in valid_prices if record['price'] == min_price),
        'max_record': next(record for record in valid_prices if record['price'] == max_price),
    }


##############################################################################################################################
# Window search ##############################################################################################################
##############################################################################################################################

def _range_end_minutes(time_obj):
    """Minutes of the end of a time range. 23:59 means the end of the day (24:00)."""
    if time_obj.hour == 23 and time_obj.minute == 59:
        return 1440
    return time_obj.hour * 60 + time_obj.minute


def _period_minutes(record):
    """Return (start, end) of a period in minutes of the day; the end of the last period is 1440."""
    start_dt = datetime.strptime(record['HourStartCET'], '%H:%M')
    start = start_dt.hour * 60 + start_dt.minute
    end_str = record.get('HourEndCET')
    if end_str:
        end_dt = datetime.strptime(end_str, '%H:%M')
        end = end_dt.hour * 60 + end_dt.minute
    else:
        end = start + 15
    if end <= start:
        end += 1440
    return start, end


def limit_periods_to_time_range(periods, time_from_str, time_to_str, cross_days=False):
    """
    Limit the number of periods so the window never exceeds the from-to time range.
    The range is converted to 15-minute periods and rounded down (e.g. 2:16 -> 9 periods).
    The configured value is not changed - only the value used for the calculation.
    """
    try:
        time_from = datetime.strptime(time_from_str, '%H:%M').time()
        time_to = datetime.strptime(time_to_str, '%H:%M').time()
    except ValueError:
        return periods

    from_minutes = time_from.hour * 60 + time_from.minute
    to_minutes = _range_end_minutes(time_to)

    # Only whole 15-minute periods lying completely inside the range are used:
    # the first period starts at time_from rounded up, the last one ends at time_to rounded down
    first_start = -(-from_minutes // 15) * 15
    last_end = (to_minutes // 15) * 15

    if cross_days:
        # From time_from today (until the end of the day) + from the start of tomorrow to time_to
        available = (1440 - first_start) // 15 + last_end // 15
    else:
        available = (last_end - first_start) // 15
        if to_minutes - from_minutes < 0:
            # time_to is before time_from - no data in a single day, nothing to limit
            return periods

    return min(periods, max(available, 0))


def _window_not_found(message, periods):
    """Result structure when no window was found."""
    return {
        'found': False,
        'message': message,
        'start_time': None,
        'end_time': None,
        'periods': periods,
        'min_price': None,
        'max_price': None,
        'avg_price': None,
        'records': [],
    }


def _is_continuous(records):
    """True when the records follow each other without gaps."""
    try:
        return all(
            parse_utc(records[i]['deliveryEnd']) == parse_utc(records[i + 1]['deliveryStart'])
            for i in range(len(records) - 1)
        )
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def _best_window(records, periods, find_lowest):
    """Sliding window search. Returns (window_records, avg_price) of the best continuous window or (None, None)."""
    best_records = None
    best_avg = None
    for i in range(len(records) - periods + 1):
        window = records[i:i + periods]
        if not _is_continuous(window):
            continue
        avg = sum(r['price'] for r in window) / periods
        if best_avg is None or (avg < best_avg if find_lowest else avg > best_avg):
            best_records, best_avg = window, avg
    return best_records, best_avg


def _window_result(window, avg_price, periods):
    """Result structure of a found window."""
    start_utc = parse_utc(window[0]['deliveryStart'])
    end_utc = parse_utc(window[-1]['deliveryEnd'])
    start_local = start_utc.astimezone(MARKET_TIMEZONE)
    end_local = end_utc.astimezone(MARKET_TIMEZONE)
    prices = [r['price'] for r in window]

    formatted_records = []
    for record in window:
        try:
            period_start_utc = parse_utc(record['deliveryStart']).strftime('%H:%M')
            period_end_utc = parse_utc(record['deliveryEnd']).strftime('%H:%M')
        except (KeyError, TypeError, ValueError, AttributeError):
            period_start_utc = record.get('HourStartCET')
            period_end_utc = record.get('HourEndCET')
        formatted_records.append({
            'price': record.get('price'),
            'period': record.get('period'),
            'delivery_start': record.get('deliveryStart'),
            'delivery_end': record.get('deliveryEnd'),
            'period_start': period_start_utc,
            'period_end': period_end_utc,
            'date': record.get('deliveryDayCET'),
            'time_local': format_market_time(record.get('deliveryStart'), '%d.%m.%Y %H:%M'),
        })

    return {
        'found': True,
        'start_time': start_local.isoformat(),
        'end_time': end_local.isoformat(),
        'start_time_UTC': f"UTC: {start_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        'end_time_UTC': f"UTC: {end_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        'start_time_local': start_local.strftime('%d.%m.%Y %H:%M'),
        'end_time_local': end_local.strftime('%d.%m.%Y %H:%M'),
        'periods': periods,
        'min_price': min(prices),
        'max_price': max(prices),
        'avg_price': round(avg_price, 2),
        'records': formatted_records,
    }


def _parse_time_range(time_from_str, time_to_str):
    """Parse 'HH:MM' strings, (None, None) when invalid."""
    try:
        return datetime.strptime(time_from_str, '%H:%M').time(), datetime.strptime(time_to_str, '%H:%M').time()
    except (TypeError, ValueError):
        return None, None


def find_window_cross_days(today_data, tomorrow_data, periods, time_from_str, time_to_str, find_lowest=True):
    """
    Find time window with lowest or highest average price across two days.
    Search from today time_from to tomorrow time_to.
    """
    periods = int(periods)
    limited_periods = limit_periods_to_time_range(periods, time_from_str, time_to_str, cross_days=True)
    if limited_periods != periods:
        LOGGER.debug("OKTE Calculation: Cross-day periods limited from %s to %s by time range %s-%s",
                     periods, limited_periods, time_from_str, time_to_str)
        periods = limited_periods
    if periods < 1:
        return _window_not_found('Time range is shorter than one period', periods)

    time_from, time_to = _parse_time_range(time_from_str, time_to_str)
    if time_from is None:
        return _window_not_found('Invalid time format', None)

    combined = []
    # Today's data from time_from onwards
    for record in today_data:
        if is_valid_record(record) and record.get('HourStartCET'):
            try:
                if datetime.strptime(record['HourStartCET'], '%H:%M').time() >= time_from:
                    combined.append(record)
            except ValueError:
                continue
    # Tomorrow's data up to time_to
    for record in tomorrow_data:
        if is_valid_record(record) and record.get('HourStartCET'):
            try:
                if _period_minutes(record)[1] <= _range_end_minutes(time_to):
                    combined.append(record)
            except ValueError:
                continue

    if len(combined) < periods:
        return _window_not_found(f'Not enough data for {periods}-period window across both days', periods)

    combined.sort(key=lambda x: x['deliveryStart'])
    window, avg = _best_window(combined, periods, find_lowest)
    if window is None:
        return _window_not_found('No window found', periods)
    return _window_result(window, avg, periods)


def find_window_in_time_range(data, periods, time_from_str, time_to_str, find_lowest=True):
    """Find time window with lowest or highest average price within specified time range of one day."""
    periods = int(periods)
    limited_periods = limit_periods_to_time_range(periods, time_from_str, time_to_str)
    if limited_periods != periods:
        LOGGER.debug("OKTE Calculation: Periods limited from %s to %s by time range %s-%s",
                     periods, limited_periods, time_from_str, time_to_str)
        periods = limited_periods
    if periods < 1:
        return _window_not_found('Time range is shorter than one period', periods)

    if not data or len(data) < periods:
        return _window_not_found(f'Not enough data for {periods}-period window', None)

    time_from, time_to = _parse_time_range(time_from_str, time_to_str)
    if time_from is None:
        return _window_not_found('Invalid time format', None)

    from_minutes = time_from.hour * 60 + time_from.minute
    to_minutes = _range_end_minutes(time_to)
    filtered = []
    for record in data:
        if not (is_valid_record(record) and record.get('HourStartCET')):
            continue
        try:
            period_start, period_end = _period_minutes(record)
        except ValueError:
            continue
        if from_minutes <= period_start and period_end <= to_minutes:
            filtered.append(record)

    if len(filtered) < periods:
        return _window_not_found(f'Not enough data in time range {time_from_str}-{time_to_str}', periods)

    filtered.sort(key=lambda x: x['deliveryStart'])
    window, avg = _best_window(filtered, periods, find_lowest)
    if window is None:
        return _window_not_found('Could not find suitable continuous time window in specified time range', periods)
    return _window_result(window, avg, periods)


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
            ENTITY_FAILOVER_DATA: STATE_FALSE,  # "true" when prices are computed from historical averages
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
            ENTITY_FAILOVER_DATA: {},
        }

        # Price history for the data failover system: {'YYYY-MM-DD': {'HH:MM': price}}
        self.price_history = {}
        self._stats_bootstrapped = False
        self._fetch_failed = False
        # Market days on which the current price was served from historical averages (at least partly).
        # Recorder statistics of these days must not be used to rebuild the price history.
        self.failover_served_days = set()
        self._served_days_dirty = False

        # Price data storage
        self.price_data = {
            'all_data': [],
            'today_data': [],
            'tomorrow_data': [],
            'last_fetch': None,
        }

        # Retry timer for failed API fetch
        self._retry_timer = None
        self._closed = False

        # Entity IDs
        self.SENSOR_ENTITY_CURRENT_PRICE = None

    def setup_entity_ids(self):
        """Setup entity IDs after entry_id is set."""
        if self._entry_id:
            self.SENSOR_ENTITY_CURRENT_PRICE = f"sensor.{ENTITY_PREFIX}_{ENTITY_CURRENT_PRICE}"

    @dataclasses.dataclass
    class Settings:
        """Settings for master device."""
        device_name: str = DEFAULT_DEVICE_NAME
        fetch_time: str = DEFAULT_FETCH_TIME
        fetch_days: int = DEFAULT_FETCH_DAYS
        data_failover_mode: str = DEFAULT_DATA_FAILOVER_MODE
        failover_weeks: int = DEFAULT_FAILOVER_WEEKS
        failover_days: int = DEFAULT_FAILOVER_DAYS
        price_unit: str = DEFAULT_PRICE_UNIT

    def async_shutdown(self):
        """Cancel pending timers (called when the config entry is unloaded)."""
        self._closed = True
        if self._retry_timer is not None:
            self._retry_timer()
            self._retry_timer = None

    def _notify_entities(self):
        """Refresh all entities of this device."""
        async_dispatcher_send(self.hass, SIGNAL_FEEDBACK_UPDATE.format(self._entry_id))

    def _get_current_local_time(self):
        """Current time in market (Slovak) time - market days are always Slovak days."""
        return datetime.now(MARKET_TIMEZONE)

    # Current price ##########################################################################################################

    def _refresh_current_price(self):
        """Update the current price sensor (and its attributes) from stored real + failover data."""
        all_records = (self.price_data.get('all_data') or []) + (self.price_data.get('failover_data') or [])
        now = self._get_current_local_time()
        current_record = find_record_at(all_records, now)

        self.sensor_states[ENTITY_CURRENT_PRICE] = current_record['price'] if current_record else None

        today_stats = calculate_price_statistics(self.price_data.get('today_data', []))
        tomorrow_stats = calculate_price_statistics(self.price_data.get('tomorrow_data', []))
        all_stats = calculate_price_statistics(all_records)
        attributes = {}
        if current_record:
            attributes = {
                'period': current_record.get('period'),
                'period_start': format_market_time(current_record.get('deliveryStart'), '%H:%M'),
                'period_end': format_market_time(current_record.get('deliveryEnd'), '%H:%M'),
            }
            # Remember days on which the current price came from historical averages (see failover_served_days)
            if current_record in (self.price_data.get('failover_data') or []):
                day = now.strftime('%Y-%m-%d')
                if day not in self.failover_served_days:
                    self.failover_served_days.add(day)
                    self._served_days_dirty = True
        elif all_records:
            LOGGER.debug("No current price found for %s", now.strftime('%H:%M'))
        attributes.update({
            'total_records': len(all_records),
            'today_average': today_stats['avg_price'],
            'tomorrow_average': tomorrow_stats['avg_price'],
            'price_spread': round(all_stats['max_price'] - all_stats['min_price'], 2)
            if all_stats['max_price'] is not None and all_stats['min_price'] is not None else None,
        })
        self.sensor_attributes[ENTITY_CURRENT_PRICE] = attributes

    async def update_current_price(self):
        """Update only current price from already fetched data - no API call."""
        try:
            self._refresh_current_price()
        except Exception as e:  # never break the controller loop
            LOGGER.error("Error updating current price: %s", e)

    # Data failover system ###################################################################################################

    def _failover_enabled(self):
        """True when the data failover system is switched on."""
        return self.settings.data_failover_mode in (FAILOVER_MODE_WEEKDAYS, FAILOVER_MODE_ALL_DAYS)

    def _update_history(self, records):
        """Store fetched (real) OKTE prices into the price history used for averages."""
        if not self._failover_enabled():
            return
        by_day = {}
        for rec in records or []:
            day = rec.get('deliveryDayCET')
            slot = rec.get('HourStartCET')
            price = rec.get('price')
            if not day or not slot or price is None:
                continue
            by_day.setdefault(day, {})[slot] = price
        for day, slots in by_day.items():
            self.price_history[day] = slots
        self._trim_history()

    def _trim_history(self):
        """Drop history (and failover markers) older than the retention period."""
        limit = (self._get_current_local_time().date() - timedelta(days=FAILOVER_HISTORY_KEEP_DAYS)).strftime('%Y-%m-%d')
        for day in [d for d in self.price_history if d < limit]:
            del self.price_history[day]
        self.failover_served_days = {d for d in self.failover_served_days if d >= limit}

    def _failover_profile(self, target_date):
        """Average price of every 15-minute slot for target_date, computed from the price history.

        Weekday mode: last N same weekdays before target_date. All-days mode: last N days before target_date.
        Returns {'HH:MM': price}.
        """
        target_str = target_date.strftime('%Y-%m-%d')
        candidates = sorted((d for d in self.price_history if d < target_str), reverse=True)
        if self.settings.data_failover_mode == FAILOVER_MODE_WEEKDAYS:
            weekday = target_date.weekday()
            candidates = [d for d in candidates if datetime.strptime(d, '%Y-%m-%d').weekday() == weekday]
            limit = self.settings.failover_weeks
        else:
            limit = self.settings.failover_days
        chosen = candidates[:max(1, int(limit))]

        sums = {}
        counts = {}
        for day in chosen:
            for slot, price in self.price_history[day].items():
                sums[slot] = sums.get(slot, 0) + price
                counts[slot] = counts.get(slot, 0) + 1
        return {slot: round(sums[slot] / counts[slot], 2) for slot in sums}

    def _build_failover_records(self, target_date, profile):
        """Create price records (same structure as records from the API) for target_date from a profile."""
        if not profile:
            return []
        target_str = target_date.strftime('%Y-%m-%d')
        current = datetime(target_date.year, target_date.month, target_date.day, tzinfo=MARKET_TIMEZONE).astimezone(timezone.utc)
        records = []
        period = 0
        while period < 110:
            local_start = current.astimezone(MARKET_TIMEZONE)
            if local_start.date() != target_date:
                break
            end = current + timedelta(minutes=15)
            period += 1
            slot = local_start.strftime('%H:%M')
            price = profile.get(slot)
            if price is not None:
                records.append({
                    'deliveryStart': current.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'deliveryEnd': end.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'deliveryDayCET': target_str,
                    'HourStartCET': slot,
                    'HourEndCET': end.astimezone(MARKET_TIMEZONE).strftime('%H:%M'),
                    'period': period,
                    'price': price,
                })
            current = end
        return records

    def _apply_failover(self, data, today, tomorrow):
        """Fill missing today/tomorrow data from historical averages and update the failover sensor.

        Real data is never overwritten. Today is always filled when real data is missing, tomorrow only after
        a failed OKTE fetch (before publication tomorrow is normally empty).
        Returns the list of records (real + computed) used for the derived sensors.
        """
        if not self._failover_enabled():
            self.sensor_states[ENTITY_FAILOVER_DATA] = STATE_FALSE
            self.sensor_attributes[ENTITY_FAILOVER_DATA] = {
                'failover_data_today': False,
                'failover_data_tomorrow': False,
            }
            self.price_data['failover_data'] = []
            return data

        computed = []
        self.price_data['failover_data'] = computed
        for day, key in ((today, 'today_data'), (tomorrow, 'tomorrow_data')):
            # Today must always have prices - missing today data means OKTE did not deliver them
            # (e.g. tomorrow prices were never published before midnight), even if the last fetch "succeeded".
            if (self._fetch_failed or key == 'today_data') and not self.price_data.get(key):
                records = self._build_failover_records(day, self._failover_profile(day))
                if records:
                    self.price_data[key] = records
                    computed.extend(records)
                    LOGGER.warning("OKTE failover: %s computed from historical averages (%d periods)", key, len(records))

        self.sensor_states[ENTITY_FAILOVER_DATA] = STATE_TRUE if computed else STATE_FALSE

        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        attributes = {
            'failover_data_today': any(rec.get('deliveryDayCET') == today.strftime('%Y-%m-%d') for rec in computed),
            'failover_data_tomorrow': any(rec.get('deliveryDayCET') == tomorrow.strftime('%Y-%m-%d') for rec in computed),
        }
        for weekday, name in enumerate(weekday_names):
            day = today + timedelta(days=(weekday - today.weekday()) % 7)
            records = self._build_failover_records(day, self._failover_profile(day))
            attributes[f"Period data {name}"] = build_period_entries(records)
        self.sensor_attributes[ENTITY_FAILOVER_DATA] = attributes

        return list(data) + computed if computed else data

    async def _async_statistics_unit_factor(self, stat_id):
        """Factor converting recorder statistics of the current price sensor to EUR/MWh."""
        try:
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.statistics import get_metadata
            metadata = await get_instance(self.hass).async_add_executor_job(
                lambda: get_metadata(self.hass, statistic_ids={stat_id})
            )
            unit = metadata.get(stat_id, (None, {}))[1].get('unit_of_measurement')
        except Exception as e:  # metadata is optional - assume EUR/MWh
            LOGGER.debug("OKTE failover: Could not read statistics metadata: %s", e)
            unit = None
        return 1000 if unit == PRICE_UNIT_LABELS[PRICE_UNIT_EUR_KWH] else 1

    async def _async_bootstrap_history(self):
        """Fill the price history from recorder statistics of the current price sensor (done once)."""
        if not self._failover_enabled() or self._stats_bootstrapped:
            return
        try:
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.statistics import statistics_during_period

            if 'recorder' not in self.hass.config.components:
                return

            stat_id = self.SENSOR_ENTITY_CURRENT_PRICE
            now_utc = datetime.now(timezone.utc)
            result = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period,
                self.hass,
                now_utc - timedelta(days=FAILOVER_STATISTICS_DAYS),
                None,
                {stat_id},
                "5minute",
                None,
                {"mean"},
            )
            factor = await self._async_statistics_unit_factor(stat_id)

            today_str = self._get_current_local_time().strftime('%Y-%m-%d')
            samples = {}
            for row in result.get(stat_id, []):
                mean = row.get('mean')
                start = row.get('start')
                if mean is None or start is None:
                    continue
                if isinstance(start, (int, float)):
                    start = datetime.fromtimestamp(start, tz=timezone.utc)
                local = start.astimezone(MARKET_TIMEZONE)
                day = local.strftime('%Y-%m-%d')
                if day >= today_str:
                    continue
                slot = local.replace(minute=(local.minute // 15) * 15, second=0, microsecond=0).strftime('%H:%M')
                samples.setdefault(day, {}).setdefault(slot, []).append(mean * factor)

            # the first day of the statistics window starts mid-day (now - FAILOVER_STATISTICS_DAYS),
            # so it is incomplete and would distort the averages - skip it
            if samples:
                samples.pop(min(samples))

            added = 0
            skipped = []
            for day, slots in samples.items():
                if day in self.price_history:
                    continue
                if day in self.failover_served_days:
                    # statistics of this day contain prices computed from averages, not real OKTE prices
                    skipped.append(day)
                    continue
                # median of the 5-minute means filters out the bin that overlaps the previous period
                self.price_history[day] = {slot: round(py_statistics.median(values), 2) for slot, values in slots.items()}
                added += 1

            self._stats_bootstrapped = True
            self._trim_history()
            LOGGER.info("OKTE failover: price history initialised from statistics of %s (%d days)", stat_id, added)
            if skipped:
                LOGGER.info("OKTE failover: days served from averages skipped: %s", ", ".join(sorted(skipped)))
            await self._async_save_data()
        except Exception as e:
            LOGGER.warning("OKTE failover: Could not initialise price history from statistics: %s", e)

    async def async_reset_failover_history(self):
        """Drop the stored price history and rebuild it from recorder statistics of the current price sensor.

        Used by the 'Reset Failover History' button, e.g. when the history is corrupted or outdated
        after a longer Home Assistant downtime. Returns True when the history was rebuilt.
        """
        if not self._failover_enabled():
            LOGGER.warning("OKTE failover: Reset of price history skipped - data failover is disabled")
            return False

        old_days = len(self.price_history)
        self.price_history = {}
        self._stats_bootstrapped = False
        LOGGER.info("OKTE failover: Price history reset (%d days dropped), rebuilding from statistics", old_days)

        await self._async_bootstrap_history()

        # statistics never contain today - add real prices already fetched from the API (today/tomorrow)
        self._update_history(self.price_data.get('all_data') or [])

        # recompute failover sensor attributes (and failover data, if the API is currently unavailable)
        self._apply_data()
        await self._async_save_data()
        LOGGER.info(
            "OKTE failover: Price history rebuilt (%d days: %s .. %s)",
            len(self.price_history), min(self.price_history, default='-'), max(self.price_history, default='-'),
        )
        return self._stats_bootstrapped

    # Data processing ########################################################################################################

    @staticmethod
    def _merge_data(old_data, new_data, today_str):
        """Merge new API records into stored ones (by deliveryStart) and drop days older than today."""
        merged = {}
        for idx, rec in enumerate(old_data or []):
            merged[rec.get('deliveryStart') or f"_old_{idx}"] = rec
        for idx, rec in enumerate(new_data or []):
            merged[rec.get('deliveryStart') or f"_new_{idx}"] = rec
        return [
            rec for _key, rec in sorted(merged.items())
            if (rec.get('deliveryDayCET') or '') >= today_str
        ]

    @staticmethod
    def _minmax_attributes(record):
        """Attributes of the min/max price sensors."""
        if not record:
            return {'available': False}
        return {
            'available': True,
            'time': format_market_time(record.get('deliveryStart'), '%d.%m.%Y %H:%M'),
            'period': record.get('period'),
            'period_start': format_market_time(record.get('deliveryStart'), '%H:%M'),
            'period_end': format_market_time(record.get('deliveryEnd'), '%H:%M'),
        }

    def _apply_day_sensors(self, day, records, avg_key, min_key, max_key, prices_key, html_key, title, now):
        """Set statistics, prices and HTML table sensors of one market day."""
        stats = calculate_price_statistics(records)
        self.sensor_states[avg_key] = stats['avg_price']
        self.sensor_states[min_key] = stats['min_price']
        self.sensor_states[max_key] = stats['max_price']
        self.sensor_attributes[min_key] = self._minmax_attributes(stats['min_record'])
        self.sensor_attributes[max_key] = self._minmax_attributes(stats['max_record'])

        period_data = build_period_entries(records)
        prices_list = [entry['price'] for entry in period_data]
        self.sensor_states[prices_key] = len(period_data)
        self.sensor_attributes[prices_key] = {
            'period_data': period_data,
            'periods': len(period_data),
            'date_range': day.strftime('%Y-%m-%d'),
            'prices_list': prices_list,
            'timestamps_list': [entry['time'] for entry in period_data],
            'labels_list': [entry['period_label'] for entry in period_data],
            'min_price': min(prices_list) if prices_list else None,
            'max_price': max(prices_list) if prices_list else None,
            'avg_price': round(sum(prices_list) / len(prices_list), 2) if prices_list else None,
        }

        self.sensor_states[html_key] = len(period_data)
        self.sensor_attributes[html_key] = {
            'html_table': self.generate_html_table(records, day, title),
            'total_records': len(period_data),
            'date': day.strftime('%d.%m.%Y'),
            'available': len(period_data) > 0,
            'last_update': now.isoformat(),
        }

    def _apply_data(self):
        """Recompute today/tomorrow split and all derived sensors from stored all_data."""
        data = self.price_data.get('all_data') or []
        now = self._get_current_local_time()
        today = now.date()
        tomorrow = today + timedelta(days=1)

        self.price_data['today_data'] = filter_data_by_date(data, today)
        self.price_data['tomorrow_data'] = filter_data_by_date(data, tomorrow)
        data = self._apply_failover(data, today, tomorrow)
        self.price_data['data_date'] = today.strftime('%Y-%m-%d')
        self.price_data['data_version'] = self.price_data.get('data_version', 0) + 1

        LOGGER.debug("OKTE API: Data split for %s - Total: %d, Today: %d, Tomorrow: %d", today,
                     len(data), len(self.price_data['today_data']), len(self.price_data['tomorrow_data']))

        self.sensor_states[ENTITY_DATA_COUNT] = len(data)

        # Error bit 1 (value 2): no valid data for today
        if self.price_data['today_data']:
            self.sensor_states[ENTITY_ERROR_CODE] &= ~2
        else:
            self.sensor_states[ENTITY_ERROR_CODE] |= 2

        self._apply_day_sensors(today, self.price_data['today_data'],
                                ENTITY_AVERAGE_PRICE_TODAY, ENTITY_MIN_PRICE_TODAY, ENTITY_MAX_PRICE_TODAY,
                                ENTITY_PRICES_TODAY, ENTITY_HTML_TABLE_TODAY,
                                "Dnešné ceny elektriky OKTE", now)
        self._apply_day_sensors(tomorrow, self.price_data['tomorrow_data'],
                                ENTITY_AVERAGE_PRICE_TOMORROW, ENTITY_MIN_PRICE_TOMORROW, ENTITY_MAX_PRICE_TOMORROW,
                                ENTITY_PRICES_TOMORROW, ENTITY_HTML_TABLE_TOMORROW,
                                "Zajtrajšie ceny elektriky OKTE", now)
        self._refresh_current_price()

        # Calculator devices recalculate their windows from the new data
        async_dispatcher_send(self.hass, SIGNAL_MASTER_DATA_UPDATED)

    def _roll_over_if_needed(self):
        """Move stored data to the current day (tomorrow -> today) without any API call."""
        today_str = self._get_current_local_time().strftime('%Y-%m-%d')
        if self.price_data.get('data_date') == today_str:
            return False
        all_data = self.price_data.get('all_data') or []
        if not all_data and self.price_data.get('data_date') is None:
            return False
        self.price_data['all_data'] = [
            rec for rec in all_data if (rec.get('deliveryDayCET') or '') >= today_str
        ]
        LOGGER.debug("OKTE API: Day changed to %s - rolling stored data over (no API call)", today_str)
        self._apply_data()
        return True

    async def async_rollover(self):
        """Scheduled midnight rollover of stored data."""
        try:
            if self._roll_over_if_needed():
                self._notify_entities()

            # No real prices for the new day (tomorrow prices were never received) - try the API right away.
            # Until real data arrive, today is covered by historical averages (see _apply_failover).
            today_str = self._get_current_local_time().strftime('%Y-%m-%d')
            if not any(rec.get('deliveryDayCET') == today_str for rec in (self.price_data.get('all_data') or [])):
                LOGGER.warning("OKTE API: No real prices for the new day after rollover - fetching from API now")
                await self.fetch_and_process_data()
                self._notify_entities()
        except Exception as e:
            LOGGER.error("OKTE API: Error during day rollover: %s", e)

    # Storage ################################################################################################################

    async def async_load_stored_data(self):
        """Restore last known data from storage (used after HA restart during API outage)."""
        try:
            stored = await get_prices_store(self.hass, self._entry_id).async_load()
            if not stored:
                return
            history = stored.get('history')
            if isinstance(history, dict):
                self.price_history = {
                    day: slots for day, slots in history.items()
                    if isinstance(slots, dict)
                }
            self.failover_served_days = set(stored.get('failover_served_days') or [])
            self._trim_history()
            self._stats_bootstrapped = bool(stored.get('stats_bootstrapped'))
            today_str = self._get_current_local_time().strftime('%Y-%m-%d')
            records = [
                rec for rec in (stored.get('all_data') or [])
                if isinstance(rec, dict) and (rec.get('deliveryDayCET') or '') >= today_str
            ]
            if not records:
                LOGGER.debug("OKTE API: Stored data is outdated, ignoring")
                return
            self.price_data['all_data'] = records
            last_fetch = None
            if stored.get('last_fetch'):
                try:
                    last_fetch = datetime.fromisoformat(stored['last_fetch'])
                except ValueError:
                    last_fetch = None
            self.price_data['last_fetch'] = last_fetch
            self._apply_data()
            if last_fetch:
                self.sensor_states[ENTITY_LAST_UPDATE] = last_fetch.isoformat()
            self.sensor_attributes[ENTITY_LAST_UPDATE] = {
                'data_records': len(records),
                'status': 'Restored from storage',
            }
            LOGGER.debug("OKTE API: Restored %d records from storage", len(records))
        except Exception as e:
            LOGGER.warning("OKTE API: Could not restore stored data: %s", e)

    async def _async_save_data(self):
        """Persist current data so it survives a restart."""
        try:
            last_fetch = self.price_data.get('last_fetch')
            await get_prices_store(self.hass, self._entry_id).async_save({
                'all_data': self.price_data.get('all_data') or [],
                'last_fetch': last_fetch.isoformat() if last_fetch else None,
                'history': self.price_history,
                'stats_bootstrapped': self._stats_bootstrapped,
                'failover_served_days': sorted(self.failover_served_days),
            })
            self._served_days_dirty = False
        except Exception as e:
            LOGGER.warning("OKTE API: Could not save data to storage: %s", e)

    # Fetching ###############################################################################################################

    def _handle_fetch_failure(self, description):
        """API fetch failed - keep stored data (rolled over to the current day) and schedule retry."""
        now = self._get_current_local_time()
        self.sensor_states[ENTITY_CONNECTION_STATUS] = False
        self._fetch_failed = True

        # Set API fetch error bit (bit 0)
        self.sensor_states[ENTITY_ERROR_CODE] |= 1

        # Keep stored data, but make sure it belongs to the current day
        rolled_over = self._roll_over_if_needed()

        # Data failover: fill missing days from historical averages (stored real data are kept)
        if (
            not rolled_over
            and self._failover_enabled()
            and (self.sensor_states.get(ENTITY_FAILOVER_DATA) != STATE_TRUE
                 or self.price_data.get('data_date') != now.strftime('%Y-%m-%d')
                 or not self.price_data.get('tomorrow_data'))
        ):
            self._apply_data()
        has_today = bool(self.price_data.get('today_data'))
        if has_today:
            self.sensor_states[ENTITY_ERROR_CODE] &= ~2
        else:
            self.sensor_states[ENTITY_ERROR_CODE] |= 2

        self._schedule_retry()

        last_fetch = self.price_data.get('last_fetch')
        self.sensor_attributes[ENTITY_CONNECTION_STATUS] = {
            'status': 'Disconnected',
            'status_description': description,
            'last_attempt': now.isoformat(),
            'using_stored_data': has_today,
            'stored_data_fetched': last_fetch.isoformat() if last_fetch else None,
            'stored_data_days': sorted({rec.get('deliveryDayCET') for rec in (self.price_data.get('all_data') or []) if rec.get('deliveryDayCET')}),
        }
        self.sensor_attributes[ENTITY_LAST_UPDATE] = {
            'data_records': len(self.price_data.get('all_data') or []),
            'status': 'Stored data (API unavailable)' if has_today else 'No valid data for today',
        }

    async def fetch_and_process_data(self):
        """Fetch data from API and process it. On failure the stored data is kept."""
        try:
            # Data failover: initialise price history from recorder statistics (once)
            await self._async_bootstrap_history()

            data = await async_fetch_okte_data(self.hass, self.settings.fetch_days)

            now = self._get_current_local_time()
            today_str = now.strftime('%Y-%m-%d')
            has_today = bool(data) and any(rec.get('deliveryDayCET') == today_str for rec in data)

            if data and not has_today:
                LOGGER.warning("OKTE API: Response does not contain data for today - ignoring it, keeping stored data")

            if not has_today:
                LOGGER.error("OKTE API: No usable data received from API - keeping stored data")
                self._handle_fetch_failure('Last data fetch failed')
                if self._served_days_dirty:
                    await self._async_save_data()
                return

            self.price_data['all_data'] = self._merge_data(self.price_data.get('all_data'), data, today_str)
            self.price_data['last_fetch'] = now
            self._fetch_failed = False
            self._update_history(data)
            self._apply_data()

            self.sensor_states[ENTITY_CONNECTION_STATUS] = True
            self.sensor_states[ENTITY_LAST_UPDATE] = now.isoformat()

            # Clear API fetch error bit (bit 0) and "no data for today" bit (bit 1)
            self.sensor_states[ENTITY_ERROR_CODE] &= ~3

            # Cancel retry timer if it exists (fetch succeeded)
            if self._retry_timer is not None:
                self._retry_timer()
                self._retry_timer = None

            # Tomorrow prices should already be published after the daily fetch time - if they are
            # missing, keep trying until they arrive (otherwise the next day would start without prices)
            if not self.price_data.get('tomorrow_data') and self._is_after_fetch_time(now):
                LOGGER.warning("OKTE API: Tomorrow prices are not published yet - will retry")
                self._schedule_retry(TOMORROW_RETRY_INTERVAL)

            self.sensor_attributes[ENTITY_CONNECTION_STATUS] = {
                'status': 'Connected',
                'status_description': 'Last data fetch was successful',
                'last_attempt': now.isoformat(),
                'using_stored_data': False,
            }
            self.sensor_attributes[ENTITY_LAST_UPDATE] = {
                'data_records': len(self.price_data['all_data']),
                'status': 'Data available',
            }

            await self._async_save_data()

        except Exception as e:
            LOGGER.error("OKTE API: Error fetching data: %s", e)
            try:
                self._handle_fetch_failure(f'Error during data fetch: {str(e)[:100]}')
            except Exception as e2:
                LOGGER.error("OKTE API: Error handling fetch failure: %s", e2)

    def _is_after_fetch_time(self, local_time):
        """True when local_time is at or after the configured daily fetch time (HH:MM)."""
        try:
            hour, minute = (int(x) for x in str(self.settings.fetch_time).split(':')[:2])
        except (ValueError, TypeError):
            hour, minute = (int(x) for x in DEFAULT_FETCH_TIME.split(':'))
        return (local_time.hour, local_time.minute) >= (hour, minute)

    def _schedule_retry(self, delay=FETCH_RETRY_INTERVAL):
        """Schedule retry of API fetch (default 1 minute after a failed attempt)."""
        if self._closed:
            return

        if self._retry_timer is not None:
            self._retry_timer()
            self._retry_timer = None

        async def retry_fetch(_now=None):
            """Retry API fetch."""
            self._retry_timer = None
            LOGGER.debug("OKTE API: Retrying API fetch")
            await self.fetch_and_process_data()
            self._notify_entities()

        self._retry_timer = async_call_later(self.hass, delay, retry_fetch)
        LOGGER.debug("OKTE API: Scheduled retry in %s seconds", delay)

    # HTML table #############################################################################################################

    @staticmethod
    def _get_price_color(price):
        """Get color for price based on value."""
        if price is None:
            return ""
        if price > THRESHOLD_PRICE_HIGH:
            return COLOR_PRICE_HIGH
        if price >= THRESHOLD_PRICE_LOW:
            return COLOR_PRICE_LOW
        return COLOR_PRICE_NEGATIVE

    def generate_html_table(self, data, date, title):
        """Create HTML table with the prices of one market day."""
        html = f"""
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%; max-width: 400px; border-color: {BORDER_COLOR_HEADER};">
            <thead>
                <tr style="background-color: {BG_COLOR_TABLE_HEADER_ROW1}; color: {TEXT_COLOR_TABLE_HEADER_ROW1};">
                    <th colspan="2" style="text-align: center; font-size: 16px; padding: {PADDING_HEADER_ROW1};">
                        {title}
                    </th>
                </tr>
                <tr style="background-color: {BG_COLOR_TABLE_HEADER_ROW2}; color: {TEXT_COLOR_TABLE_HEADER_ROW2};">
                    <th style="width: auto; max-width: 200px; text-align: center; padding: {PADDING_HEADER_ROW2};">Čas od - do</th>
                    <th style="width: auto; max-width: 200px; text-align: center; padding: {PADDING_HEADER_ROW2};">Cena [€/MWh]</th>
                </tr>
            </thead>
            <tbody>
        """

        valid_records = sorted((r for r in (data or []) if is_valid_record(r)), key=lambda x: x['deliveryStart'])
        if not valid_records:
            html += f"""
                <tr>
                    <td colspan="2" style="text-align: center; height: 200px; vertical-align: middle; border: 1px solid {BORDER_COLOR_DATA};">
                        Údaje nie sú k dispozícii
                    </td>
                </tr>
            </tbody>
        </table>
        """
            return html

        stats = calculate_price_statistics(valid_records)
        for row_index, record in enumerate(valid_records):
            time_from = format_market_time(record.get('deliveryStart'), '%H:%M')
            time_to = format_market_time(record.get('deliveryEnd'), '%H:%M')
            time_range = f"{time_from} - {time_to}" if time_from and time_to else ""
            price = record['price']
            row_bg_color = BG_COLOR_TABLE_DATA_ROW_ODD if row_index % 2 == 0 else BG_COLOR_TABLE_DATA_ROW_EVEN
            html += f"""
                <tr style="background-color: {row_bg_color};">
                    <td style="width: auto; max-width: 200px; text-align: center; padding: {PADDING_DATA_ROWS};">{time_range}</td>
                    <td style="text-align: right; width: auto; max-width: 200px; color: {self._get_price_color(price)}; padding: {PADDING_DATA_ROWS};">{price:.2f} €</td>
                </tr>
            """

        min_rec, max_rec = stats['min_record'], stats['max_record']
        min_range = f"{format_market_time(min_rec.get('deliveryStart'), '%H:%M')}-{format_market_time(min_rec.get('deliveryEnd'), '%H:%M')}"
        max_range = f"{format_market_time(max_rec.get('deliveryStart'), '%H:%M')}-{format_market_time(max_rec.get('deliveryEnd'), '%H:%M')}"
        avg_price = sum(r['price'] for r in valid_records) / len(valid_records)
        html += f"""
            </tbody>
            <tfoot>
                <tr style="background-color: #e8f4f8;">
                    <td colspan="2" style="padding: 10px; font-size: 14px;">
                        <strong>📅 Dátum:</strong> {date.strftime('%d.%m.%Y')}<br>
                        <strong>📉 Min. cena:</strong> {stats['min_price']:.2f} € ({min_range})<br>
                        <strong>📈 Max. cena:</strong> {stats['max_price']:.2f} € ({max_range})<br>
                        <strong>📊 Priemerná cena:</strong> {avg_price:.2f} €
                    </td>
                </tr>
            </tfoot>
        </table>
        """
        return html

    # Controller #############################################################################################################

    async def my_controller(self):
        """Periodic update (every 15 minutes) - day rollover and current price from cached data."""
        if self._is_running:
            return
        self._is_running = True
        try:
            self._roll_over_if_needed()
            await self.update_current_price()
            if self._served_days_dirty:
                await self._async_save_data()
        except Exception as e:
            LOGGER.error("OKTE API: Error in master controller: %s", e)
        finally:
            self._notify_entities()
            self._is_running = False


##############################################################################################################################
# Window Device Instance #####################################################################################################
##############################################################################################################################

WINDOW_SENSOR_KEYS = (
    ENTITY_LOWEST_PRICE_WINDOW,
    ENTITY_LOWEST_PRICE_WINDOW_TODAY,
    ENTITY_LOWEST_PRICE_WINDOW_TOMORROW,
    ENTITY_HIGHEST_PRICE_WINDOW,
    ENTITY_HIGHEST_PRICE_WINDOW_TODAY,
    ENTITY_HIGHEST_PRICE_WINDOW_TOMORROW,
)
DETECTOR_KEYS = (
    ENTITY_DETECTOR_LOWEST_PRICE,
    ENTITY_DETECTOR_LOWEST_PRICE_TODAY,
    ENTITY_DETECTOR_HIGHEST_PRICE,
    ENTITY_DETECTOR_HIGHEST_PRICE_TODAY,
)


def _is_now_in_window(window, now):
    """True when 'now' lies inside a found window."""
    if not window.get('found'):
        return False
    try:
        return datetime.fromisoformat(window['start_time']) <= now < datetime.fromisoformat(window['end_time'])
    except (KeyError, TypeError, ValueError) as e:
        LOGGER.debug("Error checking window detector: %s", e)
        return False


class OKTE_Window_Instance:
    """Window device instance - calculates time windows from master device data."""

    def __init__(self) -> None:
        self.settings = self.Settings()
        self._is_running = False
        self.hass = None
        self._entry_id = None

        # Storage for sensor states
        self.sensor_states = {key: None for key in WINDOW_SENSOR_KEYS}
        self.sensor_states.update({key: False for key in DETECTOR_KEYS})

        # Storage for sensor attributes
        self.sensor_attributes = {}

        # Optimization: track when calculations are needed
        self._last_calculation_time = None  # Last 15-minute period of a full calculation
        self._last_master_data_version = None  # Last data version (fetch, rollover, failover) of the master device
        self._last_config_values = None  # Last configuration values for change detection

        # Debounce timer for config changes
        self._debounce_timer = None
        self._closed = False

    def setup_entity_ids(self):
        """Entity IDs are generated by the entities themselves (kept for interface compatibility)."""

    def _get_current_local_time(self):
        """Current time in market (Slovak) time."""
        return datetime.now(MARKET_TIMEZONE)

    @dataclasses.dataclass
    class Settings:
        """Settings for window device."""
        device_name: str = DEFAULT_DEVICE_NAME
        master_device: str = DEFAULT_MASTER_DEVICE
        window_size: int = DEFAULT_WINDOW_SIZE
        time_from: str = DEFAULT_TIME_FROM
        time_to: str = DEFAULT_TIME_TO

    @property
    def calculator_number(self):
        """Number of this calculator (from its device name)."""
        return get_calculator_number_from_name(self.settings.device_name)

    def async_shutdown(self):
        """Cancel pending timers (called when the config entry is unloaded)."""
        self._closed = True
        if self._debounce_timer is not None:
            self._debounce_timer()
            self._debounce_timer = None

    def schedule_calculation(self, delay: float = None):
        """Schedule calculation with debounce to prevent multiple rapid recalculations."""
        if self._closed:
            return
        if delay is None:
            delay = CALCULATION_DEBOUNCE_DELAY

        if self._debounce_timer is not None:
            self._debounce_timer()
            self._debounce_timer = None

        async def delayed_calculation(_now=None):
            """Execute calculation after debounce delay."""
            self._debounce_timer = None
            await self.my_controller()

        self._debounce_timer = async_call_later(self.hass, delay, delayed_calculation)

    def _get_master_instance(self):
        """Return the instance of the loaded Master config entry, or None."""
        from homeassistant.config_entries import ConfigEntryState

        master_entry_id = self.settings.master_device
        if not master_entry_id:
            return None
        master_entry = self.hass.config_entries.async_get_entry(master_entry_id)
        if (
            master_entry is None
            or master_entry.domain != DOMAIN
            or master_entry.state is not ConfigEntryState.LOADED
        ):
            return None
        runtime_data = getattr(master_entry, 'runtime_data', None)
        return runtime_data.instance if runtime_data else None

    def get_master_price_data(self):
        """Get price data from master device (None when the master is not loaded)."""
        master_instance = self._get_master_instance()
        return master_instance.price_data if master_instance is not None else None

    def is_master_available(self):
        """Check if master device is available."""
        return self._get_master_instance() is not None

    def _set_unavailable(self):
        """Make all window sensors unavailable and switch detectors off."""
        for key in WINDOW_SENSOR_KEYS:
            self.sensor_states[key] = None
        for key in DETECTOR_KEYS:
            self.sensor_states[key] = False

    async def calculate_windows(self):
        """Calculate time windows from master device data."""
        try:
            now = self._get_current_local_time()
            current_15min_period = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)

            current_config = {
                'lowest_window_size': int(self.number_values.get(ENTITY_LOWEST_WINDOW_SIZE, 3)),
                'lowest_time_from': self.time_values.get(ENTITY_LOWEST_TIME_FROM, dt_time(0, 0)),
                'lowest_time_to': self.time_values.get(ENTITY_LOWEST_TIME_TO, dt_time(23, 45)),
                'highest_window_size': int(self.number_values.get(ENTITY_HIGHEST_WINDOW_SIZE, 3)),
                'highest_time_from': self.time_values.get(ENTITY_HIGHEST_TIME_FROM, dt_time(0, 0)),
                'highest_time_to': self.time_values.get(ENTITY_HIGHEST_TIME_TO, dt_time(23, 45)),
            }

            price_data = self.get_master_price_data()
            if price_data is None:
                if self._last_calculation_time is None:
                    # Typical during start-up - the Master is set up later; it notifies us when its data are ready
                    LOGGER.debug("OKTE Calculation: Master device not loaded yet - waiting for its data")
                else:
                    LOGGER.warning("OKTE Calculation: Master device not available - sensors will be unavailable")
                self._set_unavailable()
                return

            # Check if full calculation is needed
            master_data_version = price_data.get('data_version')
            reasons = []
            if self._last_calculation_time is None:
                reasons.append("first run")
            if master_data_version != self._last_master_data_version:
                reasons.append("new master data")
            if current_config != self._last_config_values:
                reasons.append("configuration changed")
            if current_15min_period != self._last_calculation_time:
                reasons.append("15-min period changed")
            if not reasons:
                return

            LOGGER.debug("OKTE Calculation: Running window calculations - Reason: %s", ", ".join(reasons))

            today_data = price_data.get('today_data', [])
            tomorrow_data = price_data.get('tomorrow_data', [])
            results = {}
            for prefix, find_lowest in (('lowest', True), ('highest', False)):
                size = current_config[f'{prefix}_window_size']
                time_from = current_config[f'{prefix}_time_from'].strftime("%H:%M")
                time_to = current_config[f'{prefix}_time_to'].strftime("%H:%M")
                results[prefix] = (
                    find_window_cross_days(today_data, tomorrow_data, size, time_from, time_to, find_lowest),
                    find_window_in_time_range(today_data, size, time_from, time_to, find_lowest),
                    find_window_in_time_range(tomorrow_data, size, time_from, time_to, find_lowest),
                )

            now = self._get_current_local_time()
            for prefix, keys in (
                ('lowest', (ENTITY_LOWEST_PRICE_WINDOW, ENTITY_LOWEST_PRICE_WINDOW_TODAY, ENTITY_LOWEST_PRICE_WINDOW_TOMORROW,
                            ENTITY_DETECTOR_LOWEST_PRICE, ENTITY_DETECTOR_LOWEST_PRICE_TODAY)),
                ('highest', (ENTITY_HIGHEST_PRICE_WINDOW, ENTITY_HIGHEST_PRICE_WINDOW_TODAY, ENTITY_HIGHEST_PRICE_WINDOW_TOMORROW,
                             ENTITY_DETECTOR_HIGHEST_PRICE, ENTITY_DETECTOR_HIGHEST_PRICE_TODAY)),
            ):
                cross_day, today_window, tomorrow_window = results[prefix]
                main_key, today_key, tomorrow_key, detector_key, detector_today_key = keys
                # General sensors (without today/tomorrow) - from today time_from to tomorrow time_to
                self.sensor_states[main_key] = json.dumps(cross_day) if cross_day['found'] else None
                self.sensor_states[today_key] = json.dumps(today_window) if today_window['found'] else None
                self.sensor_states[tomorrow_key] = json.dumps(tomorrow_window) if tomorrow_window['found'] else None
                self.sensor_states[detector_key] = _is_now_in_window(cross_day, now)
                self.sensor_states[detector_today_key] = _is_now_in_window(today_window, now)

            # Remember what the calculation was based on
            self._last_calculation_time = current_15min_period
            self._last_master_data_version = master_data_version
            self._last_config_values = current_config

        except Exception as e:
            LOGGER.error("OKTE Calculation: Error calculating windows: %s", e)
            self._set_unavailable()

    async def my_controller(self):
        """Main controller logic for Window device."""
        if self._is_running:
            return
        self._is_running = True
        try:
            await self.calculate_windows()
        except Exception as e:
            LOGGER.error("OKTE Calculation: Error in window controller: %s", e)
        finally:
            async_dispatcher_send(self.hass, SIGNAL_FEEDBACK_UPDATE.format(self._entry_id))
            self._is_running = False
