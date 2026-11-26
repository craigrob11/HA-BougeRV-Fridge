"""BougeRV CRD-series fridge BLE protocol.

Pure Python, no Home Assistant imports, so it can be unit tested on its own.

Frame layout (both directions)::

    55 AA | 01 | CMD | LEN (2 bytes, big endian) | BODY (LEN bytes) | CHECKSUM

* ``CMD`` 0x20  app -> fridge  "read everything" request (empty body)
* ``CMD`` 0x21  fridge settings/state (fridge -> app) and settings writes (app -> fridge)
* ``CMD`` 0x31  battery/power telemetry (fridge -> app); a 1-field 0x31 frame
                (field 0x32) is the acknowledgement sent after every write
* ``CHECKSUM``  sum of every preceding byte, low 8 bits

``BODY`` is a list of records::

    FIELD (1) | TYPE (1) | LENGTH (2, big endian) | VALUE (LENGTH bytes)

Record types seen: 0x00 raw block, 0x01 boolean, 0x02 32-bit integer,
0x03 text, 0x04 enumeration.

Every one of the 700+ frames captured during the 2026 Vera Wanda tests parses
cleanly with this layout and passes its checksum.
"""

from __future__ import annotations

from dataclasses import dataclass

HEADER = b"\x55\xaa"
VERSION = 0x01
MAX_BODY = 512  # largest frame seen is 166 bytes

CMD_READ = 0x20
CMD_SETTINGS = 0x21
CMD_TELEMETRY = 0x31

TYPE_RAW = 0x00
TYPE_BOOL = 0x01
TYPE_INT32 = 0x02
TYPE_TEXT = 0x03
TYPE_ENUM = 0x04

# --- Settings / state fields (CMD 0x21) ------------------------------------
F_MAIN_POWER = 0x01  # bool: 1 = on
F_LEFT_ACTUAL = 0x02  # int32, current display unit
F_LEFT_SETPOINT = 0x03  # int32, current display unit
F_RIGHT_ACTUAL = 0x04
F_RIGHT_SETPOINT = 0x05
F_UNIT = 0x06  # enum: 0 = °C, 1 = °F
F_PROTECTION = 0x07  # enum: 0 = Low, 1 = Medium, 2 = High
F_COMPRESSOR = 0x08  # enum 0/1: 1 = compressor running (confirmed in van tests)
F_EXTERNAL_POWER = 0x09  # bool: 12 V supply connected (confirmed in van tests)
F_MODE = 0x0B  # enum: 0 = Eco, 1 = Max
# Compartments. Reported as a bitmask (bit0 = left on, bit1 = right on), but
# written as one per-side command: 0 = left off, 1 = left on, 2 = right off,
# 3 = right on (confirmed in van tests). The fridge will not leave both sides
# off: turning off the last side that is on switches the other one on.
F_COMPARTMENTS = 0x12
F_FIRMWARE = 0x10  # text, fridge firmware e.g. "1.0.2"
F_INPUT_VOLTAGE = 0x16  # int32, volts x10

# --- Battery / power telemetry fields (CMD 0x31) ---------------------------
F_ACK = 0x32
F_BATTERY_SOC = 0x33  # int32, percent
F_PACK_VOLTAGE = 0x35  # int32, millivolts (= sum of the 5 cell voltages)
F_BATTERY_CURRENT = (
    0x36  # 16-bit signed milliamps in the low 2 bytes; + charging, - discharging
)
F_BATTERY_DETAIL = 0x37  # raw block, see decode_battery_detail()
F_USB_C_INPUT = 0x3B  # int32, watts
F_INPUT_3C = 0x3C  # int32, watts - not yet identified, always 0 so far
F_SOLAR_INPUT = 0x3D  # int32, watts (confirmed in van tests)
F_INPUT_3E = 0x3E  # int32, watts - not yet identified, always 0 so far
F_DC_INPUT = 0x3F  # int32, watts
F_BATTERY_FIRMWARE = 0x41  # text, e.g. "0.1.8"
F_PORT_POWER = 0x42  # int32, watts - total through all ports, in AND out

