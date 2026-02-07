from __future__ import annotations
"""The OKTE Integration"""
"""Author: Jozef Moravcik"""
"""email: jozef.moravcik@moravcik.eu"""

""" button.py """

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory, DeviceInfo

from .const import (
    DOMAIN,
    DEVICE_TYPE_MASTER,
    DEVICE_TYPE_CALCULATOR,
    MANUFACTURER,
    MODEL_MASTER,
    VERSION,
    DOCUMENTATION_URL,
)

LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities."""
    instance = hass.data[DOMAIN][entry.entry_id]["instance"]
    device_type = hass.data[DOMAIN][entry.entry_id]["device_type"]
    
    # Load translations
    translations = await _load_translations(hass)
    
    entities = []
    
    # Button is only for Master device
    if device_type == DEVICE_TYPE_MASTER:
        entities = [
            UpdateDataButton(
                hass,
                instance,
                entry_id=entry.entry_id,
                device_type=device_type,
                translations=translations,
            )
        ]
    
    async_add_entities(entities)

async def _load_translations(hass: HomeAssistant) -> dict:
    """Load translations for entity names."""
    import json
    from pathlib import Path
    
    language = hass.config.language or "en"
    integration_dir = Path(__file__).parent
    
    # Try to load language-specific translations
    translation_file = integration_dir / "translations" / f"{language}.json"
    if translation_file.exists():
        with open(translation_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    # Fallback to strings.json
    strings_file = integration_dir / "strings.json"
    if strings_file.exists():
        with open(strings_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    return {}

class UpdateDataButton(ButtonEntity):
    """Button to manually update data from API."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        instance,
        entry_id: str,
        device_type: str,
        translations: dict = None,
    ) -> None:
        """Initialize the button."""
        self.hass = hass
        self._instance = instance
        self._entry_id = entry_id
        self._device_type = device_type
        
        from .const import ENTITY_PREFIX
        
        # Master: okte_update_data
        self.entity_id = f"button.{ENTITY_PREFIX}_update_data"
        
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_update_data"
        self._attr_has_entity_name = False
        self._attr_translation_key = "update_data"
        
        # Get translated name
        translated_name = "Update Data"  # Default fallback
        if translations:
            entity_trans = translations.get("entity", {}).get("button", {}).get("update_data", {})
            trans_name = entity_trans.get("name")
            if trans_name:
                translated_name = trans_name
        
        # Apply prefix if checkbox is enabled
        if instance.settings.include_device_name_in_entity:
            self._attr_name = f"OKTE - {translated_name}"
        else:
            self._attr_name = translated_name
        
        self._attr_icon = "mdi:refresh"
        self._attr_device_class = ButtonDeviceClass.UPDATE
        self._attr_entity_category = EntityCategory.CONFIG
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._instance.settings.device_name,
            manufacturer=MANUFACTURER,
            model=MODEL_MASTER,
            sw_version=VERSION,
            configuration_url=DOCUMENTATION_URL,
        )
    
    @property
    def name(self) -> str:
        """Return the name of the button - dynamically generated."""
        translated_name = "Update Data"
        
        # Try to get translation
        try:
            import json
            from pathlib import Path
            
            language = self.hass.config.language or "en"
            integration_dir = Path(__file__).parent
            translation_file = integration_dir / "translations" / f"{language}.json"
            
            if translation_file.exists():
                with open(translation_file, "r", encoding="utf-8") as f:
                    translations = json.load(f)
                    entity_trans = translations.get("entity", {}).get("button", {}).get("update_data", {})
                    trans_name = entity_trans.get("name")
                    if trans_name:
                        translated_name = trans_name
        except:
            pass
        
        # Apply prefix if checkbox is enabled
        if self._instance.settings.include_device_name_in_entity:
            return f"OKTE - {translated_name}"
        else:
            return translated_name
    
    async def async_press(self) -> None:
        """Handle button press - fetch data from API."""
        LOGGER.info("=== MANUAL DATA UPDATE REQUESTED VIA BUTTON ===")
        
        try:
            # Call the fetch_and_process_data method
            LOGGER.info("Calling fetch_and_process_data()...")
            await self._instance.fetch_and_process_data()
            
            # Send update signal to all entities
            from homeassistant.helpers.dispatcher import async_dispatcher_send
            LOGGER.info(f"Sending dispatcher signal: {DOMAIN}_feedback_update_{self._entry_id}")
            async_dispatcher_send(self.hass, f"{DOMAIN}_feedback_update_{self._entry_id}")
            
            LOGGER.info("=== MANUAL DATA UPDATE COMPLETED SUCCESSFULLY ===")
        except Exception as e:
            LOGGER.error(f"Error during manual data update: {e}", exc_info=True)
