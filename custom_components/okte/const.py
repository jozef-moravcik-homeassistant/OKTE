"""Constants for the OKTE integration."""
"""Author: Jozef Moravcik"""
"""email: jozef.moravcik@moravcik.eu"""

DOMAIN = "okte"

# Operating modes for the okte method
MODE_ALL = 0
MODE_CALCULATION = 1

# Static constants for default values
DEFAULT_MODE = MODE_ALL
DEFAULT_CHEAPEST_TIME_WINDOW_PERIOD = 5
DEFAULT_MOST_EXPENSIVE_TIME_WINDOW_PERIOD = 5
DEFAULT_WINDOW_COUNT = 1
DEFAULT_FETCH_DAYS = 2
DEFAULT_FETCH_TIME = "14:00"  # Default time for daily fetch

# API Configuration
OKTE_API_BASE_URL = "https://isot.okte.sk/api/v1/dam/results"
# OKTE_API_BASE_URL = "https://www.moravcik.eu/json/test11.json"  # for testing
REQUEST_TIMEOUT = 30

# Service names
SERVICE_FETCH_DATA = "fetch_data"
SERVICE_CALCULATE_STATISTICS = "calculate_statistics"
SERVICE_FIND_CHEAPEST_WINDOW = "find_cheapest_window"
SERVICE_FIND_MOST_EXPENSIVE_WINDOW = "find_most_expensive_window"
SERVICE_FIND_MULTIPLE_EXPENSIVE_WINDOWS = "find_multiple_expensive_windows"
SERVICE_FIND_MULTIPLE_CHEAP_WINDOWS = "find_multiple_cheap_windows"
SERVICE_PRINT_STATISTICS = "print_statistics"
SERVICE_PRINT_CHEAPEST_WINDOW = "print_cheapest_window"
SERVICE_PRINT_MOST_EXPENSIVE_WINDOW = "print_most_expensive_window"

# Configuration keys
CONF_FETCH_START_DAY = "fetch_start_day"
CONF_MOST_EXPENSIVE_TIME_WINDOW_PERIOD = "most_expensive_time_window_period"
CONF_CHEAPEST_TIME_WINDOW_PERIOD = "cheapest_time_window_period"
CONF_FETCH_TIME = "fetch_time"  # Time when to automatically fetch data
CONF_COUNT = "count"
CONF_TITLE = "title"

# Default configuration values
DEFAULT_NAME = "OKTE Price Monitor"
DEFAULT_TITLE = "Štatistiky cien"