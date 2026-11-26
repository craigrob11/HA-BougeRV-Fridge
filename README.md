# BougeRV Fridge for Home Assistant

Local Bluetooth control and monitoring of BougeRV dual-zone compressor fridges
(the ones that advertise as `SYZ-CRD…`, e.g. the CRD2 2.0). No cloud, no account.

Works through Home Assistant's own Bluetooth: a built-in adapter or an
ESPHome Bluetooth proxy (with active connections enabled).

> Independent community project, not affiliated with or endorsed by BougeRV.
> The protocol was worked out by recording the BougeRV app's Bluetooth traffic.

## What you get

| Entity | Type | Notes |
|---|---|---|
| Power | switch + status | Main fridge power |
| Left compartment / Right compartment | switch + status | Each side on/off |
| Left setpoint / Right setpoint | number | −20 to +20 °C (−4 to 68 °F) |
| Left temperature / Right temperature | sensor | Actual compartment temperature |
| Input voltage | sensor | Supply voltage at the fridge |
| Cooling mode | select | Eco / Max |
| Battery protection | select | Low / Medium / High cut-off |
| Temperature unit | select | °C / °F (changes the fridge display too) |
| Compressor | binary sensor (diagnostic) | Running / not running |

**With the optional BougeRV internal battery** (choose this when adding the fridge,
or later under *Configure*):

| Entity | Type | Notes |
|---|---|---|
| Battery | sensor | Charge level in % |
| Charging | binary sensor | On when any input is supplying power |
| DC input / Solar input / USB-C input | sensor | Watts going in |
| USB output | sensor | Watts drawn from the USB outlets |
| Battery voltage / Battery current / Battery power | sensor | Current is + charging, − discharging |
| External power | binary sensor (diagnostic) | 12 V supply connected |
| Lowest / highest cell voltage | sensor (diagnostic) | |
| Battery temperature | sensor (diagnostic, hidden) | |
| Cell 1–5 voltage | sensor (diagnostic, disabled) | |
| Total port power | sensor (diagnostic, disabled) | All ports, in **and** out |

## Installation

### HACS (recommended)

1. HACS → three-dot menu → **Custom repositories**
2. Add `https://github.com/craigrob11/HA-BougeRV-Fridge`, type **Integration**
3. Install **BougeRV Fridge** and restart Home Assistant

### Manual

Copy `custom_components/bougerv_fridge` into your Home Assistant `config/custom_components/` folder and restart.

## Setup

1. **Close the BougeRV app on your phone.** The fridge accepts only one Bluetooth connection.
2. The fridge should be discovered automatically (*Settings → Devices & services*).
   If not, choose **Add integration → BougeRV Fridge**.
3. Say whether the internal battery is fitted, and choose °C or °F.
   The unit is sent to the fridge once (its own display changes too); change it
   later with the *Temperature unit* control.

The integration connects briefly each update (default every 30 s) and then
disconnects, so the phone app can still be used in between.

## Phone alerts (blueprint)

A ready-made automation that sends phone notifications when:

* a compartment is warmer than its setpoint by a set amount for a set time
* the fridge or a compartment is switched off
* the fridge goes **offline** (lost power, blown fuse, out of Bluetooth range)
* the external 12 V supply is lost (battery models)
* the internal battery is low

plus optional "back to normal" messages.

[![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fcraigrob11%2FHA-BougeRV-Fridge%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fbougerv_fridge%2Ffridge_alerts.yaml)

Then *Settings → Automations → Create automation → BougeRV Fridge alerts*, pick
the fridge and your phones, and save.

**Alert level** defaults to **Critical**, which sounds even when the phone is on
silent or in Focus / Do Not Disturb:

* **iPhone:** iOS Settings → Notifications → Home Assistant → allow **Critical Alerts**.
* **Android:** critical alerts play on the alarm stream.

## Coming from the early test builds

The pre-release test builds used the integration name `bougerv`. Delete that
integration and its `custom_components/bougerv` folder, restart, then install
this one and set the fridge up again.

## Troubleshooting and reporting problems

* **Debug log:** *Settings → Devices & services → BougeRV Fridge → Enable debug logging*.
  Every frame sent and received is logged with its decoded fields.
* **Diagnostics:** on the same page, three-dot menu → **Download diagnostics**.
  This contains the last 2000 Bluetooth messages, with the fields that changed
  in each. Please attach it to any issue.

### Test tools

For decoding how the fridge works (for example to add support for another
model), turn on **Show test tools** under *Settings → Devices & services →
BougeRV Fridge → Configure*. They appear in the device's **Configuration** card:

* **Live capture** (switch): holds the connection open and records every
  message as it happens. Turns itself off after 30 minutes; the phone app
  can't connect meanwhile.
* **Add capture marker** (button) and **Capture note** (text): label what you
  were doing at that moment in the recording.
* **Test command** (text): sends one raw setting, typed as field and value in
  hex (e.g. `12 01`). Only use it if you know what the field does.
* Then **Download diagnostics**: each message shows only the fields that
  changed, next to your markers and notes.

Turn the option off again for normal use; the tools are removed.

## Known limits

* The fridge won't have both compartments off, so turning off the last one
  that is on is refused; use the main Power switch instead.
* The lid/light is not reported by the fridge, so there is no lid sensor.
* Tested on a CRD2 2.0 (fridge firmware 1.0.2, battery firmware 0.1.8).
  Reports from other models are very welcome.

## Licence

MIT
