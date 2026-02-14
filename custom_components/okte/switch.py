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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.const import STATE_ON, STATE_OFF

from .const import (
    DOMAIN,
    DEVICE_TYPE_CALCULATOR,
    CONF_DEVICE_TYPE,
    ENTITY_LOWEST_AUTO_TIME_FROM,
    ENTITY_LOWEST_AUTO_TIME_TO,
    ENTITY_HIGHEST_AUTO_TIME_FROM,
    ENTITY_HIGHEST_AUTO_TIME_TO,
    ENTITY_LOWEST_TIME_FROM,
    ENTITY_LOWEST_TIME_TO,
    ENTITY_HIGHEST_TIME_FROM,
    ENTITY_HIGHEST_TIME_TO,
)

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OKTE switch entities."""
    device_type = config_entry.data.get(CONF_DEVICE_TYPE)
    LOGGER.info(f"Switch platform setup for entry {config_entry.entry_id}, device_type: {device_type}")
    
    # Only Window (Calculator) devices have switch entities
    if device_type != DEVICE_TYPE_CALCULATOR:
        LOGGER.info(f"Skipping switch entities - not a Window device (type: {device_type})")
        return
    
    instance = hass.data[DOMAIN][config_entry.entry_id]["instance"]
    LOGGER.info(f"Creating switch entities for Calculator device")
    
    switches = [
        OkteAutoTimeSwitch(hass, config_entry, instance, ENTITY_LOWEST_AUTO_TIME_FROM, ENTITY_LOWEST_TIME_FROM),
        OkteAutoTimeSwitch(hass, config_entry, instance, ENTITY_LOWEST_AUTO_TIME_TO, ENTITY_LOWEST_TIME_TO),
        OkteAutoTimeSwitch(hass, config_entry, instance, ENTITY_HIGHEST_AUTO_TIME_FROM, ENTITY_HIGHEST_TIME_FROM),
        OkteAutoTimeSwitch(hass, config_entry, instance, ENTITY_HIGHEST_AUTO_TIME_TO, ENTITY_HIGHEST_TIME_TO),
    ]
    
    LOGGER.info(f"Adding {len(switches)} switch entities")
    async_add_entities(switches, True)


class OkteAutoTimeSwitch(SwitchEntity):
    """Switch entity for automatic day start/end time setting."""
    
    def __init__(
        self, 
        hass: HomeAssistant, 
        config_entry: ConfigEntry, 
        instance, 
        entity_id: str,
        time_entity_id: str
    ):
        """Initialize the switch entity."""
        self.hass = hass
        self.config_entry = config_entry
        self.instance = instance
        self._entity_id_key = entity_id  # Store the key
        self._time_entity_id = time_entity_id
        self._entry_id = config_entry.entry_id
        
        # Generate entity_id
        from .const import ENTITY_PREFIX, get_calculator_number_from_name
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
        from homeassistant.helpers.event import async_track_state_change_event
        
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
        
        # Track device registry changes to update entity name immediately when device name changes
        from homeassistant.helpers.device_registry import async_get as async_get_device_registry, EVENT_DEVICE_REGISTRY_UPDATED
        
        @callback
        def device_registry_updated(event):
            """Handle device registry update - refresh entity name."""
            # Check if this event is for our device
            if event.data.get("device_id"):
                device_registry = async_get_device_registry(self.hass)
                device = device_registry.async_get(event.data["device_id"])
                if device and (DOMAIN, self._entry_id) in device.identifiers:
                    # Device name changed - update entity state to refresh the name
                    self.async_write_ha_state()
        
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_DEVICE_REGISTRY_UPDATED, device_registry_updated)
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
        from datetime import datetime
        import zoneinfo
        
        if is_from:
            time_attr = sun_state.attributes.get("next_rising")
        else:
            time_attr = sun_state.attributes.get("next_setting")
        
        if not time_attr:
            LOGGER.warning("Sun time not found in sun.sun attributes, using default")
            self.instance.time_values[self._time_entity_id] = dt_time(0, 0) if is_from else dt_time(23, 45)
            async_dispatcher_send(self.hass, f"{DOMAIN}_time_update_{self.config_entry.entry_id}")
            return
        
        # Parse time
        sun_time = self._parse_sun_time(time_attr)
        if not sun_time:
            LOGGER.warning("Failed to parse sun time, using default")
            self.instance.time_values[self._time_entity_id] = dt_time(0, 0) if is_from else dt_time(23, 45)
            async_dispatcher_send(self.hass, f"{DOMAIN}_time_update_{self.config_entry.entry_id}")
            return
        
        # Extract time component and clean it (remove seconds and microseconds)
        time_raw = sun_time.time()
        time_value = dt_time(time_raw.hour, time_raw.minute)
        
        # Get old value for comparison
        old_value = self.instance.time_values.get(self._time_entity_id)
        
        # Set the value
        self.instance.time_values[self._time_entity_id] = time_value
        
        sun_type = "sunrise" if is_from else "sunset"
        if old_value != time_value:
            LOGGER.info(f"Setting {self._time_entity_id} to {sun_type} time: {time_value.strftime('%H:%M')} (was {old_value.strftime('%H:%M') if old_value else 'None'})")
        
        # Notify the time entity to update
        async_dispatcher_send(self.hass, f"{DOMAIN}_time_update_{self.config_entry.entry_id}")
        
        # Note: Recalculation is triggered by the calling switch (async_turn_on/off) with debounce
    
    def _parse_sun_time(self, time_attr) -> datetime | None:
        """Parse sun time attribute and convert to local datetime."""
        try:
            from datetime import datetime
            import zoneinfo
            
            # Parse datetime
            if isinstance(time_attr, str):
                # String format - parse it
                sun_time = datetime.fromisoformat(time_attr.replace('Z', '+00:00'))
            elif isinstance(time_attr, datetime):
                sun_time = time_attr
            else:
                LOGGER.warning(f"Unexpected time_attr type: {type(time_attr)}")
                return None
            
            # Make sure it's timezone aware
            if sun_time.tzinfo is None:
                # Assume UTC if naive
                sun_time = sun_time.replace(tzinfo=zoneinfo.ZoneInfo('UTC'))
            
            # Convert to local timezone
            ha_timezone = self.hass.config.time_zone
            tz = zoneinfo.ZoneInfo(ha_timezone)
            local_time = sun_time.astimezone(tz)
            
            return local_time
            
        except Exception as e:
            LOGGER.error(f"Error parsing sun time: {e}")
            return None
    
    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self.config_entry.entry_id}_{self._entity_id_key}"
    
    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        from .const import MANUFACTURER, MODEL_CALCULATOR, VERSION, DOCUMENTATION_URL
        from homeassistant.helpers.entity import DeviceInfo
        
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
        # Base names
        names = {
            ENTITY_LOWEST_AUTO_TIME_FROM: "Časový rozsah pre najnižšie ceny 'od' bude východ slnka",
            ENTITY_LOWEST_AUTO_TIME_TO: "Časový rozsah pre najnižšie ceny 'do' bude západ slnka",
            ENTITY_HIGHEST_AUTO_TIME_FROM: "Časový rozsah pre najvyššie ceny 'od' bude východ slnka",
            ENTITY_HIGHEST_AUTO_TIME_TO: "Časový rozsah pre najvyššie ceny 'do' bude západ slnka",
        }
        translated_name = names.get(self._entity_id_key, self._entity_id_key)
        
        # Apply prefix based on checkbox setting
        if self.instance.settings.include_device_name_in_entity:
            # Calculator: "OKTE - {device_label} - {translated_name}"
            from homeassistant.helpers import device_registry as dr
            device_registry = dr.async_get(self.hass)
            device_entry = device_registry.async_get_device(identifiers={(DOMAIN, self._entry_id)})
            
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
