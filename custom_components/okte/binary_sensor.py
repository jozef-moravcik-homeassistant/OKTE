from __future__ import annotations
"""The OKTE Integration"""
"""Author: Jozef Moravcik"""
"""email: jozef.moravcik@moravcik.eu"""

""" binary_sensor.py """

""" Binary Sensor platform for OKTE Integration."""

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DEVICE_TYPE_CALCULATOR,
    DEVICE_TYPE_MASTER,
    DOCUMENTATION_URL,
    DOMAIN,
    ENTITY_DETECTOR_HIGHEST_PRICE,
    ENTITY_DETECTOR_HIGHEST_PRICE_TODAY,
    ENTITY_DETECTOR_LOWEST_PRICE,
    ENTITY_DETECTOR_LOWEST_PRICE_TODAY,
    ENTITY_PREFIX,
    MANUFACTURER,
    MODEL_CALCULATOR,
    MODEL_MASTER,
    SIGNAL_FEEDBACK_UPDATE,
    VERSION,
    async_load_translations,
    entity_name,
    get_calculator_number_from_name,
)

LOGGER = logging.getLogger(__name__)

# (key, fallback name, icon)
CALCULATOR_BINARY_SENSORS = (
    (ENTITY_DETECTOR_LOWEST_PRICE, "Detector Lowest Price", "mdi:clock-check"),
    (ENTITY_DETECTOR_LOWEST_PRICE_TODAY, "Detector Lowest Price Today", "mdi:clock-check"),
    (ENTITY_DETECTOR_HIGHEST_PRICE, "Detector Highest Price", "mdi:clock-alert"),
    (ENTITY_DETECTOR_HIGHEST_PRICE_TODAY, "Detector Highest Price Today", "mdi:clock-alert"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensor entities (Calculator devices only)."""
    device_type = entry.runtime_data.device_type
    if device_type != DEVICE_TYPE_CALCULATOR:
        return

    instance = entry.runtime_data.instance
    translations = await async_load_translations(hass)
    async_add_entities(
        BinarySensorEntityDefinition(
            hass, instance, entry_id=entry.entry_id, device_type=device_type,
            entity_id=key, name=name, translations=translations, icon=icon,
        )
        for key, name, icon in CALCULATOR_BINARY_SENSORS
    )


class BinarySensorEntityDefinition(BinarySensorEntity):
    """OKTE detector - ON while the current time is inside the found price window."""

    # Home Assistant puts the device name in front of the entity name: "<device> <name>"
    _attr_has_entity_name = True

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
    ) -> None:
        """Initialize the binary sensor."""
        self.hass = hass
        self._instance = instance
        self._entry_id = entry_id
        self._device_type = device_type
        self._entity_id = entity_id

        if device_type == DEVICE_TYPE_MASTER:
            self.entity_id = f"binary_sensor.{ENTITY_PREFIX}_{entity_id}"
        else:
            calculator_number = get_calculator_number_from_name(instance.settings.device_name)
            self.entity_id = f"binary_sensor.{ENTITY_PREFIX}_{calculator_number}_{entity_id}"
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{entity_id}"

        translated = (translations or {}).get("entity", {}).get("binary_sensor", {}).get(entity_id, {}).get("name")
        self._attr_name = entity_name(translated or name)

        self._attr_icon = icon
        self._attr_is_on = False
        self._attr_available = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._instance.settings.device_name,
            manufacturer=MANUFACTURER,
            model=MODEL_MASTER if self._device_type == DEVICE_TYPE_MASTER else MODEL_CALCULATOR,
            sw_version=VERSION,
            configuration_url=DOCUMENTATION_URL,
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_FEEDBACK_UPDATE.format(self._entry_id), self._handle_feedback_update)
        )

    @callback
    def _handle_feedback_update(self) -> None:
        """Handle feedback update."""
        new_value = self._instance.sensor_states.get(self._entity_id)
        if hasattr(self._instance, 'is_master_available') and not self._instance.is_master_available():
            self._attr_available = False
        else:
            self._attr_available = True
            if new_value is not None:
                self._attr_is_on = new_value
        self.async_write_ha_state()
