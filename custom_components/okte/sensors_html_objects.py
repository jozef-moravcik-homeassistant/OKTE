"""
OKTE Integration for Home Assistant
Custom integration for fetching and analyzing electricity prices from OKTE Slovakia
*** HTML objects sensors for OKTE integration ***
*** HTML Tables and objects for display ***

Author: Jozef Moravcik
email: jozef.moravcik@moravcik.eu
"""

import logging
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant

from .base import OkteBaseSensor
from .okte import format_local_time

_LOGGER = logging.getLogger(__name__)

# Color and styling constants
COLOR_PRICE_HIGH = "#009000"  # Green for high prices
COLOR_PRICE_LOW = "#d08000"  # Orange for low prices
COLOR_PRICE_NEGATIVE = "#d00000"  # Red for negative prices
THRESHOLD_PRICE_HIGH = 20
THRESHOLD_PRICE_LOW = 0
BG_COLOR_TABLE_HEADER_ROW1 = "#4a90e2"
BG_COLOR_TABLE_HEADER_ROW2 = "#f2f2f2"
BG_COLOR_TABLE_HEADER_ROW3 = "#f2f2f2"
TEXT_COLOR_TABLE_HEADER_ROW1 = "#ffffff"
TEXT_COLOR_TABLE_HEADER_ROW2 = "#000000"
TEXT_COLOR_TABLE_HEADER_ROW3 = "#000000"
BORDER_COLOR_HEADER = "#a0a0a0"
BORDER_COLOR_DATA = "#a0a0a0"
PADDING_HEADER_ROW1 = "10px 10px 10px 10px"
PADDING_HEADER_ROW2 = "2px 7px 2px 7px"
PADDING_HEADER_ROW3 = "2px 7px 2px 7px"
PADDING_DATA_ROWS = "1px 7px 1px 7px"
BG_COLOR_TABLE_DATA_ROW_ODD = "#ffffff"
BG_COLOR_TABLE_DATA_ROW_EVEN = "#f5f7ff"


