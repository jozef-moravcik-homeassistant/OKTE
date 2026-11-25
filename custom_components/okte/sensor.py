from __future__ import annotations
"""The OKTE Integration"""
"""Author: Jozef Moravcik"""
"""email: jozef.moravcik@moravcik.eu"""

""" sensor.py """

""" Sensor platform for OKTE Integration."""

import json
import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    DEVICE_TYPE_CALCULATOR,
    DEVICE_TYPE_MASTER,
    DOCUMENTATION_URL,
    DOMAIN,
    ENTITY_AVERAGE_PRICE_TODAY,
    ENTITY_AVERAGE_PRICE_TOMORROW,
    ENTITY_CONNECTION_STATUS,
    ENTITY_CURRENT_PRICE,
    ENTITY_DATA_COUNT,
    ENTITY_ERROR_CODE,
    ENTITY_FAILOVER_DATA,
    ENTITY_HIGHEST_PRICE_WINDOW,
    ENTITY_HIGHEST_PRICE_WINDOW_TODAY,
    ENTITY_HIGHEST_PRICE_WINDOW_TOMORROW,
    ENTITY_HIGHEST_SEARCH_WINDOW_SIZE,
    ENTITY_HIGHEST_TIME_FROM,
    ENTITY_HIGHEST_TIME_TO,
    ENTITY_HIGHEST_WINDOW_SIZE,
    ENTITY_HIGHEST_WINDOW_SIZE_TIME,
    ENTITY_HTML_TABLE_TODAY,
    ENTITY_HTML_TABLE_TOMORROW,
    ENTITY_LAST_UPDATE,
    ENTITY_LOWEST_PRICE_WINDOW,
    ENTITY_LOWEST_PRICE_WINDOW_TODAY,
    ENTITY_LOWEST_PRICE_WINDOW_TOMORROW,
    ENTITY_LOWEST_SEARCH_WINDOW_SIZE,
    ENTITY_LOWEST_TIME_FROM,
    ENTITY_LOWEST_TIME_TO,
    ENTITY_LOWEST_WINDOW_SIZE,
    ENTITY_LOWEST_WINDOW_SIZE_TIME,
    ENTITY_MAX_PRICE_TODAY,
    ENTITY_MAX_PRICE_TOMORROW,
    ENTITY_MIN_PRICE_TODAY,
    ENTITY_MIN_PRICE_TOMORROW,
    ENTITY_PREFIX,
    ENTITY_PRICES_TODAY,
    ENTITY_PRICES_TOMORROW,
    MANUFACTURER,
    MARKET_TIMEZONE,
    MODEL_CALCULATOR,
    MODEL_MASTER,
    PRICE_UNIT_EUR_KWH,
    PRICE_UNIT_EUR_MWH,
    PRICE_UNIT_LABELS,
    SIGNAL_FEEDBACK_UPDATE,
    STATE_FALSE,
    STATE_WINDOW_FOUND,
    STATE_WINDOW_NOT_FOUND,
    VERSION,
    async_load_translations,
    entity_name,
    get_calculator_number_from_name,
)

LOGGER = logging.getLogger(__name__)

# Sensors whose value is a price (EUR/MWh from OKTE, optionally converted to EUR/kWh)
PRICE_VALUE_SENSORS = {
    ENTITY_CURRENT_PRICE,
    ENTITY_AVERAGE_PRICE_TODAY,
    ENTITY_MIN_PRICE_TODAY,
    ENTITY_MAX_PRICE_TODAY,
    ENTITY_AVERAGE_PRICE_TOMORROW,
    ENTITY_MIN_PRICE_TOMORROW,
    ENTITY_MAX_PRICE_TOMORROW,
}

# Sensors with very large attributes (price lists, HTML tables, failover profiles)
LARGE_ATTRIBUTE_SENSORS = {
    ENTITY_PRICES_TODAY,
    ENTITY_PRICES_TOMORROW,
    ENTITY_HTML_TABLE_TODAY,
    ENTITY_HTML_TABLE_TOMORROW,
    ENTITY_FAILOVER_DATA,
}