LEFT_BIT = 0x01
RIGHT_BIT = 0x02

UNITS = {0: "°C", 1: "°F"}
PROTECTION_LEVELS = {0: "Low", 1: "Medium", 2: "High"}
MODES = {0: "Eco", 1: "Max"}

# Setpoint limits in each display unit (fridge range is -20 °C .. +20 °C).
SETPOINT_LIMITS = {"°C": (-20, 20), "°F": (-4, 68)}


class ProtocolError(ValueError):
    """Raised for frames that cannot be built or decoded."""


def checksum(data: bytes) -> int:
    return sum(data) & 0xFF


def build_frame(cmd: int, body: bytes = b"") -> bytes:
    if len(body) > 0xFFFF:
        raise ProtocolError("body too long")
    frame = HEADER + bytes([VERSION, cmd]) + len(body).to_bytes(2, "big") + body
    return frame + bytes([checksum(frame)])


def build_record(field: int, rtype: int, value: bytes) -> bytes:
    return bytes([field, rtype]) + len(value).to_bytes(2, "big") + value


def read_request() -> bytes:
    """``55AA 0120 0000 20`` - ask the fridge for all settings and telemetry."""
    return build_frame(CMD_READ)


def _write(field: int, rtype: int, value: bytes) -> bytes:
    return build_frame(CMD_SETTINGS, build_record(field, rtype, value))


def cmd_main_power(on: bool) -> bytes:
    return _write(F_MAIN_POWER, TYPE_BOOL, bytes([1 if on else 0]))


def cmd_compartment(right: bool, on: bool) -> bytes:
    """Switch one compartment: 0 left off, 1 left on, 2 right off, 3 right on."""
    value = (2 if right else 0) + (1 if on else 0)
    return _write(F_COMPARTMENTS, TYPE_ENUM, bytes([value]))


def cmd_setpoint(right: bool, value: int) -> bytes:
    field = F_RIGHT_SETPOINT if right else F_LEFT_SETPOINT
    return _write(field, TYPE_INT32, int(value).to_bytes(4, "big", signed=True))


def cmd_mode(mode: str) -> bytes:
    return _write(F_MODE, TYPE_ENUM, bytes([_key_for(MODES, mode)]))


def cmd_protection(level: str) -> bytes:
    return _write(F_PROTECTION, TYPE_ENUM, bytes([_key_for(PROTECTION_LEVELS, level)]))


def cmd_unit(unit: str) -> bytes:
    return _write(F_UNIT, TYPE_ENUM, bytes([_key_for(UNITS, unit)]))


def _key_for(table: dict[int, str], label: str) -> int:
    for key, value in table.items():
        if value == label:
            return key
    raise ProtocolError(f"unknown option {label!r}")


@dataclass(frozen=True)
class Record:
    field: int
    rtype: int
    value: bytes

    def decoded(self) -> int | bool | str | bytes:
        if self.rtype == TYPE_INT32 and len(self.value) == 4:
            return int.from_bytes(self.value, "big", signed=True)
        if self.rtype == TYPE_BOOL and len(self.value) == 1:
            return bool(self.value[0])
        if self.rtype == TYPE_ENUM and len(self.value) == 1:
            return self.value[0]
        if self.rtype == TYPE_TEXT:
            return self.value.decode("ascii", "replace")
        return self.value


@dataclass(frozen=True)
class Frame:
    cmd: int
    records: tuple[Record, ...]
    raw: bytes

    def fields(self) -> dict[int, int | bool | str | bytes]:
        return {r.field: r.decoded() for r in self.records}

    @property
    def is_ack(self) -> bool:
        return self.cmd == CMD_TELEMETRY and [r.field for r in self.records] == [F_ACK]