class OkteHtmlPriceTableSensor(OkteBaseSensor):
    """Sensor - HTML tabuľka s dnešnými a zajtrajšími hodinovými cenami"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "html_price_table")
        self._attr_name = "HTML Price Table"
        self._attr_icon = "mdi:table"

    @property
    def native_value(self):
        """Return number of today's records in table."""
        today_data = self._filter_data_by_date(datetime.now().date())
        if not today_data:
            return 0
        
        valid_records = [record for record in today_data if record.get('price') is not None and record.get('deliveryStart')]
        return len(valid_records)

    def _get_price_color(self, price):
        """Get color for price based on value."""
        if price is None:
            return ""
        
        if price > THRESHOLD_PRICE_HIGH:
            return COLOR_PRICE_HIGH
        elif price >= THRESHOLD_PRICE_LOW:
            return COLOR_PRICE_LOW
        else:
            return COLOR_PRICE_NEGATIVE

    def _convert_to_local_time(self, utc_time_str):
        """Convert UTC time string to local time string."""
        if not utc_time_str:
            return ""
        
        try:
            # Parse UTC time from API (format: 2024-12-28T23:00:00Z)
            utc_time = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
            
            # Convert to local timezone
            try:
                import zoneinfo
                ha_timezone = self.hass.config.time_zone
                tz = zoneinfo.ZoneInfo(ha_timezone)
                local_time = utc_time.astimezone(tz)
            except ImportError:
                # Fallback for older Python versions - assume CET/CEST (UTC+1/UTC+2)
                # Approximate offset for Central European Time
                local_time = utc_time + timedelta(hours=1)  # CET is UTC+1, CEST is UTC+2
                
            return local_time.strftime('%H:%M')
        except Exception as e:
            _LOGGER.debug(f"Error converting time {utc_time_str}: {e}")
            return ""

    def _create_html_combined_price_table(self):
        """Create HTML table with today's and tomorrow's hourly prices."""
        today_data = self._filter_data_by_date(datetime.now().date())
        tomorrow = datetime.now().date() + timedelta(days=1)
        tomorrow_data = self._filter_data_by_date(tomorrow)
        
        # Get today's date formatted
        today_formatted = datetime.now().strftime('%d.%m.%Y')
        
        # Start building HTML table with header (always show)
        html = f"""
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%; max-width: 600px; border-color: {BORDER_COLOR_HEADER};">
            <thead>
                <tr style="background-color: {BG_COLOR_TABLE_HEADER_ROW1}; color: {TEXT_COLOR_TABLE_HEADER_ROW1};">
                    <th colspan="3" style="text-align: center; font-size: 16px; padding: {PADDING_HEADER_ROW1};">
                        Ceny elektriky na trhu OKTE
                    </th>
                </tr>
                <tr style="background-color: {BG_COLOR_TABLE_HEADER_ROW2}; color: {TEXT_COLOR_TABLE_HEADER_ROW2};">
                    <th rowspan="2" style="width: auto; min-width: 90px; max-width: 200px; text-align: center; vertical-align: middle; border-bottom: none; padding: {PADDING_HEADER_ROW2};">Čas od - do</th>
                    <th colspan="2" style="width: auto; max-width: 400px; text-align: center; border-bottom: none; padding: {PADDING_HEADER_ROW2};">Cena [€/MWh]</th>
                </tr>
                <tr style="background-color: {BG_COLOR_TABLE_HEADER_ROW3}; color: {TEXT_COLOR_TABLE_HEADER_ROW3};">
                    <th style="width: 30%; text-align: center; border-top: none; padding: {PADDING_HEADER_ROW3};">Dnes</th>
                    <th style="width: 30%; text-align: center; border-top: none; padding: {PADDING_HEADER_ROW3};">Zajtra</th>
                </tr>
            </thead>
            <tbody>
        """
        
        if not today_data:
            # No data available - show message
            html += f"""
                <tr>
                    <td colspan="3" style="text-align: center; height: 200px; vertical-align: middle; border: 1px solid {BORDER_COLOR_DATA};">
                        Údaje nie sú k dispozícii
                    </td>
                </tr>
            """
            html += """
            </tbody>
        </table>
        """
            return html
        
        # Filter and sort valid records for today
        today_valid_records = [record for record in today_data if record.get('price') is not None and record.get('deliveryStart')]
        
        if not today_valid_records:
            # No valid records for today - show message
            html += f"""
                <tr>
                    <td colspan="3" style="text-align: center; height: 200px; vertical-align: middle; border: 1px solid {BORDER_COLOR_DATA};">
                        Údaje nie sú k dispozícii
                    </td>
                </tr>
            """
            html += """
            </tbody>
        </table>
        """
            return html
        
        today_valid_records.sort(key=lambda x: x.get('deliveryStart', ''))
        
        # Filter and sort valid records for tomorrow (can be empty)
        tomorrow_valid_records = []
        if tomorrow_data:
            tomorrow_valid_records = [record for record in tomorrow_data if record.get('price') is not None and record.get('deliveryStart')]
            tomorrow_valid_records.sort(key=lambda x: x.get('deliveryStart', ''))
        
        # Create a mapping of tomorrow records by time for easy lookup
        tomorrow_records_by_time = {}
        for record in tomorrow_valid_records:
            time_from = self._convert_to_local_time(record.get('deliveryStart', ''))
            if time_from:
                tomorrow_records_by_time[time_from] = record
        
        # Add data rows based on today's records
        row_index = 0
        for record in today_valid_records:
            # Convert UTC times to local times
            time_from = self._convert_to_local_time(record.get('deliveryStart', ''))
            time_to = self._convert_to_local_time(record.get('deliveryEnd', ''))
            
            # Create time range string
            time_range = f"{time_from} - {time_to}" if time_from and time_to else ""
            
            # Today's price
            today_price = record.get('price', 0)
            today_price_color = self._get_price_color(today_price)
            today_price_formatted = f"{today_price:.2f} €"
            
            # Tomorrow's price (if available for the same time)
            tomorrow_price_formatted = ""
            tomorrow_price_color = ""
            if time_from in tomorrow_records_by_time:
                tomorrow_price = tomorrow_records_by_time[time_from].get('price', 0)
                tomorrow_price_color = self._get_price_color(tomorrow_price)
                tomorrow_price_formatted = f"{tomorrow_price:.2f} €"
            
            # Determine row background color (alternating)
            row_bg_color = BG_COLOR_TABLE_DATA_ROW_ODD if row_index % 2 == 0 else BG_COLOR_TABLE_DATA_ROW_EVEN
            
            html += f"""
                <tr style="background-color: {row_bg_color};">
                    <td style="width: auto; min-width: 90px; max-width: 200px; text-align: center; padding: {PADDING_DATA_ROWS};">{time_range}</td>
                    <td style="text-align: right; width: 30%; color: {today_price_color}; padding: {PADDING_DATA_ROWS};">{today_price_formatted}</td>
                    <td style="text-align: right; width: 30%; color: {tomorrow_price_color}; padding: {PADDING_DATA_ROWS};">{tomorrow_price_formatted}</td>
                </tr>
            """
            row_index += 1
        
        # Calculate statistics for today
        today_prices = [record['price'] for record in today_valid_records]
        today_min_price = min(today_prices)
        today_max_price = max(today_prices)
        today_avg_price = sum(today_prices) / len(today_prices)
        
        today_min_record = next(record for record in today_valid_records if record['price'] == today_min_price)
        today_max_record = next(record for record in today_valid_records if record['price'] == today_max_price)
        
        # Calculate statistics for tomorrow (if available)
        tomorrow_stats = ""
        if tomorrow_valid_records:
            tomorrow_prices = [record['price'] for record in tomorrow_valid_records]
            tomorrow_min_price = min(tomorrow_prices)
            tomorrow_max_price = max(tomorrow_prices)
            tomorrow_avg_price = sum(tomorrow_prices) / len(tomorrow_prices)
            
            tomorrow_min_record = next(record for record in tomorrow_valid_records if record['price'] == tomorrow_min_price)
            tomorrow_max_record = next(record for record in tomorrow_valid_records if record['price'] == tomorrow_max_price)
            
            tomorrow_min_time_from = self._convert_to_local_time(tomorrow_min_record.get('deliveryStart', ''))
            tomorrow_min_time_to = self._convert_to_local_time(tomorrow_min_record.get('deliveryEnd', ''))
            tomorrow_max_time_from = self._convert_to_local_time(tomorrow_max_record.get('deliveryStart', ''))
            tomorrow_max_time_to = self._convert_to_local_time(tomorrow_max_record.get('deliveryEnd', ''))
            
            tomorrow_formatted = tomorrow.strftime('%d.%m.%Y')
            tomorrow_stats = f"""<br>
                        <strong>📅 Zajtra ({tomorrow_formatted}):</strong><br>
                        📉 Min: {tomorrow_min_price:.2f} € ({tomorrow_min_time_from}-{tomorrow_min_time_to})<br>
                        📈 Max: {tomorrow_max_price:.2f} € ({tomorrow_max_time_from}-{tomorrow_max_time_to})<br>
                        📊 Priemer: {tomorrow_avg_price:.2f} €"""
        
        # Add footer with statistics
        today_min_time_from = self._convert_to_local_time(today_min_record.get('deliveryStart', ''))
        today_min_time_to = self._convert_to_local_time(today_min_record.get('deliveryEnd', ''))
        today_max_time_from = self._convert_to_local_time(today_max_record.get('deliveryStart', ''))
        today_max_time_to = self._convert_to_local_time(today_max_record.get('deliveryEnd', ''))
        
        html += f"""
            </tbody>
            <tfoot>
                <tr style="background-color: #e8f4f8;">
                    <td colspan="3" style="padding: 10px; font-size: 14px;">
                        <strong>📅 Dnes ({today_formatted}):</strong><br>
                        📉 Min: {today_min_price:.2f} € ({today_min_time_from}-{today_min_time_to})<br>
                        📈 Max: {today_max_price:.2f} € ({today_max_time_from}-{today_max_time_to})<br>
                        📊 Priemer: {today_avg_price:.2f} €{tomorrow_stats}
                    </td>
                </tr>
            </tfoot>
        </table>
        """
        
        return html

    @property
    def extra_state_attributes(self):
        """Return HTML table and related data."""
        today_data = self._filter_data_by_date(datetime.now().date())
        valid_records = [record for record in today_data if record.get('price') is not None and record.get('deliveryStart')] if today_data else []
        
        return {
            'html_table': self._create_html_combined_price_table(),
            'total_records': len(valid_records),
            'date': datetime.now().strftime('%d.%m.%Y'),
            'available': len(valid_records) > 0,
            'last_update': datetime.now().isoformat()
        }


