"""The OKTE Integration"""
"""Author: Jozef Moravcik"""
"""email: jozef.moravcik@moravcik.eu"""

""" const.py """

""" Constants for the OKTE Integration."""

from dataclasses import dataclass, field
from typing import Any

from homeassistant.util import dt as dt_util

# OKTE is the Slovak market - market days and periods are always in Slovak local time,
# independent of the Home Assistant time zone (resolved at import time, outside the event loop)
MARKET_TIMEZONE = dt_util.get_time_zone("Europe/Bratislava")

# Custom states for window sensors
STATE_WINDOW_FOUND = "OK"
STATE_WINDOW_NOT_FOUND = "NOT"

DOMAIN = "okte"
VERSION = "1.01.04"
DOCUMENTATION_URL = "https://github.com/jozef-moravcik-homeassistant/okte"
MANUFACTURER = "Jozef Moravcik"
MODEL_MASTER = "OKTE Master"
MODEL_CALCULATOR = "Calculator"
NAME = "OKTE - Slovak Energy Market"

# Entity ID prefix
ENTITY_PREFIX = "okte"

def sanitize_device_name(device_name: str) -> str:
    """Sanitize device name for use in entity IDs."""
    import re
    # Convert to lowercase
    sanitized = device_name.lower()
    # Replace spaces and special characters with underscore
    sanitized = re.sub(r'[^a-z0-9]+', '_', sanitized)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    # Limit length
    sanitized = sanitized[:20]
    return sanitized if sanitized else "device"

def get_next_calculator_number(hass) -> int:
    """Get the next available calculator number, filling gaps if any exist."""
    # Get all existing calculator entries
    existing_entries = hass.config_entries.async_entries(DOMAIN)
    calculator_entries = [
        entry for entry in existing_entries
        if entry.data.get(CONF_DEVICE_TYPE) == DEVICE_TYPE_CALCULATOR
    ]
    
    # Extract calculator numbers from device names
    calculator_numbers = []
    for entry in calculator_entries:
        device_name = entry.data.get(CONF_DEVICE_NAME, "")
        if device_name.startswith("Calculator "):
            try:
                num = int(device_name.replace("Calculator ", ""))
                calculator_numbers.append(num)
            except ValueError:
                continue
    
    if not calculator_numbers:
        return 1
    
    # Sort numbers
    calculator_numbers.sort()
    
    # Find first gap
    for i in range(1, max(calculator_numbers) + 1):
        if i not in calculator_numbers:
            return i
    
    # No gaps, return next number
    return max(calculator_numbers) + 1

def get_calculator_number_from_name(device_name: str) -> int:
    """Extract calculator number from device name."""
    try:
        if device_name.startswith("Calculator "):
            return int(device_name.replace("Calculator ", ""))
    except ValueError:
        pass
    return 1

##############################################################################################################################
# Services ###################################################################################################################
##############################################################################################################################
SERVICE_FETCH_DATA = "fetch_data"

##############################################################################################################################
# Dispatcher signals #########################################################################################################
##############################################################################################################################
SIGNAL_FEEDBACK_UPDATE = DOMAIN + "_feedback_update_{}"   # entry_id - refresh all entities of an entry
SIGNAL_MASTER_DATA_UPDATED = DOMAIN + "_master_data_updated"  # Master price data changed (fetch, rollover, failover)

##############################################################################################################################
# States and commands ########################################################################################################
##############################################################################################################################
STATE_NONE = "none"
STATE_FALSE = "false"
STATE_TRUE = "true"

##############################################################################################################################
# Device Types ###############################################################################################################
##############################################################################################################################
DEVICE_TYPE_MASTER = "master"
DEVICE_TYPE_CALCULATOR = "calculator"

##############################################################################################################################
# Configuration keys - Common ################################################################################################
##############################################################################################################################
CONF_DEVICE_TYPE = "device_type"
CONF_DEVICE_NAME = "device_name"
DEFAULT_DEVICE_NAME = "Device 1"
MASTER_DEVICE_NAME = "OKTE"                  # Entity names of the Master: "OKTE Current Price"
MASTER_ENTRY_TITLE = "Master"                # Title of the Master config entry (shown above the device name)
LEGACY_MASTER_DEVICE_NAME = "OKTE Master"    # Master device name used by older versions

