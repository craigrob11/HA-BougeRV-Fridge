"""Protocol tests against real frames captured from a BougeRV CRD2 2.0.

Run with:  python -m pytest tests  (or: python tests/test_protocol.py)
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "bougerv_protocol", ROOT / "custom_components" / "bougerv_fridge" / "protocol.py"
)
p = importlib.util.module_from_spec(_spec)
sys.modules["bougerv_protocol"] = p
_spec.loader.exec_module(p)

# Each entry is one BLE notification exactly as logged by nRF Connect.
NOTIFICATIONS = [
    bytes.fromhex(h)
    for h in json.loads((Path(__file__).parent / "captured_frames.json").read_text())
]


def _split(notifications):
    asm = p.FrameAssembler()
    frames = []
    for n in notifications:
        frames += [f.raw for f in asm.feed(n)]
    assert asm.dropped == 0
    return frames


FRAMES = _split(NOTIFICATIONS)


def test_two_frames_in_one_notification():
    # Seen for real: a settings frame and the write acknowledgement joined together.
    joined = h(
        "55AA 0121 0010 0202 0004 0000 0002 0402 0004 FFFF FFFF 41"
        "55AA 0131 0005 3201 0001 006A"
    )
    assert joined in NOTIFICATIONS
    out = p.FrameAssembler().feed(joined)
    assert len(out) == 2 and out[1].is_ack


def h(text: str) -> bytes:
    return bytes.fromhex(text.replace(" ", ""))


def test_every_captured_frame_parses():
    assert len(FRAMES) > 700
    for raw in FRAMES:
        frame = p.parse_frame(raw)
        assert frame.raw == raw
        assert frame.cmd in (p.CMD_SETTINGS, p.CMD_TELEMETRY)


def test_commands_match_confirmed_app_captures():
    confirmed = {
        p.read_request(): "55AA 0120 0000 20",
        p.cmd_main_power(False): "55AA 0121 0005 0101 0001 0029",
        p.cmd_main_power(True): "55AA 0121 0005 0101 0001 012A",
        p.cmd_compartments(0b10): "55AA 0121 0005 1204 0001 023F",  # left off
        p.cmd_compartments(0b01): "55AA 0121 0005 1204 0001 013E",  # right off
        p.cmd_compartments(0b11): "55AA 0121 0005 1204 0001 0340",  # both on
        p.cmd_mode("Eco"): "55AA 0121 0005 0B04 0001 0036",
        p.cmd_mode("Max"): "55AA 0121 0005 0B04 0001 0137",
        p.cmd_protection("Low"): "55AA 0121 0005 0704 0001 0032",
        p.cmd_protection("Medium"): "55AA 0121 0005 0704 0001 0133",
        p.cmd_protection("High"): "55AA 0121 0005 0704 0001 0234",
        p.cmd_unit("°C"): "55AA 0121 0005 0604 0001 0031",
        p.cmd_unit("°F"): "55AA 0121 0005 0604 0001 0132",
        p.cmd_setpoint(False, 1): "55AA 0121 0008 0302 0004 0000 0001 33",
        p.cmd_setpoint(False, 0): "55AA 0121 0008 0302 0004 0000 0000 32",
        p.cmd_setpoint(False, -1): "55AA 0121 0008 0302 0004 FFFF FFFF 2E",
        p.cmd_setpoint(False, -4): "55AA 0121 0008 0302 0004 FFFF FFFC 2B",
        p.cmd_setpoint(False, 5): "55AA 0121 0008 0302 0004 0000 0005 37",
        p.cmd_setpoint(True, -3): "55AA 0121 0008 0502 0004 FFFF FFFD 2E",
        p.cmd_setpoint(True, 4): "55AA 0121 0008 0502 0004 0000 0004 38",
    }
    for built, expected in confirmed.items():
        assert built == h(expected), (built.hex(), expected)


def test_both_compartments_off_is_refused():
    try:
        p.cmd_compartments(0)
    except p.ProtocolError:
        return
    raise AssertionError("mask 0 should be refused until it has been captured")


def test_battery_soc_from_full_status_frame():
    # 9 Aug 13:55, user: "battery ... around 48%"
    frame = p.parse_frame(
        h(
            "55AA 0131 00A6 3201 0001 0133 0200 0400 0000 2F34 0400 0100 3502 0004 0000 4084"
            " 3602 0004 0000 FFE2 3700 0023 E80C E70C E70C E70C E80C 0000 0000 E80B E60B C50B"
            " C40B 2F11 00D0 3950 1B00 0000 0030 0038 0000 150B 0000 2A01 0000 0000 2B01 0000"
            " 0000 1901 0000 0000 3900 0001 103A 0000 0200 003B 0200 0400 0000 003C 0200 0400"
            " 0000 003D 0200 0400 0000 003E 0200 0400 0000 003F 0200 0400 0000 0041 0300 0530"
            " 2E31 2E38 4202 0004 0000 0000 6F"
        )
    )
    state = p.decode_state([frame])
    assert state["battery"] == 47
    assert state["battery_firmware"] == "0.1.8"
    assert state["dc_input"] == 0 and state["usb_c_input"] == 0


def test_battery_never_taken_from_other_fields():
    """V3.0.7 read DC-input watts or 0 as the battery % from frames without field 0x33."""
    for raw in FRAMES:
        frame = p.parse_frame(raw)
        state = p.decode_state([frame])
        if "battery" in state:
            fields = frame.fields()
            assert p.F_BATTERY_SOC in fields or p.F_BATTERY_DETAIL in fields


def test_battery_copy_in_detail_block_agrees_with_soc_field():
    checked = 0
    for raw in FRAMES:
        fields = p.parse_frame(raw).fields()
        if p.F_BATTERY_SOC in fields and p.F_BATTERY_DETAIL in fields:
            assert fields[p.F_BATTERY_DETAIL][22] == fields[p.F_BATTERY_SOC]
            checked += 1
    assert checked >= 10


def test_pack_voltage_is_sum_of_cells():
    close = total = 0
    for raw in FRAMES:
        state = p.decode_state([p.parse_frame(raw)])
        if "pack_voltage" in state and "cell_voltages" in state:
            total += 1
            close += abs(state["pack_voltage"] - sum(state["cell_voltages"])) <= 0.015
    assert total > 400 and close / total > 0.98


def test_battery_current_sign():
    # 9 Aug 14:06, 12 V supply removed: running from the battery at about -1.98 A
    frame = p.parse_frame(
        h(
            "55AA 0131 0055 3502 0004 0000 40BD 3602 0004 0000 F844 3700 0023 F10C F20C F30C"
            " F50C F20C 0000 BC07 EB0B E90B D80B D70B 3411 00D0 3910 1E00 0021 0030 0038 0000"
            " 150B 0000 7301 0000 0000 7C01 0000 0000 7502 0000 5008 3900 0001 001A"
        )
    )
    state = p.decode_state([frame])
    assert state["battery_current"] == -1.98
    assert state["pack_voltage"] == 16.573
    assert state["battery"] == 52
    assert state["battery_power"] < 0


def test_charging_frame_values():
    # 18 Aug 23:02 - DC 81 W + USB-C 59 W charging, total through ports 140 W, battery 96 %
    frames = [p.parse_frame(r) for r in FRAMES]
    found = [
        p.decode_state([f])
        for f in frames
        if f.fields().get(p.F_DC_INPUT) == 81 and f.fields().get(p.F_USB_C_INPUT) == 59
    ]
    assert found and found[0]["port_power"] == 140 and found[0]["battery"] == 96


def test_settings_frame():
    frame = p.parse_frame(
        h(
            "55AA 0121 0020 0202 0004 0000 0000 0302 0004 0000 0000"
            " 0402 0004 FFFF FFFE 0502 0004 FFFF FFFE 5D"
        )
    )
    state = p.decode_state([frame])
    assert state == {
        "left_actual": 0,
        "left_setpoint": 0,
        "right_actual": -2,
        "right_setpoint": -2,
    }


def test_compartment_states_seen():
    masks = {p.decode_state([p.parse_frame(r)]).get("compartments") for r in FRAMES} - {
        None
    }
    assert masks == {1, 2, 3}


def test_ack_ignored():
    ack = p.parse_frame(h("55AA 0131 0005 3201 0001 006A"))
    assert ack.is_ack
    assert p.decode_state([ack]) == {}


def test_assembler_handles_split_and_joined_notifications():
    stream = b"".join(FRAMES[:50])
    for chunk in (1, 7, 20, 244, len(stream)):
        asm = p.FrameAssembler()
        out = []
        for i in range(0, len(stream), chunk):
            out += asm.feed(stream[i : i + chunk])
        assert [f.raw for f in out] == FRAMES[:50], chunk
        assert asm.dropped == 0


def test_assembler_resyncs_after_garbage():
    asm = p.FrameAssembler()
    good = FRAMES[0]
    out = asm.feed(b"\x00\x55\xaa\x01\x21\xff" + good[:10])
    out += asm.feed(good[10:])
    assert [f.raw for f in out] == [good]


if __name__ == "__main__":
    import sys

    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as err:  # noqa: BLE001
                failed += 1
                print("FAIL", name, repr(err))
    sys.exit(1 if failed else 0)
