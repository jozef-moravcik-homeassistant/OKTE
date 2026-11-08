from __future__ import annotations
"""The OKTE Integration"""
"""Author: Jozef Moravcik"""
"""email: jozef.moravcik@moravcik.eu"""

""" __init__.py """

import asyncio
import logging
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import Template
from homeassistant.helpers.event import async_call_later, async_track_time_interval, async_track_state_change_event, async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import DeviceInfo
from datetime import timedelta, datetime, time as dt_time

from .const import (
    DOMAIN,
    DEVICE_TYPE_MASTER,
    DEVICE_TYPE_CALCULATOR,
    CONF_FETCH_TIME,
    DEFAULT_FETCH_TIME,
    CONF_INCLUDE_DEVICE_NAME_IN_ENTITY,
    DEFAULT_INCLUDE_DEVICE_NAME_IN_ENTITY,
    OkteRuntimeData,
)

LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON, Platform.NUMBER, Platform.SWITCH, Platform.TIME]

# Optional YAML configuration (imported into a config entry for the Master device)
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Any(
            None,
            vol.Schema(
                {
                    vol.Optional(CONF_FETCH_TIME, default=DEFAULT_FETCH_TIME): cv.time,
                    vol.Optional(
                        CONF_INCLUDE_DEVICE_NAME_IN_ENTITY,
                        default=DEFAULT_INCLUDE_DEVICE_NAME_IN_ENTITY,
                    ): cv.boolean,
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up OKTE from configuration.yaml."""
    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "import"}, data=config[DOMAIN] or {}
        )
    )

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OKTE from a config entry."""
    
    from .const import (
        CONF_DEVICE_TYPE, CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME,
        CONF_INCLUDE_DEVICE_NAME_IN_ENTITY, DEFAULT_INCLUDE_DEVICE_NAME_IN_ENTITY,
        CONF_FETCH_TIME, DEFAULT_FETCH_TIME,
        CONF_FETCH_DAYS, DEFAULT_FETCH_DAYS,
        CONF_MASTER_DEVICE, DEFAULT_MASTER_DEVICE,
        SERVICE_SYSTEM_STARTED, SERVICE_FETCH_DATA,
        DEBOUNCE_DELAY,
        DEFAULT_FALLBACK_CHECK_INTERVAL,
        DEFAULT_FALLBACK_CHECK_INTERVAL_CALCULATOR,
        ENTITY_LOWEST_WINDOW_SIZE, ENTITY_LOWEST_TIME_FROM, ENTITY_LOWEST_TIME_TO,
        ENTITY_HIGHEST_WINDOW_SIZE, ENTITY_HIGHEST_TIME_FROM, ENTITY_HIGHEST_TIME_TO,
        ENTITY_LOWEST_AUTO_TIME_FROM, ENTITY_LOWEST_AUTO_TIME_TO,
        ENTITY_HIGHEST_AUTO_TIME_FROM, ENTITY_HIGHEST_AUTO_TIME_TO,
        AUTO_TIME_PREFIX_KEYS,
    )
    from .okte import OKTE_Master_Instance, OKTE_Window_Instance

    # Get device type
    device_type = entry.options.get(
        CONF_DEVICE_TYPE,
        entry.data.get(CONF_DEVICE_TYPE, DEVICE_TYPE_MASTER)
    )
    
    # Load common parameters
    device_name = entry.options.get(
        CONF_DEVICE_NAME,
        entry.data.get(CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME)
    )
    include_device_name_in_entity = entry.options.get(
        CONF_INCLUDE_DEVICE_NAME_IN_ENTITY,
        entry.data.get(CONF_INCLUDE_DEVICE_NAME_IN_ENTITY, DEFAULT_INCLUDE_DEVICE_NAME_IN_ENTITY)
    )

    # Initialize instance based on device type
    if device_type == DEVICE_TYPE_MASTER:
        instance = OKTE_Master_Instance()
        
        # Load master-specific parameters
        fetch_time = entry.options.get(
            CONF_FETCH_TIME,
            entry.data.get(CONF_FETCH_TIME, DEFAULT_FETCH_TIME)
        )
        
        # Set master settings
        instance.settings.device_name = device_name
        instance.settings.include_device_name_in_entity = include_device_name_in_entity
        instance.settings.fetch_time = fetch_time
        instance.settings.fetch_days = DEFAULT_FETCH_DAYS  # Fixed value, not configurable
        
    else:  # DEVICE_TYPE_CALCULATOR
        instance = OKTE_Window_Instance()
        
        # Load window-specific parameters
        master_device = entry.options.get(
            CONF_MASTER_DEVICE,
            entry.data.get(CONF_MASTER_DEVICE, DEFAULT_MASTER_DEVICE)
        )
        
        # Set window settings
        instance.settings.device_name = device_name
        instance.settings.include_device_name_in_entity = include_device_name_in_entity
        instance.settings.master_device = master_device
        
        # Load number values from Config Entry (or use defaults)
        instance.number_values = {
            ENTITY_LOWEST_WINDOW_SIZE: entry.options.get(ENTITY_LOWEST_WINDOW_SIZE, 3),
            ENTITY_HIGHEST_WINDOW_SIZE: entry.options.get(ENTITY_HIGHEST_WINDOW_SIZE, 3),
        }
        
        # Load time values from Config Entry (or use defaults)
        # Time values are stored as strings in format "HH:MM"
        def parse_time_from_config(time_str, default_time):
            """Parse time string from config or return default."""
            if time_str:
                try:
                    parts = time_str.split(':')
                    return dt_time(int(parts[0]), int(parts[1]))
                except (ValueError, IndexError):
                    return default_time
            return default_time
        
        instance.time_values = {
            ENTITY_LOWEST_TIME_FROM: parse_time_from_config(
                entry.options.get(ENTITY_LOWEST_TIME_FROM), dt_time(0, 0)
            ),
            ENTITY_LOWEST_TIME_TO: parse_time_from_config(
                entry.options.get(ENTITY_LOWEST_TIME_TO), dt_time(23, 59)
            ),
            ENTITY_HIGHEST_TIME_FROM: parse_time_from_config(
                entry.options.get(ENTITY_HIGHEST_TIME_FROM), dt_time(0, 0)
            ),
            ENTITY_HIGHEST_TIME_TO: parse_time_from_config(
                entry.options.get(ENTITY_HIGHEST_TIME_TO), dt_time(23, 59)
            ),
        }
        # Prefixes for auto day start/end (default 0:00)
        for prefix_key in AUTO_TIME_PREFIX_KEYS.values():
            instance.time_values[prefix_key] = parse_time_from_config(
                entry.options.get(prefix_key), dt_time(0, 0)
            )
        
        # Load switch values from Config Entry (or use defaults)
        instance.switch_values = {
            ENTITY_LOWEST_AUTO_TIME_FROM: entry.options.get(ENTITY_LOWEST_AUTO_TIME_FROM, False),
            ENTITY_LOWEST_AUTO_TIME_TO: entry.options.get(ENTITY_LOWEST_AUTO_TIME_TO, False),
            ENTITY_HIGHEST_AUTO_TIME_FROM: entry.options.get(ENTITY_HIGHEST_AUTO_TIME_FROM, False),
            ENTITY_HIGHEST_AUTO_TIME_TO: entry.options.get(ENTITY_HIGHEST_AUTO_TIME_TO, False),
        }

    # Set hass and entry_id
    instance.hass = hass
    instance._entry_id = entry.entry_id
    
    # Setup entity IDs
    instance.setup_entity_ids()
    platforms_forwarded = False

    try:
        entry.runtime_data = OkteRuntimeData(
            instance=instance,
            device_type=device_type,
            device_name=device_name,
            include_device_name_in_entity=include_device_name_in_entity,
            options=dict(entry.options),  # Used by update_listener for comparison
            fetch_time=fetch_time if device_type == DEVICE_TYPE_MASTER else None,
            master_device=master_device if device_type != DEVICE_TYPE_MASTER else None,
        )

        LOGGER.info(f"=== SETUP ENTRY === Entry ID: {entry.entry_id}, Device Type: {device_type}, Device Name: {device_name}")
        LOGGER.info(f"About to setup platforms: {PLATFORMS}")
        
        # Create repair issue to inform user about recorder exclusion recommendation
        # These entities have large attributes (HTML tables, price JSON) exceeding 16KB limit
        if device_type == DEVICE_TYPE_MASTER:
            try:
                from homeassistant.helpers import issue_registry as ir
                from .const import ENTITY_PREFIX
                
                entities_list = "\n".join([
                    f"- sensor.{ENTITY_PREFIX}_prices_today",
                    f"- sensor.{ENTITY_PREFIX}_prices_tomorrow",
                    f"- sensor.{ENTITY_PREFIX}_html_table_today",
                    f"- sensor.{ENTITY_PREFIX}_html_table_tomorrow",
                ])
                
                yaml_config = (
                    "recorder:\n"
                    "  exclude:\n"
                    "    entities:\n" +
                    "\n".join([
                        f"      - sensor.{ENTITY_PREFIX}_prices_today",
                        f"      - sensor.{ENTITY_PREFIX}_prices_tomorrow",
                        f"      - sensor.{ENTITY_PREFIX}_html_table_today",
                        f"      - sensor.{ENTITY_PREFIX}_html_table_tomorrow",
                    ])
                )
                
                ir.async_create_issue(
                    hass,
                    DOMAIN,
                    "recorder_exclude_large_entities",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="recorder_exclude_recommendation",
                    translation_placeholders={
                        "entities": entities_list,
                        "yaml_config": yaml_config,
                    },
                )
            except Exception as e:
                LOGGER.debug(f"Could not create repair issue: {e}")
        
        if device_type == DEVICE_TYPE_MASTER:
            await instance.async_load_stored_data()

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        platforms_forwarded = True
        
        LOGGER.info(f"Platforms setup completed for {device_name}")
        
        
        # Register services
        if not hass.services.has_service(DOMAIN, SERVICE_SYSTEM_STARTED):
            hass.services.async_register(
                DOMAIN,
                SERVICE_SYSTEM_STARTED,
                system_started_service,
            )
        
        if device_type == DEVICE_TYPE_MASTER and not hass.services.has_service(DOMAIN, SERVICE_FETCH_DATA):
            hass.services.async_register(
                DOMAIN,
                SERVICE_FETCH_DATA,
                fetch_data_service,
            )
        
        # Register update listener for options changes
        entry.async_on_unload(entry.add_update_listener(update_listener))
        
        # Setup controller callbacks
        async def async_update_settings_sensors(_now=None):
            """Asynchronous update of settings sensors."""
            async_dispatcher_send(hass, f"{DOMAIN}_settings_update_{entry.entry_id}")
        
        async def async_run_my_controller(_now=None):
            """Periodic execution of my_controller."""
            await instance.my_controller()
        
        async def async_run_fetch_data(_now=None):
            """Fetch data from API - for Master device daily schedule."""
            if hasattr(instance, 'fetch_and_process_data'):
                LOGGER.info("OKTE API: Running scheduled API fetch...")
                await instance.fetch_and_process_data()
                # Also send update signal
                async_dispatcher_send(hass, f"{DOMAIN}_feedback_update_{entry.entry_id}")
            else:
                LOGGER.warning("OKTE API: fetch_and_process_data not available for this device type")

        async def async_run_rollover(_now=None):
            """Move stored data to the new day at midnight (no API call)."""
            await instance.async_rollover()

        # Schedule initial calls
        entry.async_on_unload(async_call_later(hass, 2, async_update_settings_sensors))
        
        # For Master device: initial API fetch on startup and schedule daily fetch
        if device_type == DEVICE_TYPE_MASTER:
            # Fetch data on startup (after 5 seconds)
            entry.async_on_unload(async_call_later(hass, 5, async_run_fetch_data))
            LOGGER.info("Scheduled initial API fetch on startup (5 seconds)")
            
            # First my_controller call AFTER fetch completes (after 8 seconds)
            entry.async_on_unload(async_call_later(hass, 8, async_run_my_controller))
            LOGGER.info("Scheduled first controller update after API fetch (8 seconds)")
            
            try:
                fetch_time_parts = fetch_time.split(':')
                fetch_hour = int(fetch_time_parts[0])
                fetch_minute = int(fetch_time_parts[1])
                
                entry.async_on_unload(
                    async_track_time_change(
                        hass,
                        async_run_fetch_data,  # Use fetch_data callback for API calls
                        hour=fetch_hour,
                        minute=fetch_minute,
                        second=0
                    )
                )
                LOGGER.info(f"Scheduled daily API fetch at {fetch_time}")
                
                # At midnight move stored data (tomorrow -> today) without any API call
                entry.async_on_unload(
                    async_track_time_change(
                        hass,
                        async_run_rollover,
                        hour=0,
                        minute=0,
                        second=0
                    )
                )
                LOGGER.info("Scheduled day rollover at 00:00:00")
            except Exception as e:
                LOGGER.error(f"Error scheduling daily fetch: {e}")
        
        # For Calculator device: wait for Master to have data before first calculation
        elif device_type == DEVICE_TYPE_CALCULATOR:
            # First my_controller call after Master has fetched data (after 10 seconds)
            entry.async_on_unload(async_call_later(hass, 10, async_run_my_controller))
            LOGGER.info("Scheduled first calculator update after Master fetch (10 seconds)")
        
        # For Window device: setup state change listener for master device
        if device_type == DEVICE_TYPE_CALCULATOR and master_device:
            # Track changes of the Master "last update" sensor. The entity id is deterministic,
            # so the listener also works when Master is set up later than this Calculator.
            from .const import ENTITY_PREFIX, ENTITY_LAST_UPDATE
            tracked_entities = [f"sensor.{ENTITY_PREFIX}_{ENTITY_LAST_UPDATE}"]

            async def async_state_changed(event):
                """React to state changes of the Master device."""
                LOGGER.debug("OKTE Calculation: Master device data updated, recalculating windows")
                await instance.my_controller()

            entry.async_on_unload(
                async_track_state_change_event(
                    hass,
                    tracked_entities,
                    async_state_changed
                )
            )

            # Setup 15-minute time tracker for precise detector updates
            # This ensures detectors update exactly at the start of each 15-minute period
            entry.async_on_unload(
                async_track_time_change(
                    hass,
                    async_run_my_controller,
                    minute=[0, 15, 30, 45],
                    second=0
                )
            )
            LOGGER.info("Scheduled detector updates every 15 minutes (:00, :15, :30, :45)")
            
            # Listen for device name changes and update entity names directly in Entity Registry
            from homeassistant.helpers import device_registry as dr, entity_registry as er
            from .sensor import _load_translations
            
            @callback
            def device_registry_updated(event):
                """Handle device registry update - update entity names when device name changes."""
                if event.data.get("action") != "update":
                    return
                
                # Check if this is our device
                device_id = event.data.get("device_id")
                if not device_id:
                    return
                
                changes = event.data.get("changes", {})
                if "name_by_user" not in changes:
                    return
                    
                device_registry = dr.async_get(hass)
                device_entry = device_registry.async_get(device_id)
                
                if device_entry and (DOMAIN, entry.entry_id) in device_entry.identifiers:
                    # Our device was updated
                    new_device_name = device_entry.name_by_user or device_entry.name
                    
                    LOGGER.info(f"Device name changed to '{new_device_name}' for {entry.entry_id}, updating entity names")
                    
                    # Get current value of checkbox from runtime data (updated on reload)
                    current_include_device_name = entry.runtime_data.include_device_name_in_entity
                    
                    # Only update if checkbox is enabled
                    if current_include_device_name:
                        # Schedule async update
                        async def update_entity_names():
                            # Load translations
                            translations = await _load_translations(hass)
                            
                            # Get entity registry
                            entity_registry = er.async_get(hass)
                            
                            # Find all entities for this device
                            entities = er.async_entries_for_device(entity_registry, device_id)
                            
                            # Update each entity name
                            for entity_entry in entities:
                                # Get translation_key to lookup translated name
                                translation_key = entity_entry.translation_key
                                
                                if translation_key and translations:
                                    # Determine if sensor or binary_sensor
                                    domain = entity_entry.entity_id.split('.')[0]
                                    
                                    # Get translated name
                                    entity_trans = translations.get("entity", {}).get(domain, {}).get(translation_key, {})
                                    translated_name = entity_trans.get("name", translation_key.replace('_', ' ').title())
                                    
                                    # Build new name with updated device label
                                    new_entity_name = f"OKTE - {new_device_name} - {translated_name}"
                                    
                                    # Update entity name in registry
                                    entity_registry.async_update_entity(
                                        entity_entry.entity_id,
                                        name=new_entity_name
                                    )
                                    
                                    LOGGER.debug(f"Updated {entity_entry.entity_id} name to: {new_entity_name}")
                        
                        # Run async update
                        hass.async_create_task(update_entity_names())
            
            entry.async_on_unload(
                hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, device_registry_updated)
            )
        
        # Fallback periodic check - use different intervals for Master and Calculator
        if device_type == DEVICE_TYPE_MASTER:
            # Master: 5 minutes (300s)
            if hasattr(instance.settings, 'fallback_check_interval'):
                fallback_interval = instance.settings.fallback_check_interval
            else:
                fallback_interval = DEFAULT_FALLBACK_CHECK_INTERVAL
        else:
            # Calculator: 30 seconds for faster detector updates
            if hasattr(instance.settings, 'fallback_check_interval'):
                fallback_interval = instance.settings.fallback_check_interval
            else:
                fallback_interval = DEFAULT_FALLBACK_CHECK_INTERVAL_CALCULATOR
        
        if fallback_interval > 0:
            LOGGER.info(f"Fallback periodic check enabled: every {fallback_interval} seconds")
            entry.async_on_unload(
                async_track_time_interval(
                    hass,
                    async_run_my_controller,
                    timedelta(seconds=fallback_interval)
                )
            )
        
        LOGGER.info(f"OKTE {device_type} device '{device_name}' configured successfully")

    except Exception:
        LOGGER.exception("Error while setting up OKTE entry %s", entry.entry_id)
        # Clean up everything that was already started, then let the original error propagate
        instance.async_shutdown()
        if platforms_forwarded:
            await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        raise

    return True


def _loaded_entries(hass: HomeAssistant, device_type: str | None = None) -> list[ConfigEntry]:
    """Return loaded OKTE config entries (optionally only of one device type)."""
    return [
        loaded_entry
        for loaded_entry in hass.config_entries.async_entries(DOMAIN)
        if loaded_entry.state is ConfigEntryState.LOADED
        and (device_type is None or loaded_entry.runtime_data.device_type == device_type)
    ]


async def system_started_service(call: ServiceCall) -> None:
    """Handle system started service call."""
    try:
        entries = _loaded_entries(call.hass)
        if not entries:
            LOGGER.error("No integrations configured")
            return

        for loaded_entry in entries:
            await call.hass.async_add_executor_job(loaded_entry.runtime_data.instance.system_started)

    except Exception as ex:
        LOGGER.error("Error in system_started: %s", ex)


async def fetch_data_service(call: ServiceCall) -> None:
    """Handle fetch data service call."""
    try:
        entries = _loaded_entries(call.hass, DEVICE_TYPE_MASTER)
        if not entries:
            LOGGER.error("No integrations configured")
            return

        # Fetch data for all Master devices
        for loaded_entry in entries:
            await loaded_entry.runtime_data.instance.fetch_and_process_data()
            async_dispatcher_send(call.hass, f"{DOMAIN}_feedback_update_{loaded_entry.entry_id}")

    except Exception as ex:
        LOGGER.error("Error in fetch_data: %s", ex)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    from .const import (
        CONF_INCLUDE_DEVICE_NAME_IN_ENTITY, DEFAULT_INCLUDE_DEVICE_NAME_IN_ENTITY,
        CONF_DEVICE_TYPE, DEVICE_TYPE_MASTER,
        ENTITY_LOWEST_WINDOW_SIZE, ENTITY_HIGHEST_WINDOW_SIZE,
        ENTITY_LOWEST_TIME_FROM, ENTITY_LOWEST_TIME_TO,
        ENTITY_HIGHEST_TIME_FROM, ENTITY_HIGHEST_TIME_TO,
        ENTITY_LOWEST_AUTO_TIME_FROM, ENTITY_LOWEST_AUTO_TIME_TO,
        ENTITY_HIGHEST_AUTO_TIME_FROM, ENTITY_HIGHEST_AUTO_TIME_TO,
        AUTO_TIME_PREFIX_KEYS
    )
    
    # List of entity value keys that don't require reload
    entity_value_keys = {
        ENTITY_LOWEST_WINDOW_SIZE, ENTITY_HIGHEST_WINDOW_SIZE,
        ENTITY_LOWEST_TIME_FROM, ENTITY_LOWEST_TIME_TO,
        ENTITY_HIGHEST_TIME_FROM, ENTITY_HIGHEST_TIME_TO,
        ENTITY_LOWEST_AUTO_TIME_FROM, ENTITY_LOWEST_AUTO_TIME_TO,
        ENTITY_HIGHEST_AUTO_TIME_FROM, ENTITY_HIGHEST_AUTO_TIME_TO,
        *AUTO_TIME_PREFIX_KEYS.values()
    }
    
    # Get old and new values of checkbox
    runtime_data = getattr(entry, 'runtime_data', None)
    old_include_device_name = runtime_data.include_device_name_in_entity if runtime_data else None
    new_include_device_name = entry.options.get(
        CONF_INCLUDE_DEVICE_NAME_IN_ENTITY,
        entry.data.get(CONF_INCLUDE_DEVICE_NAME_IN_ENTITY, DEFAULT_INCLUDE_DEVICE_NAME_IN_ENTITY)
    )
    
    # Check if only entity values changed (no reload needed)
    # Get previous options from runtime data
    old_options = runtime_data.options if runtime_data else {}
    new_options = entry.options
    
    # Find what changed
    changed_keys = set()
    for key in set(list(old_options.keys()) + list(new_options.keys())):
        if old_options.get(key) != new_options.get(key):
            changed_keys.add(key)
    
    # If ONLY entity values changed, skip reload
    only_entity_values_changed = changed_keys and changed_keys.issubset(entity_value_keys)
    
    if only_entity_values_changed:
        LOGGER.debug(f"Only entity values changed: {changed_keys}, skipping reload")
        # Update stored options for next comparison
        if runtime_data:
            runtime_data.options = dict(new_options)
        return
    
    # Store new options for next comparison
    if runtime_data:
        runtime_data.options = dict(new_options)
    
    # Reload entry (only if non-entity-value options changed)
    LOGGER.info(f"Config options changed (not just entity values), reloading entry")
    await hass.config_entries.async_reload(entry.entry_id)
    
    # If checkbox changed, update entity names in registry
    if old_include_device_name is not None and old_include_device_name != new_include_device_name:
        from homeassistant.helpers import device_registry as dr, entity_registry as er
        from .sensor import _load_translations
        
        LOGGER.info(f"Checkbox changed from {old_include_device_name} to {new_include_device_name}, updating entity names")
        
        # Find the device of this entry through its entities (async_get_device is deprecated)
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)
        device_entry = None
        for reg_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            if reg_entry.device_id:
                device_entry = device_registry.async_get(reg_entry.device_id)
                break
        
        if device_entry:
            # Get entity registry
            entity_registry = er.async_get(hass)
            
            # Load translations
            translations = await _load_translations(hass)
            
            # Find all entities for this device
            entities = er.async_entries_for_device(entity_registry, device_entry.id)
            
            # Get device label
            device_label = device_entry.name_by_user or device_entry.name
            
            # Update each entity name
            for entity_entry in entities:
                # Get translation_key to lookup translated name
                translation_key = entity_entry.translation_key
                
                if translation_key and translations:
                    # Determine domain (sensor, binary_sensor, switch, etc.)
                    domain = entity_entry.entity_id.split('.')[0]
                    
                    # Get translated name
                    entity_trans = translations.get("entity", {}).get(domain, {}).get(translation_key, {})
                    translated_name = entity_trans.get("name", translation_key.replace('_', ' ').title())
                    
                    # Build new name based on checkbox setting
                    if new_include_device_name:
                        device_type = entry.data.get(CONF_DEVICE_TYPE, DEVICE_TYPE_MASTER)
                        if device_type == DEVICE_TYPE_MASTER:
                            new_entity_name = f"OKTE - {translated_name}"
                        else:
                            new_entity_name = f"OKTE - {device_label} - {translated_name}"
                    else:
                        new_entity_name = translated_name
                    
                    # Update entity name in registry
                    entity_registry.async_update_entity(
                        entity_entry.entity_id,
                        name=new_entity_name
                    )
                    
                    LOGGER.debug(f"Updated {entity_entry.entity_id} name to: {new_entity_name}")

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    try:
        runtime_data = getattr(entry, 'runtime_data', None)
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

        if unload_ok and runtime_data is not None:
            # Cancel pending retry/debounce timers of the instance
            runtime_data.instance.async_shutdown()

        return unload_ok

    except Exception as ex:
        LOGGER.error("Error unloading entry: %s", ex)
        return False


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove stored price data when the config entry is deleted."""
    try:
        from .okte import get_prices_store
        await get_prices_store(hass, entry.entry_id).async_remove()
    except Exception as ex:
        LOGGER.debug("Could not remove stored data: %s", ex)