# Removed setting (Home Assistant always puts the device name in front of the entity name) - ignored if still present
LEGACY_CONF_INCLUDE_DEVICE_NAME_IN_ENTITY = "include_device_name_in_entity"

##############################################################################################################################
# Configuration keys - Master Device #########################################################################################
##############################################################################################################################
CONF_FETCH_TIME = "fetch_time"
DEFAULT_FETCH_TIME = "14:00"

CONF_FETCH_DAYS = "fetch_days"
DEFAULT_FETCH_DAYS = 2

# Data failover system (prices computed from historical averages when OKTE is unavailable)
CONF_DATA_FAILOVER_MODE = "data_failover_mode"
FAILOVER_MODE_WEEKDAYS = "weekdays"
FAILOVER_MODE_ALL_DAYS = "all_days"
FAILOVER_MODE_DISABLED = "disabled"
FAILOVER_MODES = [FAILOVER_MODE_WEEKDAYS, FAILOVER_MODE_ALL_DAYS, FAILOVER_MODE_DISABLED]
DEFAULT_DATA_FAILOVER_MODE = FAILOVER_MODE_WEEKDAYS

CONF_FAILOVER_WEEKS = "failover_weeks"
DEFAULT_FAILOVER_WEEKS = 4
MIN_FAILOVER_WEEKS = 1
MAX_FAILOVER_WEEKS = 12

CONF_FAILOVER_DAYS = "failover_days"
DEFAULT_FAILOVER_DAYS = 7
MIN_FAILOVER_DAYS = 1
MAX_FAILOVER_DAYS = 30

FAILOVER_HISTORY_KEEP_DAYS = 90  # how many days of price history are kept in storage
FAILOVER_STATISTICS_DAYS = 10  # retention of short-term recorder statistics
TOMORROW_RETRY_INTERVAL = 900  # seconds between fetch retries when tomorrow prices are missing after the daily fetch time
FETCH_RETRY_INTERVAL = 60  # seconds between fetch retries after a failed fetch

# Unit of the price sensors (OKTE publishes EUR/MWh)
CONF_PRICE_UNIT = "price_unit"
PRICE_UNIT_EUR_MWH = "eur_mwh"
PRICE_UNIT_EUR_KWH = "eur_kwh"
PRICE_UNITS = [PRICE_UNIT_EUR_MWH, PRICE_UNIT_EUR_KWH]
DEFAULT_PRICE_UNIT = PRICE_UNIT_EUR_MWH
PRICE_UNIT_LABELS = {PRICE_UNIT_EUR_MWH: "EUR/MWh", PRICE_UNIT_EUR_KWH: "EUR/kWh"}

##############################################################################################################################
# Configuration keys - Window Device #########################################################################################
##############################################################################################################################
CONF_MASTER_DEVICE = "master_device"
DEFAULT_MASTER_DEVICE = None

CONF_WINDOW_SIZE = "window_size"
DEFAULT_WINDOW_SIZE = 12

CONF_TIME_FROM = "time_from"
DEFAULT_TIME_FROM = "00:00"

CONF_TIME_TO = "time_to"
DEFAULT_TIME_TO = "23:59"

##############################################################################################################################
# API Configuration ##########################################################################################################
##############################################################################################################################
OKTE_API_BASE_URL = "https://isot.okte.sk/api/v1/dam/results"
REQUEST_TIMEOUT = 30

##############################################################################################################################
# Internal entity names (will be prefixed with DOMAIN in code) ###############################################################
# These entities are created by this integration #############################################################################
##############################################################################################################################

