"""Diagnostics download: decoded state plus recent raw Bluetooth frames, markers and notes.

Settings > Devices & services > BougeRV > (three dots) > Download diagnostics.
This is what to send when reporting a problem or helping decode a new field.

Each received frame lists its decoded fields and, under "changed", only the
fields whose value differs from the last time that field was seen. Fields that
change on every frame (the battery detail blocks) are left out of "changed".
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .protocol import F_BATTERY_DETAIL, FrameAssembler

NOISY_FIELDS = {F_BATTERY_DETAIL, 0x38}


def _fmt(value: Any) -> Any:
    return value.hex(" ").upper() if isinstance(value, bytes) else value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    last_seen: dict[tuple[int, int], Any] = {}
    events = []
    for ts, kind, payload in coordinator.client.history:
        item: dict[str, Any] = {
            "time": datetime.fromtimestamp(ts, UTC)
            .astimezone()
            .isoformat(timespec="milliseconds"),
            "dir": kind,
        }
        if kind == "note":
            item["note"] = payload
        else:
            item["hex"] = payload
        if kind == "rx":
            parsed = FrameAssembler().feed(bytes.fromhex(payload.replace(" ", "")))
            if parsed:
                frame = parsed[0]
                fields = frame.fields()
                item["fields"] = {f"{k:02X}": _fmt(v) for k, v in fields.items()}
                changed = {}
                for field, value in fields.items():
                    key = (frame.cmd, field)
                    if (
                        key in last_seen
                        and last_seen[key] != value
                        and field not in NOISY_FIELDS
                    ):
                        changed[f"{field:02X}"] = [_fmt(last_seen[key]), _fmt(value)]
                    last_seen[key] = value
                if changed:
                    item["changed"] = changed
        events.append(item)

    return {
        "options": dict(entry.options),
        "live_capture": coordinator.client.live,
        "state": coordinator.data,
        "battery_available": coordinator.battery_available,
        "last_update_success": coordinator.last_update_success,
        "events": events,
    }