def parse_records(body: bytes) -> tuple[Record, ...]:
    records: list[Record] = []
    i = 0
    while i < len(body):
        if i + 4 > len(body):
            raise ProtocolError(f"truncated record header at byte {i}")
        length = int.from_bytes(body[i + 2 : i + 4], "big")
        end = i + 4 + length
        if end > len(body):
            raise ProtocolError(f"record 0x{body[i]:02X} overruns frame")
        records.append(Record(body[i], body[i + 1], bytes(body[i + 4 : end])))
        i = end
    return tuple(records)


def parse_frame(frame: bytes) -> Frame:
    if len(frame) < 7 or frame[:2] != HEADER or frame[2] != VERSION:
        raise ProtocolError("not a BougeRV frame")
    length = int.from_bytes(frame[4:6], "big")
    if len(frame) != 7 + length:
        raise ProtocolError("frame length mismatch")
    if frame[-1] != checksum(frame[:-1]):
        raise ProtocolError("bad checksum")
    return Frame(frame[3], parse_records(frame[6:-1]), bytes(frame))


class FrameAssembler:
    """Turns a stream of BLE notifications into complete, checksummed frames.

    Frames normally arrive whole, but this also copes with a frame split
    across notifications or several frames in one notification, and skips
    any garbage between frames.
    """

    def __init__(self) -> None:
        self._buf = bytearray()
        self.dropped = 0

    def feed(self, data: bytes) -> list[Frame]:
        self._buf += data
        frames: list[Frame] = []
        while True:
            start = self._buf.find(HEADER)
            if start < 0:
                # Keep a trailing 0x55 in case the header is split.
                keep = 1 if self._buf[-1:] == b"\x55" else 0
                self.dropped += len(self._buf) - keep
                del self._buf[: len(self._buf) - keep]
                return frames
            if start:
                self.dropped += start
                del self._buf[:start]
            if len(self._buf) < 6:
                return frames
            body_len = int.from_bytes(self._buf[4:6], "big")
            if self._buf[2] != VERSION or body_len > MAX_BODY:
                # Not a plausible frame header; skip it and resync.
                self.dropped += 2
                del self._buf[:2]
                continue
            total = 7 + body_len
            if len(self._buf) < total:
                return frames
            candidate = bytes(self._buf[:total])
            try:
                frames.append(parse_frame(candidate))
                del self._buf[:total]
            except ProtocolError:
                # Not a real frame start; skip this header and resync.
                self.dropped += 2
                del self._buf[:2]


def decode_battery_detail(block: bytes) -> dict[str, object]:
    """Field 0x37 (35 bytes), little-endian 16-bit values.

    Bytes 0-9    five cell voltages, mV   (sum matches field 0x35 in 465/469 captures)
    Bytes 10-11  charge current, mA
    Bytes 12-13  discharge current, mA     (these two track field 0x36)
    Bytes 14-21  four temperatures, 0.1 K  (25-36 °C in captures; exact sensors unknown)
    Byte  22     battery %                 (matches field 0x33 whenever both are present)
    Remaining bytes not yet understood.
    """
    if len(block) < 23:
        return {}
    u16 = [int.from_bytes(block[i : i + 2], "little") for i in range(0, 22, 2)]
    out: dict[str, object] = {
        "cell_voltages": [v / 1000 for v in u16[0:5]],
        "battery_temperatures": [round(v / 10 - 273.15, 1) for v in u16[7:11]],
    }
    if 0 <= block[22] <= 100:
        out["battery_from_detail"] = block[22]
    return out


def _no_battery(f: dict[int, object]) -> bool:
    """True for the zero-filled telemetry frame a fridge without a battery sends.

    Seen from a CRD2 2.0 with no battery: battery firmware (0x41) is an empty
    string and the cell block (0x37) is empty. With a battery fitted the
    firmware is e.g. "0.1.8" and the cell block is 35 bytes. Field 0x32 is NOT
    a reliable indicator (it is sometimes false with a battery fitted).
    """
    return f.get(F_BATTERY_FIRMWARE) == "" or f.get(F_BATTERY_DETAIL) == b""