# Master Device Entities
ENTITY_CONNECTION_STATUS = "connection_status"
ENTITY_LAST_UPDATE = "last_update"
ENTITY_DATA_COUNT = "data_count"
ENTITY_CURRENT_PRICE = "current_price"
ENTITY_AVERAGE_PRICE_TODAY = "average_price_today"
ENTITY_MIN_PRICE_TODAY = "min_price_today"
ENTITY_MAX_PRICE_TODAY = "max_price_today"
ENTITY_AVERAGE_PRICE_TOMORROW = "average_price_tomorrow"
ENTITY_MIN_PRICE_TOMORROW = "min_price_tomorrow"
ENTITY_MAX_PRICE_TOMORROW = "max_price_tomorrow"
ENTITY_PRICES_TODAY = "prices_today"
ENTITY_PRICES_TOMORROW = "prices_tomorrow"
ENTITY_HTML_TABLE_TODAY = "html_table_today"
ENTITY_HTML_TABLE_TOMORROW = "html_table_tomorrow"
ENTITY_ERROR_CODE = "error_code"
ENTITY_FAILOVER_DATA = "failover_data"

# Window Device Entities
ENTITY_LOWEST_PRICE_WINDOW = "lowest_price_window"
ENTITY_LOWEST_PRICE_WINDOW_TODAY = "lowest_price_window_today"
ENTITY_LOWEST_PRICE_WINDOW_TOMORROW = "lowest_price_window_tomorrow"
ENTITY_HIGHEST_PRICE_WINDOW = "highest_price_window"
ENTITY_HIGHEST_PRICE_WINDOW_TODAY = "highest_price_window_today"
ENTITY_HIGHEST_PRICE_WINDOW_TOMORROW = "highest_price_window_tomorrow"
ENTITY_DETECTOR_LOWEST_PRICE = "detector_lowest_price"
ENTITY_DETECTOR_LOWEST_PRICE_TODAY = "detector_lowest_price_today"
ENTITY_DETECTOR_HIGHEST_PRICE = "detector_highest_price"
ENTITY_DETECTOR_HIGHEST_PRICE_TODAY = "detector_highest_price_today"

# Window Device - Duration Sensors (showing time in H:MM format)
# These sensors display the same data as number entities but in time format
# Note: entity_id can be same as number entities because domain is different (sensor vs number)
ENTITY_LOWEST_WINDOW_SIZE_TIME = "lowest_price_window_size"
ENTITY_HIGHEST_WINDOW_SIZE_TIME = "highest_price_window_size"  
ENTITY_LOWEST_SEARCH_WINDOW_SIZE = "lowest_price_search_window_size"
ENTITY_HIGHEST_SEARCH_WINDOW_SIZE = "highest_price_search_window_size"

# Window Device Settings - Number Entities
ENTITY_LOWEST_WINDOW_SIZE = "lowest_price_window_size"
ENTITY_LOWEST_TIME_FROM = "lowest_price_time_from"
ENTITY_LOWEST_TIME_TO = "lowest_price_time_to"
ENTITY_HIGHEST_WINDOW_SIZE = "highest_price_window_size"
ENTITY_HIGHEST_TIME_FROM = "highest_price_time_from"
ENTITY_HIGHEST_TIME_TO = "highest_price_time_to"

# Window Device Settings - Switch Entities (Auto Day Start/End)
ENTITY_LOWEST_AUTO_TIME_FROM = "lowest_price_window_from_as_day_start"
ENTITY_LOWEST_AUTO_TIME_TO = "lowest_price_window_to_as_day_end"
ENTITY_HIGHEST_AUTO_TIME_FROM = "highest_price_window_from_as_day_start"
ENTITY_HIGHEST_AUTO_TIME_TO = "highest_price_window_to_as_day_end"

# Window Device Settings - Time Entities (Prefix for Auto Day Start/End)
# FROM prefix is added to the day start (sunrise), TO prefix is subtracted from the day end (sunset)
ENTITY_LOWEST_AUTO_TIME_FROM_PREFIX = "lowest_price_window_from_as_day_start_prefix"
ENTITY_LOWEST_AUTO_TIME_TO_PREFIX = "lowest_price_window_to_as_day_end_prefix"
ENTITY_HIGHEST_AUTO_TIME_FROM_PREFIX = "highest_price_window_from_as_day_start_prefix"
ENTITY_HIGHEST_AUTO_TIME_TO_PREFIX = "highest_price_window_to_as_day_end_prefix"

