# 🔌 OKTE - Slovak Energy Market Integration for Home Assistant

[![Version](https://img.shields.io/badge/version-1.01.04-blue.svg)](https://github.com/jozef-moravcik-homeassistant/okte)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> 📖 **[Slovenská verzia dokumentácie / Slovak Documentation →](README_SK.md)**

---

## 📋 Introduction

**OKTE Integration** is a comprehensive Home Assistant custom integration that provides automatic data retrieval from the Slovak Energy Market (OKTE - Operátor krátkodobého trhu s elektrinou). This integration enables smart home automation based on real-time electricity prices, helping you optimize energy costs by scheduling energy-intensive devices during the cheapest price windows.

### ✨ Key Features

- 🔄 **Automatic data synchronization** from OKTE API
- 📊 **Comprehensive price sensors** for today and tomorrow
- 🕐 **Flexible time window calculations** for finding lowest and highest price periods
- 📈 **Interactive price charts** with ApexCharts support
- 📋 **HTML tables** for easy price visualization
- 🎯 **Binary detectors** for automation triggers
- ⚡ **Real-time current price** tracking
- 🔢 **Statistical sensors** (min, max, average prices)
- 🌓 **Sunrise/sunset integration** for time window configuration
- 🔧 **Multiple Calculator devices** for independent automation scenarios
- 🔀 **Failover function** In the case of data source failure, averaged prices based on periods and timeframes are used

---

## 📑 Table of Contents

1. [Installation](#-installation)
   - [Via Marketplace](#via-marketplace-recommended)
   - [Manual Installation](#manual-installation)
   - [Device Configuration](#device-configuration)
   - [Entity Names](#entity-names)
2. [Master Device](#-master-device)
   - [Master Device Configuration](#master-device-configuration)
   - [Master Device Entities](#master-device-entities)
3. [Calculator Device](#-calculator-device)
   - [Calculator Device Configuration](#calculator-device-configuration)
   - [Calculator Device Entities](#calculator-device-entities)
   - [Entity ID Prefixes](#entity-id-prefixes)
4. [Price Charts](#-price-charts)
5. [HTML Price Tables](#-html-price-tables)
6. [Automation Examples](#-automation-examples)
7. [Support](#-support)

---

## 🔧 Installation

> ℹ️ **Requirements:** Home Assistant **2026.3.0** or newer.

### Via Marketplace (Recommended)

1. Open **Marketplace** in your Home Assistant
2. Search **okte** and click to **Install** button
#### If you can't find okte in Marketplace, follow next steps ####
3. Click the **3 dots** menu in the top right corner in **Marketplace**
4. Select **Custom repositories**
5. Add repository URL: `https://github.com/jozef-moravcik-homeassistant/okte`
6. Category: **Integration**
7. Click **Download**
8. Restart Home Assistant

### Manual Installation

1. Download the latest release from [GitHub](https://github.com/jozef-moravcik-homeassistant/okte)
2. Extract the `okte` folder to your `custom_components` directory:
   ```
   config/
   └── custom_components/
       └── okte/
           ├── __init__.py
           ├── manifest.json
           ├── config_flow.py
           └── ...
   ```
3. Restart Home Assistant

### Device Configuration

The OKTE integration uses **two types of virtual devices**:

#### 🎯 Master Device
- **Automatically installed first** during initial setup
- **Only ONE Master device** is allowed per Home Assistant instance
- Handles automatic data fetching from OKTE API
- Provides price sensors, statistics, and data for Calculator devices
- **Default data fetch time: 14:00** (OKTE publishes next day prices around 13:00)
- Master provides a "failover function" that, in the case of data source outage, uses averaged prices based on individual periods and days.

![Master Configuration](docs/images/en_device_okte_master_configuration.jpg)

#### 🔢 Calculator Devices
- You can add **unlimited number** of Calculator devices
- Each Calculator device is **independently configured**
- Calculators are automatically numbered: Calculator 1, Calculator 2, Calculator 3, etc.
- Uses data from Master to find optimal price windows
- Perfect for different automation scenarios (battery charging, heat pump operation, etc.)

#### Adding Devices

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **"OKTE"**
4. The device type is selected automatically:
   - **Master** - if no Master device exists yet (first installation); the configuration form of the Master is shown
   - **Calculator** - if the Master device already exists; the Calculator is created immediately, without a configuration form

![Integration Cards](docs/images/en_integration_card_01.jpg)

![Device Update](docs/images/en_device_update.jpg)

### Entity Names

Home Assistant always shows the device name in front of the entity name: `<device name> <entity name>`.

| Device | Device name | Entity name example |
|--------|-------------|---------------------|
| Master | `OKTE` | `OKTE Current Price` |
| Calculator | `Calculator 1` or the name set in the UI (e.g. `Battery`) | `Battery Detector Lowest Price` |

- The Master device is named **OKTE**; the title of its entry on the integration page is **Master**.
- Any device can be renamed in the UI (**Settings** → **Devices & Services** → **OKTE** → device → rename). The entity names follow the new device name automatically.
- Entity IDs do not depend on the device name (e.g. `sensor.okte_current_price`, `binary_sensor.okte_1_detector_lowest_price`), so automations and dashboards keep working after a rename.

## 📡 'Master' Device

The **Master** device is the core component that handles all communication with the OKTE API, data storage and calculation of average prices in the event of a data source failure. It automatically downloads electricity price data and provides it to the system.

### Master Device Configuration

![Master Device Settings](docs/images/en_device_okte_master_configuration.jpg)

#### Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| **Daily fetch time** | 14:00 | Time when data is automatically downloaded from OKTE API |
| **Data Failover mode** | Averages by week days | In case of data source unavailability, OKTE will populate the data in the sensors using price averages. |
| **Number of weeks included in averages** | 4 | Number of weeks over which price averages are calculated (valid only for Data Failover mode = "Averages by week days") |
| **Number of days included in averages** | 7 | Number of days over which price averages are calculated (valid only for Data Failover mode = "Averages from all days") |
| **Unit of price sensors** | EUR/MWh |  |

**Data Failover mode option:**
  - **Averages by week days** - It calculates the average for individual periods for each calendar day of the week and uses these values ​​if the OKTE data source is unavailable and data in sensors is outdated or invalid.
  - **Averages from all days** - It calculates averages for individual periods from all days and uses them if the OKTE data source is unavailable and data in sensors is outdated or invalid.
  - **Disabled** – the Data Failover function is disabled; if the OKTE data source is unavailable and the sensors contain outdated or invalid data, the data in the sensors will remain invalid.

> ⚠️ **Important:**
>   - **OKTE publishes next-day prices around 13:00**, so the default fetch time of 14:00 (configurable) provides up-to-date data for both today and tomorrow.
>   - **Midnight:** data for the following day is automatically moved to the current day, so no download is needed after midnight; the next day's data is added at the next scheduled download.
>   - **Failed download** (e.g., an interrupted internet connection or an issue on the OKTE side): the integration retries every minute until it succeeds; the status is shown in `sensor.okte_connection_status` and any error code in `sensor.okte_error_code`.
>   - **Storage:** the data is kept in HA storage, so it remains available after an HA restart.
>   - **Failover:** if the connection to OKTE is not restored and the data in the sensors becomes outdated (e.g., the data for the following day has been moved to the current day at midnight and the next download also fails), price averages calculated for each period from previous data are automatically loaded into the sensors, so automations and processes depending on this data do not fail. As soon as the connection is restored, the data from OKTE is loaded into the sensors automatically.

### Master Device Entities

The Master device creates the following entities:

![Master Entities](docs/images/en_card_okte_master_entities.jpg)

#### 📊 Price Sensors

| Entity ID | Description | Unit | Attributes |
|-----------|-------------|------|------------|
| `sensor.okte_current_price` | Current electricity price | EUR/MWh | - |
| `sensor.okte_average_price_today` | Today's average price | EUR/MWh | - |
| `sensor.okte_min_price_today` | Today's minimum price | EUR/MWh | `time`, `period`, `period_start`, `period_end` |
| `sensor.okte_max_price_today` | Today's maximum price | EUR/MWh | `time`, `period`, `period_start`, `period_end` |
| `sensor.okte_average_price_tomorrow` | Tomorrow's average price | EUR/MWh | - |
| `sensor.okte_min_price_tomorrow` | Tomorrow's minimum price | EUR/MWh | `time`, `period`, `period_start`, `period_end` |
| `sensor.okte_max_price_tomorrow` | Tomorrow's maximum price | EUR/MWh | `time`, `period`, `period_start`, `period_end` |
| `sensor.okte_failover_data` | Calculated averages (`true`) or real data (`false`) in the price sensors | - | `failover_data_today`, `failover_data_tomorrow`, `Period data Monday` … `Period data Sunday` |

> ⚠️ **INFO:** If `sensor.okte_failover_data` is `false`, the price sensors contain actual data retrieved from the OKTE data source, if it is `true`, the sensors contain price averages.

#### 📈 Chart Data Sensors

| Entity ID | Description | Purpose |
|-----------|-------------|---------|
| `sensor.okte_prices_today` | Today's prices | **For ApexCharts graphs** |
| `sensor.okte_prices_tomorrow` | Tomorrow's prices | **For ApexCharts graphs** |

**Attributes:**
- `period_data`: Array of objects containing:
  - `time`: ISO timestamp
  - `price`: Price value in EUR/MWh
  - `period`: period of the day

#### 📋 HTML Table Sensors

| Entity ID | Description | Purpose |
|-----------|-------------|---------|
| `sensor.okte_html_table_today` | Today's price table in HTML | **For HTML template cards** |
| `sensor.okte_html_table_tomorrow` | Tomorrow's price table in HTML | **For HTML template cards** |

**Attributes:**
- `html_table`: Complete HTML table code with:
  - Periodical breakdown (00:00 - 23:59)
  - Color-coded prices (green=low, yellow=medium, red=high)
  - Formatted prices with 2 decimal places

#### 🔧 Diagnostic Sensors

| Entity ID | Description | Values |
|-----------|-------------|--------|
| `sensor.okte_connection_status` | API connection status | `True` / `False` (attribute `status`: `Connected` / `Disconnected`, attribute `status_description`) |
| `sensor.okte_last_update` | Last successful data fetch | Timestamp |
| `sensor.okte_data_count` | Number of price records | Integer |
| `sensor.okte_error_code` | Error code | `0` = OK, `1` = data download failed, `2` = no valid data for today, `3` = both |

#### 🔘 Control Buttons

| Entity ID | Description | Action |
|-----------|-------------|--------|
| `button.okte_update_data` | Manual data fetch | Triggers immediate API data download |
| `button.okte_reset_failover_history` | Manual reset of Failover history | Resets all price averages for failover and rebuilds them from the recorder statistics of `sensor.okte_current_price` (last 10 days) and the real prices already downloaded from OKTE. |

### Example Card for Master Device

```yaml
type: grid
cards:
  - type: entities
    entities:
      - entity: sensor.okte_current_price
      - type: divider
      - entity: sensor.okte_prices_today
      - entity: sensor.okte_prices_tomorrow
      - type: divider
      - entity: sensor.okte_max_price_today
      - entity: sensor.okte_max_price_tomorrow
      - type: divider
      - entity: sensor.okte_min_price_today
      - entity: sensor.okte_min_price_tomorrow
      - type: divider
      - entity: sensor.okte_average_price_today
      - entity: sensor.okte_average_price_tomorrow
      - type: divider
      - entity: sensor.okte_html_table_today
      - entity: sensor.okte_html_table_tomorrow
      - type: divider
      - entity: sensor.okte_failover_data
      - type: divider
      - entity: sensor.okte_error_code
      - entity: sensor.okte_data_count
      - entity: sensor.okte_connection_status
      - entity: sensor.okte_last_update
      - type: divider
      - entity: button.okte_update_data
      - entity: button.okte_reset_failover_history
    title: OKTE
    grid_options:
      columns: full
column_span: 2
```

---

## 🔢 Calculator Device

The **Calculator** device uses data from the Master to find optimal time windows with the lowest or highest electricity prices. You can add **unlimited** Calculator devices, each with independent configuration for different automation scenarios.

### Calculator Device Configuration

The Calculator device has **no configuration parameters**. It is created immediately after it is added, and its behaviour is controlled by its entities (time ranges, window sizes, sunrise/sunset switches) described below.

### Calculator Device Entities

Each Calculator device creates a comprehensive set of entities for finding and tracking optimal price windows:

![Calculator Entities Part 1](docs/images/en_card_okte_calculator_entities_01.jpg)

![Calculator Entities Part 2](docs/images/en_card_okte_calculator_entities_02.jpg)

### Entity ID Prefixes

Calculator devices use **numbered prefixes** in entity IDs:

| Device | Entity ID Example | Pattern |
|--------|------------------|---------|
| Calculator 1 | `sensor.okte_1_lowest_price_window` | `okte_1_{entity_name}` |
| Calculator 2 | `sensor.okte_2_lowest_price_window` | `okte_2_{entity_name}` |
| Calculator 3 | `sensor.okte_3_lowest_price_window` | `okte_3_{entity_name}` |

> 💡 **Note:** The number automatically increments for each new Calculator device

#### 📊 Lowest Price Window Sensors

| Entity ID Pattern | Description | Attributes |
|-------------------|-------------|------------|
| `sensor.okte_N_lowest_price_window` | Combined lowest price window (today or tomorrow) | see [Window sensor attributes](#window-sensor-attributes) |
| `sensor.okte_N_lowest_price_window_today` | Today's lowest price window | see [Window sensor attributes](#window-sensor-attributes) |
| `sensor.okte_N_lowest_price_window_tomorrow` | Tomorrow's lowest price window | see [Window sensor attributes](#window-sensor-attributes) |
| `sensor.okte_N_lowest_price_window_size` | Window duration in H:MM format | - |
| `sensor.okte_N_lowest_price_search_window_size` | Search window duration in H:MM format | - |

#### 📊 Highest Price Window Sensors

| Entity ID Pattern | Description | Attributes |
|-------------------|-------------|------------|
| `sensor.okte_N_highest_price_window` | Combined highest price window (today or tomorrow) | see [Window sensor attributes](#window-sensor-attributes) |
| `sensor.okte_N_highest_price_window_today` | Today's highest price window | see [Window sensor attributes](#window-sensor-attributes) |
| `sensor.okte_N_highest_price_window_tomorrow` | Tomorrow's highest price window | see [Window sensor attributes](#window-sensor-attributes) |
| `sensor.okte_N_highest_price_window_size` | Window duration in H:MM format | - |
| `sensor.okte_N_highest_price_search_window_size` | Search window duration in H:MM format | - |

#### Window Sensor Attributes

The state of the window sensors is `OK` when a window was found, otherwise `NOT`.

| Attribute | Description |
|-----------|-------------|
| `found` | `true` when a window was found |
| `start_time_local`, `end_time_local` | Start and end of the window in local time (`DD.MM.YYYY HH:MM`) |
| `start_time_UTC`, `end_time_UTC` | Start and end of the window in UTC |
| `periods` | Number of 15-minute periods of the window |
| `window_size`, `window_search_size` | Size of the window and of the search window |
| `min_price`, `max_price`, `avg_price` | Minimum, maximum and average price in the window (EUR/MWh) |
| `records` | List of the periods of the window with their prices |

#### 🎯 Binary Sensor Detectors

These detectors automatically turn **ON** when the current time is within the calculated price window:

**Lowest Price Detectors:**
| Entity ID Pattern | Description | States |
|-------------------|-------------|--------|
| `binary_sensor.okte_N_detector_lowest_price` | ON when in lowest price window (combined) | ON / OFF |
| `binary_sensor.okte_N_detector_lowest_price_today` | ON when in today's lowest price window | ON / OFF |

**Highest Price Detectors:**
| Entity ID Pattern | Description | States |
|-------------------|-------------|--------|
| `binary_sensor.okte_N_detector_highest_price` | ON when in highest price window (combined) | ON / OFF |
| `binary_sensor.okte_N_detector_highest_price_today` | ON when in today's highest price window | ON / OFF |

> 💡 **Use Case:** Perfect for automation triggers! Turn on battery charging when detector is ON, or reduce consumption during high price periods.

#### ⚙️ Control Entities - Lowest Price Window

**Time Range Configuration:**
| Entity ID Pattern | Type | Description | Default |
|-------------------|------|-------------|---------|
| `switch.okte_N_lowest_price_window_from_as_day_start` | Switch | Auto-set start time to sunrise | OFF |
| `time.okte_N_lowest_price_window_from_as_day_start_prefix` | Time | Delay in the start of the search window after sunrise | 00:00 |
| `time.okte_N_lowest_price_time_from` | Time | Start time of the search window | 00:00 |
| `switch.okte_N_lowest_price_window_to_as_day_end` | Switch | Auto-set end time to sunset | OFF |
| `time.okte_N_lowest_price_window_to_as_day_end_prefix` | Time | Shorten search window end before sunset by: | 00:00 |
| `time.okte_N_lowest_price_time_to` | Time | End time of the search window | 23:59 |
| `number.okte_N_lowest_price_window_size` | Number | Price window size in 15-minute periods (1–96) | 3 (= 45 min) |

**How Sunrise/Sunset Switches Work:**
- ✅ **ON**: Time is automatically set to sunrise/sunset
- If a delay after sunrise is set (e.g., 2:00), this duration is added to the sunrise time (e.g., 6:30), resulting in a later start for the search window (in our example, at 8:30).
- If a setting is configured to shorten the search window before sunset (e.g., by 2 hours), and sunset occurs at 17:30, the search window will end at 15:30.
- Delaying the start and shortening the end of the search window is particularly useful for scheduling the operation of large appliances, such as a heat pump, this is because, after sunrise, it takes some time for the power output from the PV system to become sufficient to operate the heat pump.

- ⬜ **OFF**: The start and end times of the search window are entered manually.

#### ⚙️ Control Entities - Highest Price Window

**Time Range Configuration:**
| Entity ID Pattern | Type | Description | Default |
|-------------------|------|-------------|---------|
| `switch.okte_N_highest_price_window_from_as_day_start` | Switch | Auto-set start time to sunrise | OFF |
| `time.okte_N_highest_price_window_from_as_day_start_prefix` | Time | Delay in the start of the search window after sunrise | 00:00 |
| `time.okte_N_highest_price_time_from` | Time | Manual start time | 00:00 |
| `switch.okte_N_highest_price_window_to_as_day_end` | Switch | Auto-set end time to sunset | OFF |
| `time.okte_N_highest_price_window_to_as_day_end_prefix` | Time | Shorten search window end before sunset by: | 00:00 |
| `time.okte_N_highest_price_time_to` | Time | Manual end time | 23:59 |
| `number.okte_N_highest_price_window_size` | Number | Price window size in 15-minute periods (1–96) | 3 (= 45 min) |

### Example Card for Calculator Device

```yaml
type: grid
cards:
  # Lowest Price Window Information
  - type: entities
    entities:
      - entity: binary_sensor.okte_1_detector_lowest_price
      - entity: binary_sensor.okte_1_detector_lowest_price_today
      - entity: sensor.okte_1_lowest_price_window
      - entity: sensor.okte_1_lowest_price_window_today
      - entity: sensor.okte_1_lowest_price_window_tomorrow
      - entity: sensor.okte_1_lowest_price_window_size
      - entity: sensor.okte_1_lowest_price_search_window_size
    title: OKTE Calculator 1 - Lowest Prices
    grid_options:
      columns: full
      rows: auto
  
  # Lowest Price Window Controls
  - type: entities
    entities:
      - entity: switch.okte_1_lowest_price_window_from_as_day_start
      - entity: time.okte_1_lowest_price_time_from
      - entity: switch.okte_1_lowest_price_window_to_as_day_end
      - entity: time.okte_1_lowest_price_time_to
      - entity: number.okte_1_lowest_price_window_size
    title: Lowest Price - Settings
    grid_options:
      columns: full
      rows: auto
  
  # Highest Price Window Information
  - type: entities
    entities:
      - entity: binary_sensor.okte_1_detector_highest_price
      - entity: binary_sensor.okte_1_detector_highest_price_today
      - entity: sensor.okte_1_highest_price_window
      - entity: sensor.okte_1_highest_price_window_today
      - entity: sensor.okte_1_highest_price_window_tomorrow
      - entity: sensor.okte_1_highest_price_window_size
      - entity: sensor.okte_1_highest_price_search_window_size
    title: OKTE Calculator 1 - Highest Prices
    grid_options:
      columns: full
      rows: auto
  
  # Highest Price Window Controls
  - type: entities
    entities:
      - entity: switch.okte_1_highest_price_window_from_as_day_start
      - entity: time.okte_1_highest_price_time_from
      - entity: switch.okte_1_highest_price_window_to_as_day_end
      - entity: time.okte_1_highest_price_time_to
      - entity: number.okte_1_highest_price_window_size
    title: Highest Price - Settings
    grid_options:
      columns: full
      rows: auto
column_span: 2
```

---

## 📈 Price Charts

The OKTE integration provides price data perfectly formatted for **ApexCharts Card** visualization. This allows you to create beautiful, interactive price charts.

### Prerequisites

Install the **ApexCharts Card** via HACS:
1. Open HACS → Frontend
2. Search for "ApexCharts Card"
3. Install and restart Home Assistant

### Chart Examples

![Price Charts](docs/images/en_card_graphs.jpg)

#### Today's Prices Chart

```yaml
type: custom:apexcharts-card
grid_options:
  columns: 12
  rows: auto
card_mod:
  style: |
    ha-card {
      min-width: 400px;
      padding: 0px 10px 0px 0px;
    }
    ha-card div#header__title {
      font-size: 17px !important;
      color:#1a60b2;
      padding: 5px 0px 10px 10px;
    }
apex_config:
  chart:
    zoom:
      autoScaleYaxis: false
  plotOptions:
    bar:
      columnWidth: 70%
graph_span: 24h
span:
  start: day
header:
  show: true
  title: OKTE - Electricity prices today [€/MWh]
  show_states: true
  colorize_states: true
now:
  show: true
experimental:
  color_threshold: true
series:
  - entity: sensor.okte_prices_today
    name: Price €/MWh
    type: column
    color_threshold:
      - value: 0
        color: red
      - value: 0
        color: "#FFAA10"
      - value: 20
        color: "#219610"
      - value: 300
        color: "#2196F0"
    stroke_width: 0
    color: "#219610"
    data_generator: |
      const data = entity.attributes.period_data || [];
      return data
        .slice(0,96)
        .map((entry) => {
          return [new Date(entry.time).getTime(), entry.price];
        });
    show:
      extremas: false
      in_header: false
  - entity: sensor.okte_current_price
    name: Current price
    color: "#219610"
    data_generator: |
      const now = new Date();
      const currentValue = parseFloat(entity.state);
      return [[now.getTime(), currentValue]];
    show:
      in_chart: false
      in_header: true
  - entity: sensor.okte_min_price_today
    name: Min today
    color: red
    data_generator: |
      const now = new Date();
      const minValue = parseFloat(entity.state);
      return [[now.getTime(), minValue]];
    show:
      in_chart: false
      in_header: true
  - entity: sensor.okte_max_price_today
    name: Max today
    color: "#2196F0"
    data_generator: |
      const now = new Date();
      const maxValue = parseFloat(entity.state);
      return [[now.getTime(), maxValue]];
    show:
      in_chart: false
      in_header: true
```

#### Tomorrow's Prices Chart

```yaml
type: custom:apexcharts-card
grid_options:
  columns: 12
  rows: auto
card_mod:
  style: |
    ha-card {
      min-width: 400px;
      padding: 0px 10px 0px 0px;
    }
    ha-card div#header__title {
      font-size: 17px !important;
      color:#1a60b2;
      padding: 5px 0px 10px 10px;
    }
apex_config:
  chart:
    zoom:
      autoScaleYaxis: false
  plotOptions:
    bar:
      columnWidth: 70%
graph_span: 24h
span:
  start: day
  offset: +1d
header:
  show: true
  title: OKTE - Electricity prices tomorrow [€/MWh]
  show_states: true
  colorize_states: true
now:
  show: false
experimental:
  color_threshold: true
series:
  - entity: sensor.okte_prices_tomorrow
    name: Price €/MWh
    type: column
    color_threshold:
      - value: 0
        color: red
      - value: 0
        color: "#FFAA10"
      - value: 20
        color: "#219610"
      - value: 300
        color: "#2196F0"
    stroke_width: 0
    color: "#219610"
    data_generator: |
      const data = entity.attributes.period_data || [];
      return data
        .slice(0,96)
        .map((entry) => {
          return [new Date(entry.time).getTime(), entry.price];
        });
    show:
      extremas: false
      in_header: false
  - entity: sensor.okte_min_price_tomorrow
    name: Min tomorrow
    color: red
    data_generator: |
      const now = new Date();
      const minValue = parseFloat(entity.state);
      return [[now.getTime(), minValue]];
    show:
      in_chart: false
      in_header: true
  - entity: sensor.okte_max_price_tomorrow
    name: Max tomorrow
    color: "#2196F0"
    data_generator: |
      const now = new Date();
      const maxValue = parseFloat(entity.state);
      return [[now.getTime(), maxValue]];
    show:
      in_chart: false
      in_header: true
```

### Chart Features

- 📊 **Color-coded bars** based on price ranges
- 🎯 **Current time indicator** (today's chart)
- 📈 **Min/Max/Current prices** in header
- 🖱️ **Interactive zoom** and hover tooltips
- 📱 **Responsive design** for mobile devices

---

## 📋 HTML Price Tables

The OKTE integration generates fully formatted **HTML tables** with color-coded prices for easy visualization.

### Prerequisites

Install the **HTML Template Card** via HACS:
1. Open HACS → Frontend
2. Search for "HTML Template Card"
3. Install and restart Home Assistant

### Table Examples

![HTML Tables](docs/images/en_card_html_table.jpg)

#### Today's Price Table

```yaml
type: custom:html-template-card
content: >-
  {% set out %}
  {% set d = state_attr('sensor.okte_prices_today', 'period_data') or [] %}
  {% set mnp = state_attr('sensor.okte_prices_today', 'min_price') %}
  {% set mxp = state_attr('sensor.okte_prices_today', 'max_price') %}
  <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%; max-width: 400px; border-color: color-mix(in srgb, var(--primary-text-color, #000000) 35%, transparent); color: var(--primary-text-color, #000000);">
  <thead>
  <tr style="background-color: var(--primary-color, #4a90e2); color: var(--text-primary-color, #ffffff);"><th colspan="2" style="text-align: center; font-size: 16px; padding: 10px;">Dnešné ceny elektriky OKTE</th></tr>
  <tr style="background-color: var(--secondary-background-color, #f2f2f2); color: var(--primary-text-color, #000000);"><th style="text-align: center; padding: 2px 7px;">Čas od - do</th><th style="text-align: center; padding: 2px 7px;">Cena [€/MWh]</th></tr>
  </thead>
  <tbody>
  {% if d | count == 0 %}
  <tr><td colspan="2" style="text-align: center; height: 200px; vertical-align: middle;">Údaje nie sú k dispozícii</td></tr>
  {% else %}
  {% for p in d %}
  <tr style="background-color: {{ 'var(--card-background-color, #ffffff)' if loop.index0 % 2 == 0 else 'color-mix(in srgb, var(--primary-text-color, #000000) 6%, var(--card-background-color, #ffffff))' }};"><td style="text-align: center; padding: 1px 7px;">{{ p.period_start }} - {{ p.period_end }}</td><td style="text-align: right; color: {{ 'light-dark(#009000, #5fd35f)' if p.price > 20 else ('light-dark(#d08000, #ffb74d)' if p.price >= 0 else 'light-dark(#d00000, #ff6b6b)') }}; padding: 1px 7px;">{{ '%.2f' | format(p.price) }} €</td></tr>
  {% endfor %}
  {% endif %}
  </tbody>
  {% if d | count > 0 %}
  {% set mn = d | selectattr('price', 'eq', mnp) | first %}
  {% set mx = d | selectattr('price', 'eq', mxp) | first %}
  {% set dr = state_attr('sensor.okte_prices_today', 'date_range').split('-') %}
  <tfoot>
  <tr style="background-color: color-mix(in srgb, var(--primary-color, #4a90e2) 12%, var(--card-background-color, #ffffff));"><td colspan="2" style="padding: 10px; font-size: 14px;">
  <strong>📅 Dátum:</strong> {{ dr[2] }}.{{ dr[1] }}.{{ dr[0] }}<br>
  <strong>📉 Min. cena:</strong> {{ '%.2f' | format(mnp) }} € ({{ mn.period_start }}-{{ mn.period_end }})<br>
  <strong>📈 Max. cena:</strong> {{ '%.2f' | format(mxp) }} € ({{ mx.period_start }}-{{ mx.period_end }})<br>
  <strong>📊 Priemerná cena:</strong> {{ '%.2f' | format(state_attr('sensor.okte_prices_today', 'avg_price')) }} €
  </td></tr>
  </tfoot>
  {% endif %}
  </table>
  {% endset %}{{ out | replace('\n', '') | trim }}
```

#### Tomorrow's Price Table

```yaml
type: custom:html-template-card
content: >-
  {% set out %}
  {% set d = state_attr('sensor.okte_prices_tomorrow', 'period_data') or [] %}
  {% set mnp = state_attr('sensor.okte_prices_tomorrow', 'min_price') %}
  {% set mxp = state_attr('sensor.okte_prices_tomorrow', 'max_price') %}
  <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%; max-width: 400px; border-color: color-mix(in srgb, var(--primary-text-color, #000000) 35%, transparent); color: var(--primary-text-color, #000000);">
  <thead>
  <tr style="background-color: var(--primary-color, #4a90e2); color: var(--text-primary-color, #ffffff);"><th colspan="2" style="text-align: center; font-size: 16px; padding: 10px;">Zajtrajšie ceny elektriky OKTE</th></tr>
  <tr style="background-color: var(--secondary-background-color, #f2f2f2); color: var(--primary-text-color, #000000);"><th style="text-align: center; padding: 2px 7px;">Čas od - do</th><th style="text-align: center; padding: 2px 7px;">Cena [€/MWh]</th></tr>
  </thead>
  <tbody>
  {% if d | count == 0 %}
  <tr><td colspan="2" style="text-align: center; height: 200px; vertical-align: middle;">Údaje nie sú k dispozícii</td></tr>
  {% else %}
  {% for p in d %}
  <tr style="background-color: {{ 'var(--card-background-color, #ffffff)' if loop.index0 % 2 == 0 else 'color-mix(in srgb, var(--primary-text-color, #000000) 6%, var(--card-background-color, #ffffff))' }};"><td style="text-align: center; padding: 1px 7px;">{{ p.period_start }} - {{ p.period_end }}</td><td style="text-align: right; color: {{ 'light-dark(#009000, #5fd35f)' if p.price > 20 else ('light-dark(#d08000, #ffb74d)' if p.price >= 0 else 'light-dark(#d00000, #ff6b6b)') }}; padding: 1px 7px;">{{ '%.2f' | format(p.price) }} €</td></tr>
  {% endfor %}
  {% endif %}
  </tbody>
  {% if d | count > 0 %}
  {% set mn = d | selectattr('price', 'eq', mnp) | first %}
  {% set mx = d | selectattr('price', 'eq', mxp) | first %}
  {% set dr = state_attr('sensor.okte_prices_tomorrow', 'date_range').split('-') %}
  <tfoot>
  <tr style="background-color: color-mix(in srgb, var(--primary-color, #4a90e2) 12%, var(--card-background-color, #ffffff));"><td colspan="2" style="padding: 10px; font-size: 14px;">
  <strong>📅 Dátum:</strong> {{ dr[2] }}.{{ dr[1] }}.{{ dr[0] }}<br>
  <strong>📉 Min. cena:</strong> {{ '%.2f' | format(mnp) }} € ({{ mn.period_start }}-{{ mn.period_end }})<br>
  <strong>📈 Max. cena:</strong> {{ '%.2f' | format(mxp) }} € ({{ mx.period_start }}-{{ mx.period_end }})<br>
  <strong>📊 Priemerná cena:</strong> {{ '%.2f' | format(state_attr('sensor.okte_prices_tomorrow', 'avg_price')) }} €
  </td></tr>
  </tfoot>
  {% endif %}
  </table>
  {% endset %}{{ out | replace('\n', '') | trim }}
```

### Table Features

- 🎨 **Color-coded prices**:
  - 🟢 **Green**: Low prices (good for energy consumption)
  - 🟡 **Yellow**: Medium prices
  - 🔴 **Red**: High prices (reduce consumption)
- 🕐 **Periodical breakdown** from 00:00 to 23:59
- 💰 **Formatted prices** with 2 decimal places
- 📱 **Responsive design** adapts to screen size

---

## 🤖 Automation Examples

The OKTE integration provides powerful tools for creating smart energy automations based on electricity prices.

### Example 1: Battery Charging During Lowest Prices

Automatically charge your battery when electricity prices are at their lowest:

```yaml
automation:
  - alias: "Battery - Charge During Lowest Price Window"
    description: "Charge battery when in lowest price window"
    triggers:
      - trigger: state
        entity_id: binary_sensor.okte_1_detector_lowest_price
        to: "on"
    conditions:
      - condition: numeric_state
        entity_id: sensor.battery_level
        below: 80
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.battery_charger
      - action: notify.mobile_app
        data:
          title: "⚡ Battery Charging Started"
          message: "Charging during low price period ({{ states('sensor.okte_current_price') }} €/MWh)"
  
  - alias: "Battery - Stop Charging After Lowest Price Window"
    description: "Stop charging when lowest price window ends"
    triggers:
      - trigger: state
        entity_id: binary_sensor.okte_1_detector_lowest_price
        to: "off"
    actions:
      - action: switch.turn_off
        target:
          entity_id: switch.battery_charger
      - action: notify.mobile_app
        data:
          title: "🔋 Battery Charging Stopped"
          message: "Low price period ended"
```

### Example 2: Heat Pump Operation During Low Prices

Optimize heat pump operation based on electricity prices:

```yaml
automation:
  - alias: "Heat Pump - Boost During Low Prices"
    description: "Increase heat pump power during lowest price window"
    triggers:
      - trigger: state
        entity_id: binary_sensor.okte_2_detector_lowest_price
        to: "on"
    conditions:
      - condition: numeric_state
        entity_id: sensor.outdoor_temperature
        below: 5
    actions:
      - action: climate.set_temperature
        target:
          entity_id: climate.heat_pump
        data:
          temperature: 23
      - action: number.set_value
        target:
          entity_id: number.heat_pump_power_limit
        data:
          value: 100
```

### Example 3: Avoid High Price Periods

Reduce energy consumption during the most expensive periods:

```yaml
automation:
  - alias: "Energy - Reduce Consumption During High Prices"
    description: "Disable non-essential devices during highest price window"
    triggers:
      - trigger: state
        entity_id: binary_sensor.okte_3_detector_highest_price
        to: "on"
    actions:
      - action: switch.turn_off
        target:
          entity_id:
            - switch.electric_water_heater
            - switch.pool_pump
            - switch.ev_charger
      - action: notify.mobile_app
        data:
          title: "⚠️ High Price Period"
          message: "Non-essential devices disabled ({{ states('sensor.okte_current_price') }} €/MWh)"
```

### Example 4: Dynamic Window Size Adjustment

Automatically adjust the price window size based on battery level:

```yaml
automation:
  - alias: "Battery - Adjust Charging Window Size"
    description: "Increase charging window when battery is very low"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.battery_level
        below: 20
    actions:
      - action: number.set_value
        target:
          entity_id: number.okte_1_lowest_price_window_size
        data:
          value: 24  # 24 periods = 6 hours
  
  - alias: "Battery - Normal Charging Window Size"
    description: "Use normal window size when battery is OK"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.battery_level
        above: 50
    actions:
      - action: number.set_value
        target:
          entity_id: number.okte_1_lowest_price_window_size
        data:
          value: 12  # 12 periods = 3 hours
```

### Example 5: Price Notification

Get notified about tomorrow's lowest price window:

```yaml
automation:
  - alias: "OKTE - Tomorrow's Lowest Price Notification"
    description: "Send notification with tomorrow's cheapest time"
    triggers:
      - trigger: time
        at: "14:30:00"
    actions:
      - action: notify.mobile_app
        data:
          title: "⚡ Tomorrow's Lowest Price Window"
          message: >
            Lowest prices tomorrow:
            {{ state_attr('sensor.okte_1_lowest_price_window_tomorrow', 'start_time_local') }} - 
            {{ state_attr('sensor.okte_1_lowest_price_window_tomorrow', 'end_time_local') }}
            Average: {{ state_attr('sensor.okte_1_lowest_price_window_tomorrow', 'avg_price') }} €/MWh
```

### Automation Tips

💡 **Best Practices:**

1. **Use multiple Calculator devices** for different appliances (battery, heat pump, water heater)
2. **Adjust window sizes** based on your needs (window size in 15-minute periods, e.g. 12 periods = 3 h for battery, 24 periods = 6 h for heat pump)
3. **Combine price detectors** with other conditions (temperature, battery level)
4. **Set sunrise/sunset switches** for more natural automation patterns
5. **Use notifications** to stay informed about price changes

---

## 💬 Support

### 📧 Contact & Links

- **GitHub Repository**: [https://github.com/jozef-moravcik-homeassistant/okte](https://github.com/jozef-moravcik-homeassistant/okte)
- **Issues & Bug Reports**: [GitHub Issues](https://github.com/jozef-moravcik-homeassistant/okte/issues)
- **Author**: Jozef Moravcik
- **Email**: jozef.moravcik@moravcik.eu

### 🐛 Reporting Issues

When reporting issues, please include:
1. Home Assistant version
2. OKTE integration version
3. Relevant log entries from Settings → System → Logs
4. Steps to reproduce the issue
5. Screenshots if applicable

### ⭐ Support Me

If you find this integration useful, please consider:
- ⭐ **Star the repository** on GitHub
- 🐛 **Report bugs** or suggest features
- 📝 **Share your automation examples** with the community
- ☕ **Buy me a coffee** (donation link in repository)

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **OKTE** (Operátor krátkodobého trhu s elektrinou) for providing the public API
- **Home Assistant Community** for continuous support and inspiration
- **All Contributors** who helped improve this integration

---

<div align="center">

**[⬆ Back to Top](#-okte---slovak-energy-market-integration-for-home-assistant)**

Made with ❤️ for the Home Assistant community

</div>
