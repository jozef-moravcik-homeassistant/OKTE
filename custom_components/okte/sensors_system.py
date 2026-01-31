"""
OKTE Integration for Home Assistant
Custom integration for fetching and analyzing electricity prices from OKTE Slovakia
*** System and diagnostic sensors for OKTE integration ***

Author: Jozef Moravcik
email: jozef.moravcik@moravcik.eu
"""

import logging
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant

from .base import OkteBaseSensor
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class OkteConnectionSensor(OkteBaseSensor):
    """Sensor for OKTE connection status."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "connection")
        self._attr_name = "Connection Status"
        self._attr_icon = "mdi:connection"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        """Return connection status."""
        if DOMAIN not in self.hass.data:
            return 0
        
        connection_status = self.hass.data[DOMAIN].get("connection_status", False)
        return 1 if connection_status else 0

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        if DOMAIN not in self.hass.data:
            return {"status": "Integration not ready"}
        
        connection_status = self.hass.data[DOMAIN].get("connection_status", False)
        last_update = self.hass.data[DOMAIN].get("last_update")
        
        attrs = {
            "status": "Connected" if connection_status else "Disconnected",
            "status_description": "Last data fetch was successful" if connection_status else "Last data fetch failed"
        }
        
        if last_update:
            attrs["last_attempt"] = last_update.isoformat()
        
        return attrs


class OkteDataCountSensor(OkteBaseSensor):
    """Sensor for data record count."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "data_count")
        self._attr_name = "Data Record Count"
        self._attr_icon = "mdi:counter"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "records"

    @property
    def native_value(self):
        """Return the count of data records."""
        data = self._get_okte_data()
        return len(data) if data else 0

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        stats = self._get_statistics()
        data = self._get_okte_data()
        
        attrs = {}
        if stats:
            attrs["valid_records"] = stats.get('count', 0)
        
        if data:
            attrs["total_records"] = len(data)
            # Get date range
            try:
                dates = [record.get('deliveryDayCET') for record in data if record.get('deliveryDayCET')]
                if dates:
                    attrs["date_from"] = min(dates)
                    attrs["date_to"] = max(dates)
            except:
                pass
        
        return attrs


class OkteLastUpdateSensor(OkteBaseSensor):
    """Sensor for last update timestamp."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "last_update")
        self._attr_name = "Last Update"
        self._attr_icon = "mdi:clock-outline"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def available(self):
        """Return if sensor is available."""
        # Sensor is available if we have domain data
        return DOMAIN in self.hass.data

    @property
    def native_value(self):
        """Return the last update timestamp."""
        if DOMAIN not in self.hass.data:
            return None
        
        last_update = self.hass.data[DOMAIN].get("last_update")
        if last_update and isinstance(last_update, datetime):
            # For timestamp sensors, we need timezone info
            # Use the Home Assistant timezone if available, otherwise default to local
            if last_update.tzinfo is None:
                # Get Home Assistant timezone
                ha_timezone = self.hass.config.time_zone
                try:
                    import zoneinfo
                    tz = zoneinfo.ZoneInfo(ha_timezone)
                    return last_update.replace(tzinfo=tz)
                except ImportError:
                    # Fallback for older Python versions
                    from datetime import timezone, timedelta
                    # Estimate timezone offset (this is a fallback)
                    local_offset = datetime.now() - datetime.utcnow()
                    tz_offset = timezone(timedelta(seconds=int(local_offset.total_seconds())))
                    return last_update.replace(tzinfo=tz_offset)
            return last_update
        return None

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        if DOMAIN not in self.hass.data:
            return {"status": "Integration not ready"}
            
        data = self._get_okte_data()
        if not data:
            return {"status": "No data"}
        
        return {
            "data_records": len(data),
            "status": "Data available"
        }