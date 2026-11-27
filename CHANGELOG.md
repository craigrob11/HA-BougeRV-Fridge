# Changelog

## 1.1.0

Everything below was confirmed on a CRD2 2.0 with the battery, in the van.

**Fixes**
- **Left/right compartment switches.** The fridge takes a per-side command
  (0 left off, 1 left on, 2 right off, 3 right on), not the bitmask it
  reports, so the old switches turned the wrong side off. The fridge won't
  have both sides off, so turning off the last one is refused; use Power.
- Fridges without the internal battery: if the battery option is ticked by
  mistake, battery sensors show unavailable instead of 0 % (which would also
  have triggered a false low-battery alert).

**New**
- **Solar input** sensor (field 0x3D).
- **USB-C input** confirmed (field 0x3B).
- **USB output** sensor: total port power (0x42) minus the inputs.
- **Compressor** and **External power** confirmed and enabled by default.
- **Phone alerts blueprint:** compartment warm, fridge or compartment
  switched off, offline, external 12 V lost, low battery. Critical alerts
  (sound on silent) by default, choice of iPhone sound, optional repeat until
  fixed, and optional "back to normal" messages.
- **Show test tools** option under *Configure* (off by default) for decoding:
  Live capture, capture marker and note, and a new Test command. If you used
  the tools before, turn the option on after updating.
- Brand icon now fills its square.

**Not possible**
- Lid/light: the fridge does not report it, so there is no lid sensor.

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
