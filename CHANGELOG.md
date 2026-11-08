# OKTE

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/jozef-moravcik-homeassistant/okte)](https://github.com/jozef-moravcik-homeassistant/okte/releases)

OKTE Slovak Energy Market

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