# Sensors whose attributes are managed by okte.py (sensor_attributes)
INSTANCE_ATTRIBUTE_SENSORS = {
    ENTITY_PRICES_TODAY, ENTITY_PRICES_TOMORROW,
    ENTITY_HTML_TABLE_TODAY, ENTITY_HTML_TABLE_TOMORROW,
    ENTITY_CURRENT_PRICE, ENTITY_MIN_PRICE_TODAY, ENTITY_MAX_PRICE_TODAY,
    ENTITY_MIN_PRICE_TOMORROW, ENTITY_MAX_PRICE_TOMORROW,
    ENTITY_CONNECTION_STATUS, ENTITY_LAST_UPDATE, ENTITY_FAILOVER_DATA,
}

WINDOW_SENSORS = {
    ENTITY_LOWEST_PRICE_WINDOW, ENTITY_LOWEST_PRICE_WINDOW_TODAY, ENTITY_LOWEST_PRICE_WINDOW_TOMORROW,
    ENTITY_HIGHEST_PRICE_WINDOW, ENTITY_HIGHEST_PRICE_WINDOW_TODAY, ENTITY_HIGHEST_PRICE_WINDOW_TOMORROW,
}
CROSS_DAY_WINDOW_SENSORS = {ENTITY_LOWEST_PRICE_WINDOW, ENTITY_HIGHEST_PRICE_WINDOW}

# Duration sensors computed from the calculator settings: entity -> (number key, time from key, time to key)
WINDOW_SIZE_SENSORS = {
    ENTITY_LOWEST_WINDOW_SIZE_TIME: ENTITY_LOWEST_WINDOW_SIZE,
    ENTITY_HIGHEST_WINDOW_SIZE_TIME: ENTITY_HIGHEST_WINDOW_SIZE,
}
SEARCH_WINDOW_SIZE_SENSORS = {
    ENTITY_LOWEST_SEARCH_WINDOW_SIZE: (ENTITY_LOWEST_TIME_FROM, ENTITY_LOWEST_TIME_TO),
    ENTITY_HIGHEST_SEARCH_WINDOW_SIZE: (ENTITY_HIGHEST_TIME_FROM, ENTITY_HIGHEST_TIME_TO),
}
DURATION_SENSORS = set(WINDOW_SIZE_SENSORS) | set(SEARCH_WINDOW_SIZE_SENSORS)

# (key, fallback name, icon, extra parameters)
MASTER_SENSORS = (
    (ENTITY_CONNECTION_STATUS, "Connection Status", "mdi:connection", {'default_value': False, 'entity_category': EntityCategory.DIAGNOSTIC}),
    (ENTITY_LAST_UPDATE, "Last Update", "mdi:clock-outline", {'device_class': SensorDeviceClass.TIMESTAMP, 'entity_category': EntityCategory.DIAGNOSTIC}),
    (ENTITY_DATA_COUNT, "Data Count", "mdi:counter", {'default_value': 0, 'entity_category': EntityCategory.DIAGNOSTIC}),
    (ENTITY_ERROR_CODE, "Error Code", "mdi:alert-circle", {'default_value': 0, 'entity_category': EntityCategory.DIAGNOSTIC}),
    (ENTITY_FAILOVER_DATA, "Failover Data", "mdi:database-clock", {'default_value': STATE_FALSE}),
    (ENTITY_CURRENT_PRICE, "Current Price", "mdi:currency-eur", {}),
    (ENTITY_AVERAGE_PRICE_TODAY, "Average Price Today", "mdi:chart-line", {}),
    (ENTITY_MIN_PRICE_TODAY, "Min Price Today", "mdi:arrow-down-bold", {}),
    (ENTITY_MAX_PRICE_TODAY, "Max Price Today", "mdi:arrow-up-bold", {}),
    (ENTITY_AVERAGE_PRICE_TOMORROW, "Average Price Tomorrow", "mdi:chart-line", {}),
    (ENTITY_MIN_PRICE_TOMORROW, "Min Price Tomorrow", "mdi:arrow-down-bold", {}),
    (ENTITY_MAX_PRICE_TOMORROW, "Max Price Tomorrow", "mdi:arrow-up-bold", {}),
    (ENTITY_PRICES_TODAY, "Prices Today", "mdi:table-clock", {}),
    (ENTITY_PRICES_TOMORROW, "Prices Tomorrow", "mdi:table-clock", {}),
    (ENTITY_HTML_TABLE_TODAY, "HTML Table Today", "mdi:table", {'default_value': ""}),
    (ENTITY_HTML_TABLE_TOMORROW, "HTML Table Tomorrow", "mdi:table", {'default_value': ""}),
)