class OkteHtmlPriceTodayTableSensor(OkteBaseSensor):
    """Sensor - HTML tabuľka s dnešnými hodinovými cenami"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "html_price_today_table")
        self._attr_name = "HTML Price Today Table"
        self._attr_icon = "mdi:table"

    @property
    def native_value(self):
        """Return number of today's records in table."""
        today_data = self._filter_data_by_date(datetime.now().date())
        if not today_data:
            return 0
        
        valid_records = [record for record in today_data if record.get('price') is not None and record.get('deliveryStart')]
        return len(valid_records)

    def _get_price_color(self, price):
        """Get color for price based on value."""
        if price is None:
            return ""
        
        if price > THRESHOLD_PRICE_HIGH:
            return COLOR_PRICE_HIGH
        elif price >= THRESHOLD_PRICE_LOW:
            return COLOR_PRICE_LOW
        else:
            return COLOR_PRICE_NEGATIVE

    def _convert_to_local_time(self, utc_time_str):
        """Convert UTC time string to local time string."""
        if not utc_time_str:
            return ""
        
        try:
            # Parse UTC time from API (format: 2024-12-28T23:00:00Z)
            utc_time = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
            
            # Convert to local timezone
            try:
                import zoneinfo
                ha_timezone = self.hass.config.time_zone
                tz = zoneinfo.ZoneInfo(ha_timezone)
                local_time = utc_time.astimezone(tz)
            except ImportError:
                # Fallback for older Python versions - assume CET/CEST (UTC+1/UTC+2)
                # Approximate offset for Central European Time
                local_time = utc_time + timedelta(hours=1)  # CET is UTC+1, CEST is UTC+2
                
            return local_time.strftime('%H:%M')
        except Exception as e:
            _LOGGER.debug(f"Error converting time {utc_time_str}: {e}")
            return ""

    def _create_html_today_price_table(self):
        """Create HTML table with today's hourly prices."""
        today_data = self._filter_data_by_date(datetime.now().date())
        
        # Get today's date formatted
        today_formatted = datetime.now().strftime('%d.%m.%Y')
        
        # Start building HTML table with header (always show)
        html = f"""
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%; max-width: 400px; border-color: {BORDER_COLOR_HEADER};">
            <thead>
                <tr style="background-color: {BG_COLOR_TABLE_HEADER_ROW1}; color: {TEXT_COLOR_TABLE_HEADER_ROW1};">
                    <th colspan="2" style="text-align: center; font-size: 16px; padding: {PADDING_HEADER_ROW1};">
                        Dnešné ceny elektriky OKTE
                    </th>
                </tr>
                <tr style="background-color: {BG_COLOR_TABLE_HEADER_ROW2}; color: {TEXT_COLOR_TABLE_HEADER_ROW2};">
                    <th style="width: auto; max-width: 200px; text-align: center; padding: {PADDING_HEADER_ROW2};">Čas od - do</th>
                    <th style="width: auto; max-width: 200px; text-align: center; padding: {PADDING_HEADER_ROW2};">Cena [€/MWh]</th>
                </tr>
            </thead>
            <tbody>
        """
        
        if not today_data:
            # No data available - show message
            html += f"""
                <tr>
                    <td colspan="2" style="text-align: center; height: 200px; vertical-align: middle; border: 1px solid {BORDER_COLOR_DATA};">
                        Údaje nie sú k dispozícii
                    </td>
                </tr>
            """
            html += """
            </tbody>
        </table>
        """
            return html
        
        # Filter and sort valid records
        valid_records = [record for record in today_data if record.get('price') is not None and record.get('deliveryStart')]
        
        if not valid_records:
            # No valid records - show message
            html += f"""
                <tr>
                    <td colspan="2" style="text-align: center; height: 200px; vertical-align: middle; border: 1px solid {BORDER_COLOR_DATA};">
                        Údaje nie sú k dispozícii
                    </td>
                </tr>
            """
            html += """
            </tbody>
        </table>
        """
            return html
        
        valid_records.sort(key=lambda x: x.get('deliveryStart', ''))
        
        # Calculate statistics
        prices = [record['price'] for record in valid_records]
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        
        min_record = next(record for record in valid_records if record['price'] == min_price)
        max_record = next(record for record in valid_records if record['price'] == max_price)
        
        # Add data rows
        row_index = 0
        for record in valid_records:
            # Convert UTC times to local times
            time_from = self._convert_to_local_time(record.get('deliveryStart', ''))
            time_to = self._convert_to_local_time(record.get('deliveryEnd', ''))
            
            # Create time range string
            time_range = f"{time_from} - {time_to}" if time_from and time_to else ""
            
            price = record.get('price', 0)
            
            # Format price to 2 decimal places with € symbol
            price_formatted = f"{price:.2f} €"
            price_color = self._get_price_color(price)
            
            # Determine row background color (alternating)
            row_bg_color = BG_COLOR_TABLE_DATA_ROW_ODD if row_index % 2 == 0 else BG_COLOR_TABLE_DATA_ROW_EVEN
            
            html += f"""
                <tr style="background-color: {row_bg_color};">
                    <td style="width: auto; max-width: 200px; text-align: center; padding: {PADDING_DATA_ROWS};">{time_range}</td>
                    <td style="text-align: right; width: auto; max-width: 200px; color: {price_color}; padding: {PADDING_DATA_ROWS};">{price_formatted}</td>
                </tr>
            """
            row_index += 1
        
        # Add footer with statistics
        min_time_from = self._convert_to_local_time(min_record.get('deliveryStart', ''))
        min_time_to = self._convert_to_local_time(min_record.get('deliveryEnd', ''))
        max_time_from = self._convert_to_local_time(max_record.get('deliveryStart', ''))
        max_time_to = self._convert_to_local_time(max_record.get('deliveryEnd', ''))
        
        html += f"""
            </tbody>
            <tfoot>
                <tr style="background-color: #e8f4f8;">
                    <td colspan="2" style="padding: 10px; font-size: 14px;">
                        <strong>📅 Dátum:</strong> {today_formatted}<br>
                        <strong>📉 Min. cena:</strong> {min_price:.2f} € ({min_time_from}-{min_time_to})<br>
                        <strong>📈 Max. cena:</strong> {max_price:.2f} € ({max_time_from}-{max_time_to})<br>
                        <strong>📊 Priemerná cena:</strong> {avg_price:.2f} €
                    </td>
                </tr>
            </tfoot>
        </table>
        """
        
        return html

    @property
    def extra_state_attributes(self):
        """Return HTML table and related data for today."""
        today_data = self._filter_data_by_date(datetime.now().date())
        valid_records = [record for record in today_data if record.get('price') is not None and record.get('deliveryStart')] if today_data else []
        
        return {
            'html_table': self._create_html_today_price_table(),
            'total_records': len(valid_records),
            'date': datetime.now().strftime('%d.%m.%Y'),
            'available': len(valid_records) > 0,
            'last_update': datetime.now().isoformat()
        }


