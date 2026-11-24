from __future__ import annotations
"""The OKTE Integration"""
"""Author: Jozef Moravcik"""
"""email: jozef.moravcik@moravcik.eu"""

""" button.py """

""" Button platform for OKTE integration."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEVICE_TYPE_MASTER,
    DOCUMENTATION_URL,
    DOMAIN,
    ENTITY_PREFIX,
    MANUFACTURER,
    MODEL_MASTER,
    SIGNAL_FEEDBACK_UPDATE,
    SIGNAL_NAME_UPDATE,
    VERSION,
    async_load_translations,
)

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities (Master device only)."""
    if entry.runtime_data.device_type != DEVICE_TYPE_MASTER:
        return
    instance = entry.runtime_data.instance
    translations = await async_load_translations(hass)
    async_add_entities([
        UpdateDataButton(hass, instance, entry.entry_id, translations),
        ResetFailoverHistoryButton(hass, instance, entry.entry_id, translations),
    ])


class OkteButton(ButtonEntity):
    """Base class of the OKTE Master buttons."""

    _key = ""
    _default_name = ""
    _icon = "mdi:gesture-tap-button"

    def __init__(self, hass: HomeAssistant, instance, entry_id: str, translations: dict | None = None) -> None:
        """Initialize the button."""
        self.hass = hass
        self._instance = instance
        self._entry_id = entry_id

        self.entity_id = f"button.{ENTITY_PREFIX}_{self._key}"
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{self._key}"
        self._attr_has_entity_name = False
        self._attr_translation_key = self._key
        self._attr_icon = self._icon
        self._attr_entity_category = EntityCategory.CONFIG

        translated = (translations or {}).get("entity", {}).get("button", {}).get(self._key, {}).get("name")
        self._translated_name = translated or self._default_name
        self._attr_name = (
            f"OKTE - {self._translated_name}" if instance.settings.include_device_name_in_entity else self._translated_name
        )

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

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_NAME_UPDATE.format(self._entry_id), self.async_write_ha_state)
        )

    def _notify_entities(self) -> None:
        """Refresh all entities of the Master device."""
        async_dispatcher_send(self.hass, SIGNAL_FEEDBACK_UPDATE.format(self._entry_id))


class UpdateDataButton(OkteButton):
    """Button to manually update data from API."""

    _key = "update_data"
    _default_name = "Update Data"
    _icon = "mdi:refresh"

    async def async_press(self) -> None:
        """Handle button press - fetch data from API."""
        LOGGER.debug("Manual data update requested via button")
        try:
            await self._instance.fetch_and_process_data()
            self._notify_entities()
        except Exception as e:
            LOGGER.error("Error during manual data update: %s", e, exc_info=True)


class ResetFailoverHistoryButton(OkteButton):
    """Button to reset the failover price history and rebuild it from statistics of the current price sensor."""

    _key = "reset_failover_history"
    _default_name = "Reset Failover History"
    _icon = "mdi:database-refresh"

    async def async_press(self) -> None:
        """Handle button press - reset failover history and rebuild it from statistics."""
        LOGGER.info("Failover history reset requested via button")
        try:
            rebuilt = await self._instance.async_reset_failover_history()
            self._notify_entities()
            if not rebuilt:
                LOGGER.warning("Failover history reset finished without data from statistics")
        except Exception as e:
            LOGGER.error("Error during failover history reset: %s", e, exc_info=True)