CALCULATOR_SENSORS = (
    (ENTITY_LOWEST_PRICE_WINDOW, "Lowest Price Window", "mdi:arrow-down-bold-box", {}),
    (ENTITY_LOWEST_PRICE_WINDOW_TODAY, "Lowest Price Window Today", "mdi:arrow-down-bold-box", {}),
    (ENTITY_LOWEST_PRICE_WINDOW_TOMORROW, "Lowest Price Window Tomorrow", "mdi:arrow-down-bold-box", {}),
    (ENTITY_HIGHEST_PRICE_WINDOW, "Highest Price Window", "mdi:arrow-up-bold-box", {}),
    (ENTITY_HIGHEST_PRICE_WINDOW_TODAY, "Highest Price Window Today", "mdi:arrow-up-bold-box", {}),
    (ENTITY_HIGHEST_PRICE_WINDOW_TOMORROW, "Highest Price Window Tomorrow", "mdi:arrow-up-bold-box", {}),
    (ENTITY_LOWEST_WINDOW_SIZE_TIME, "Lowest Price Window Size", "mdi:timer", {'default_value': "0:00"}),
    (ENTITY_HIGHEST_WINDOW_SIZE_TIME, "Highest Price Window Size", "mdi:timer", {'default_value': "0:00"}),
    (ENTITY_LOWEST_SEARCH_WINDOW_SIZE, "Lowest Price Search Window Size", "mdi:magnify-expand", {'default_value': "0:00"}),
    (ENTITY_HIGHEST_SEARCH_WINDOW_SIZE, "Highest Price Search Window Size", "mdi:magnify-expand", {'default_value': "0:00"}),
)


def _format_minutes(total_minutes):
    """Format minutes as H:MM."""
    return f"{total_minutes // 60}:{total_minutes % 60:02d}"


def _window_size_value(instance, number_key, periods=None):
    """Window size (periods * 15 min) in H:MM format."""
    if not hasattr(instance, 'number_values'):
        return "0:00"
    periods = periods or instance.number_values.get(number_key, 3)
    return _format_minutes(int(periods) * 15)


def _search_window_minutes(time_from, time_to, cross_day=False):
    """Length of the search range in minutes (cross-day: from time_from today to time_to tomorrow)."""
    if cross_day:
        from_min = time_from.hour * 60 + time_from.minute
        to_min = 1440 if (time_to.hour == 23 and time_to.minute == 59) else time_to.hour * 60 + time_to.minute
        return (1440 - from_min) + to_min
    return abs((time_to.hour * 60 + time_to.minute) - (time_from.hour * 60 + time_from.minute))


def _search_window_value(instance, time_keys, cross_day=False):
    """Search range size in H:MM format."""
    if not hasattr(instance, 'time_values'):
        return "0:00"
    time_from = instance.time_values.get(time_keys[0])
    time_to = instance.time_values.get(time_keys[1])
    if not (time_from and time_to):
        return "0:00"
    return _format_minutes(_search_window_minutes(time_from, time_to, cross_day))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    instance = entry.runtime_data.instance
    device_type = entry.runtime_data.device_type
    translations = await async_load_translations(hass)

    definitions = MASTER_SENSORS if device_type == DEVICE_TYPE_MASTER else CALCULATOR_SENSORS
    entities = []
    for key, name, icon, extra in definitions:
        sensor_class = LargeAttributesSensor if key in LARGE_ATTRIBUTE_SENSORS else SensorEntityDefinition
        entities.append(sensor_class(
            hass, instance, entry_id=entry.entry_id, device_type=device_type,
            entity_id=key, name=name, translations=translations, icon=icon, **extra,
        ))
    async_add_entities(entities)


