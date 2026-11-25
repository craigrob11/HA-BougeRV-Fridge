# 1.0.0 test plan (before public release)

Everything is done in Home Assistant: no nRF Connect, no copying logs.

## How a capture works

On the BougeRV device page (*Settings → Devices & services → BougeRV Fridge*)
the **Configuration** section has three test tools:

| Control | What it does |
|---|---|
| **Live capture** (switch) | Keeps Home Assistant connected and records every message from the fridge the instant it arrives. Turns itself off after 30 min. The BougeRV phone app can't connect while it's on. |
| **Add capture marker** (button) | Stamps `MARKER 1`, `MARKER 2` … into the recording at that moment. |
| **Capture note** (text) | Whatever you type is stamped into the recording, e.g. `lid open left`. |

These are **hidden by default**. Enable them first: device page →
**"+N entities not shown"** → tap each → settings cog → **Enabled**. Do the same
for **Compressor**, **External power**, **Battery temperature** and the three
**Unidentified input** sensors.

When a test is done: three-dot menu → **Download diagnostics**, and send me the
file. Each message in it lists only the fields that **changed**, next to your
markers and notes, so the answer is usually obvious at a glance.

Tip: a 1-minute gap between steps makes the recording easy to read.

## 1. Fresh install (Vera Wanda)
- [ ] Old V3 integration deleted, `/config/custom_components/bougerv` folder deleted, HA restarted.
- [ ] HACS → Custom repositories → `https://github.com/craigrob11/HA-BougeRV-Fridge` (Integration).
- [ ] Install **BougeRV Fridge**, restart. No errors in the log.
- [ ] Fridge appears under *Discovered*. Setup asks battery yes/no and °C/°F.
- [ ] Pick the unit the fridge is NOT on: fridge display changes. Restart HA: not sent again.
- [ ] Entities created as listed in the README; hidden ones under "+N entities not shown".
- [ ] Rebuild the dashboard cards with the new entity IDs.

## 2. Battery reading (the original bug)
- [ ] Leave running for a few hours. Battery % history never drops to 0 or jumps.
- [ ] Battery %, Battery voltage and Battery current look sensible against the app
      (disable the integration briefly so the app can connect).

## 3. Controls (does the fridge change, and does HA show it?)
- [ ] Left setpoint up and down, including a negative value.
- [ ] Right setpoint up and down.
- [ ] Cooling mode Eco ↔ Max.
- [ ] Battery protection Low / Medium / High.
- [ ] Temperature unit °C → °F: slider range becomes −4…68; set a °F setpoint and
      check the fridge display; then back to °C.
- [ ] Main power off → on.
- [ ] Left off → on (right must stay on). Right off → on (left must stay on).
- [ ] Left off, then try Right off: HA should refuse with a clear message.

## 4. Lid sensor (Live capture on)
- [ ] Note "lid test start", wait 1 min with both lids closed.
- [ ] Marker, open the LEFT lid (light on), wait 15 s, marker, close it. Wait 1 min.
- [ ] Repeat for the RIGHT lid.
- [ ] Repeat both once more. Download diagnostics.

## 5. Compressor (Live capture on, somewhere quiet)
- [ ] Each time you hear the compressor start: marker. Each time it stops: marker.
      Get two or three cycles (changing a setpoint a few degrees colder starts it).
- [ ] Watch the **Compressor** entity: does it follow?

## 6. External power (Live capture on, battery fitted)
- [ ] Marker, unplug the 12 V supply, wait 1 min.
- [ ] Marker, plug it back in, wait 1 min.
- [ ] Watch **External power** and **Battery current** (should go negative, then positive).

## 7. Solar input (Live capture on, panel, steady daylight)
- [ ] Note "solar off", wait 1 min. Marker, connect the panel, wait 2 min.
- [ ] Note the BougeRV app's solar watts afterwards. Download diagnostics.

## 8. Battery option
- [ ] *Configure* → untick battery: battery entities are removed, rest still works.
- [ ] Tick it again: they come back.
- [ ] Remove the battery from the fridge: battery entities go unavailable
      within ~3 updates (not 0 %).

## 9. Friend's fridge (no battery)
- [ ] Section 1, answering "no battery": no battery entities created.
- [ ] Section 3 controls all work.
