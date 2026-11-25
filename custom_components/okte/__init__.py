from __future__ import annotations
"""The OKTE Integration"""
"""Author: Jozef Moravcik"""
"""email: jozef.moravcik@moravcik.eu"""

""" __init__.py """

import logging
from datetime import time as dt_time

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_time_change

from .const import (
    AUTO_TIME_PREFIX_KEYS,
    CONF_DATA_FAILOVER_MODE,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TYPE,
    CONF_FAILOVER_DAYS,
    CONF_FAILOVER_WEEKS,
    CONF_FETCH_TIME,
    CONF_MASTER_DEVICE,
    CONF_PRICE_UNIT,
    DEFAULT_DATA_FAILOVER_MODE,
    DEFAULT_DEVICE_NAME,
    DEFAULT_FAILOVER_DAYS,
    DEFAULT_FAILOVER_WEEKS,
    DEFAULT_FETCH_DAYS,
    DEFAULT_FETCH_TIME,
    DEFAULT_MASTER_DEVICE,
    DEFAULT_PRICE_UNIT,
    DEVICE_TYPE_MASTER,
    DOMAIN,
    ENTITY_HIGHEST_AUTO_TIME_FROM,
    ENTITY_HIGHEST_AUTO_TIME_TO,
    ENTITY_HIGHEST_TIME_FROM,
    ENTITY_HIGHEST_TIME_TO,
    ENTITY_HIGHEST_WINDOW_SIZE,
    ENTITY_LOWEST_AUTO_TIME_FROM,
    ENTITY_LOWEST_AUTO_TIME_TO,
    ENTITY_LOWEST_TIME_FROM,
    ENTITY_LOWEST_TIME_TO,
    ENTITY_LOWEST_WINDOW_SIZE,
    LEGACY_CONF_INCLUDE_DEVICE_NAME_IN_ENTITY,
    LEGACY_MASTER_DEVICE_NAME,
    MASTER_DATA_DEBOUNCE_DELAY,
    MASTER_DEVICE_NAME,
    MASTER_ENTRY_TITLE,
    SERVICE_FETCH_DATA,
    SIGNAL_FEEDBACK_UPDATE,
    SIGNAL_MASTER_DATA_UPDATED,
    OkteRuntimeData,
)

LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON, Platform.NUMBER, Platform.SWITCH, Platform.TIME]

# Issue created by older versions (large attributes are now excluded from the recorder by the entities themselves)
LEGACY_RECORDER_ISSUE_ID = "recorder_exclude_large_entities"

