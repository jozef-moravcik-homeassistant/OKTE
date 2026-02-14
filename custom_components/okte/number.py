from __future__ import annotations
"""The OKTE Integration"""
"""Author: Jozef Moravcik"""
"""email: jozef.moravcik@moravcik.eu"""

""" number.py """

""" Number platform for OKTE integration."""

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    DOMAIN,
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_CALCULATOR,
    ENTITY_LOWEST_WINDOW_SIZE,
    ENTITY_HIGHEST_WINDOW_SIZE,
)

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OKTE number entities."""
    LOGGER.info(f"=== NUMBER PLATFORM CALLED === Entry ID: {config_entry.entry_id}")
    
    device_type = config_entry.data.get(CONF_DEVICE_TYPE)
    LOGGER.info(f"Number platform setup, device_type: {device_type}")
    
    # Only Calculator devices have number entities
    if device_type != DEVICE_TYPE_CALCULATOR:
        LOGGER.info(f"Skipping number entities - not a Calculator device")
        return
    
    # Get instance from hass.data
    instance = hass.data[DOMAIN][config_entry.entry_id]["instance"]
    
    LOGGER.info(f"Creating window size number entities")
    
    # Create only window size entities (time is now handled by time.py)
    numbers = [
        OkteNumberEntity(hass, config_entry, instance, ENTITY_LOWEST_WINDOW_SIZE),
        OkteNumberEntity(hass, config_entry, instance, ENTITY_HIGHEST_WINDOW_SIZE),
    ]
    
    LOGGER.info(f"Adding {len(numbers)} number entities")
    async_add_entities(numbers, True)
    LOGGER.info("Number entities added successfully")


class OkteNumberEntity(NumberEntity):
    """Number entity for window size settings."""
    
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, instance, entity_id: str):
        """Initialize the number entity."""
        self.hass = hass
        self.config_entry = config_entry
        self.instance = instance
        self._entity_id_key = entity_id
        self._entry_id = config_entry.entry_id
        self._attr_native_min_value = 1
        self._attr_native_max_value = 96  # 24 hours * 4 (15-min periods)
        self._attr_native_step = 1
        self._attr_mode = NumberMode.BOX
        self._attr_native_unit_of_measurement = "periods"
        
        # Generate entity_id
        from .const import ENTITY_PREFIX, get_calculator_number_from_name
        calculator_number = get_calculator_number_from_name(instance.settings.device_name)
        self.entity_id = f"number.{ENTITY_PREFIX}_{calculator_number}_{entity_id}"
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_{entity_id}"
        
        # Load value from config_entry.options (persistent storage)
        self._attr_native_value = config_entry.options.get(entity_id, 3)  # Default 3 hours
        
        # Also update instance value for calculations
        if not hasattr(instance, 'number_values'):
            instance.number_values = {}
        instance.number_values[entity_id] = self._attr_native_value
    
    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        
        # Listen for updates
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_number_update_{self.config_entry.entry_id}",
                self._handle_update
            )
        )
        
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
        if hasattr(self.instance, 'number_values') and self._entity_id_key in self.instance.number_values:
            self._attr_native_value = self.instance.number_values[self._entity_id_key]
            self.async_write_ha_state()
    
    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        int_value = int(value)
        self._attr_native_value = int_value
        
        # Store in instance for calculations
        if not hasattr(self.instance, 'number_values'):
            self.instance.number_values = {}
        self.instance.number_values[self._entity_id_key] = int_value
        
        # Store in config_entry.options for persistence
        new_options = {**self.config_entry.options}
        new_options[self._entity_id_key] = int_value
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
            ENTITY_LOWEST_WINDOW_SIZE: "Najnižšie ceny - Veľkosť okna",
            ENTITY_HIGHEST_WINDOW_SIZE: "Najvyššie ceny - Veľkosť okna",
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
        return "mdi:window-maximize"