class OkteHtmlPriceTomorrowTableSensor(OkteBaseSensor):
    """Sensor - HTML tabuľka so zajtrajšími hodinovými cenami"""

    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        super().__init__(hass, "html_price_tomorrow_table")
        self._attr_name = "HTML Price Tomorrow Table"
        self._attr_icon = "mdi:table"

    @property
    def native_value(self):
        """Return number of tomorrow's records in table."""
        tomorrow = datetime.now().date() + timedelta(days=1)
        tomorrow_data = self._filter_data_by_date(tomorrow)
        if not tomorrow_data:
            return 0
        
        valid_records = [record for record in tomorrow_data if record.get('price') is not None and record.get('deliveryStart')]
        return len(valid_records)

    def _get_price_color(self, price):
        """Get color for price based on value."""
        if price is None:
            return ""
        
        if price > THRESHOLD_PRICE_HIGH:
            return COLOR_PRICE_HIGH
        elif price >= THRESHOLD_PRICE_LOW:
            return COLOR_PRICE_LOW
        else:
            return COLOR_PRICE_NEGATIVE

    def _convert_to_local_time(self, utc_time_str):
        """Convert UTC time string to local time string."""
        if not utc_time_str:
            return ""
        
        try:
            # Parse UTC time from API (format: 2024-12-28T23:00:00Z)
            utc_time = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
            
            # Convert to local timezone
            try:
                import zoneinfo
                ha_timezone = self.hass.config.time_zone
                tz = zoneinfo.ZoneInfo(ha_timezone)
                local_time = utc_time.astimezone(tz)
            except ImportError:
                # Fallback for older Python versions - assume CET/CEST (UTC+1/UTC+2)
                # Approximate offset for Central European Time
                local_time = utc_time + timedelta(hours=1)  # CET is UTC+1, CEST is UTC+2
                
            return local_time.strftime('%H:%M')
        except Exception as e:
            _LOGGER.debug(f"Error converting time {utc_time_str}: {e}")
            return ""

    def _create_html_tomorrow_price_table(self):
        """Create HTML table with tomorrow's hourly prices."""
        tomorrow = datetime.now().date() + timedelta(days=1)
        tomorrow_data = self._filter_data_by_date(tomorrow)
        
        # Get tomorrow's date formatted
        tomorrow_formatted = tomorrow.strftime('%d.%m.%Y')
        
        # Start building HTML table with header (always show)
        html = f"""
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%; max-width: 400px; border-color: {BORDER_COLOR_HEADER};">
            <thead>
                <tr style="background-color: {BG_COLOR_TABLE_HEADER_ROW1}; color: {TEXT_COLOR_TABLE_HEADER_ROW1};">
                    <th colspan="2" style="text-align: center; font-size: 16px; padding: {PADDING_HEADER_ROW1};">
                        Zajtrajšie ceny elektriky OKTE
                    </th>
                </tr>
                <tr style="background-color: {BG_COLOR_TABLE_HEADER_ROW2}; color: {TEXT_COLOR_TABLE_HEADER_ROW2};">
                    <th style="width: auto; max-width: 200px; text-align: center; padding: {PADDING_HEADER_ROW2};">Čas od - do</th>
                    <th style="width: auto; max-width: 200px; text-align: center; padding: {PADDING_HEADER_ROW2};">Cena [€/MWh]</th>
                </tr>
            </thead>
            <tbody>
        """
        
        if not tomorrow_data:
            # No data available - show message
            html += f"""
                <tr>
                    <td colspan="2" style="text-align: center; height: 200px; vertical-align: middle; border: 1px solid {BORDER_COLOR_DATA};">
                        Údaje nie sú k dispozícii
                    </td>
                </tr>
            """
            html += """
            </tbody>
        </table>
        """
            return html
        
        # Filter and sort valid records
        valid_records = [record for record in tomorrow_data if record.get('price') is not None and record.get('deliveryStart')]
        
        if not valid_records:
            # No valid records - show message
            html += f"""
                <tr>
                    <td colspan="2" style="text-align: center; height: 200px; vertical-align: middle; border: 1px solid {BORDER_COLOR_DATA};">
                        Údaje nie sú k dispozícii
                    </td>
                </tr>
            """
            html += """
            </tbody>
        </table>
        """
            return html
        
        valid_records.sort(key=lambda x: x.get('deliveryStart', ''))
        
        # Calculate statistics
        prices = [record['price'] for record in valid_records]
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        
        min_record = next(record for record in valid_records if record['price'] == min_price)
        max_record = next(record for record in valid_records if record['price'] == max_price)
        
        # Add data rows
        row_index = 0
        for record in valid_records:
            # Convert UTC times to local times
            time_from = self._convert_to_local_time(record.get('deliveryStart', ''))
            time_to = self._convert_to_local_time(record.get('deliveryEnd', ''))
            
            # Create time range string
            time_range = f"{time_from} - {time_to}" if time_from and time_to else ""
            
            price = record.get('price', 0)
            
            # Format price to 2 decimal places with € symbol
            price_formatted = f"{price:.2f} €"
            price_color = self._get_price_color(price)
            
            # Determine row background color (alternating)
            row_bg_color = BG_COLOR_TABLE_DATA_ROW_ODD if row_index % 2 == 0 else BG_COLOR_TABLE_DATA_ROW_EVEN
            
            html += f"""
                <tr style="background-color: {row_bg_color};">
                    <td style="width: auto; max-width: 200px; text-align: center; padding: {PADDING_DATA_ROWS};">{time_range}</td>
                    <td style="text-align: right; width: auto; max-width: 200px; color: {price_color}; padding: {PADDING_DATA_ROWS};">{price_formatted}</td>
                </tr>
            """
            row_index += 1
        
        # Add footer with statistics
        min_time_from = self._convert_to_local_time(min_record.get('deliveryStart', ''))
        min_time_to = self._convert_to_local_time(min_record.get('deliveryEnd', ''))
        max_time_from = self._convert_to_local_time(max_record.get('deliveryStart', ''))
        max_time_to = self._convert_to_local_time(max_record.get('deliveryEnd', ''))
        
        html += f"""
            </tbody>
            <tfoot>
                <tr style="background-color: #e8f4f8;">
                    <td colspan="2" style="padding: 10px; font-size: 14px;">
                        <strong>📅 Dátum:</strong> {tomorrow_formatted}<br>
                        <strong>📉 Min. cena:</strong> {min_price:.2f} € ({min_time_from}-{min_time_to})<br>
                        <strong>📈 Max. cena:</strong> {max_price:.2f} € ({max_time_from}-{max_time_to})<br>
                        <strong>📊 Priemerná cena:</strong> {avg_price:.2f} €
                    </td>
                </tr>
            </tfoot>
        </table>
        """
        
        return html

    @property
    def extra_state_attributes(self):
        """Return HTML table and related data for tomorrow."""
        tomorrow = datetime.now().date() + timedelta(days=1)
        tomorrow_data = self._filter_data_by_date(tomorrow)
        valid_records = [record for record in tomorrow_data if record.get('price') is not None and record.get('deliveryStart')] if tomorrow_data else []
        
        return {
            'html_table': self._create_html_tomorrow_price_table(),
            'total_records': len(valid_records),
            'date': tomorrow.strftime('%d.%m.%Y'),
            'available': len(valid_records) > 0,
            'last_update': datetime.now().isoformat()
        }