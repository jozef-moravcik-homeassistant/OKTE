from __future__ import annotations
"""The OKTE Integration"""
"""Author: Jozef Moravcik"""
"""email: jozef.moravcik@moravcik.eu"""

""" sensor.py """

"""Sensor platform for OKTE Integration."""

import logging
import json

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
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
    """Set up sensor entities."""
    instance = hass.data[DOMAIN][entry.entry_id]["instance"]
    device_type = hass.data[DOMAIN][entry.entry_id]["device_type"]
    
    translations = await _load_translations(hass)

    entities = []
    
    if device_type == DEVICE_TYPE_MASTER:
        # Master device sensors
        entities = [
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_CONNECTION_STATUS, 
                name="Connection Status",
                translations=translations, 
                icon="mdi:connection",
                default_value=False,
                enabled_by_default=True,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_LAST_UPDATE, 
                name="Last Update",
                translations=translations, 
                icon="mdi:clock-outline",
                default_value=None,
                enabled_by_default=True,
                device_class=SensorDeviceClass.TIMESTAMP,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_DATA_COUNT, 
                name="Data Count",
                translations=translations, 
                icon="mdi:counter",
                default_value=0,
                enabled_by_default=True,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_CURRENT_PRICE, 
                name="Current Price",
                translations=translations, 
                icon="mdi:currency-eur",
                default_value=None,
                enabled_by_default=True,
                device_class=SensorDeviceClass.MONETARY,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="EUR/MWh",
                suggested_display_precision=2,
            ),
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_AVERAGE_PRICE_TODAY, 
                name="Average Price Today",
                translations=translations, 
                icon="mdi:chart-line",
                default_value=None,
                enabled_by_default=True,
                device_class=SensorDeviceClass.MONETARY,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="EUR/MWh",
                suggested_display_precision=2,
            ),
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_MIN_PRICE_TODAY, 
                name="Min Price Today",
                translations=translations, 
                icon="mdi:arrow-down-bold",
                default_value=None,
                enabled_by_default=True,
                device_class=SensorDeviceClass.MONETARY,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="EUR/MWh",
                suggested_display_precision=2,
            ),
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_MAX_PRICE_TODAY, 
                name="Max Price Today",
                translations=translations, 
                icon="mdi:arrow-up-bold",
                default_value=None,
                enabled_by_default=True,
                device_class=SensorDeviceClass.MONETARY,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="EUR/MWh",
                suggested_display_precision=2,
            ),
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_AVERAGE_PRICE_TOMORROW, 
                name="Average Price Tomorrow",
                translations=translations, 
                icon="mdi:chart-line",
                default_value=None,
                enabled_by_default=True,
                device_class=SensorDeviceClass.MONETARY,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="EUR/MWh",
                suggested_display_precision=2,
            ),
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_MIN_PRICE_TOMORROW, 
                name="Min Price Tomorrow",
                translations=translations, 
                icon="mdi:arrow-down-bold",
                default_value=None,
                enabled_by_default=True,
                device_class=SensorDeviceClass.MONETARY,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="EUR/MWh",
                suggested_display_precision=2,
            ),
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_MAX_PRICE_TOMORROW, 
                name="Max Price Tomorrow",
                translations=translations, 
                icon="mdi:arrow-up-bold",
                default_value=None,
                enabled_by_default=True,
                device_class=SensorDeviceClass.MONETARY,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="EUR/MWh",
                suggested_display_precision=2,
            ),
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_PRICES_TODAY, 
                name="Prices Today",
                translations=translations, 
                icon="mdi:table-clock",
                default_value=None,
                enabled_by_default=True,
            ),
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_PRICES_TOMORROW, 
                name="Prices Tomorrow",
                translations=translations, 
                icon="mdi:table-clock",
                default_value=None,
                enabled_by_default=True,
            ),
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_HTML_TABLE_TODAY, 
                name="HTML Table Today",
                translations=translations, 
                icon="mdi:table",
                default_value="",
                enabled_by_default=True,
            ),
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_HTML_TABLE_TOMORROW, 
                name="HTML Table Tomorrow",
                translations=translations, 
                icon="mdi:table",
                default_value="",
                enabled_by_default=True,
            ),
        ]
    
    elif device_type == DEVICE_TYPE_CALCULATOR:
        # Window device sensors
        entities = [
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_LOWEST_PRICE_WINDOW, 
                name="Lowest Price Window",
                translations=translations, 
                icon="mdi:arrow-down-bold-box",
                default_value=None,
                enabled_by_default=True,
            ),
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_LOWEST_PRICE_WINDOW_TODAY, 
                name="Lowest Price Window Today",
                translations=translations, 
                icon="mdi:arrow-down-bold-box",
                default_value=None,
                enabled_by_default=True,
            ),
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_LOWEST_PRICE_WINDOW_TOMORROW, 
                name="Lowest Price Window Tomorrow",
                translations=translations, 
                icon="mdi:arrow-down-bold-box",
                default_value=None,
                enabled_by_default=True,
            ),
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_HIGHEST_PRICE_WINDOW, 
                name="Highest Price Window",
                translations=translations, 
                icon="mdi:arrow-up-bold-box",
                default_value=None,
                enabled_by_default=True,
            ),
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_HIGHEST_PRICE_WINDOW_TODAY, 
                name="Highest Price Window Today",
                translations=translations, 
                icon="mdi:arrow-up-bold-box",
                default_value=None,
                enabled_by_default=True,
            ),
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_HIGHEST_PRICE_WINDOW_TOMORROW, 
                name="Highest Price Window Tomorrow",
                translations=translations, 
                icon="mdi:arrow-up-bold-box",
                default_value=None,
                enabled_by_default=True,
            ),
            # Duration sensors - showing time in H:MM format
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_LOWEST_WINDOW_SIZE_TIME, 
                name="Lowest Price Window Size",
                translations=translations, 
                icon="mdi:timer",
                default_value="0:00",
                enabled_by_default=True,
                available=True,
            ),
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_HIGHEST_WINDOW_SIZE_TIME, 
                name="Highest Price Window Size",
                translations=translations, 
                icon="mdi:timer",
                default_value="0:00",
                enabled_by_default=True,
                available=True,
            ),
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_LOWEST_SEARCH_WINDOW_SIZE, 
                name="Lowest Price Search Window Size",
                translations=translations, 
                icon="mdi:magnify-expand",
                default_value="0:00",
                enabled_by_default=True,
                available=True,
            ),
            SensorEntityDefinition(
                hass,
                instance, 
                entry_id=entry.entry_id,
                device_type=device_type,
                entity_id=ENTITY_HIGHEST_SEARCH_WINDOW_SIZE, 
                name="Highest Price Search Window Size",
                translations=translations, 
                icon="mdi:magnify-expand",
                default_value="0:00",
                enabled_by_default=True,
                available=True,
            ),
        ]

    async_add_entities(entities)

