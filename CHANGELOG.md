# OKTE

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/jozef-moravcik-homeassistant/okte)](https://github.com/jozef-moravcik-homeassistant/okte/releases)

OKTE Slovak Energy Market

## v1.01.04

## 📋 Changes
- Added a "Data Failover System": if the data cannot be downloaded from the OKTE portal (e.g., the portal or the internet connection is unavailable), the prices are calculated from the averages of historical prices and all related sensors are filled with them as if the connection were working.
- Valid data for the current day that are already stored or shown in the sensors are never overwritten by calculated data; the calculated data are used for the following day only. If there are no valid data for the current day, calculated data are used for the current day as well.
- Added a new "Data Failover Mode" select to the Master device configuration:
  - Averages by week days – the averages are calculated from the prices of the same weekdays (e.g., the last X Fridays),
  - Averages from all days – the averages are calculated from the prices of the last X days (1–30),
  - Disabled – the failover system is switched off; during a long outage the sensors stay empty.
- Added parameters to the Master device configuration: the number of weeks and the number of days included in the averages.
- The price history is stored in HA storage. If the averages are not yet available (e.g., after installation or after enabling the failover system), they are initialised from the statistics of sensor.okte_current_price and then recalculated after each successful data download from OKTE.
- Added a new "Reset Failover History" button (button.okte_reset_failover_history) to the Master device: it deletes the stored price history and rebuilds it from the statistics of sensor.okte_current_price and the real prices already downloaded from OKTE. It does nothing when the failover system is disabled.
- Added a new "Failover Data" sensor (sensor.okte_failover_data) – "true" when the sensors contain calculated data, otherwise "false".
- The "Failover Data" sensor has the attributes failover_data_today and failover_data_tomorrow, which indicate whether the sensors contain calculated averages (true) or real data (false) for today and for tomorrow.
- The "Failover Data" sensor also has the attributes "Period data Monday" … "Period data Sunday" with the calculated averages of all periods for each day of the week, in the same structure as the period_data attribute of sensor.okte_prices_today.
- The "Failover Data" sensor was added to the list of entities recommended to be excluded from the recorder (large attributes).

## v1.01.03

## 📋 Changes
- Added a time entity to delay the start of the search window after sunrise.
- Added a time entity to shorten the end of the search window before sunset.
- Data for the following day is automatically moved to the current day at midnight, therefore, it is not necessary to download data from the API at midnight.
- Data is now saved in HA storage, ensuring that it remains in the entities even after an HA restart or in the event of a failure to download data from the OKTE portal (e.g., if the OKTE portal is unavailable).
- Updated documentation

## v1.01.02

## 📋 Changes
- Logo was created and added

## v1.01.01

## 📋 Changes
- some minor fixes were made
