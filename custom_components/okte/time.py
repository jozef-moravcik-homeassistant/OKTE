"""Time platform for OKTE integration."""
from __future__ import annotations

import logging
from typing import Any
from datetime import time as dt_time, datetime
import zoneinfo

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send

from .const import (
    DOMAIN,
    DEVICE_TYPE_CALCULATOR,
    ENTITY_LOWEST_TIME_FROM,
    ENTITY_LOWEST_TIME_TO,
    ENTITY_HIGHEST_TIME_FROM,
    ENTITY_HIGHEST_TIME_TO,
    ENTITY_LOWEST_AUTO_TIME_FROM,
    ENTITY_LOWEST_AUTO_TIME_TO,
    ENTITY_HIGHEST_AUTO_TIME_FROM,
    ENTITY_HIGHEST_AUTO_TIME_TO,
)

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OKTE time entities."""
    LOGGER.info(f"=== TIME PLATFORM CALLED === Entry ID: {config_entry.entry_id}")
    LOGGER.info(f"Config entry data: {config_entry.data}")
    
    device_type = config_entry.data.get("device_type")
    LOGGER.info(f"Time platform setup for entry {config_entry.entry_id}, device_type: {device_type}")
    
    if device_type != DEVICE_TYPE_CALCULATOR:
        LOGGER.info(f"Skipping time entities - not a Calculator device (type: {device_type})")
        return
    
    LOGGER.info("Proceeding to create time entities - device_type is Calculator")
    
    # Get instance from hass.data
    instance = hass.data[DOMAIN][config_entry.entry_id]["instance"]
    LOGGER.info(f"Got instance: {type(instance).__name__}")
    
    # Create time entities for Calculator device
    time_entities = [
        OkteTimeEntity(hass, config_entry, instance, ENTITY_LOWEST_TIME_FROM),
        OkteTimeEntity(hass, config_entry, instance, ENTITY_LOWEST_TIME_TO),
        OkteTimeEntity(hass, config_entry, instance, ENTITY_HIGHEST_TIME_FROM),
        OkteTimeEntity(hass, config_entry, instance, ENTITY_HIGHEST_TIME_TO),
    ]
    
    LOGGER.info(f"Creating time entities for Calculator device")
    LOGGER.info(f"Created {len(time_entities)} time entity objects")
    LOGGER.info(f"Adding {len(time_entities)} time entities")
    async_add_entities(time_entities, True)
    LOGGER.info("Time entities added successfully")


class OkteTimeEntity(TimeEntity):
    """Time entity for time range settings (HH:MM format)."""
    
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, instance, entity_id: str):
        """Initialize the time entity."""
        self.hass = hass
        self.config_entry = config_entry
        self.instance = instance
        self._entity_id_key = entity_id
        self._entry_id = config_entry.entry_id
        
        # Generate entity_id
        from .const import ENTITY_PREFIX, get_calculator_number_from_name
        calculator_number = get_calculator_number_from_name(instance.settings.device_name)
        self.entity_id = f"time.{ENTITY_PREFIX}_{calculator_number}_{entity_id}"
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_{entity_id}"
        
        # Set initial value from instance or default
        if hasattr(instance, 'time_values') and entity_id in instance.time_values:
            self._attr_native_value = instance.time_values[entity_id]
        else:
            # Default values
            if 'from' in entity_id:
                self._attr_native_value = dt_time(0, 0)  # 00:00
            else:
                self._attr_native_value = dt_time(23, 45)  # 23:45
    
    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        # Listen for updates
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_time_update_{self.config_entry.entry_id}",
                self._handle_update
            )
        )
        
        # Track sun.sun entity for sunrise/sunset changes
        from homeassistant.helpers.event import async_track_state_change_event
        
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
    
    async def _handle_sun_change(self) -> None:
        """Update time value based on sun position if auto mode is enabled."""
        if not hasattr(self.instance, 'switch_values'):
            return
        
        # Determine which auto switch controls this entity
        auto_entity = None
        is_sunrise = False
        
        if self._entity_id_key == ENTITY_LOWEST_TIME_FROM:
            auto_entity = ENTITY_LOWEST_AUTO_TIME_FROM
            is_sunrise = True
        elif self._entity_id_key == ENTITY_LOWEST_TIME_TO:
            auto_entity = ENTITY_LOWEST_AUTO_TIME_TO
            is_sunrise = False
        elif self._entity_id_key == ENTITY_HIGHEST_TIME_FROM:
            auto_entity = ENTITY_HIGHEST_AUTO_TIME_FROM
            is_sunrise = True
        elif self._entity_id_key == ENTITY_HIGHEST_TIME_TO:
            auto_entity = ENTITY_HIGHEST_AUTO_TIME_TO
            is_sunrise = False
        
        # Check if auto mode is enabled
        if not auto_entity or not self.instance.switch_values.get(auto_entity, False):
            return
        
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
        
        # Convert to local time
        sun_time = self._parse_sun_time(time_attr)
        if not sun_time:
            return
        
        # Extract time component and clean it (remove seconds and microseconds)
        from datetime import time as dt_time
        sun_time_raw = sun_time.time()
        time_value = dt_time(sun_time_raw.hour, sun_time_raw.minute)
        
        # Update value
        old_value = self._attr_native_value
        self._attr_native_value = time_value
        
        # Store in instance
        if not hasattr(self.instance, 'time_values'):
            self.instance.time_values = {}
        self.instance.time_values[self._entity_id_key] = time_value
        
        # Trigger recalculation if value changed
        if old_value != time_value:
            sun_type = "sunrise" if is_sunrise else "sunset"
            LOGGER.info(f"{sun_type.capitalize()} time changed for {self._entity_id_key}: {time_value.strftime('%H:%M')} (was {old_value.strftime('%H:%M') if old_value else 'None'})")
            await self.instance.my_controller()
        
        self.async_write_ha_state()
    
    def _parse_sun_time(self, time_attr) -> datetime | None:
        """Parse sun time attribute and convert to local datetime."""
        try:
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
    
    @callback
    def _handle_update(self) -> None:
        """Handle updates from instance."""
        if hasattr(self.instance, 'time_values') and self._entity_id_key in self.instance.time_values:
            self._attr_native_value = self.instance.time_values[self._entity_id_key]
            self.async_write_ha_state()
    
    async def async_set_value(self, value: dt_time) -> None:
        """Update the current time value."""
        from homeassistant.exceptions import HomeAssistantError
        
        # Check if auto mode is enabled
        if hasattr(self.instance, 'switch_values'):
            auto_entity = None
            if self._entity_id_key == ENTITY_LOWEST_TIME_FROM:
                auto_entity = ENTITY_LOWEST_AUTO_TIME_FROM
            elif self._entity_id_key == ENTITY_LOWEST_TIME_TO:
                auto_entity = ENTITY_LOWEST_AUTO_TIME_TO
            elif self._entity_id_key == ENTITY_HIGHEST_TIME_FROM:
                auto_entity = ENTITY_HIGHEST_AUTO_TIME_FROM
            elif self._entity_id_key == ENTITY_HIGHEST_TIME_TO:
                auto_entity = ENTITY_HIGHEST_AUTO_TIME_TO
            
            # If auto mode is enabled, reject the change with error message
            if auto_entity and self.instance.switch_values.get(auto_entity, False):
                sun_type = "východ slnka" if 'from' in self._entity_id_key else "západ slnka"
                # Force UI update to current (correct) value before raising exception
                self.async_write_ha_state()
                raise HomeAssistantError(
                    f"Nemožno zmeniť čas - je zapnutý automatický režim ({sun_type}). "
                    f"Najprv vypnite príslušný switch."
                )
        
        # Clean the time value - remove seconds and microseconds (keep only HH:MM)
        from datetime import time as dt_time
        clean_value = dt_time(value.hour, value.minute)
        
        self._attr_native_value = clean_value
        
        # Store in instance
        if not hasattr(self.instance, 'time_values'):
            self.instance.time_values = {}
        self.instance.time_values[self._entity_id_key] = clean_value
        
        # Trigger recalculation
        await self.instance.my_controller()
        
        # Update state
        self.async_write_ha_state()
    
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
            ENTITY_LOWEST_TIME_FROM: "Najnižšie ceny - Časový rozsah od",
            ENTITY_LOWEST_TIME_TO: "Najnižšie ceny - Časový rozsah do",
            ENTITY_HIGHEST_TIME_FROM: "Najvyššie ceny - Časový rozsah od",
            ENTITY_HIGHEST_TIME_TO: "Najvyššie ceny - Časový rozsah do",
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
        if 'from' in self._entity_id_key:
            return "mdi:clock-start"
        else:
            return "mdi:clock-end"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {}
        
        # Check if auto mode is enabled
        if hasattr(self.instance, 'switch_values'):
            auto_entity = None
            if self._entity_id_key == ENTITY_LOWEST_TIME_FROM:
                auto_entity = ENTITY_LOWEST_AUTO_TIME_FROM
            elif self._entity_id_key == ENTITY_LOWEST_TIME_TO:
                auto_entity = ENTITY_LOWEST_AUTO_TIME_TO
            elif self._entity_id_key == ENTITY_HIGHEST_TIME_FROM:
                auto_entity = ENTITY_HIGHEST_AUTO_TIME_FROM
            elif self._entity_id_key == ENTITY_HIGHEST_TIME_TO:
                auto_entity = ENTITY_HIGHEST_AUTO_TIME_TO
            
            if auto_entity:
                is_auto = self.instance.switch_values.get(auto_entity, False)
                attrs["auto_mode_enabled"] = is_auto
                if is_auto:
                    # Show that this is controlled by sunrise/sunset
                    if 'from' in self._entity_id_key:
                        attrs["controlled_by"] = "sunrise"
                    else:
                        attrs["controlled_by"] = "sunset"
        
        return attrs
