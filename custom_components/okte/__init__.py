from __future__ import annotations
"""The OKTE Integration"""
"""Author: Jozef Moravcik"""
"""email: jozef.moravcik@moravcik.eu"""

""" __init__.py """

import asyncio
import logging
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import ConfigEntryNotReady
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
)

LOGGER = logging.getLogger(__name__)
# Note: Platform.SELECT is not included but select.py file is kept for future use
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON, Platform.NUMBER, Platform.SWITCH, Platform.TIME]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up OKTE from configuration.yaml."""
    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "import"}, data=config[DOMAIN]
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
        ENTITY_LOWEST_WINDOW_SIZE, ENTITY_LOWEST_TIME_FROM, ENTITY_LOWEST_TIME_TO,
        ENTITY_HIGHEST_WINDOW_SIZE, ENTITY_HIGHEST_TIME_FROM, ENTITY_HIGHEST_TIME_TO,
        ENTITY_LOWEST_AUTO_TIME_FROM, ENTITY_LOWEST_AUTO_TIME_TO,
        ENTITY_HIGHEST_AUTO_TIME_FROM, ENTITY_HIGHEST_AUTO_TIME_TO,
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
        fetch_days = entry.options.get(
            CONF_FETCH_DAYS,
            entry.data.get(CONF_FETCH_DAYS, DEFAULT_FETCH_DAYS)
        )
        
        # Set master settings
        instance.settings.device_name = device_name
        instance.settings.include_device_name_in_entity = include_device_name_in_entity
        instance.settings.fetch_time = fetch_time
        instance.settings.fetch_days = fetch_days
        
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
        
        # Initialize number values for window size (will be set by number entities)
        instance.number_values = {
            ENTITY_LOWEST_WINDOW_SIZE: 3,  # Default 3 hours
            ENTITY_HIGHEST_WINDOW_SIZE: 3,  # Default 3 hours
        }
        
        # Initialize time values (will be set by time entities)
        instance.time_values = {
            ENTITY_LOWEST_TIME_FROM: dt_time(0, 0),  # Default 00:00
            ENTITY_LOWEST_TIME_TO: dt_time(23, 45),  # Default 23:45
            ENTITY_HIGHEST_TIME_FROM: dt_time(0, 0),  # Default 00:00
            ENTITY_HIGHEST_TIME_TO: dt_time(23, 45),  # Default 23:45
        }
        
        # Initialize switch values (will be set by switch entities)
        instance.switch_values = {
            ENTITY_LOWEST_AUTO_TIME_FROM: False,
            ENTITY_LOWEST_AUTO_TIME_TO: False,
            ENTITY_HIGHEST_AUTO_TIME_FROM: False,
            ENTITY_HIGHEST_AUTO_TIME_TO: False,
        }

    # Set hass and entry_id
    instance.hass = hass
    instance._entry_id = entry.entry_id
    
    # Setup entity IDs
    instance.setup_entity_ids()

    try:
        hass.data.setdefault(DOMAIN, {})
        
        if device_type == DEVICE_TYPE_MASTER:
            hass.data[DOMAIN][entry.entry_id] = {
                "instance": instance,
                "device_type": device_type,
                CONF_DEVICE_NAME: device_name,
                CONF_INCLUDE_DEVICE_NAME_IN_ENTITY: include_device_name_in_entity,
                CONF_FETCH_TIME: fetch_time,
                CONF_FETCH_DAYS: fetch_days,
            }
        else:
            hass.data[DOMAIN][entry.entry_id] = {
                "instance": instance,
                "device_type": device_type,
                CONF_DEVICE_NAME: device_name,
                CONF_INCLUDE_DEVICE_NAME_IN_ENTITY: include_device_name_in_entity,
                CONF_MASTER_DEVICE: master_device,
            }

        LOGGER.info(f"=== SETUP ENTRY === Entry ID: {entry.entry_id}, Device Type: {device_type}, Device Name: {device_name}")
        LOGGER.info(f"About to setup platforms: {PLATFORMS}")
        
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        
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

        # Schedule initial calls
        async_call_later(hass, 2, async_update_settings_sensors)
        async_call_later(hass, 3, async_run_my_controller)
        
        # For Master device: schedule daily fetch at specified time
        if device_type == DEVICE_TYPE_MASTER:
            try:
                fetch_time_parts = fetch_time.split(':')
                fetch_hour = int(fetch_time_parts[0])
                fetch_minute = int(fetch_time_parts[1])
                
                entry.async_on_unload(
                    async_track_time_change(
                        hass,
                        async_run_my_controller,
                        hour=fetch_hour,
                        minute=fetch_minute,
                        second=0
                    )
                )
                LOGGER.info(f"Scheduled daily fetch at {fetch_time}")
            except Exception as e:
                LOGGER.error(f"Error scheduling daily fetch: {e}")
        
        # For Window device: setup state change listener for master device
        if device_type == DEVICE_TYPE_CALCULATOR and master_device:
            # Track changes in master device sensors
            from .const import sanitize_device_name
            if master_device in hass.data.get(DOMAIN, {}):
                master_instance = hass.data[DOMAIN][master_device].get("instance")
                if master_instance:
                    tracked_entities = [
                        master_instance.SENSOR_ENTITY_LAST_UPDATE,
                    ]
                    
                    async def async_state_changed(event):
                        """React to state changes with debounce."""
                        LOGGER.debug("Master device data updated, recalculating windows")
                        await instance.my_controller()
                    
                    entry.async_on_unload(
                        async_track_state_change_event(
                            hass,
                            tracked_entities,
                            async_state_changed
                        )
                    )
            
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
                    
                    # Get current value of checkbox from hass.data (updated on reload)
                    current_include_device_name = hass.data[DOMAIN][entry.entry_id].get(CONF_INCLUDE_DEVICE_NAME_IN_ENTITY, DEFAULT_INCLUDE_DEVICE_NAME_IN_ENTITY)
                    
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
        
        # Fallback periodic check
        if hasattr(instance.settings, 'fallback_check_interval'):
            fallback_interval = instance.settings.fallback_check_interval
        else:
            fallback_interval = DEFAULT_FALLBACK_CHECK_INTERVAL
        
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

    except Exception as ex:
        LOGGER.error("Error while configuration saving: %s", ex)
        raise ConfigEntryNotReady from ex

    return True


async def system_started_service(call: ServiceCall) -> None:
    """Handle system started service call."""
    try:
        if DOMAIN not in call.hass.data or not call.hass.data[DOMAIN]:
            LOGGER.error("No integrations configured")
            return

        for entry_id, entry_data in call.hass.data[DOMAIN].items():
            instance = entry_data.get("instance")
            if instance:
                await call.hass.async_add_executor_job(instance.system_started)

    except Exception as ex:
        LOGGER.error("Error in system_started: %s", ex)


async def fetch_data_service(call: ServiceCall) -> None:
    """Handle fetch data service call."""
    try:
        if DOMAIN not in call.hass.data or not call.hass.data[DOMAIN]:
            LOGGER.error("No integrations configured")
            return

        # Find all master devices and fetch data
        for entry_id, entry_data in call.hass.data[DOMAIN].items():
            if entry_data.get("device_type") == DEVICE_TYPE_MASTER:
                instance = entry_data.get("instance")
                if instance:
                    await instance.fetch_and_process_data()
                    async_dispatcher_send(call.hass, f"{DOMAIN}_feedback_update_{entry_id}")

    except Exception as ex:
        LOGGER.error("Error in fetch_data: %s", ex)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    from .const import (
        CONF_INCLUDE_DEVICE_NAME_IN_ENTITY, DEFAULT_INCLUDE_DEVICE_NAME_IN_ENTITY,
        CONF_DEVICE_TYPE, DEVICE_TYPE_MASTER
    )
    
    # Get old and new values of checkbox
    old_include_device_name = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get(CONF_INCLUDE_DEVICE_NAME_IN_ENTITY)
    new_include_device_name = entry.options.get(
        CONF_INCLUDE_DEVICE_NAME_IN_ENTITY,
        entry.data.get(CONF_INCLUDE_DEVICE_NAME_IN_ENTITY, DEFAULT_INCLUDE_DEVICE_NAME_IN_ENTITY)
    )
    
    # Reload entry
    await hass.config_entries.async_reload(entry.entry_id)
    
    # If checkbox changed, update entity names in registry
    if old_include_device_name is not None and old_include_device_name != new_include_device_name:
        from homeassistant.helpers import device_registry as dr, entity_registry as er
        from .sensor import _load_translations
        
        LOGGER.info(f"Checkbox changed from {old_include_device_name} to {new_include_device_name}, updating entity names")
        
        # Get device registry
        device_registry = dr.async_get(hass)
        device_entry = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
        
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
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        
        if unload_ok:
            hass.data[DOMAIN].pop(entry.entry_id, None)

        return unload_ok

    except Exception as ex:
        LOGGER.error("Error unloading entry: %s", ex)
        if DOMAIN in hass.data and entry.entry_id in hass.data.get(DOMAIN, {}):
            hass.data[DOMAIN].pop(entry.entry_id, None)
        return False


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
