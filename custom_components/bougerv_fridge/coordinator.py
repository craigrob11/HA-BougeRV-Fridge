"""Polling coordinator for BougeRV fridges."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from bleak.exc import BleakError
from bleak_retry_connector import BleakNotFoundError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .ble import BougeRVClient, BougeRVNotFound
from .const import (
    BATTERY_STALE_POLLS,
    CONF_HAS_BATTERY,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LIVE_CAPTURE_LIMIT,
)
from .protocol import Frame, ProtocolError, decode_state

_LOGGER = logging.getLogger(__name__)

_CONNECTION_ERRORS = (BleakError, BleakNotFoundError, BougeRVNotFound, TimeoutError)


class BougeRVCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the fridge and keeps the last known value of every field.

    The fridge does not send every field in every frame, so values are merged
    into the previous state instead of replacing it. A missing field therefore
    keeps its last value rather than dropping to 0 or unknown.
    """

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: BougeRVClient
    ) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"BougeRV {client.address}",
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self.has_battery: bool = entry.options.get(CONF_HAS_BATTERY, False)
        self._state: dict[str, Any] = {}
        self._battery_seen_at: float | None = None
        self._live_timer: CALLBACK_TYPE | None = None
        self.marker_count = 0
        client.on_pushed_frames = self._on_pushed_frames
        client.on_live_changed = self._on_live_changed

    # -- helpers used by entities ------------------------------------------------

    @property
    def battery_available(self) -> bool:
        if self._battery_seen_at is None:
            return False
        stale_after = BATTERY_STALE_POLLS * self.update_interval.total_seconds()
        return time.monotonic() - self._battery_seen_at < stale_after

    async def async_send(self, payload: bytes) -> None:
        """Send a command and refresh state from the fridge's reply."""
        try:
            frames = await self.client.write(payload, self.has_battery)
        except _CONNECTION_ERRORS as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        self.async_set_updated_data(self._merge(frames))

    # -- live capture --------------------------------------------------------------

    async def async_start_live(self) -> None:
        try:
            await self.client.start_live()
        except _CONNECTION_ERRORS as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        self._cancel_live_timer()
        self._live_timer = async_call_later(
            self.hass, LIVE_CAPTURE_LIMIT, self._live_timeout
        )

    async def async_stop_live(self) -> None:
        self._cancel_live_timer()
        await self.client.stop_live()

    async def async_shutdown(self) -> None:
        self._cancel_live_timer()
        await self.client.stop_live()
        await super().async_shutdown()

    def add_marker(self) -> int:
        self.marker_count += 1
        self.client.note(f"MARKER {self.marker_count}")
        return self.marker_count

    @callback
    def _live_timeout(self, _now: Any) -> None:
        self._live_timer = None
        self.client.note(
            f"live capture auto-stopped after {LIVE_CAPTURE_LIMIT // 60} min"
        )
        self.config_entry.async_create_background_task(
            self.hass, self.client.stop_live(), f"{DOMAIN}_stop_live"
        )

    def _cancel_live_timer(self) -> None:
        if self._live_timer is not None:
            self._live_timer()
            self._live_timer = None

    @callback
    def _on_pushed_frames(self, frames: list[Frame]) -> None:
        self.async_set_updated_data(self._merge(frames))

    @callback
    def _on_live_changed(self, _live: bool) -> None:
        self.async_update_listeners()

    # -- DataUpdateCoordinator ---------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            frames = await self.client.read(self.has_battery)
        except _CONNECTION_ERRORS as err:
            raise UpdateFailed(f"Could not reach the fridge: {err}") from err
        except ProtocolError as err:  # should not happen; assembler drops bad frames
            raise UpdateFailed(f"Unexpected data from the fridge: {err}") from err
        if not frames:
            raise UpdateFailed("The fridge did not reply")
        return self._merge(frames)

    def _merge(self, frames: list[Frame]) -> dict[str, Any]:
        update = decode_state(frames)
        if update.pop("battery_seen", False):
            self._battery_seen_at = time.monotonic()
        self._state.update(update)
        return dict(self._state)
