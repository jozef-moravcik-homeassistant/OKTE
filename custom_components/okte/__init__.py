"""
OKTE Integration for Home Assistant
Custom integration for fetching and analyzing electricity prices from OKTE Slovakia

Author: Jozef Moravcik
email: jozef.moravcik@moravcik.eu
"""

import logging
import asyncio
from datetime import datetime, time, timedelta

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import Platform
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    CONF_MOST_EXPENSIVE_TIME_WINDOW_PERIOD,
    CONF_CHEAPEST_TIME_WINDOW_PERIOD,
    CONF_FETCH_TIME,
    DEFAULT_MOST_EXPENSIVE_TIME_WINDOW_PERIOD,
    DEFAULT_CHEAPEST_TIME_WINDOW_PERIOD,
    DEFAULT_FETCH_DAYS,
    DEFAULT_FETCH_TIME,
)
from .okte import (
    fetch_okte_data,
    calculate_price_statistics,
    find_cheapest_time_window,
    find_most_expensive_time_window,
    print_price_statistics,
    print_cheapest_window,
    print_most_expensive_window,
    find_multiple_expensive_windows,
    find_multiple_cheap_windows,
)

_LOGGER = logging.getLogger(__name__)

# Platforms supported by this integration
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON, Platform.NUMBER]

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the OKTE component."""
    _LOGGER.info("Setting up OKTE integration")
    
    # Store the configuration
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OKTE from a config entry."""
    _LOGGER.info(f"Setting up OKTE config entry: {entry.title}")
    
    # Initialize data storage
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    
    hass.data[DOMAIN]["config"] = entry.data
    hass.data[DOMAIN]["options"] = entry.options
    hass.data[DOMAIN]["connection_status"] = False  # Initial connection status
    
    # Setup coordinator for automatic data fetching
    coordinator = OkteDataCoordinator(hass, entry)
    hass.data[DOMAIN]["coordinator"] = coordinator
    
    # Start the coordinator
    await coordinator.async_start()
    
    # Set up sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    await _async_register_services(hass)
    
    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options updates."""
    _LOGGER.info("Updating OKTE options")
    
    # Update stored options
    hass.data[DOMAIN]["options"] = entry.options
    
    # Restart coordinator with new settings
    coordinator = hass.data[DOMAIN]["coordinator"]
    await coordinator.async_restart()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info(f"Unloading OKTE config entry: {entry.title}")
    
    # Stop coordinator
    if "coordinator" in hass.data[DOMAIN]:
        coordinator = hass.data[DOMAIN]["coordinator"]
        await coordinator.async_stop()
    
    # Unload sensor platform
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    # Clean up stored data
    if unload_ok and DOMAIN in hass.data:
        hass.data[DOMAIN].clear()
    
    return unload_ok


class OkteDataCoordinator:
    """Coordinator for automatic OKTE data fetching."""
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize the coordinator."""
        self.hass = hass
        self._attr_unique_id = "okte_fetch_data"
        self._attr_name = "Fetch Data"
        self._attr_icon = "mdi:download"
        self._attr_has_entity_name = True
        self._attr_translation_key = "fetch_data"
        self.entry = entry
        self._unsub_timer = None
        self._unsub_retry_timer = None
        self._last_fetch_date = None
        
    async def async_start(self):
        """Start the automatic fetching."""
        _LOGGER.info("Starting OKTE data coordinator")
        await self._schedule_next_fetch()
        
        # Also fetch data immediately if we don't have any
        if DOMAIN not in self.hass.data or "data" not in self.hass.data[DOMAIN]:
            _LOGGER.info("Fetching initial data")
            await self._fetch_data()
    
    async def async_stop(self):
        """Stop the automatic fetching."""
        _LOGGER.info("Stopping OKTE data coordinator")
        if self._unsub_timer:
            self._unsub_timer.cancel()
            self._unsub_timer = None
        if self._unsub_retry_timer:
            self._unsub_retry_timer.cancel()
            self._unsub_retry_timer = None
    
    async def async_restart(self):
        """Restart the coordinator with new settings."""
        await self.async_stop()
        await self.async_start()
    
    async def _schedule_next_fetch(self):
        """Schedule the next data fetch."""
        # Get fetch time from config
        fetch_time_str = self._get_fetch_time()
        
        try:
            fetch_time = time.fromisoformat(fetch_time_str)
        except ValueError:
            _LOGGER.error(f"Invalid fetch time format: {fetch_time_str}, using default")
            fetch_time = time.fromisoformat(DEFAULT_FETCH_TIME)
        
        # Calculate next fetch time
        now = datetime.now()
        next_fetch = datetime.combine(now.date(), fetch_time)
        
        # If the time has already passed today, schedule for tomorrow
        if next_fetch <= now:
            next_fetch += timedelta(days=1)
        
        # Calculate delay
        delay = (next_fetch - now).total_seconds()
        
        _LOGGER.info(f"Next OKTE data fetch scheduled for: {next_fetch}")
        
        # Schedule the fetch
        self._unsub_timer = self.hass.loop.call_later(
            delay, lambda: asyncio.create_task(self._fetch_and_reschedule())
        )
    
    async def _fetch_and_reschedule(self):
        """Fetch data and schedule next fetch."""
        await self._fetch_data()
        await self._schedule_next_fetch()
    
    async def _schedule_retry(self):
        """Schedule retry in 1 minute if fetch failed."""
        _LOGGER.info("Scheduling retry in 1 minute")
        self._unsub_retry_timer = self.hass.loop.call_later(
            60, lambda: asyncio.create_task(self._fetch_data())
        )
    
    async def _fetch_data(self):
        """Fetch OKTE data."""
        try:
            _LOGGER.debug("Fetching OKTE data automatically")
            
            # Get configuration
            max_window_hours = self._get_max_window_hours()
            min_window_hours = self._get_min_window_hours()
            fetch_days = DEFAULT_FETCH_DAYS
            
            # Fetch data in executor to avoid blocking
            data = await self.hass.async_add_executor_job(
                fetch_okte_data, fetch_days, None
            )
            
            if data:
                # Calculate statistics
                statistics = await self.hass.async_add_executor_job(
                    calculate_price_statistics, data
                )
                
                # Find cheapest window
                cheapest_window = await self.hass.async_add_executor_job(
                    find_cheapest_time_window, data, min_window_hours
                )
                
                # Find most expensive window
                most_expensive_window = await self.hass.async_add_executor_job(
                    find_most_expensive_time_window, data, max_window_hours
                )
                
                # Store data
                self.hass.data[DOMAIN]["data"] = data
                self.hass.data[DOMAIN]["statistics"] = statistics
                self.hass.data[DOMAIN]["cheapest_window"] = cheapest_window
                self.hass.data[DOMAIN]["most_expensive_window"] = most_expensive_window
                self.hass.data[DOMAIN]["last_update"] = datetime.now()
                self.hass.data[DOMAIN]["connection_status"] = True  # Success
                
                # Cancel retry timer if it exists
                if self._unsub_retry_timer:
                    self._unsub_retry_timer.cancel()
                    self._unsub_retry_timer = None
                
                _LOGGER.info(f"Successfully fetched {len(data)} OKTE records")
                
                # Fire event for other components
                self.hass.bus.async_fire(f"{DOMAIN}_data_updated", {
                    "records": len(data),
                    "timestamp": datetime.now().isoformat()
                })
                
                # Update all sensors
                await self._update_sensors()
                
            else:
                _LOGGER.warning("Failed to fetch OKTE data - scheduling retry")
                self.hass.data[DOMAIN]["connection_status"] = False  # Failed
                await self._schedule_retry()
                
        except Exception as e:
            _LOGGER.error(f"Error fetching OKTE data: {e} - scheduling retry")
            self.hass.data[DOMAIN]["connection_status"] = False  # Failed
            await self._schedule_retry()
    
    async def _update_sensors(self):
        """Update all OKTE sensors after data fetch."""
        try:
            # Simple approach: fire a state change event to trigger sensor updates
            self.hass.bus.async_fire(f"{DOMAIN}_sensors_update")
            _LOGGER.debug("Triggered sensor updates after data fetch")
            
        except Exception as e:
            _LOGGER.warning(f"Error updating sensors: {e}")
    
    def _get_fetch_time(self) -> str:
        """Get fetch time from configuration."""
        options = self.hass.data[DOMAIN].get("options", {})
        config = self.hass.data[DOMAIN].get("config", {})
        return options.get(CONF_FETCH_TIME) or config.get(CONF_FETCH_TIME, DEFAULT_FETCH_TIME)
    
    def _get_max_window_hours(self) -> int:
        """Get max window hours from configuration."""
        options = self.hass.data[DOMAIN].get("options", {})
        config = self.hass.data[DOMAIN].get("config", {})
        return options.get(CONF_MOST_EXPENSIVE_TIME_WINDOW_PERIOD) or config.get(CONF_MOST_EXPENSIVE_TIME_WINDOW_PERIOD, DEFAULT_MOST_EXPENSIVE_TIME_WINDOW_PERIOD)
    
    def _get_min_window_hours(self) -> int:
        """Get min window hours from configuration."""
        options = self.hass.data[DOMAIN].get("options", {})
        config = self.hass.data[DOMAIN].get("config", {})
        return options.get(CONF_CHEAPEST_TIME_WINDOW_PERIOD) or config.get(CONF_CHEAPEST_TIME_WINDOW_PERIOD, DEFAULT_CHEAPEST_TIME_WINDOW_PERIOD)


