# BioLite Backup for Home Assistant

A custom Home Assistant integration for the [BioLite BaseCamp HomeCharge](https://bioliteenergy.com/)
backup battery (WiFi-capable, cloud-connected via ESP RainMaker).

BioLite does not publish a public API. This integration was built by reverse-engineering
BioLite's cloud REST API and the proprietary binary `device-state` blob it returns, by
diffing samples against BioLite's own app under known physical conditions (charging from
grid, full load, battery-only, etc). There is no guarantee BioLite's backend will keep
working the same way -- if they change their API, this integration may break without notice.

## What it provides

One Home Assistant device ("BioLite Backup") with:

- Core / Extend battery state of charge (%)
- Core temperature
- AC input / AC output / DC-DC link / gate-link power (W)
- Core rated capacity (Wh)
- Cloud connectivity (binary sensor)
- "On Battery" (binary sensor) -- true when output is being sourced from the battery
  inverter rather than passed through from the grid

## Installation

### Via HACS (custom repository)

1. HACS -> Integrations -> (top-right) -> Custom repositories
2. Add this repo's URL, category "Integration"
3. Install "BioLite Backup", restart Home Assistant

### Manual

Copy `custom_components/biolite` into your Home Assistant `config/custom_components/`
folder and restart Home Assistant.

## Setup

Settings -> Devices & Services -> Add Integration -> "BioLite Backup" -> enter your
BioLite account email/password. Credentials are only used to call BioLite's own login
endpoint and are never sent anywhere else.

## Notes / caveats

- This relies entirely on reverse-engineered, undocumented behavior of BioLite's backend.
- Only the single `device-state` string param is exposed by BioLite's device schema --
  everything here is decoded out of that one opaque blob.
- Some fields in the raw blob are still unidentified/unused and are intentionally not
  surfaced as entities.

## Future work

This integration is cloud-polling only (`iot_class: cloud_polling`) -- it depends on
internet connectivity to reach BioLite's backend, which is a real limitation for a
backup-power device you may most want visibility into during an outage.

A fully local (no-internet) path was investigated and ruled out for Wi-Fi: the unit
does not advertise ESP RainMaker's local-control service and has no open TCP ports at
all. A BLE-based local path looks more promising (the unit exposes a custom BLE
provisioning service with endpoints named `device-state` and `hcp-data`, matching the
cloud API's data model) but was not completed -- it requires implementing Espressif's
protocomm session handshake over BLE, which is a separate, substantial piece of work.
Contributions welcome.
