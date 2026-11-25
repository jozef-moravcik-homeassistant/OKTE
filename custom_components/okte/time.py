from __future__ import annotations
"""The OKTE Integration"""
"""Author: Jozef Moravcik"""
"""email: jozef.moravcik@moravcik.eu"""

""" time.py """

""" Time platform for OKTE integration."""

import logging
from typing import Any
from datetime import time as dt_time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    AUTO_TIME_PREFIX_KEYS,
    AUTO_TIME_SWITCH_KEYS,
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_CALCULATOR,
    DOCUMENTATION_URL,
    DOMAIN,
    ENTITY_HIGHEST_AUTO_TIME_FROM_PREFIX,
    ENTITY_HIGHEST_AUTO_TIME_TO_PREFIX,
    ENTITY_HIGHEST_TIME_FROM,
    ENTITY_HIGHEST_TIME_TO,
    ENTITY_LOWEST_AUTO_TIME_FROM_PREFIX,
    ENTITY_LOWEST_AUTO_TIME_TO_PREFIX,
    ENTITY_LOWEST_TIME_FROM,
    ENTITY_LOWEST_TIME_TO,
    ENTITY_PREFIX,
    MANUFACTURER,
    MODEL_CALCULATOR,
    VERSION,
    apply_sun_prefix,
    async_load_translations,
    entity_name,
    get_calculator_number_from_name,
    parse_sun_time,
)

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OKTE time entities (Calculator devices only)."""
    if config_entry.data.get(CONF_DEVICE_TYPE) != DEVICE_TYPE_CALCULATOR:
        return

    instance = config_entry.runtime_data.instance
    translations = await async_load_translations(hass)

    # Create time entities for Calculator device
    time_entities = [
        OkteTimeEntity(hass, config_entry, instance, ENTITY_LOWEST_TIME_FROM, translations),
        OkteTimeEntity(hass, config_entry, instance, ENTITY_LOWEST_TIME_TO, translations),
        OkteTimeEntity(hass, config_entry, instance, ENTITY_HIGHEST_TIME_FROM, translations),
        OkteTimeEntity(hass, config_entry, instance, ENTITY_HIGHEST_TIME_TO, translations),
        OkteTimePrefixEntity(hass, config_entry, instance, ENTITY_LOWEST_AUTO_TIME_FROM_PREFIX, translations),
        OkteTimePrefixEntity(hass, config_entry, instance, ENTITY_LOWEST_AUTO_TIME_TO_PREFIX, translations),
        OkteTimePrefixEntity(hass, config_entry, instance, ENTITY_HIGHEST_AUTO_TIME_FROM_PREFIX, translations),
        OkteTimePrefixEntity(hass, config_entry, instance, ENTITY_HIGHEST_AUTO_TIME_TO_PREFIX, translations),
    ]
    async_add_entities(time_entities, True)


class OkteTimeEntity(TimeEntity):
    """Time entity for time range settings (HH:MM format)."""

    # Home Assistant puts the device name in front of the entity name: "<device> <name>"
    _attr_has_entity_name = True
    
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, instance, entity_id: str, translations: dict | None = None):
        """Initialize the time entity."""
        self._translations = translations or {}
        self.hass = hass
        self.config_entry = config_entry
        self.instance = instance
        self._entity_id_key = entity_id
        self._entry_id = config_entry.entry_id
        
        # Generate entity_id
        calculator_number = get_calculator_number_from_name(instance.settings.device_name)
        self.entity_id = f"time.{ENTITY_PREFIX}_{calculator_number}_{entity_id}"
        # unique_id is provided by the unique_id property (format kept for existing entities)
        
        # Set initial value from instance or default
        if hasattr(instance, 'time_values') and entity_id in instance.time_values:
            self._attr_native_value = instance.time_values[entity_id]
        else:
            # Default values
            if 'from' in entity_id:
                self._attr_native_value = dt_time(0, 0)  # 00:00
            else:
                self._attr_native_value = dt_time(23, 59)  # 23:59
    
    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        
        # Values are loaded from Config Entry in __init__.py
        # Just ensure instance has the value
        if hasattr(self.instance, 'time_values') and self._entity_id_key in self.instance.time_values:
            self._attr_native_value = self.instance.time_values[self._entity_id_key]
        
        # Listen for updates
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_time_update_{self.config_entry.entry_id}",
                self._handle_update
            )
        )
        
        # Listen for prefix changes (recalculate auto time if its switch is ON)
        @callback
        def prefix_changed():
            self.hass.async_create_task(self._handle_sun_change())
        
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_prefix_update_{self.config_entry.entry_id}",
                prefix_changed
            )
        )
        
        # Track sun.sun entity for sunrise/sunset changes
        @callback
        def sun_changed(event):
            """Handle sun.sun state changes."""
            self.hass.async_create_task(self._handle_sun_change())
        
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                ["sun.sun"],
                sun_changed
            )
        )
        
        # Initial check for auto mode at startup
        await self._handle_sun_change()

    def _is_auto_mode(self) -> bool:
        """True when this time is set automatically from sunrise/sunset (its switch is ON)."""
        auto_entity = AUTO_TIME_SWITCH_KEYS.get(self._entity_id_key)
        return bool(
            auto_entity
            and hasattr(self.instance, 'switch_values')
            and self.instance.switch_values.get(auto_entity, False)
        )

    async def _handle_sun_change(self) -> None:
        """Update time value based on sun position if auto mode is enabled."""
        if not self._is_auto_mode():
            return
        is_sunrise = self._entity_id_key in (ENTITY_LOWEST_TIME_FROM, ENTITY_HIGHEST_TIME_FROM)
        
        # Get sun.sun entity
        sun_state = self.hass.states.get("sun.sun")
        if not sun_state:
            LOGGER.warning("sun.sun entity not found")
            return
        
        # Get sunrise or sunset time
        if is_sunrise:
            time_attr = sun_state.attributes.get("next_rising")
        else:
            time_attr = sun_state.attributes.get("next_setting")
        
        if not time_attr:
            LOGGER.warning(f"Sun time not found in sun.sun attributes")
            return
        
        # Convert to market time (the windows are searched in Slovak time)
        sun_time = parse_sun_time(time_attr)
        if not sun_time:
            return
        
        # Extract time component and clean it (remove seconds and microseconds)
        from datetime import time as dt_time
        sun_time_raw = sun_time.time()
        time_value = dt_time(sun_time_raw.hour, sun_time_raw.minute)
        
        # Apply prefix (day start + prefix / day end - prefix)
        time_value = apply_sun_prefix(
            time_value,
            self.instance.time_values.get(AUTO_TIME_PREFIX_KEYS.get(self._entity_id_key)),
            is_sunrise,
        )
        
        # Update value
        old_value = self._attr_native_value
        self._attr_native_value = time_value
        
        # Store in instance
        if not hasattr(self.instance, 'time_values'):
            self.instance.time_values = {}
        self.instance.time_values[self._entity_id_key] = time_value
        
        # Trigger recalculation if value changed
        if old_value != time_value:
            LOGGER.debug("%s time changed for %s: %s", "Sunrise" if is_sunrise else "Sunset",
                         self._entity_id_key, time_value.strftime('%H:%M'))
            await self.instance.my_controller()

        self.async_write_ha_state()

    @callback
    def _handle_update(self) -> None:
        """Handle updates from instance."""
        if hasattr(self.instance, 'time_values') and self._entity_id_key in self.instance.time_values:
            self._attr_native_value = self.instance.time_values[self._entity_id_key]
            self.async_write_ha_state()
    
    async def async_set_value(self, value: dt_time) -> None:
        """Update the current time value."""
        # If auto mode is enabled, reject the change with a translated error message
        if self._is_auto_mode():
            # Force UI update to current (correct) value before raising exception
            self.async_write_ha_state()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="auto_mode_sunrise" if 'from' in self._entity_id_key else "auto_mode_sunset",
            )

        # Clean the time value - remove seconds and microseconds (keep only HH:MM)
        clean_value = dt_time(value.hour, value.minute)
        
        self._attr_native_value = clean_value
        
        # Store in instance for calculations
        if not hasattr(self.instance, 'time_values'):
            self.instance.time_values = {}
        self.instance.time_values[self._entity_id_key] = clean_value
        
        # Store in config_entry.options for persistence (as string "HH:MM")
        new_options = {**self.config_entry.options}
        new_options[self._entity_id_key] = clean_value.strftime("%H:%M")
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            options=new_options
        )
        
        # Trigger recalculation with debounce (prevents multiple rapid recalculations)
        if hasattr(self.instance, 'schedule_calculation'):
            self.instance.schedule_calculation()
        else:
            # Fallback if schedule_calculation not available
            await self.instance.my_controller()
        
        # Update state
        self.async_write_ha_state()
    
    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self.config_entry.entry_id}_{self._entity_id_key}"
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self.instance.settings.device_name,
            manufacturer=MANUFACTURER,
            model=MODEL_CALCULATOR,
            sw_version=VERSION,
            configuration_url=DOCUMENTATION_URL,
        )
    
    @property
    def name(self) -> str:
        """Return the entity part of the name (Home Assistant adds the device name)."""
        translated_name = (
            self._translations.get("entity", {}).get("time", {}).get(self._entity_id_key, {}).get("name")
            or self._entity_id_key
        )
        return entity_name(translated_name)
    
    @property
    def icon(self) -> str:
        """Return icon."""
        if 'from' in self._entity_id_key:
            return "mdi:clock-start"
        else:
            return "mdi:clock-end"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        attrs = {}
        if hasattr(self.instance, 'switch_values') and self._entity_id_key in AUTO_TIME_SWITCH_KEYS:
            is_auto = self._is_auto_mode()
            attrs["auto_mode_enabled"] = is_auto
            if is_auto:
                # Show that this is controlled by sunrise/sunset
                attrs["controlled_by"] = "sunrise" if 'from' in self._entity_id_key else "sunset"
        return attrs


class OkteTimePrefixEntity(OkteTimeEntity):
    """Time entity with prefix for auto day start/end (HH:MM).

    FROM prefix is added to the day start (sunrise),
    TO prefix is subtracted from the day end (sunset).
    """
    
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, instance, entity_id: str, translations: dict | None = None):
        """Initialize the prefix time entity."""
        super().__init__(hass, config_entry, instance, entity_id, translations)
        if not (hasattr(instance, 'time_values') and entity_id in instance.time_values):
            self._attr_native_value = dt_time(0, 0)
    
    async def async_set_value(self, value: dt_time) -> None:
        """Update the prefix value."""
        clean_value = dt_time(value.hour, value.minute)
        self._attr_native_value = clean_value
        
        if not hasattr(self.instance, 'time_values'):
            self.instance.time_values = {}
        self.instance.time_values[self._entity_id_key] = clean_value
        
        # Store in config_entry.options for persistence (as string "HH:MM")
        new_options = {**self.config_entry.options}
        new_options[self._entity_id_key] = clean_value.strftime("%H:%M")
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            options=new_options
        )
        
        # Recalculate the related time entity (only does something if its auto switch is ON)
        async_dispatcher_send(self.hass, f"{DOMAIN}_prefix_update_{self.config_entry.entry_id}")
        
        self.async_write_ha_state()
    
    @property
    def icon(self) -> str:
        """Return icon."""
        if self._entity_id_key in (ENTITY_LOWEST_AUTO_TIME_FROM_PREFIX, ENTITY_HIGHEST_AUTO_TIME_FROM_PREFIX):
            return "mdi:timer-plus-outline"
        return "mdi:timer-minus-outline"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """No extra attributes for prefix entities."""
        return {}