# Optional YAML configuration (imported into a config entry for the Master device)
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Any(
            None,
            vol.Schema(
                {
                    vol.Optional(CONF_FETCH_TIME, default=DEFAULT_FETCH_TIME): cv.time,
                    # Removed setting - still accepted in YAML, but ignored
                    vol.Remove(LEGACY_CONF_INCLUDE_DEVICE_NAME_IN_ENTITY): cv.boolean,
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up OKTE: register services and import optional YAML configuration."""
    hass.services.async_register(DOMAIN, SERVICE_FETCH_DATA, fetch_data_service)

    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "import"}, data=config[DOMAIN] or {}
            )
        )
    return True


def _option(entry: ConfigEntry, key, default):
    """Value of a setting - options take precedence over the data of the entry."""
    return entry.options.get(key, entry.data.get(key, default))


def _parse_time_from_config(time_str, default_time):
    """Parse 'HH:MM' from config or return default."""
    if time_str:
        try:
            parts = time_str.split(':')
            return dt_time(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError, AttributeError):
            return default_time
    return default_time


def _create_master_instance(entry: ConfigEntry, device_name: str):
    """Create and configure the Master instance."""
    from .okte import OKTE_Master_Instance

    instance = OKTE_Master_Instance()
    settings = instance.settings
    settings.device_name = device_name
    settings.fetch_time = _option(entry, CONF_FETCH_TIME, DEFAULT_FETCH_TIME)
    settings.fetch_days = DEFAULT_FETCH_DAYS  # Fixed value, not configurable
    settings.data_failover_mode = _option(entry, CONF_DATA_FAILOVER_MODE, DEFAULT_DATA_FAILOVER_MODE)
    settings.failover_weeks = int(_option(entry, CONF_FAILOVER_WEEKS, DEFAULT_FAILOVER_WEEKS))
    settings.failover_days = int(_option(entry, CONF_FAILOVER_DAYS, DEFAULT_FAILOVER_DAYS))
    settings.price_unit = _option(entry, CONF_PRICE_UNIT, DEFAULT_PRICE_UNIT)
    return instance


def _create_calculator_instance(entry: ConfigEntry, device_name: str):
    """Create and configure a Calculator instance (values of its entities are stored in entry.options)."""
    from .okte import OKTE_Window_Instance

    instance = OKTE_Window_Instance()
    instance.settings.device_name = device_name
    instance.settings.master_device = _option(entry, CONF_MASTER_DEVICE, DEFAULT_MASTER_DEVICE)

    instance.number_values = {
        ENTITY_LOWEST_WINDOW_SIZE: entry.options.get(ENTITY_LOWEST_WINDOW_SIZE, 3),
        ENTITY_HIGHEST_WINDOW_SIZE: entry.options.get(ENTITY_HIGHEST_WINDOW_SIZE, 3),
    }
    instance.time_values = {
        ENTITY_LOWEST_TIME_FROM: _parse_time_from_config(entry.options.get(ENTITY_LOWEST_TIME_FROM), dt_time(0, 0)),
        ENTITY_LOWEST_TIME_TO: _parse_time_from_config(entry.options.get(ENTITY_LOWEST_TIME_TO), dt_time(23, 59)),
        ENTITY_HIGHEST_TIME_FROM: _parse_time_from_config(entry.options.get(ENTITY_HIGHEST_TIME_FROM), dt_time(0, 0)),
        ENTITY_HIGHEST_TIME_TO: _parse_time_from_config(entry.options.get(ENTITY_HIGHEST_TIME_TO), dt_time(23, 59)),
    }
    # Prefixes for auto day start/end (default 0:00)
    for prefix_key in AUTO_TIME_PREFIX_KEYS.values():
        instance.time_values[prefix_key] = _parse_time_from_config(entry.options.get(prefix_key), dt_time(0, 0))

    instance.switch_values = {
        key: entry.options.get(key, False)
        for key in (ENTITY_LOWEST_AUTO_TIME_FROM, ENTITY_LOWEST_AUTO_TIME_TO,
                    ENTITY_HIGHEST_AUTO_TIME_FROM, ENTITY_HIGHEST_AUTO_TIME_TO)
    }
    return instance


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OKTE from a config entry."""
    device_type = _option(entry, CONF_DEVICE_TYPE, DEVICE_TYPE_MASTER)
    if device_type == DEVICE_TYPE_MASTER:
        _async_migrate_master_device_name(hass, entry)
    device_name = _option(entry, CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME)

    if device_type == DEVICE_TYPE_MASTER:
        instance = _create_master_instance(entry, device_name)
    else:
        instance = _create_calculator_instance(entry, device_name)

    instance.hass = hass
    instance._entry_id = entry.entry_id
    instance.setup_entity_ids()
    platforms_forwarded = False

    try:
        entry.runtime_data = OkteRuntimeData(
            instance=instance,
            device_type=device_type,
            device_name=device_name,
            options=dict(entry.options),  # Used by update_listener for comparison
            fetch_time=instance.settings.fetch_time if device_type == DEVICE_TYPE_MASTER else None,
            master_device=instance.settings.master_device if device_type != DEVICE_TYPE_MASTER else None,
        )
        LOGGER.debug("Setting up entry %s (%s, %s)", entry.entry_id, device_type, device_name)

        if device_type == DEVICE_TYPE_MASTER:
            # Older versions asked the user to exclude large entities from the recorder - no longer needed
            ir.async_delete_issue(hass, DOMAIN, LEGACY_RECORDER_ISSUE_ID)
            await instance.async_load_stored_data()

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        platforms_forwarded = True
        _async_remove_legacy_registry_names(hass, entry)

        entry.async_on_unload(entry.add_update_listener(update_listener))

        async def async_run_my_controller(_now=None):
            """Periodic execution of my_controller."""
            await instance.my_controller()

        if device_type == DEVICE_TYPE_MASTER:
            async def async_run_fetch_data(_now=None):
                """Fetch data from API."""
                await instance.fetch_and_process_data()
                async_dispatcher_send(hass, SIGNAL_FEEDBACK_UPDATE.format(entry.entry_id))

            async def async_run_rollover(_now=None):
                """Move stored data to the new day at midnight (no API call)."""
                await instance.async_rollover()

            # Initial API fetch on startup, first controller run after it
            entry.async_on_unload(async_call_later(hass, 5, async_run_fetch_data))
            entry.async_on_unload(async_call_later(hass, 8, async_run_my_controller))

            try:
                fetch_hour, fetch_minute = (int(x) for x in instance.settings.fetch_time.split(':')[:2])
                entry.async_on_unload(
                    async_track_time_change(hass, async_run_fetch_data, hour=fetch_hour, minute=fetch_minute, second=0)
                )
            except (ValueError, AttributeError) as e:
                LOGGER.error("Error scheduling daily fetch: %s", e)

            # At midnight move stored data (tomorrow -> today) without any API call
            entry.async_on_unload(async_track_time_change(hass, async_run_rollover, hour=0, minute=0, second=0))

        else:
            # First calculation after the Master had time to load its data
            entry.async_on_unload(async_call_later(hass, 10, async_run_my_controller))

            # Recalculate whenever the Master data change (fetch, day rollover, failover)
            @callback
            def master_data_updated():
                instance.schedule_calculation(MASTER_DATA_DEBOUNCE_DELAY)

            entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_MASTER_DATA_UPDATED, master_data_updated))

        # Current price (Master) and detectors (Calculator) change at the start of every 15-minute period
        entry.async_on_unload(
            async_track_time_change(hass, async_run_my_controller, minute=[0, 15, 30, 45], second=0)
        )

        LOGGER.debug("OKTE %s device '%s' configured successfully", device_type, device_name)

    except Exception:
        LOGGER.exception("Error while setting up OKTE entry %s", entry.entry_id)
        # Clean up everything that was already started, then let the original error propagate
        instance.async_shutdown()
        if platforms_forwarded:
            await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        raise

    return True


@callback
def _async_migrate_master_device_name(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """One-time rename of the Master device from 'OKTE Master' to 'OKTE' (entity names 'OKTE Current Price').

    A name the user gave the device in the UI (name_by_user) would take precedence, so it is cleared once.
    A later rename in the UI is kept - this runs only while the entry still has the old name.
    """
    if entry.data.get(CONF_DEVICE_NAME) == MASTER_DEVICE_NAME and entry.title == MASTER_DEVICE_NAME:
        # A previous version of this migration also set the entry title to "OKTE" - restore "Master"
        hass.config_entries.async_update_entry(entry, title=MASTER_ENTRY_TITLE)
        return
    if entry.data.get(CONF_DEVICE_NAME) != LEGACY_MASTER_DEVICE_NAME:
        return
    device_registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if (DOMAIN, entry.entry_id) in device_entry.identifiers:
            device_registry.async_update_device(device_entry.id, name=MASTER_DEVICE_NAME, name_by_user=None)
    hass.config_entries.async_update_entry(
        entry,
        title=MASTER_ENTRY_TITLE,
        data={**entry.data, CONF_DEVICE_NAME: MASTER_DEVICE_NAME},
    )
    LOGGER.info("OKTE Master device renamed to '%s'", MASTER_DEVICE_NAME)


@callback
def _async_remove_legacy_registry_names(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove entity names that older versions wrote into the entity registry.

    Home Assistant puts the device name in front of a registry name, so a stored name like
    'OKTE - Battery - Detector Lowest Price' was shown as 'Battery OKTE - Battery - Detector Lowest Price'.
    Only names generated by older versions are removed - names set by the user stay untouched.
    """
    entity_registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        stored_name = entity_entry.name
        translated_name = entity_entry.original_name
        if stored_name is None or not translated_name:
            continue
        if (
            stored_name in (translated_name, f"OKTE - {translated_name}")
            or (stored_name.startswith("OKTE - ") and stored_name.endswith(f" - {translated_name}"))
        ):
            entity_registry.async_update_entity(entity_entry.entity_id, name=None)


def _loaded_entries(hass: HomeAssistant, device_type: str | None = None) -> list[ConfigEntry]:
    """Return loaded OKTE config entries (optionally only of one device type)."""
    return [
        loaded_entry
        for loaded_entry in hass.config_entries.async_entries(DOMAIN)
        if loaded_entry.state is ConfigEntryState.LOADED
        and (device_type is None or loaded_entry.runtime_data.device_type == device_type)
    ]


async def fetch_data_service(call: ServiceCall) -> None:
    """Handle fetch data service call - fetch prices for all Master devices."""
    entries = _loaded_entries(call.hass, DEVICE_TYPE_MASTER)
    if not entries:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_master_device")
    for loaded_entry in entries:
        await loaded_entry.runtime_data.instance.fetch_and_process_data()
        async_dispatcher_send(call.hass, SIGNAL_FEEDBACK_UPDATE.format(loaded_entry.entry_id))


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    # Entity values are stored in options too - changing them must not reload the entry
    entity_value_keys = {
        ENTITY_LOWEST_WINDOW_SIZE, ENTITY_HIGHEST_WINDOW_SIZE,
        ENTITY_LOWEST_TIME_FROM, ENTITY_LOWEST_TIME_TO,
        ENTITY_HIGHEST_TIME_FROM, ENTITY_HIGHEST_TIME_TO,
        ENTITY_LOWEST_AUTO_TIME_FROM, ENTITY_LOWEST_AUTO_TIME_TO,
        ENTITY_HIGHEST_AUTO_TIME_FROM, ENTITY_HIGHEST_AUTO_TIME_TO,
        *AUTO_TIME_PREFIX_KEYS.values(),
    }

    runtime_data = getattr(entry, 'runtime_data', None)

    old_options = runtime_data.options if runtime_data else {}
    new_options = entry.options
    changed_keys = {
        key for key in set(old_options) | set(new_options)
        if old_options.get(key) != new_options.get(key)
    }

    if runtime_data:
        runtime_data.options = dict(new_options)

    if changed_keys and changed_keys.issubset(entity_value_keys):
        LOGGER.debug("Only entity values changed: %s, skipping reload", changed_keys)
        return

    LOGGER.debug("Config options changed, reloading entry %s", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    runtime_data = getattr(entry, 'runtime_data', None)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and runtime_data is not None:
        # Cancel pending retry/debounce timers of the instance
        runtime_data.instance.async_shutdown()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove stored price data when the config entry is deleted."""
    try:
        from .okte import get_prices_store
        await get_prices_store(hass, entry.entry_id).async_remove()
    except Exception as ex:
        LOGGER.debug("Could not remove stored data: %s", ex)
