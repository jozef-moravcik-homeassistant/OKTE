from __future__ import annotations
"""The OKTE Integration"""
"""Author: Jozef Moravcik"""
"""email: jozef.moravcik@moravcik.eu"""

""" diagnostics.py """

""" Diagnostics support for OKTE Integration (Settings -> Devices & Services -> OKTE -> Download diagnostics)."""

import dataclasses
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DEVICE_TYPE_MASTER, ENTITY_FAILOVER_DATA, VERSION

# Attributes that are too large to be useful in a diagnostics file - only their size is reported
_LARGE_KEYS = ("period_data", "prices_list", "timestamps_list", "labels_list", "html_table")


def _summarize_records(records) -> dict[str, Any]:
    """Short summary of a list of price records."""
    records = records or []
    days = sorted({rec.get('deliveryDayCET') for rec in records if rec.get('deliveryDayCET')})
    return {"records": len(records), "days": days}


def _summarize_attributes(attributes: dict) -> dict[str, Any]:
    """Sensor attributes with large values replaced by their size."""
    result = {}
    for key, value in (attributes or {}).items():
        if key in _LARGE_KEYS or key.startswith("Period data"):
            result[key] = f"<{len(value)} items>" if isinstance(value, (list, dict)) else f"<{len(str(value))} chars>"
        else:
            result[key] = value
    return result


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = getattr(entry, "runtime_data", None)
    diagnostics: dict[str, Any] = {
        "version": VERSION,
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
    }
    if runtime_data is None:
        return diagnostics

    instance = runtime_data.instance
    diagnostics["device_type"] = runtime_data.device_type
    diagnostics["settings"] = dataclasses.asdict(instance.settings)
    diagnostics["sensor_states"] = {
        key: (f"<{len(value)} chars>" if isinstance(value, str) and len(value) > 200 else value)
        for key, value in instance.sensor_states.items()
    }

    if runtime_data.device_type == DEVICE_TYPE_MASTER:
        price_data = instance.price_data
        last_fetch = price_data.get("last_fetch")
        history = instance.price_history
        diagnostics["master"] = {
            "last_fetch": last_fetch.isoformat() if last_fetch else None,
            "fetch_failed": instance._fetch_failed,
            "data_date": price_data.get("data_date"),
            "data_version": price_data.get("data_version"),
            "all_data": _summarize_records(price_data.get("all_data")),
            "today_data": _summarize_records(price_data.get("today_data")),
            "tomorrow_data": _summarize_records(price_data.get("tomorrow_data")),
            "failover_data": _summarize_records(price_data.get("failover_data")),
            "retry_scheduled": instance._retry_timer is not None,
        }
        diagnostics["failover"] = {
            "stats_bootstrapped": instance._stats_bootstrapped,
            "history_days": len(history),
            "history_first_day": min(history, default=None),
            "history_last_day": max(history, default=None),
            "incomplete_history_days": sorted(day for day, slots in history.items() if len(slots) < 92),
            "failover_served_days": sorted(instance.failover_served_days),
            "sensor_attributes": _summarize_attributes(instance.sensor_attributes.get(ENTITY_FAILOVER_DATA)),
        }
        diagnostics["sensor_attributes"] = {
            key: _summarize_attributes(value) for key, value in instance.sensor_attributes.items()
            if key != ENTITY_FAILOVER_DATA
        }
    else:
        diagnostics["calculator"] = {
            "master_available": instance.is_master_available(),
            "last_calculation": instance._last_calculation_time.isoformat() if instance._last_calculation_time else None,
            "number_values": dict(getattr(instance, "number_values", {})),
            "time_values": {key: value.strftime("%H:%M") for key, value in getattr(instance, "time_values", {}).items() if value},
            "switch_values": dict(getattr(instance, "switch_values", {})),
        }

    return diagnostics