async def _recalculate_time_windows(hass: HomeAssistant):
    """Recalculate time windows and update sensors."""
    try:
        # Get current data
        data = hass.data[DOMAIN].get("data", [])
        if not data:
            _LOGGER.warning("No OKTE data available for time window recalculation")
            return False
        
        # Get current window hours from config
        coordinator = hass.data[DOMAIN]["coordinator"]
        max_window_hours = coordinator._get_max_window_hours()
        min_window_hours = coordinator._get_min_window_hours()
        
        # Recalculate windows
        cheapest_window = await hass.async_add_executor_job(
            find_cheapest_time_window, data, min_window_hours
        )
        
        most_expensive_window = await hass.async_add_executor_job(
            find_most_expensive_time_window, data, max_window_hours
        )
        
        # Update stored windows
        hass.data[DOMAIN]["cheapest_window"] = cheapest_window
        hass.data[DOMAIN]["most_expensive_window"] = most_expensive_window
        
        # Fire event for sensor updates
        hass.bus.async_fire(f"{DOMAIN}_data_updated", {
            "timestamp": datetime.now().isoformat(),
            "recalculated": True
        })
        
        # Force immediate update of all sensors and detectors
        await _force_update_all_entities(hass)
        
        # Force immediate update of detectors specifically
        await _update_detectors_immediately(hass)
        
        _LOGGER.info(f"Recalculated time windows: cheapest={min_window_hours}h, most_expensive={max_window_hours}h")
        return True
        
    except Exception as e:
        _LOGGER.error(f"Error recalculating time windows: {e}")
        return False


