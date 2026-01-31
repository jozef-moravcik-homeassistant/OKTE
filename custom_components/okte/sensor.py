"""
OKTE Integration for Home Assistant
Custom integration for fetching and analyzing electricity prices from OKTE Slovakia
*** OKTE sensors for Home Assistant ***

Author: Jozef Moravcik
email: jozef.moravcik@moravcik.eu
"""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

# Import všetkých sensorov z jednotlivých súborov
from .sensors_prices_all import (
    OkteHourlyPriceSensor,
    OkteCurrentPriceSensor,
    OkteAveragePriceSensor,
    OkteMinPriceSensor,
    OkteMinPriceTimeSensor,
    OkteMaxPriceSensor,
    OkteMaxPriceTimeSensor,
)
from .sensors_prices_today import (
    OkteHourlyPriceTodaySensor,
    OkteMinPriceTodaySensor,
    OkteMinPriceTimeTodaySensor,
    OkteMaxPriceTodaySensor,
    OkteMaxPriceTimeTodaySensor,
)
from .sensors_prices_tomorrow import (
    OkteHourlyPriceTomorrowSensor,
    OkteMinPriceTomorrowSensor,
    OkteMinPriceTimeTomorrowSensor,
    OkteMaxPriceTomorrowSensor,
    OkteMaxPriceTimeTomorrowSensor,
)
from .sensors_analysis_cheapest_window import (
    OkteCheapestTimeWindowSensor,
    OkteCheapestTimeWindowTodaySensor,
    OkteCheapestTimeWindowTomorrowSensor,
)
from .sensors_analysis_most_expensive_window import (
    OkteMostExpensiveTimeWindowSensor,
    OkteMostExpensiveTimeWindowTodaySensor,
    OkteMostExpensiveTimeWindowTomorrowSensor,
)
from .sensors_detectors_all import (
    OkteCheapestTimeWindowDetectorSensor,
    OkteMostExpensiveTimeWindowDetectorSensor,
)
from .sensors_detectors_today import (
    OkteCheapestTimeWindowTodayDetectorSensor,
    OkteMostExpensiveTimeWindowTodayDetectorSensor,
)
from .sensors_detectors_tomorrow import (
    OkteCheapestTimeWindowTomorrowDetectorSensor,
    OkteMostExpensiveTimeWindowTomorrowDetectorSensor,
)
from .sensors_system import (
    OkteConnectionSensor,
    OkteDataCountSensor,
    OkteLastUpdateSensor,
)
from .sensors_html_objects import (
    OkteHtmlPriceTableSensor,
    OkteHtmlPriceTodayTableSensor,
    OkteHtmlPriceTomorrowTableSensor,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OKTE sensors from a config entry."""
    sensors = [

        # Sensory so všetkými cenami (súbor: sensors_prices_all.py)
        OkteHourlyPriceSensor(hass),
        OkteCurrentPriceSensor(hass),
        OkteAveragePriceSensor(hass),
        OkteMinPriceSensor(hass),
        OkteMinPriceTimeSensor(hass),
        OkteMaxPriceSensor(hass),
        OkteMaxPriceTimeSensor(hass),

        # Sensory s dnešnými cenami (súbor: sensors_prices_today.py)
        OkteHourlyPriceTodaySensor(hass),
        OkteMinPriceTodaySensor(hass),
        OkteMinPriceTimeTodaySensor(hass),
        OkteMaxPriceTodaySensor(hass),
        OkteMaxPriceTimeTodaySensor(hass),

        # Sensory so zajtrajšími cenami (súbor: sensors_prices_tomorrow.py)
        OkteHourlyPriceTomorrowSensor(hass),
        OkteMinPriceTomorrowSensor(hass),
        OkteMinPriceTimeTomorrowSensor(hass),
        OkteMaxPriceTomorrowSensor(hass),
        OkteMaxPriceTimeTomorrowSensor(hass),

        # Analytické sensory (súbor: sensors_analysis_cheapest_window.py)
        # Dátové senzory časových okien (napr. pre grafy)
        OkteCheapestTimeWindowSensor(hass),
        OkteCheapestTimeWindowTodaySensor(hass),
        OkteCheapestTimeWindowTomorrowSensor(hass),

        # Analytické sensory (súbor: sensors_analysis_most_expensive_window.py)
        # Dátové senzory časových okien (napr. pre grafy)
        OkteMostExpensiveTimeWindowSensor(hass),
        OkteMostExpensiveTimeWindowTodaySensor(hass),
        OkteMostExpensiveTimeWindowTomorrowSensor(hass),

        # Detektor sensory  (súbor: sensors_detectors_all.py)
        # Detektory časových okien pre všetky záznamy (napr. pre automatizácie)
        OkteCheapestTimeWindowDetectorSensor(hass),
        OkteMostExpensiveTimeWindowDetectorSensor(hass),

        # Detektor sensory  (súbor: sensors_detectors_today.py)
        # Detektory časových okien pre dnešné záznamy (napr. pre automatizácie)
        OkteCheapestTimeWindowTodayDetectorSensor(hass),
        OkteMostExpensiveTimeWindowTodayDetectorSensor(hass),

        # Detektor sensory  (súbor: sensors_detectors_tomorrow.py)
        # Detektory časových okien pre zajtrajšie záznamy (napr. pre automatizácie)
        OkteCheapestTimeWindowTomorrowDetectorSensor(hass),
        OkteMostExpensiveTimeWindowTomorrowDetectorSensor(hass),

        # Systémové sensory (súbor: sensors_system.py)
        OkteConnectionSensor(hass),
        OkteDataCountSensor(hass),
        OkteLastUpdateSensor(hass),
        
        # Html objekty pre zobrazenie údajov
        OkteHtmlPriceTableSensor(hass),
        OkteHtmlPriceTodayTableSensor(hass),
        OkteHtmlPriceTomorrowTableSensor(hass),
    ]
    
    async_add_entities(sensors)