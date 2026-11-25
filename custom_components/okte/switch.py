from __future__ import annotations
"""The OKTE Integration"""
"""Author: Jozef Moravcik"""
"""email: jozef.moravcik@moravcik.eu"""

""" switch.py """

""" Switch entities for OKTE Calculator device """

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    AUTO_TIME_PREFIX_KEYS,
    AUTO_TIME_SWITCH_KEYS,
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_CALCULATOR,
    DOCUMENTATION_URL,
    DOMAIN,
    ENTITY_PREFIX,
    MANUFACTURER,
    MODEL_CALCULATOR,
    SIGNAL_NAME_UPDATE,
    VERSION,
    apply_sun_prefix,
    async_load_translations,
    get_calculator_number_from_name,
    parse_sun_time,
)

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OKTE switch entities (Calculator devices only)."""
    if config_entry.data.get(CONF_DEVICE_TYPE) != DEVICE_TYPE_CALCULATOR:
        return

    instance = config_entry.runtime_data.instance
    translations = await async_load_translations(hass)
    async_add_entities([
        OkteAutoTimeSwitch(hass, config_entry, instance, switch_key, time_key, translations)
        for time_key, switch_key in AUTO_TIME_SWITCH_KEYS.items()
    ], True)


class OkteAutoTimeSwitch(SwitchEntity):
    """Switch entity for automatic day start/end time setting."""

    # The full name (incl. "OKTE -" prefix and device name) is built in the name property - do not let HA prepend the device name
    _attr_has_entity_name = False
    
    def __init__(
        self, 
        hass: HomeAssistant, 
        config_entry: ConfigEntry, 
        instance, 
        entity_id: str,
        time_entity_id: str,
        translations: dict | None = None
    ):
        """Initialize the switch entity."""
        self._translations = translations or {}
        self.hass = hass
        self.config_entry = config_entry
        self.instance = instance
        self._entity_id_key = entity_id  # Store the key
        self._time_entity_id = time_entity_id
        self._entry_id = config_entry.entry_id
        
        # Generate entity_id
        calculator_number = get_calculator_number_from_name(instance.settings.device_name)
        self.entity_id = f"switch.{ENTITY_PREFIX}_{calculator_number}_{entity_id}"
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_{entity_id}"
        
        # Set initial value from instance or default
        if hasattr(instance, 'switch_values') and entity_id in instance.switch_values:
            self._attr_is_on = instance.switch_values[entity_id]
        else:
            self._attr_is_on = False
    
    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        
        # Values are loaded from Config Entry in __init__.py
        # Just ensure instance has the value and sync to entity
        if hasattr(self.instance, 'switch_values') and self._entity_id_key in self.instance.switch_values:
            self._attr_is_on = self.instance.switch_values[self._entity_id_key]
        
        # Listen for updates
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_switch_update_{self.config_entry.entry_id}",
                self._handle_update
            )
        )
        
        # Track sun.sun entity for sunrise/sunset changes
        @callback
        def sun_changed(event):
            """Handle sun.sun state changes - update time if switch is ON."""
            if self._attr_is_on:
                self.hass.async_create_task(self._update_time_value())
        
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                ["sun.sun"],
                sun_changed
            )
        )
        
        # If switch is ON at startup, update the time value
        if self._attr_is_on:
            await self._update_time_value()

        # Device renamed - write the state again to refresh the name
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_NAME_UPDATE.format(self._entry_id), self.async_write_ha_state)
        )
    
    @callback
    def _handle_update(self) -> None:
        """Handle updates from instance."""
        if hasattr(self.instance, 'switch_values') and self._entity_id_key in self.instance.switch_values:
            self._attr_is_on = self.instance.switch_values[self._entity_id_key]
            self.async_write_ha_state()
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._attr_is_on = True
        
        # Store in instance for calculations
        if not hasattr(self.instance, 'switch_values'):
            self.instance.switch_values = {}
        self.instance.switch_values[self._entity_id_key] = True
        
        # Store in config_entry.options for persistence
        new_options = {**self.config_entry.options}
        new_options[self._entity_id_key] = True
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            options=new_options
        )
        
        # Update the corresponding time value
        await self._update_time_value()
        
        # Notify number entity to update its state (make it read-only)
        async_dispatcher_send(self.hass, f"{DOMAIN}_number_update_{self.config_entry.entry_id}")
        
        # Trigger recalculation with debounce (prevents multiple rapid recalculations)
        if hasattr(self.instance, 'schedule_calculation'):
            self.instance.schedule_calculation()
        else:
            # Fallback if schedule_calculation not available
            await self.instance.my_controller()
        
        self.async_write_ha_state()
    
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._attr_is_on = False
        
        # Store in instance for calculations
        if not hasattr(self.instance, 'switch_values'):
            self.instance.switch_values = {}
        self.instance.switch_values[self._entity_id_key] = False
        
        # Store in config_entry.options for persistence
        new_options = {**self.config_entry.options}
        new_options[self._entity_id_key] = False
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            options=new_options
        )
        
        # Notify number entity to update its state (make it editable)
        async_dispatcher_send(self.hass, f"{DOMAIN}_number_update_{self.config_entry.entry_id}")
        
        # Trigger recalculation with debounce (prevents multiple rapid recalculations)
        if hasattr(self.instance, 'schedule_calculation'):
            self.instance.schedule_calculation()
        else:
            # Fallback if schedule_calculation not available
            await self.instance.my_controller()
        
        self.async_write_ha_state()
    
    async def _update_time_value(self) -> None:
        """Update the time entity value based on sunrise/sunset."""
        from datetime import time as dt_time
        
        if not hasattr(self.instance, 'time_values'):
            self.instance.time_values = {}
        
        # Determine if this is a 'from' (sunrise) or 'to' (sunset) entity
        is_from = 'from' in self._time_entity_id
        
        # Get sun.sun entity
        sun_state = self.hass.states.get("sun.sun")
        if not sun_state:
            LOGGER.warning("sun.sun entity not found, using default time")
            # Fallback to default times
            self.instance.time_values[self._time_entity_id] = dt_time(0, 0) if is_from else dt_time(23, 45)
            async_dispatcher_send(self.hass, f"{DOMAIN}_time_update_{self.config_entry.entry_id}")
            return
        
        # Get sunrise or sunset time
        if is_from:
            time_attr = sun_state.attributes.get("next_rising")
        else:
            time_attr = sun_state.attributes.get("next_setting")
        
        if not time_attr:
            LOGGER.warning("Sun time not found in sun.sun attributes, using default")
            self.instance.time_values[self._time_entity_id] = dt_time(0, 0) if is_from else dt_time(23, 45)
            async_dispatcher_send(self.hass, f"{DOMAIN}_time_update_{self.config_entry.entry_id}")
            return
        
        # Parse time (market time - the windows are searched in Slovak time)
        sun_time = parse_sun_time(time_attr)
        if not sun_time:
            LOGGER.warning("Failed to parse sun time, using default")
            self.instance.time_values[self._time_entity_id] = dt_time(0, 0) if is_from else dt_time(23, 45)
            async_dispatcher_send(self.hass, f"{DOMAIN}_time_update_{self.config_entry.entry_id}")
            return
        
        # Extract time component and clean it (remove seconds and microseconds)
        time_raw = sun_time.time()
        time_value = dt_time(time_raw.hour, time_raw.minute)
        
        # Apply prefix (day start + prefix / day end - prefix)
        time_value = apply_sun_prefix(
            time_value,
            self.instance.time_values.get(AUTO_TIME_PREFIX_KEYS.get(self._time_entity_id)),
            is_from,
        )
        
        # Get old value for comparison
        old_value = self.instance.time_values.get(self._time_entity_id)
        
        # Set the value
        self.instance.time_values[self._time_entity_id] = time_value
        
        if old_value != time_value:
            LOGGER.debug("Setting %s to %s time: %s", self._time_entity_id, "sunrise" if is_from else "sunset",
                         time_value.strftime('%H:%M'))

        # Notify the time entity to update
        async_dispatcher_send(self.hass, f"{DOMAIN}_time_update_{self.config_entry.entry_id}")

        # Note: Recalculation is triggered by the calling switch (async_turn_on/off) with debounce
    
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
        """Return the name - dynamically generated with device prefix."""
        translated_name = (
            self._translations.get("entity", {}).get("switch", {}).get(self._entity_id_key, {}).get("name")
            or self._entity_id_key
        )
        
        # Apply prefix based on checkbox setting
        if self.instance.settings.include_device_name_in_entity:
            # Calculator: "OKTE - {device_label} - {translated_name}"
            device_entry = self.device_entry
            
            if device_entry and device_entry.name_by_user:
                device_label = device_entry.name_by_user
            else:
                device_label = self.instance.settings.device_name
            
            return f"OKTE - {device_label} - {translated_name}"
        else:
            return translated_name
    
    @property
    def icon(self) -> str:
        """Return icon."""
        if self._attr_is_on:
            return "mdi:timer-check"
        else:
            return "mdi:timer-off"