async def _force_update_all_entities(hass: HomeAssistant):
    """Force immediate update of all OKTE entities."""
    try:
        # Get entity registry using the new method
        entity_registry = er.async_get(hass)
        okte_entities = []
        
        # Find all OKTE entities
        for entity_id, entity_entry in entity_registry.entities.items():
            if entity_entry.platform == DOMAIN:
                okte_entities.append(entity_id)
        
        # Force update each entity
        for entity_id in okte_entities:
            entity = hass.states.get(entity_id)
            if entity:
                # Get the entity object and force update
                entity_obj = None
                
                # Try to get entity from different domains
                for domain in ['sensor', 'button']:
                    domain_entities = getattr(hass.data.get(domain, {}), 'entities', {})
                    if entity_id in domain_entities:
                        entity_obj = domain_entities[entity_id]
                        break
                
                if entity_obj and hasattr(entity_obj, 'async_write_ha_state'):
                    # Force state update for the entity
                    try:
                        await entity_obj.async_write_ha_state()
                        _LOGGER.debug(f"Force updated entity: {entity_id}")
                    except Exception as e:
                        _LOGGER.debug(f"Could not force update {entity_id}: {e}")
        
        # Alternative method: Fire a specific update event
        hass.bus.async_fire(f"{DOMAIN}_force_update", {
            "timestamp": datetime.now().isoformat(),
            "entities_count": len(okte_entities)
        })
        
        _LOGGER.debug(f"Forced update of {len(okte_entities)} OKTE entities")
        
    except Exception as e:
        _LOGGER.warning(f"Error in force update of entities: {e}")