# Mapping: time entity key -> its prefix entity key
AUTO_TIME_PREFIX_KEYS = {
    ENTITY_LOWEST_TIME_FROM: ENTITY_LOWEST_AUTO_TIME_FROM_PREFIX,
    ENTITY_LOWEST_TIME_TO: ENTITY_LOWEST_AUTO_TIME_TO_PREFIX,
    ENTITY_HIGHEST_TIME_FROM: ENTITY_HIGHEST_AUTO_TIME_FROM_PREFIX,
    ENTITY_HIGHEST_TIME_TO: ENTITY_HIGHEST_AUTO_TIME_TO_PREFIX,
}

# Mapping: time entity key -> switch entity key that sets it automatically (sunrise for "from", sunset for "to")
AUTO_TIME_SWITCH_KEYS = {
    ENTITY_LOWEST_TIME_FROM: ENTITY_LOWEST_AUTO_TIME_FROM,
    ENTITY_LOWEST_TIME_TO: ENTITY_LOWEST_AUTO_TIME_TO,
    ENTITY_HIGHEST_TIME_FROM: ENTITY_HIGHEST_AUTO_TIME_FROM,
    ENTITY_HIGHEST_TIME_TO: ENTITY_HIGHEST_AUTO_TIME_TO,
}


def parse_sun_time(time_attr):
    """Parse a sun.sun next_rising/next_setting attribute to a datetime in market time (None if invalid)."""
    from datetime import datetime
    try:
        if isinstance(time_attr, str):
            sun_time = datetime.fromisoformat(time_attr.replace('Z', '+00:00'))
        elif isinstance(time_attr, datetime):
            sun_time = time_attr
        else:
            return None
        if sun_time.tzinfo is None:
            sun_time = sun_time.replace(tzinfo=dt_util.UTC)
        return sun_time.astimezone(MARKET_TIMEZONE)
    except (TypeError, ValueError):
        return None


async def async_load_translations(hass) -> dict:
    """Load the integration translation file for the configured language (strings.json fallback)."""
    import json
    from pathlib import Path

    def _load() -> dict:
        integration_dir = Path(__file__).parent
        for path in (
            integration_dir / "translations" / f"{hass.config.language or 'en'}.json",
            integration_dir / "strings.json",
        ):
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as file:
                        return json.load(file)
                except (OSError, ValueError):
                    continue
        return {}

    return await hass.async_add_executor_job(_load)


def entity_name(translated_name: str) -> str:
    """Entity part of the name - Home Assistant puts the device name in front: '<device> <translated_name>'."""
    return translated_name


def apply_sun_prefix(sun_time, prefix, is_from):
    """Apply prefix to sunrise/sunset time (both datetime.time, HH:MM).

    is_from=True : day start + prefix (limited to 23:59)
    is_from=False: day end - prefix (limited to 00:00)
    """
    from datetime import time as dt_time
    if prefix is None:
        return sun_time
    sun_minutes = sun_time.hour * 60 + sun_time.minute
    prefix_minutes = prefix.hour * 60 + prefix.minute
    if is_from:
        result = min(sun_minutes + prefix_minutes, 23 * 60 + 59)
    else:
        result = max(sun_minutes - prefix_minutes, 0)
    return dt_time(result // 60, result % 60)

##############################################################################################################################
# Default values of static parameters ########################################################################################
##############################################################################################################################
CALCULATION_DEBOUNCE_DELAY = 2.0  # seconds - delay for window calculations after config changes (prevents multiple recalculations during value adjustments)
MASTER_DATA_DEBOUNCE_DELAY = 0.5  # seconds - delay for window calculations after Master data changed


@dataclass
class OkteRuntimeData:
    """Runtime data stored in ConfigEntry.runtime_data."""

    instance: Any
    device_type: str
    device_name: str
    options: dict = field(default_factory=dict)  # Copy of entry.options used by update_listener for comparison
    fetch_time: str | None = None  # Master only
    master_device: str | None = None  # Calculator only