def decode_state(frames: list[Frame]) -> dict[str, object]:
    """Map frames to the friendly keys used by the Home Assistant entities.

    Only fields that are actually present are returned, so callers can merge
    the result into previously known state (partial frames are normal).
    """
    out: dict[str, object] = {}
    for frame in frames:
        if frame.is_ack:
            continue
        f = frame.fields()
        if frame.cmd == CMD_SETTINGS:
            if F_MAIN_POWER in f:
                out["main_power"] = bool(f[F_MAIN_POWER])
            for field, key in (
                (F_LEFT_ACTUAL, "left_actual"),
                (F_LEFT_SETPOINT, "left_setpoint"),
                (F_RIGHT_ACTUAL, "right_actual"),
                (F_RIGHT_SETPOINT, "right_setpoint"),
            ):
                if isinstance(f.get(field), int):
                    out[key] = f[field]
            if F_UNIT in f:
                out["unit"] = UNITS.get(f[F_UNIT], "°C")
            if F_COMPRESSOR in f:
                out["compressor"] = bool(f[F_COMPRESSOR])
            if F_EXTERNAL_POWER in f:
                out["external_power"] = bool(f[F_EXTERNAL_POWER])
            if F_PROTECTION in f:
                out["protection"] = PROTECTION_LEVELS.get(f[F_PROTECTION])
            if F_MODE in f:
                out["mode"] = MODES.get(f[F_MODE])
            if isinstance(f.get(F_COMPARTMENTS), int):
                out["compartments"] = f[F_COMPARTMENTS]
                out["left_on"] = bool(f[F_COMPARTMENTS] & LEFT_BIT)
                out["right_on"] = bool(f[F_COMPARTMENTS] & RIGHT_BIT)
            if isinstance(f.get(F_INPUT_VOLTAGE), int):
                out["voltage"] = f[F_INPUT_VOLTAGE] / 10
            if isinstance(f.get(F_FIRMWARE), str):
                out["firmware"] = f[F_FIRMWARE]
        elif frame.cmd == CMD_TELEMETRY:
            if _no_battery(f):
                # Fridges without the battery still send this frame, all zeros.
                out["battery_present"] = False
                continue
            out["battery_seen"] = True
            out["battery_present"] = True
            detail = f.get(F_BATTERY_DETAIL)
            if isinstance(detail, bytes):
                d = decode_battery_detail(detail)
                if "battery_from_detail" in d:
                    out["battery"] = d.pop("battery_from_detail")
                out.update(d)
                cells = d.get("cell_voltages")
                if cells:
                    out["cell_min"] = min(cells)
                    out["cell_max"] = max(cells)
                temps = d.get("battery_temperatures")
                if temps:
                    out["battery_temperature"] = max(temps)
            soc = f.get(F_BATTERY_SOC)  # dedicated field wins over the copy in 0x37
            if isinstance(soc, int) and 0 <= soc <= 100:
                out["battery"] = soc
            if isinstance(f.get(F_PACK_VOLTAGE), int):
                out["pack_voltage"] = f[F_PACK_VOLTAGE] / 1000
            if isinstance(f.get(F_BATTERY_CURRENT), int):
                raw = f[F_BATTERY_CURRENT] & 0xFFFF
                out["battery_current"] = (raw - 0x10000 if raw & 0x8000 else raw) / 1000
            if "pack_voltage" in out and "battery_current" in out:
                out["battery_power"] = round(
                    out["pack_voltage"] * out["battery_current"], 1
                )
            for field, key in (
                (F_USB_C_INPUT, "usb_c_input"),
                (F_DC_INPUT, "dc_input"),
                (F_INPUT_3C, "input_3c"),
                (F_SOLAR_INPUT, "solar_input"),
                (F_INPUT_3E, "input_3e"),
                (F_PORT_POWER, "port_power"),
            ):
                if isinstance(f.get(field), int) and f[field] >= 0:
                    out[key] = f[field]
            if isinstance(f.get(F_BATTERY_FIRMWARE), str):
                out["battery_firmware"] = f[F_BATTERY_FIRMWARE]
    return out
