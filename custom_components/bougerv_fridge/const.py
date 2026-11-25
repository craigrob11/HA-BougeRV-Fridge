"""Constants for the BougeRV integration."""

from __future__ import annotations

DOMAIN = "bougerv_fridge"
MANUFACTURER = "BougeRV"

# GATT: one characteristic carries writes and notifications.
SERVICE_UUID = "00001234-0000-1000-8000-00805f9b34fb"
DATA_CHAR_UUID = "00001237-0000-1000-8000-00805f9b34fb"
LOCAL_NAME_PREFIX = "SYZ-CRD"

CONF_HAS_BATTERY = "has_battery"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_INITIAL_UNIT = "initial_unit"

DEFAULT_SCAN_INTERVAL = 30  # seconds
MIN_SCAN_INTERVAL = 15
MAX_SCAN_INTERVAL = 600

# How long to listen for the fridge's reply after asking for its state.
POLL_TIMEOUT = 4.0
# After a write, wait this long for the acknowledgement before re-reading.
WRITE_SETTLE = 0.5
# Battery entities go unavailable if no battery telemetry for this many polls.
BATTERY_STALE_POLLS = 3

# Recent raw frames, markers and notes kept for the diagnostics download.
RAW_HISTORY = 2000

# Live capture switches itself off after this long (it blocks the phone app).
LIVE_CAPTURE_LIMIT = 30 * 60  # seconds
