from __future__ import annotations
"""The OKTE Integration"""
"""Author: Jozef Moravcik"""
"""email: jozef.moravcik@moravcik.eu"""

""" binary_sensor.py """

"""Binary Sensor platform for OKTE Integration."""

import logging
import json

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory, DeviceInfo

from .const import *

LOGGER = logging.getLogger(__name__)

async def _load_translations(hass: HomeAssistant) -> dict:
    """Load translations for the current language."""
    import json
    import os
    
    def _load_file():
        try:
            language = hass.config.language if hass else "en"
            
            translations_path = os.path.join(os.path.dirname(__file__), "translations", f"{language}.json")
            
            if not os.path.exists(translations_path):
                translations_path = os.path.join(os.path.dirname(__file__), "strings.json")
            
            if os.path.exists(translations_path):
                with open(translations_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return {}
    
    return await hass.async_add_executor_job(_load_file)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    instance = hass.data[DOMAIN][entry.entry_id]["instance"]
    device_type = hass.data[DOMAIN][entry.entry_id]["device_type"]
    
    translations = await _load_translations(hass)

    entities = []
    
    # Binary sensors are only for Window devices
    if device_type == DEVICE_TYPE_CALCULATOR:
        entities = [
            BinarySensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_DETECTOR_LOWEST_PRICE, 
                name="Detector Lowest Price",
                translations=translations, 
                icon="mdi:clock-check",
                default_value=False,
                enabled_by_default=True,
            ),
            BinarySensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_DETECTOR_LOWEST_PRICE_TODAY, 
                name="Detector Lowest Price Today",
                translations=translations, 
                icon="mdi:clock-check",
                default_value=False,
                enabled_by_default=True,
            ),
            BinarySensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_DETECTOR_LOWEST_PRICE_TOMORROW, 
                name="Detector Lowest Price Tomorrow",
                translations=translations, 
                icon="mdi:clock-check",
                default_value=False,
                enabled_by_default=True,
            ),
            BinarySensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_DETECTOR_HIGHEST_PRICE, 
                name="Detector Highest Price",
                translations=translations, 
                icon="mdi:clock-alert",
                default_value=False,
                enabled_by_default=True,
            ),
            BinarySensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_DETECTOR_HIGHEST_PRICE_TODAY, 
                name="Detector Highest Price Today",
                translations=translations, 
                icon="mdi:clock-alert",
                default_value=False,
                enabled_by_default=True,
            ),
            BinarySensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_DETECTOR_HIGHEST_PRICE_TOMORROW, 
                name="Detector Highest Price Tomorrow",
                translations=translations, 
                icon="mdi:clock-alert",
                default_value=False,
                enabled_by_default=True,
            ),
        ]

    async_add_entities(entities)

class BinarySensorEntityDefinition(BinarySensorEntity):

    @property
    def device_info(self) -> DeviceInfo:
        model = MODEL_MASTER if self._device_type == DEVICE_TYPE_MASTER else MODEL_CALCULATOR
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._instance.settings.device_name,
            manufacturer=MANUFACTURER,
            model=model,
            sw_version=VERSION,
            configuration_url=DOCUMENTATION_URL,
        )
    
    @property
    def name(self) -> str:
        """Return the name of the entity - dynamically generated."""
        translated_name = self._original_translated_name
        
        # Apply prefix based on device type and checkbox setting
        if self._instance.settings.include_device_name_in_entity:
            if self._device_type == DEVICE_TYPE_MASTER:
                # Master: "OKTE - {translated_name}"
                return f"OKTE - {translated_name}"
            else:
                # Calculator: "OKTE - {device_label} - {translated_name}"
                # Get device label from Home Assistant (the name user sets in native HA dialog)
                from homeassistant.helpers import device_registry as dr
                device_registry = dr.async_get(self.hass)
                device_entry = device_registry.async_get_device(identifiers={(DOMAIN, self._entry_id)})
                
                if device_entry and device_entry.name_by_user:
                    device_label = device_entry.name_by_user
                else:
                    # Fallback to automatic name if user hasn't set custom name
                    device_label = self._instance.settings.device_name
                
                return f"OKTE - {device_label} - {translated_name}"
        else:
            # No prefix - just translated name
            return translated_name

    def __init__(
        self,
        hass: HomeAssistant,
        instance,
        entry_id: str,
        device_type: str,
        entity_id: str,
        name: str,
        translations: dict = None,
        icon: str = "mdi:eye",
        default_value: bool = False,
        enabled_by_default: bool = True,
        device_class: BinarySensorDeviceClass | None = None,
        entity_category: EntityCategory | None = None,
        available: bool = True,
    ) -> None:
        """Initialize the binary sensor."""
        self.hass = hass
        self._instance = instance
        self._entry_id = entry_id
        self._device_type = device_type
        
        from .const import ENTITY_PREFIX, get_calculator_number_from_name
        
        # Generate entity_id based on device type
        if device_type == DEVICE_TYPE_MASTER:
            # Master: okte_{entity_name}
            self.entity_id = f"binary_sensor.{ENTITY_PREFIX}_{entity_id}"
        else:
            # Calculator: okte_N_{entity_name}
            calculator_number = get_calculator_number_from_name(instance.settings.device_name)
            self.entity_id = f"binary_sensor.{ENTITY_PREFIX}_{calculator_number}_{entity_id}"
        
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{entity_id}"
        self._attr_has_entity_name = False  # Always False - we manage full name manually
        self._attr_translation_key = entity_id
        
        # Get translated name from translations
        translated_name = name  # Default fallback
        if translations:
            entity_trans = translations.get("entity", {}).get("binary_sensor", {}).get(entity_id, {})
            trans_name = entity_trans.get("name")
            if trans_name:
                translated_name = trans_name
        
        # Store original translated name for dynamic name generation
        self._original_translated_name = translated_name
        
        # Don't set _attr_name here - use property instead for dynamic updates
        
        self._attr_icon = icon
        self._entity_id = entity_id
        self._attr_is_on = default_value
        self._attr_available = available
        self._attr_entity_registry_enabled_default = enabled_by_default
        self._attr_entity_registry_visible_default = enabled_by_default

        if device_class is not None:
            self._attr_device_class = device_class
        if entity_category is not None:
            self._attr_entity_category = entity_category

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_feedback_update_{self._entry_id}",
                self._handle_feedback_update,
            )
        )

    @callback
    def _handle_feedback_update(self) -> None:
        """Handle feedback update."""
        new_value = self._instance.sensor_states.get(self._entity_id)
        # Check if master is available for Window devices
        if hasattr(self._instance, 'is_master_available'):
            if not self._instance.is_master_available():
                self._attr_available = False
            else:
                self._attr_available = True
                if new_value is not None:
                    self._attr_is_on = new_value
        else:
            # Master device binary sensors (if any in future)
            self._attr_available = True
            if new_value is not None:
                self._attr_is_on = new_value
        
        # Force state update to refresh name from @property
        self.async_write_ha_state()
        
        # Also force entity registry update to refresh displayed name
        try:
            from homeassistant.helpers import entity_registry as er
            entity_registry = er.async_get(self.hass)
            
            # Get current entity entry
            entity_entry = entity_registry.async_get(self.entity_id)
            if entity_entry:
                # Update with current name from @property
                current_name = self.name
                if entity_entry.name != current_name and entity_entry.original_name != current_name:
                    entity_registry.async_update_entity(
                        self.entity_id,
                        original_name=current_name
                    )
        except Exception as e:
            LOGGER.debug(f"Could not update entity registry: {e}")

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        return self._attr_is_on
