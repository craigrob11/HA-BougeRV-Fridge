# Changelog

## Unreleased

- **Phone alerts blueprint**: warm compartment, switched off, offline, external
  power lost, low battery, with optional "back to normal" messages. Critical
  alert level (sounds on silent) by default.
- Fridges without the internal battery: if the battery option is ticked by
  mistake, battery sensors now show unavailable instead of 0 % (which would
  also have triggered a false low-battery alert). Found from a tester's
  diagnostics (CRD2 2.0, firmware 1.0.1).

## 1.0.0 (first public release)

Changes since the private V3 test builds:

**Fixes**
- Battery % no longer drops to 0 (or jumps to the DC-input wattage). It is now
  read only from its own field (0x33) and keeps its last value when the fridge
  sends a frame without it.
- Frames are decoded record by record and checksum-verified, instead of
  searching for byte patterns. Two frames arriving in one Bluetooth message
  (seen in real captures) are both handled.
- The reply is read until it is complete (up to 4 s) instead of a fixed 1.2 s wait.
- Setpoint slider range follows the temperature unit (°C or °F).

**New**
- Switches and status sensors for main power and each compartment.
- Setup asks whether the internal battery is fitted; battery entities are only
  created when it is. Changeable later, along with the update interval.
- Setup also asks for °C or °F (defaults to Home Assistant's unit) and sets the
  fridge to it once.
- Automatic Bluetooth discovery (`SYZ-CRD…`).
- Fridge and battery firmware versions shown on the device page.
- Diagnostics download with the last 2000 messages, showing what changed in each, and frame-level debug logging.
- Three disabled "unidentified input" sensors to help decode the solar input.
- Battery voltage, current (+/−), power, temperature and per-cell voltages.
- Compressor running and External power sensors (from captures; being confirmed).
- Live capture switch, capture marker button and capture note, so decoding tests
  can be done entirely in Home Assistant. These, and the sensors still being
  confirmed, are hidden (disabled) by default.

**Breaking (test builds only)**
- Integration domain is now `bougerv_fridge` (was `bougerv`). Remove the old
  integration and folder, then set the fridge up again.