async def _update_detectors_immediately(hass: HomeAssistant):
    """Force immediate update of all detector sensors."""
    try:
        # Fire specific detector update event
        hass.bus.async_fire(f"{DOMAIN}_detectors_update", {
            "timestamp": datetime.now().isoformat(),
            "force_update": True
        })
        
        # Also try to directly update detector states if possible
        entity_registry = er.async_get(hass)
        detector_entities = []
        
        # Find detector entities
        for entity_id, entity_entry in entity_registry.entities.items():
            if (entity_entry.platform == DOMAIN and 
                'detector' in entity_id.lower()):
                detector_entities.append(entity_id)
        
        _LOGGER.debug(f"Found {len(detector_entities)} detector entities for immediate update")
        
        # Schedule immediate detector state updates
        for entity_id in detector_entities:
            # Try to trigger entity update via service call
            try:
                await hass.services.async_call(
                    'homeassistant', 
                    'update_entity', 
                    {'entity_id': entity_id},
                    blocking=False
                )
            except Exception as e:
                _LOGGER.debug(f"Could not update detector {entity_id}: {e}")
        
    except Exception as e:
        _LOGGER.warning(f"Error updating detectors immediately: {e}")


async def _async_register_services(hass: HomeAssistant):
    """Register OKTE services."""
    
    async def fetch_data_service(call: ServiceCall):
        """Handle fetch data service call."""
        fetch_days = DEFAULT_FETCH_DAYS
        fetch_start_day = call.data.get("fetch_start_day")
        
        _LOGGER.info(f"Manual OKTE data fetch requested for {fetch_days} days")
        
        try:
            # Fetch data
            data = await hass.async_add_executor_job(
                fetch_okte_data, fetch_days, fetch_start_day
            )
            
            if data:
                # Get window hours for analysis
                coordinator = hass.data[DOMAIN]["coordinator"]
                max_window_hours = coordinator._get_max_window_hours()
                min_window_hours = coordinator._get_min_window_hours()
                
                # Calculate statistics
                statistics = await hass.async_add_executor_job(
                    calculate_price_statistics, data
                )
                
                # Find windows
                cheapest_window = await hass.async_add_executor_job(
                    find_cheapest_time_window, data, min_window_hours
                )
                
                most_expensive_window = await hass.async_add_executor_job(
                    find_most_expensive_time_window, data, max_window_hours
                )
                
                # Store data
                hass.data[DOMAIN]["data"] = data
                hass.data[DOMAIN]["statistics"] = statistics
                hass.data[DOMAIN]["cheapest_window"] = cheapest_window
                hass.data[DOMAIN]["most_expensive_window"] = most_expensive_window
                hass.data[DOMAIN]["last_update"] = datetime.now()
                hass.data[DOMAIN]["connection_status"] = True  # Success
                
                _LOGGER.info(f"Manual fetch completed: {len(data)} records")
                
                # Fire event
                hass.bus.async_fire(f"{DOMAIN}_data_updated", {
                    "records": len(data),
                    "timestamp": datetime.now().isoformat(),
                    "manual": True
                })
                
                # Update all sensors after manual fetch
                coordinator = hass.data[DOMAIN]["coordinator"]
                await coordinator._update_sensors()
            else:
                _LOGGER.warning("Manual fetch failed")
                hass.data[DOMAIN]["connection_status"] = False  # Failed
                
        except Exception as e:
            _LOGGER.error(f"Error in manual data fetch: {e}")
            hass.data[DOMAIN]["connection_status"] = False  # Failed
    
    async def calculate_price_statistics_service(call: ServiceCall):
        """Handle calculate price statistics service call."""
        try:
            data = hass.data[DOMAIN].get("data", [])
            if not data:
                _LOGGER.warning("No OKTE data available for statistics calculation")
                return
            
            # Calculate statistics
            statistics = await hass.async_add_executor_job(
                calculate_price_statistics, data
            )
            
            # Update stored statistics
            hass.data[DOMAIN]["statistics"] = statistics
            
            # Fire event for sensor updates
            hass.bus.async_fire(f"{DOMAIN}_data_updated", {
                "timestamp": datetime.now().isoformat(),
                "statistics_updated": True
            })
            
            _LOGGER.info("Price statistics recalculated")
            
        except Exception as e:
            _LOGGER.error(f"Error calculating price statistics: {e}")
    

    
    async def find_multiple_expensive_windows_service(call: ServiceCall):
        """Handle find multiple expensive windows service call."""
        try:
            data = hass.data[DOMAIN].get("data", [])
            if not data:
                _LOGGER.warning("No OKTE data available for multiple expensive windows calculation")
                return
            
            window_hours = call.data.get("window_hours", DEFAULT_MOST_EXPENSIVE_TIME_WINDOW_PERIOD)
            count = call.data.get("count", 1)
            
            # Calculate multiple expensive windows
            expensive_windows = await hass.async_add_executor_job(
                find_multiple_expensive_windows, data, window_hours, count
            )
            
            # Store in temporary data (for debugging/logging)
            hass.data[DOMAIN]["multiple_expensive_windows"] = expensive_windows
            
            _LOGGER.info(f"Found {len(expensive_windows)} most expensive {window_hours}-hour windows")
            
        except Exception as e:
            _LOGGER.error(f"Error finding multiple expensive windows: {e}")
    
    async def find_multiple_cheap_windows_service(call: ServiceCall):
        """Handle find multiple cheap windows service call."""
        try:
            data = hass.data[DOMAIN].get("data", [])
            if not data:
                _LOGGER.warning("No OKTE data available for multiple cheap windows calculation")
                return
            
            window_hours = call.data.get("window_hours", DEFAULT_CHEAPEST_TIME_WINDOW_PERIOD)
            count = call.data.get("count", 1)
            
            # Calculate multiple cheap windows
            cheap_windows = await hass.async_add_executor_job(
                find_multiple_cheap_windows, data, window_hours, count
            )
            
            # Store in temporary data (for debugging/logging)
            hass.data[DOMAIN]["multiple_cheap_windows"] = cheap_windows
            
            _LOGGER.info(f"Found {len(cheap_windows)} cheapest {window_hours}-hour windows")
            
        except Exception as e:
            _LOGGER.error(f"Error finding multiple cheap windows: {e}")
    
    async def set_cheapest_window_hours_service(call: ServiceCall):
        """Handle set cheapest window hours service call."""
        try:
            # Get current value from configuration as default
            coordinator = hass.data[DOMAIN]["coordinator"]
            current_value = coordinator._get_min_window_hours()
            
            window_hours = call.data.get("window_hours", current_value)
            
            # Validate input
            if not isinstance(window_hours, int) or window_hours < 1 or window_hours > 24:
                _LOGGER.error(f"Invalid window_hours value: {window_hours}. Must be between 1 and 24.")
                return
            
            # Update configuration
            entry = coordinator.entry
            
            # Update options
            new_options = dict(entry.options)
            new_options[CONF_CHEAPEST_TIME_WINDOW_PERIOD] = window_hours
            
            # Save to config entry
            hass.config_entries.async_update_entry(entry, options=new_options)
            
            # Update runtime data
            hass.data[DOMAIN]["options"] = new_options
            
            # Recalculate time windows
            await _recalculate_time_windows(hass)
            
            _LOGGER.info(f"Updated cheapest time window period from {current_value} to {window_hours} hours and recalculated windows")
            
        except Exception as e:
            _LOGGER.error(f"Error setting cheapest window hours: {e}")
    
    async def set_most_expensive_window_hours_service(call: ServiceCall):
        """Handle set most expensive window hours service call."""
        try:
            # Get current value from configuration as default
            coordinator = hass.data[DOMAIN]["coordinator"]
            current_value = coordinator._get_max_window_hours()
            
            window_hours = call.data.get("window_hours", current_value)
            
            # Validate input
            if not isinstance(window_hours, int) or window_hours < 1 or window_hours > 24:
                _LOGGER.error(f"Invalid window_hours value: {window_hours}. Must be between 1 and 24.")
                return
            
            # Update configuration
            entry = coordinator.entry
            
            # Update options
            new_options = dict(entry.options)
            new_options[CONF_MOST_EXPENSIVE_TIME_WINDOW_PERIOD] = window_hours
            
            # Save to config entry
            hass.config_entries.async_update_entry(entry, options=new_options)
            
            # Update runtime data
            hass.data[DOMAIN]["options"] = new_options
            
            # Recalculate time windows
            await _recalculate_time_windows(hass)
            
            _LOGGER.info(f"Updated most expensive time window period from {current_value} to {window_hours} hours and recalculated windows")
            
        except Exception as e:
            _LOGGER.error(f"Error setting most expensive window hours: {e}")
    
    async def print_price_statistics_service(call: ServiceCall):
        """Handle print price statistics service call."""
        try:
            data = hass.data[DOMAIN].get("data", [])
            if not data:
                _LOGGER.warning("No OKTE data available for printing statistics")
                return
            
            title = call.data.get("title", "Štatistiky cien")
            
            # Print statistics to log
            await hass.async_add_executor_job(
                print_price_statistics, data, title
            )
            
        except Exception as e:
            _LOGGER.error(f"Error printing price statistics: {e}")
    
    async def print_cheapest_window_service(call: ServiceCall):
        """Handle print cheapest window service call."""
        try:
            data = hass.data[DOMAIN].get("data", [])
            if not data:
                _LOGGER.warning("No OKTE data available for printing cheapest window")
                return
            
            window_hours = call.data.get("window_hours", DEFAULT_CHEAPEST_TIME_WINDOW_PERIOD)
            
            # Print cheapest window to log
            await hass.async_add_executor_job(
                print_cheapest_window, data, window_hours
            )
            
        except Exception as e:
            _LOGGER.error(f"Error printing cheapest window: {e}")
    
    async def print_most_expensive_window_service(call: ServiceCall):
        """Handle print most expensive window service call."""
        try:
            data = hass.data[DOMAIN].get("data", [])
            if not data:
                _LOGGER.warning("No OKTE data available for printing most expensive window")
                return
            
            window_hours = call.data.get("window_hours", DEFAULT_MOST_EXPENSIVE_TIME_WINDOW_PERIOD)
            
            # Print most expensive window to log
            await hass.async_add_executor_job(
                print_most_expensive_window, data, window_hours
            )
            
        except Exception as e:
            _LOGGER.error(f"Error printing most expensive window: {e}")
    
    # Register all services
    services_to_register = [
        ("fetch_data", fetch_data_service),
        ("calculate_price_statistics", calculate_price_statistics_service),
        ("find_multiple_expensive_windows", find_multiple_expensive_windows_service),
        ("find_multiple_cheap_windows", find_multiple_cheap_windows_service),
        ("set_cheapest_window_hours", set_cheapest_window_hours_service),
        ("set_most_expensive_window_hours", set_most_expensive_window_hours_service),
        ("print_price_statistics", print_price_statistics_service),
        ("print_cheapest_window", print_cheapest_window_service),
        ("print_most_expensive_window", print_most_expensive_window_service),
    ]
    
    for service_name, service_handler in services_to_register:
        hass.services.async_register(
            DOMAIN,
            service_name,
            service_handler,
        )
    
    _LOGGER.info(f"Registered {len(services_to_register)} OKTE services")