class SensorEntityDefinition(SensorEntity):

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
        default_value: str = None,
        enabled_by_default: bool = True,
        device_class: SensorDeviceClass | None = None,
        state_class: SensorStateClass | None = None,
        native_unit_of_measurement: str | None = None,
        suggested_display_precision: int | None = None,
        suggested_unit_of_measurement: str | None = None,
        entity_category: EntityCategory | None = None,
        options: list[str] | None = None,
        available: bool = True,
        last_reset: str | None = None,
        attributes: dict | None = None,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._instance = instance
        self._entry_id = entry_id
        self._device_type = device_type
        
        from .const import ENTITY_PREFIX, get_calculator_number_from_name
        
        # Generate entity_id based on device type
        if device_type == DEVICE_TYPE_MASTER:
            # Master: okte_{entity_name}
            self.entity_id = f"sensor.{ENTITY_PREFIX}_{entity_id}"
        else:
            # Calculator: okte_N_{entity_name}
            calculator_number = get_calculator_number_from_name(instance.settings.device_name)
            self.entity_id = f"sensor.{ENTITY_PREFIX}_{calculator_number}_{entity_id}"
        
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{entity_id}"
        self._attr_has_entity_name = False  # Always False - we manage full name manually
        self._attr_translation_key = entity_id
        
        # Get translated name from translations
        translated_name = name  # Default fallback
        if translations:
            entity_trans = translations.get("entity", {}).get("sensor", {}).get(entity_id, {})
            trans_name = entity_trans.get("name")
            if trans_name:
                translated_name = trans_name
        
        # Store original translated name for dynamic name generation
        self._original_translated_name = translated_name
        
        # Don't set _attr_name here - use property instead for dynamic updates
        
        self._attr_icon = icon
        self._entity_id = entity_id
        self._attr_native_value = default_value
        self._attr_available = available
        self._attr_entity_registry_enabled_default = enabled_by_default
        self._attr_entity_registry_visible_default = enabled_by_default
        
        # Initialize storage for large data (prices JSON, HTML tables, and window data)
        self._prices_data = None
        self._html_data = None
        self._window_data = None
        
        # Store attributes configuration
        self._attributes_config = attributes if attributes else {}

        if device_class is not None:
            self._attr_device_class = device_class
        if state_class is not None:
            self._attr_state_class = state_class
        if native_unit_of_measurement is not None:
            self._attr_native_unit_of_measurement = native_unit_of_measurement
        if suggested_display_precision is not None:
            self._attr_suggested_display_precision = suggested_display_precision
        if suggested_unit_of_measurement is not None:
            self._attr_suggested_unit_of_measurement = suggested_unit_of_measurement
        if entity_category is not None:
            self._attr_entity_category = entity_category
        if options is not None:
            self._attr_options = options
        if last_reset is not None:
            self._attr_last_reset = last_reset

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        
        # Duration sensors need immediate update with computed values
        if self._entity_id in [ENTITY_LOWEST_WINDOW_SIZE_TIME, ENTITY_HIGHEST_WINDOW_SIZE_TIME,
                                ENTITY_LOWEST_SEARCH_WINDOW_SIZE, ENTITY_HIGHEST_SEARCH_WINDOW_SIZE]:
            # Force initial state update - value will be computed in native_value property
            self.async_write_ha_state()
            LOGGER.debug(f"Duration sensor {self.entity_id} initialized with computed value")
            # Skip sensor_states initialization for duration sensors
        else:
            # Load initial value from sensor_states if available (for non-duration sensors)
            initial_value = self._instance.sensor_states.get(self._entity_id)
            if initial_value is not None:
                # For prices sensors - just set state (count), attributes come from sensor_attributes
                if self._entity_id in [ENTITY_PRICES_TODAY, ENTITY_PRICES_TOMORROW]:
                    self._attr_native_value = initial_value
                    LOGGER.debug(f"Entity {self.entity_id} initialized with count: {initial_value}")
                # For HTML sensors - just set state (count), attributes come from sensor_attributes
                elif self._entity_id in [ENTITY_HTML_TABLE_TODAY, ENTITY_HTML_TABLE_TOMORROW]:
                    self._attr_native_value = initial_value
                    LOGGER.debug(f"Entity {self.entity_id} initialized with count: {initial_value}")
                # For window sensors - store in _window_data
                elif self._entity_id in [ENTITY_LOWEST_PRICE_WINDOW_TODAY, ENTITY_LOWEST_PRICE_WINDOW_TOMORROW,
                                          ENTITY_HIGHEST_PRICE_WINDOW_TODAY, ENTITY_HIGHEST_PRICE_WINDOW_TOMORROW]:
                    self._window_data = initial_value
                    LOGGER.debug(f"Entity {self.entity_id} initialized with window data")
                # For other sensors - normal value
                else:
                    self._attr_native_value = initial_value
                    LOGGER.debug(f"Entity {self.entity_id} initialized with value from sensor_states: {initial_value}")
            else:
                LOGGER.debug(f"Entity {self.entity_id} initialized with default value")
        
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
        # Duration sensors are computed from number_values and time_values, not from sensor_states
        if self._entity_id in [ENTITY_LOWEST_WINDOW_SIZE_TIME, ENTITY_HIGHEST_WINDOW_SIZE_TIME,
                                ENTITY_LOWEST_SEARCH_WINDOW_SIZE, ENTITY_HIGHEST_SEARCH_WINDOW_SIZE]:
            # These sensors are always available if Calculator device
            if self._device_type == DEVICE_TYPE_CALCULATOR:
                self._attr_available = True
                # Value is computed in native_value property, no need to set it here
                self.async_write_ha_state()
                LOGGER.debug(f"Updated duration sensor {self.entity_id}")
            return
        
        new_value = self._instance.sensor_states.get(self._entity_id)
        
        LOGGER.debug(f"Feedback update for {self.entity_id}: entity_id_key={self._entity_id}, new_value_length={len(str(new_value)) if new_value else 0}")
        
        # For Window device sensors, if value is None, sensor is unavailable
        if self._device_type == DEVICE_TYPE_CALCULATOR and new_value is None:
            self._attr_available = False
        else:
            self._attr_available = True
            
            # For prices sensors - just update the state (count), attributes come from sensor_attributes
            if self._entity_id in [ENTITY_PRICES_TODAY, ENTITY_PRICES_TOMORROW]:
                self._attr_native_value = new_value
                if new_value:
                    LOGGER.debug(f"Updated {self.entity_id} with {new_value} records")
            
            # For HTML table sensors - just update the state (count), attributes come from sensor_attributes
            elif self._entity_id in [ENTITY_HTML_TABLE_TODAY, ENTITY_HTML_TABLE_TOMORROW]:
                self._attr_native_value = new_value
                if new_value:
                    LOGGER.debug(f"Updated {self.entity_id} with {new_value} records")
            
            # For window sensors - store in _window_data
            elif self._entity_id in [ENTITY_LOWEST_PRICE_WINDOW, ENTITY_LOWEST_PRICE_WINDOW_TODAY, ENTITY_LOWEST_PRICE_WINDOW_TOMORROW,
                                      ENTITY_HIGHEST_PRICE_WINDOW, ENTITY_HIGHEST_PRICE_WINDOW_TODAY, ENTITY_HIGHEST_PRICE_WINDOW_TOMORROW]:
                self._window_data = new_value
                if new_value:
                    try:
                        import json
                        data = json.loads(new_value)
                        if data.get('found'):
                            LOGGER.debug(f"Updated {self.entity_id} with window data: {data.get('start_time_local')} - {data.get('end_time_local')}, avg: {data.get('avg_price')}")
                        else:
                            LOGGER.debug(f"Updated {self.entity_id}: window not found")
                    except Exception as e:
                        LOGGER.error(f"Error parsing window JSON for {self.entity_id}: {e}")
                        self._window_data = None
                else:
                    self._window_data = None
            
            # For ENTITY_LAST_UPDATE - parse ISO string to datetime
            elif self._entity_id == ENTITY_LAST_UPDATE:
                if new_value:
                    try:
                        from datetime import datetime
                        self._attr_native_value = datetime.fromisoformat(new_value)
                        LOGGER.debug(f"Updated {self.entity_id} with timestamp: {self._attr_native_value}")
                    except Exception as e:
                        LOGGER.error(f"Error parsing timestamp for {self.entity_id}: {e}")
                        self._attr_native_value = None
                else:
                    self._attr_native_value = None
            
            # For all other sensors - normal update
            else:
                self._attr_native_value = new_value
        
        # Force state update
        self.async_write_ha_state()
        
        LOGGER.debug(f"Updated {self.entity_id} complete")

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        # For prices_today and prices_tomorrow - return attributes from sensor_attributes (managed by okte.py)
        if self._entity_id in [ENTITY_PRICES_TODAY, ENTITY_PRICES_TOMORROW]:
            return self._instance.sensor_attributes.get(self._entity_id, {})
        
        # For HTML tables - return attributes from sensor_attributes (managed by okte.py)
        elif self._entity_id in [ENTITY_HTML_TABLE_TODAY, ENTITY_HTML_TABLE_TOMORROW]:
            return self._instance.sensor_attributes.get(self._entity_id, {})
        
        # For current price, min/max price sensors - return attributes from sensor_attributes (managed by okte.py)
        elif self._entity_id in [ENTITY_CURRENT_PRICE, ENTITY_MIN_PRICE_TODAY, ENTITY_MAX_PRICE_TODAY,
                                  ENTITY_MIN_PRICE_TOMORROW, ENTITY_MAX_PRICE_TOMORROW]:
            return self._instance.sensor_attributes.get(self._entity_id, {})
        
        # For connection status and last update - return attributes from sensor_attributes (managed by okte.py)
        elif self._entity_id in [ENTITY_CONNECTION_STATUS, ENTITY_LAST_UPDATE]:
            return self._instance.sensor_attributes.get(self._entity_id, {})
        
        # For window sensors - return all window data in attributes
        elif self._entity_id in [ENTITY_LOWEST_PRICE_WINDOW, ENTITY_LOWEST_PRICE_WINDOW_TODAY, ENTITY_LOWEST_PRICE_WINDOW_TOMORROW,
                                  ENTITY_HIGHEST_PRICE_WINDOW, ENTITY_HIGHEST_PRICE_WINDOW_TODAY, ENTITY_HIGHEST_PRICE_WINDOW_TOMORROW]:
            if hasattr(self, '_window_data') and self._window_data:
                try:
                    import json
                    data = json.loads(self._window_data)
                    
                    # Determine if this is lowest or highest window
                    is_lowest = 'lowest' in self._entity_id
                    
                    # Calculate window size and search window size
                    if is_lowest:
                        # Window size from number entity
                        if hasattr(self._instance, 'number_values'):
                            periods = self._instance.number_values.get(ENTITY_LOWEST_WINDOW_SIZE, 3)
                            total_minutes = periods * 15
                            hours = total_minutes // 60
                            minutes = total_minutes % 60
                            window_size_value = f"{hours}:{minutes:02d}"
                        else:
                            window_size_value = "0:00"
                        
                        # Search window size from time entities
                        if hasattr(self._instance, 'time_values'):
                            from datetime import datetime
                            time_from = self._instance.time_values.get(ENTITY_LOWEST_TIME_FROM)
                            time_to = self._instance.time_values.get(ENTITY_LOWEST_TIME_TO)
                            
                            if time_from and time_to:
                                dt_from = datetime.combine(datetime.today(), time_from)
                                dt_to = datetime.combine(datetime.today(), time_to)
                                diff = abs(dt_to - dt_from)
                                total_minutes = int(diff.total_seconds() / 60)
                                hours = total_minutes // 60
                                minutes = total_minutes % 60
                                search_window_size_value = f"{hours}:{minutes:02d}"
                            else:
                                search_window_size_value = "0:00"
                        else:
                            search_window_size_value = "0:00"
                    else:
                        # Window size from number entity
                        if hasattr(self._instance, 'number_values'):
                            periods = self._instance.number_values.get(ENTITY_HIGHEST_WINDOW_SIZE, 3)
                            total_minutes = periods * 15
                            hours = total_minutes // 60
                            minutes = total_minutes % 60
                            window_size_value = f"{hours}:{minutes:02d}"
                        else:
                            window_size_value = "0:00"
                        
                        # Search window size from time entities
                        if hasattr(self._instance, 'time_values'):
                            from datetime import datetime
                            time_from = self._instance.time_values.get(ENTITY_HIGHEST_TIME_FROM)
                            time_to = self._instance.time_values.get(ENTITY_HIGHEST_TIME_TO)
                            
                            if time_from and time_to:
                                dt_from = datetime.combine(datetime.today(), time_from)
                                dt_to = datetime.combine(datetime.today(), time_to)
                                diff = abs(dt_to - dt_from)
                                total_minutes = int(diff.total_seconds() / 60)
                                hours = total_minutes // 60
                                minutes = total_minutes % 60
                                search_window_size_value = f"{hours}:{minutes:02d}"
                            else:
                                search_window_size_value = "0:00"
                        else:
                            search_window_size_value = "0:00"
                    
                    if data.get('found'):
                        return {
                            "found": True,
                            "start_time_UTC": data.get('start_time_UTC'),
                            "end_time_UTC": data.get('end_time_UTC'),
                            "start_time_local": data.get('start_time_local'),
                            "end_time_local": data.get('end_time_local'),
                            "periods": data.get('periods'),
                            "window_size": window_size_value,
                            "window_search_size": search_window_size_value,
                            "min_price": data.get('min_price'),
                            "max_price": data.get('max_price'),
                            "avg_price": data.get('avg_price'),
                            "records": data.get('records', [])
                        }
                    else:
                        # Window not found - return structure with null values
                        return {
                            "found": False,
                            "message": data.get('message', 'Window not found'),
                            "periods": data.get('periods'),
                            "window_size": window_size_value,
                            "window_search_size": search_window_size_value,
                            "min_price": None,
                            "max_price": None,
                            "avg_price": None,
                            "records": []
                        }
                except:
                    return {}
            # No data available - return structure with null values
            return {
                "found": False,
                "message": "No data available",
                "periods": None,
                "min_price": None,
                "max_price": None,
                "avg_price": None,
                "records": []
            }
        
        # For duration sensors - add start/end times and periods
        elif self._entity_id in [ENTITY_LOWEST_WINDOW_SIZE_TIME, ENTITY_HIGHEST_WINDOW_SIZE_TIME]:
            attrs = {}
            
            # Determine if this is lowest or highest
            is_lowest = self._entity_id == ENTITY_LOWEST_WINDOW_SIZE_TIME
            
            if hasattr(self._instance, 'number_values') and hasattr(self._instance, 'time_values'):
                from datetime import datetime, time as dt_time
                import zoneinfo
                
                # Get periods from number entity
                if is_lowest:
                    periods = self._instance.number_values.get(ENTITY_LOWEST_WINDOW_SIZE, 3)
                    time_from = self._instance.time_values.get(ENTITY_LOWEST_TIME_FROM)
                    time_to = self._instance.time_values.get(ENTITY_LOWEST_TIME_TO)
                else:
                    periods = self._instance.number_values.get(ENTITY_HIGHEST_WINDOW_SIZE, 3)
                    time_from = self._instance.time_values.get(ENTITY_HIGHEST_TIME_FROM)
                    time_to = self._instance.time_values.get(ENTITY_HIGHEST_TIME_TO)
                
                attrs["periods"] = periods
                
                # Convert local times to UTC
                if time_from and time_to:
                    try:
                        # Get timezone
                        ha_timezone = self.hass.config.time_zone
                        tz_local = zoneinfo.ZoneInfo(ha_timezone)
                        tz_utc = zoneinfo.ZoneInfo('UTC')
                        
                        # Create datetime objects for today with local timezone
                        today = datetime.now(tz_local).date()
                        dt_from_local = datetime.combine(today, time_from, tzinfo=tz_local)
                        dt_to_local = datetime.combine(today, time_to, tzinfo=tz_local)
                        
                        # Convert to UTC
                        dt_from_utc = dt_from_local.astimezone(tz_utc)
                        dt_to_utc = dt_to_local.astimezone(tz_utc)
                        
                        # Format times
                        attrs["start_time_local"] = dt_from_local.strftime("%H:%M")
                        attrs["end_time_local"] = dt_to_local.strftime("%H:%M")
                        attrs["start_time_UTC"] = f"UTC: {dt_from_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                        attrs["end_time_UTC"] = f"UTC: {dt_to_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                    except Exception as e:
                        LOGGER.error(f"Error converting times to UTC: {e}")
                        attrs["start_time_local"] = None
                        attrs["end_time_local"] = None
                        attrs["start_time_UTC"] = None
                        attrs["end_time_UTC"] = None
                else:
                    attrs["start_time_local"] = None
                    attrs["end_time_local"] = None
                    attrs["start_time_UTC"] = None
                    attrs["end_time_UTC"] = None
            
            return attrs
        
        # For search window size sensors - add start/end times
        elif self._entity_id in [ENTITY_LOWEST_SEARCH_WINDOW_SIZE, ENTITY_HIGHEST_SEARCH_WINDOW_SIZE]:
            attrs = {}
            
            # Determine if this is lowest or highest
            is_lowest = self._entity_id == ENTITY_LOWEST_SEARCH_WINDOW_SIZE
            
            if hasattr(self._instance, 'time_values'):
                from datetime import datetime
                import zoneinfo
                
                # Get times from time entities
                if is_lowest:
                    time_from = self._instance.time_values.get(ENTITY_LOWEST_TIME_FROM)
                    time_to = self._instance.time_values.get(ENTITY_LOWEST_TIME_TO)
                else:
                    time_from = self._instance.time_values.get(ENTITY_HIGHEST_TIME_FROM)
                    time_to = self._instance.time_values.get(ENTITY_HIGHEST_TIME_TO)
                
                # Convert local times to UTC
                if time_from and time_to:
                    try:
                        # Get timezone
                        ha_timezone = self.hass.config.time_zone
                        tz_local = zoneinfo.ZoneInfo(ha_timezone)
                        tz_utc = zoneinfo.ZoneInfo('UTC')
                        
                        # Create datetime objects for today with local timezone
                        today = datetime.now(tz_local).date()
                        dt_from_local = datetime.combine(today, time_from, tzinfo=tz_local)
                        dt_to_local = datetime.combine(today, time_to, tzinfo=tz_local)
                        
                        # Convert to UTC
                        dt_from_utc = dt_from_local.astimezone(tz_utc)
                        dt_to_utc = dt_to_local.astimezone(tz_utc)
                        
                        # Format times
                        attrs["start_time_local"] = dt_from_local.strftime("%H:%M")
                        attrs["end_time_local"] = dt_to_local.strftime("%H:%M")
                        attrs["start_time_UTC"] = f"UTC: {dt_from_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                        attrs["end_time_UTC"] = f"UTC: {dt_to_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                    except Exception as e:
                        LOGGER.error(f"Error converting times to UTC: {e}")
                        attrs["start_time_local"] = None
                        attrs["end_time_local"] = None
                        attrs["start_time_UTC"] = None
                        attrs["end_time_UTC"] = None
                else:
                    attrs["start_time_local"] = None
                    attrs["end_time_local"] = None
                    attrs["start_time_UTC"] = None
                    attrs["end_time_UTC"] = None
            
            return attrs
        
        # For other sensors with configured attributes - return from config
        elif self._attributes_config:
            return self._attributes_config
        
        # For other sensors - no extra attributes
        return {}
    
    @property
    def native_value(self) -> str | int | float | None:
        """Return the state of the sensor."""
        # For prices sensors - return count as state (set by okte.py)
        if self._entity_id in [ENTITY_PRICES_TODAY, ENTITY_PRICES_TOMORROW]:
            return self._attr_native_value
        
        # For HTML table sensors - return state directly (count set by okte.py)
        elif self._entity_id in [ENTITY_HTML_TABLE_TODAY, ENTITY_HTML_TABLE_TOMORROW]:
            return self._attr_native_value
        
        # For window sensors - return STATE_ON/STATE_OFF based on whether window was found
        elif self._entity_id in [ENTITY_LOWEST_PRICE_WINDOW, ENTITY_LOWEST_PRICE_WINDOW_TODAY, ENTITY_LOWEST_PRICE_WINDOW_TOMORROW,
                                  ENTITY_HIGHEST_PRICE_WINDOW, ENTITY_HIGHEST_PRICE_WINDOW_TODAY, ENTITY_HIGHEST_PRICE_WINDOW_TOMORROW]:
            if hasattr(self, '_window_data') and self._window_data:
                try:
                    import json
                    data = json.loads(self._window_data)
                    if data.get('found'):
                        return STATE_ON
                    return STATE_OFF
                except:
                    return STATE_OFF
            return STATE_OFF
        
        # Duration sensors - window size in H:MM format (periods * 15 minutes)
        elif self._entity_id == ENTITY_LOWEST_WINDOW_SIZE_TIME:
            if hasattr(self._instance, 'number_values'):
                periods = self._instance.number_values.get(ENTITY_LOWEST_WINDOW_SIZE, 3)
                total_minutes = periods * 15
                hours = total_minutes // 60
                minutes = total_minutes % 60
                return f"{hours}:{minutes:02d}"
            return "0:00"
        
        elif self._entity_id == ENTITY_HIGHEST_WINDOW_SIZE_TIME:
            if hasattr(self._instance, 'number_values'):
                periods = self._instance.number_values.get(ENTITY_HIGHEST_WINDOW_SIZE, 3)
                total_minutes = periods * 15
                hours = total_minutes // 60
                minutes = total_minutes % 60
                return f"{hours}:{minutes:02d}"
            return "0:00"
        
        # Search window size - time difference between from and to
        elif self._entity_id == ENTITY_LOWEST_SEARCH_WINDOW_SIZE:
            if hasattr(self._instance, 'time_values'):
                from datetime import datetime, timedelta
                time_from = self._instance.time_values.get(ENTITY_LOWEST_TIME_FROM)
                time_to = self._instance.time_values.get(ENTITY_LOWEST_TIME_TO)
                
                if time_from and time_to:
                    # Convert times to datetime for calculation
                    dt_from = datetime.combine(datetime.today(), time_from)
                    dt_to = datetime.combine(datetime.today(), time_to)
                    
                    # Calculate difference (absolute value)
                    diff = abs(dt_to - dt_from)
                    total_minutes = int(diff.total_seconds() / 60)
                    hours = total_minutes // 60
                    minutes = total_minutes % 60
                    return f"{hours}:{minutes:02d}"
            return "0:00"
        
        elif self._entity_id == ENTITY_HIGHEST_SEARCH_WINDOW_SIZE:
            if hasattr(self._instance, 'time_values'):
                from datetime import datetime, timedelta
                time_from = self._instance.time_values.get(ENTITY_HIGHEST_TIME_FROM)
                time_to = self._instance.time_values.get(ENTITY_HIGHEST_TIME_TO)
                
                if time_from and time_to:
                    # Convert times to datetime for calculation
                    dt_from = datetime.combine(datetime.today(), time_from)
                    dt_to = datetime.combine(datetime.today(), time_to)
                    
                    # Calculate difference (absolute value)
                    diff = abs(dt_to - dt_from)
                    total_minutes = int(diff.total_seconds() / 60)
                    hours = total_minutes // 60
                    minutes = total_minutes % 60
                    return f"{hours}:{minutes:02d}"
            return "0:00"
        
        # For all other sensors - return actual value
        return self._attr_native_value