class SensorEntityDefinition(SensorEntity):
    """OKTE sensor - value and attributes come from the device instance."""

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
        default_value: Any = None,
        device_class: SensorDeviceClass | None = None,
        entity_category: EntityCategory | None = None,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._instance = instance
        self._entry_id = entry_id
        self._device_type = device_type
        self._entity_id = entity_id

        if device_type == DEVICE_TYPE_MASTER:
            self.entity_id = f"sensor.{ENTITY_PREFIX}_{entity_id}"
        else:
            calculator_number = get_calculator_number_from_name(instance.settings.device_name)
            self.entity_id = f"sensor.{ENTITY_PREFIX}_{calculator_number}_{entity_id}"
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{entity_id}"

        translated = (translations or {}).get("entity", {}).get("sensor", {}).get(entity_id, {}).get("name")
        self._attr_name = entity_name(translated or name)

        self._attr_icon = icon
        self._attr_native_value = default_value
        self._attr_available = True
        self._window_data = None

        if device_class is not None:
            self._attr_device_class = device_class
        if entity_category is not None:
            self._attr_entity_category = entity_category

        # Price sensors - unit selected in the Master settings
        self._price_factor = 1
        if entity_id in PRICE_VALUE_SENSORS:
            unit = getattr(instance.settings, 'price_unit', PRICE_UNIT_EUR_MWH)
            self._attr_native_unit_of_measurement = PRICE_UNIT_LABELS.get(unit, PRICE_UNIT_LABELS[PRICE_UNIT_EUR_MWH])
            self._attr_state_class = SensorStateClass.MEASUREMENT
            if unit == PRICE_UNIT_EUR_KWH:
                self._price_factor = 0.001
                self._attr_suggested_display_precision = 4
            else:
                self._attr_suggested_display_precision = 2

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

    def _set_value(self, value) -> None:
        """Store a value from the instance in the entity."""
        if self._entity_id in WINDOW_SENSORS:
            self._window_data = value or None
        elif self._entity_id == ENTITY_LAST_UPDATE:
            try:
                self._attr_native_value = datetime.fromisoformat(value) if value else None
            except (TypeError, ValueError):
                self._attr_native_value = None
        else:
            self._attr_native_value = value

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        if self._entity_id not in DURATION_SENSORS:
            initial_value = self._instance.sensor_states.get(self._entity_id)
            if initial_value is not None:
                self._set_value(initial_value)

        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_FEEDBACK_UPDATE.format(self._entry_id), self._handle_feedback_update)
        )

    @callback
    def _handle_feedback_update(self) -> None:
        """Handle feedback update."""
        if self._entity_id in DURATION_SENSORS:
            # Computed from number_values and time_values in native_value
            self.async_write_ha_state()
            return

        new_value = self._instance.sensor_states.get(self._entity_id)
        # Calculator sensors without a value are unavailable
        if self._device_type == DEVICE_TYPE_CALCULATOR and new_value is None:
            self._attr_available = False
        else:
            self._attr_available = True
            self._set_value(new_value)
        self.async_write_ha_state()

    def _window_attributes(self) -> dict[str, Any]:
        """Attributes of the window sensors."""
        if not self._window_data:
            return {
                "found": False,
                "message": "No data available",
                "periods": None,
                "min_price": None,
                "max_price": None,
                "avg_price": None,
                "records": [],
            }
        try:
            data = json.loads(self._window_data)
        except (TypeError, ValueError):
            return {}

        is_lowest = 'lowest' in self._entity_id
        number_key = ENTITY_LOWEST_WINDOW_SIZE if is_lowest else ENTITY_HIGHEST_WINDOW_SIZE
        time_keys = (ENTITY_LOWEST_TIME_FROM, ENTITY_LOWEST_TIME_TO) if is_lowest else (ENTITY_HIGHEST_TIME_FROM, ENTITY_HIGHEST_TIME_TO)
        window_size_value = _window_size_value(self._instance, number_key, data.get('periods'))
        search_window_size_value = _search_window_value(self._instance, time_keys, self._entity_id in CROSS_DAY_WINDOW_SENSORS)

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
                "records": data.get('records', []),
            }
        return {
            "found": False,
            "message": data.get('message', 'Window not found'),
            "periods": data.get('periods'),
            "window_size": window_size_value,
            "window_search_size": search_window_size_value,
            "min_price": None,
            "max_price": None,
            "avg_price": None,
            "records": [],
        }

    def _search_window_attributes(self) -> dict[str, Any]:
        """Start/end of the search range (market time and UTC)."""
        empty = {"start_time_local": None, "end_time_local": None, "start_time_UTC": None, "end_time_UTC": None}
        if not hasattr(self._instance, 'time_values'):
            return {}
        time_from_key, time_to_key = SEARCH_WINDOW_SIZE_SENSORS[self._entity_id]
        time_from = self._instance.time_values.get(time_from_key)
        time_to = self._instance.time_values.get(time_to_key)
        if not (time_from and time_to):
            return empty
        today = datetime.now(MARKET_TIMEZONE).date()
        dt_from = datetime.combine(today, time_from, tzinfo=MARKET_TIMEZONE)
        dt_to = datetime.combine(today, time_to, tzinfo=MARKET_TIMEZONE)
        return {
            "start_time_local": dt_from.strftime("%H:%M"),
            "end_time_local": dt_to.strftime("%H:%M"),
            "start_time_UTC": f"UTC: {dt_from.astimezone(dt_util.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
            "end_time_UTC": f"UTC: {dt_to.astimezone(dt_util.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if self._entity_id in INSTANCE_ATTRIBUTE_SENSORS:
            return self._instance.sensor_attributes.get(self._entity_id, {})
        if self._entity_id in WINDOW_SENSORS:
            return self._window_attributes()
        if self._entity_id in WINDOW_SIZE_SENSORS:
            if hasattr(self._instance, 'number_values'):
                return {"periods": self._instance.number_values.get(WINDOW_SIZE_SENSORS[self._entity_id], 3)}
            return {}
        if self._entity_id in SEARCH_WINDOW_SIZE_SENSORS:
            return self._search_window_attributes()
        return {}

    @property
    def native_value(self) -> str | int | float | datetime | None:
        """Return the state of the sensor."""
        if self._entity_id in WINDOW_SENSORS:
            if self._window_data:
                try:
                    return STATE_WINDOW_FOUND if json.loads(self._window_data).get('found') else STATE_WINDOW_NOT_FOUND
                except (TypeError, ValueError):
                    pass
            return STATE_WINDOW_NOT_FOUND
        if self._entity_id in WINDOW_SIZE_SENSORS:
            return _window_size_value(self._instance, WINDOW_SIZE_SENSORS[self._entity_id])
        if self._entity_id in SEARCH_WINDOW_SIZE_SENSORS:
            return _search_window_value(self._instance, SEARCH_WINDOW_SIZE_SENSORS[self._entity_id])
        if self._price_factor != 1 and isinstance(self._attr_native_value, (int, float)):
            return round(self._attr_native_value * self._price_factor, 5)
        return self._attr_native_value


class LargeAttributesSensor(SensorEntityDefinition):
    """Sensor with very large attributes - they are shown in the UI but not stored in the recorder database."""

    _unrecorded_attributes = frozenset({
        # prices today/tomorrow
        "period_data", "prices_list", "timestamps_list", "labels_list",
        # HTML tables
        "html_table",
        # failover profiles
        "Period data Monday", "Period data Tuesday", "Period data Wednesday", "Period data Thursday",
        "Period data Friday", "Period data Saturday", "Period data Sunday",
    })
