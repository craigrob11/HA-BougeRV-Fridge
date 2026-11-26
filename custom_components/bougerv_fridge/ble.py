"""Bluetooth transport for BougeRV fridges.

Normal mode: the fridge accepts only one Bluetooth connection, so each update
connects, reads (or writes then reads) and disconnects again, leaving the
fridge free for the BougeRV phone app between polls.

Live capture mode: the connection is held open so every frame the fridge
pushes (lid, compressor, power changes...) is recorded the moment it arrives.
Used for decoding tests; switches itself off after a time limit.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import deque
from collections.abc import Callable

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .const import DATA_CHAR_UUID, POLL_TIMEOUT, RAW_HISTORY, WRITE_SETTLE
from .protocol import (
    CMD_SETTINGS,
    CMD_TELEMETRY,
    F_MAIN_POWER,
    F_PORT_POWER,
    Frame,
    FrameAssembler,
    read_request,
)

_LOGGER = logging.getLogger(__name__)


class BougeRVNotFound(Exception):
    """The fridge is not currently visible to any Bluetooth adapter or proxy."""


class BougeRVClient:
    """Bluetooth session handling for one fridge."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        self.hass = hass
        self.address = address
        self._lock = asyncio.Lock()
        self._assembler = FrameAssembler()
        self._frames: list[Frame] = []
        self._got_frame = asyncio.Event()
        self._in_session = False
        self._live_client: BleakClient | None = None
        self.history: deque[tuple[float, str, str]] = deque(maxlen=RAW_HISTORY)
        # Set by the coordinator: frames that arrive outside a read/write
        # (only possible in live mode) and live-mode on/off changes.
        self.on_pushed_frames: Callable[[list[Frame]], None] | None = None
        self.on_live_changed: Callable[[bool], None] | None = None

    @property
    def live(self) -> bool:
        return self._live_client is not None and self._live_client.is_connected

    # -- public ---------------------------------------------------------------

    async def read(self, want_battery: bool) -> list[Frame]:
        """Ask the fridge for everything and return the frames it sends."""
        async with self._lock:
            return await self._session(None, want_battery)

    async def write(self, payload: bytes, want_battery: bool) -> list[Frame]:
        """Send one command, then read back the resulting state."""
        async with self._lock:
            return await self._session(payload, want_battery)

    async def start_live(self) -> None:
        async with self._lock:
            if self.live:
                return
            self._live_client = await self._connect(self._on_live_disconnect)
            self.note("live capture started")
            # Ask for a full read so the capture starts with a complete picture.
            await self._send(self._live_client, read_request())
        self._set_live(True)

    async def stop_live(self) -> None:
        async with self._lock:
            client, self._live_client = self._live_client, None
            if client is not None:
                self.note("live capture stopped")
                await self._disconnect(client)
        self._set_live(False)

    def note(self, text: str) -> None:
        """Add a marker or note to the capture history."""
        self.history.append((time.time(), "note", text))
        _LOGGER.debug("%s NOTE %s", self.address, text)

    # -- internals ------------------------------------------------------------

    def _ble_device(self) -> BLEDevice:
        device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if device is None:
            raise BougeRVNotFound(
                f"BougeRV fridge {self.address} is not in range of any Bluetooth adapter or proxy"
            )
        return device

    async def _connect(self, disconnected_callback=None) -> BleakClient:
        self._assembler = FrameAssembler()
        client = await establish_connection(
            BleakClientWithServiceCache,
            self._ble_device(),
            f"BougeRV {self.address}",
            disconnected_callback=disconnected_callback,
            ble_device_callback=self._ble_device,
            max_attempts=3,
        )
        try:
            await client.start_notify(DATA_CHAR_UUID, self._on_notify)
        except Exception:
            await self._disconnect(client)
            raise
        return client

    async def _disconnect(self, client: BleakClient) -> None:
        try:
            await client.disconnect()
        except Exception:
            _LOGGER.debug("%s: error while disconnecting", self.address, exc_info=True)

    async def _send(self, client: BleakClient, payload: bytes) -> None:
        self.history.append((time.time(), "tx", payload.hex(" ").upper()))
        _LOGGER.debug("%s TX %s", self.address, payload.hex(" ").upper())
        await client.write_gatt_char(DATA_CHAR_UUID, payload, response=True)

    async def _session(self, command: bytes | None, want_battery: bool) -> list[Frame]:
        self._frames = []
        self._got_frame.clear()
        reuse = self.live
        client = self._live_client if reuse else await self._connect()
        assert client is not None
        self._in_session = True
        try:
            if command is not None:
                await self._send(client, command)
                await asyncio.sleep(WRITE_SETTLE)
            await self._send(client, read_request())
            await self._wait_for_reply(want_battery)
        finally:
            self._in_session = False
            if not reuse:
                await self._disconnect(client)
        return list(self._frames)

    async def _wait_for_reply(self, want_battery: bool) -> None:
        deadline = time.monotonic() + POLL_TIMEOUT
        while not self._complete(want_battery):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _LOGGER.debug(
                    "%s: reply incomplete after %.1fs (%d frames)",
                    self.address,
                    POLL_TIMEOUT,
                    len(self._frames),
                )
                return
            # Notifications are delivered on the event loop, so none can slip in
            # between the completeness check above and this clear().
            self._got_frame.clear()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._got_frame.wait(), remaining)

    def _complete(self, want_battery: bool) -> bool:
        """The read reply is a full settings frame, then (with a battery) a full telemetry frame."""
        have_settings = any(
            f.cmd == CMD_SETTINGS and F_MAIN_POWER in f.fields() for f in self._frames
        )
        if not want_battery:
            return have_settings
        have_battery = any(
            f.cmd == CMD_TELEMETRY and F_PORT_POWER in f.fields() for f in self._frames
        )
        return have_settings and have_battery

    def _on_notify(self, _sender: object, data: bytearray) -> None:
        frames = self._assembler.feed(bytes(data))
        for frame in frames:
            self.history.append((time.time(), "rx", frame.raw.hex(" ").upper()))
            _LOGGER.debug(
                "%s RX %s -> %s",
                self.address,
                frame.raw.hex(" ").upper(),
                {
                    f"{k:02X}": v
                    for k, v in frame.fields().items()
                    if not isinstance(v, bytes)
                },
            )
        if self._assembler.dropped:
            _LOGGER.debug(
                "%s: %d unrecognised bytes skipped",
                self.address,
                self._assembler.dropped,
            )
        if self._in_session:
            self._frames.extend(frames)
            self._got_frame.set()
        elif frames and self.on_pushed_frames is not None:
            self.on_pushed_frames(frames)

    def _on_live_disconnect(self, _client: BleakClient) -> None:
        if self._live_client is not None:
            self._live_client = None
            self.note("live capture connection lost")
            self._set_live(False)

    def _set_live(self, live: bool) -> None:
        if self.on_live_changed is not None:
            self.on_live_changed(live)
