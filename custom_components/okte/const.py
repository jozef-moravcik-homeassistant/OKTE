"""The OKTE Integration"""
"""Author: Jozef Moravcik"""
"""email: jozef.moravcik@moravcik.eu"""

""" const.py """

""" Constants for the OKTE Integration."""

from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNKNOWN, STATE_UNAVAILABLE, STATE_OK, STATE_PROBLEM

# Custom states for window sensors
STATE_WINDOW_FOUND = "OK"
STATE_WINDOW_NOT_FOUND = "NOT"

DOMAIN = "okte"
VERSION = "1.01.01"
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
    from homeassistant.config_entries import ConfigEntry
    
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
SERVICE_SYSTEM_STARTED = "system_started"
SERVICE_FETCH_DATA = "fetch_data"

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

CONF_INCLUDE_DEVICE_NAME_IN_ENTITY = "include_device_name_in_entity"
DEFAULT_INCLUDE_DEVICE_NAME_IN_ENTITY = True

##############################################################################################################################
# Configuration keys - Master Device #########################################################################################
##############################################################################################################################
CONF_FETCH_TIME = "fetch_time"
DEFAULT_FETCH_TIME = "14:00"

CONF_FETCH_DAYS = "fetch_days"
DEFAULT_FETCH_DAYS = 2

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

##############################################################################################################################
# Default values of static parameters ########################################################################################
##############################################################################################################################
DEFAULT_FALLBACK_CHECK_INTERVAL = 15  # 15 seconds - for Master devices (fast current price updates)
DEFAULT_FALLBACK_CHECK_INTERVAL_CALCULATOR = 15  # 15 seconds - for Calculator devices (fast detector updates)
DEBOUNCE_DELAY = 0.2  # seconds - it groups all changes within this time period (due to better performance)
CALCULATION_DEBOUNCE_DELAY = 2.0  # seconds - delay for window calculations after config changes (prevents multiple recalculations during value adjustments)
