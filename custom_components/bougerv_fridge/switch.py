"""Power switches for BougeRV fridges."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import BougeRVEntity
from .protocol import LEFT_BIT, RIGHT_BIT, cmd_compartments, cmd_main_power


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            MainPowerSwitch(coordinator),
            CompartmentSwitch(coordinator, LEFT_BIT, "left_power", "left_on"),
            CompartmentSwitch(coordinator, RIGHT_BIT, "right_power", "right_on"),
            LiveCaptureSwitch(coordinator),
        ]
    )


class MainPowerSwitch(BougeRVEntity, SwitchEntity):
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_translation_key = "main_power"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "main_power")

    @property
    def is_on(self) -> bool | None:
        return (self.coordinator.data or {}).get("main_power")

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_send(cmd_main_power(True))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_send(cmd_main_power(False))


class CompartmentSwitch(BougeRVEntity, SwitchEntity):
    """Left or right compartment.

    Both compartments share one setting (a bitmask), so each command must
    carry the other compartment's current state.
    """

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self, coordinator, bit: int, translation_key: str, state_key: str
    ) -> None:
        super().__init__(coordinator, translation_key)
        self._bit = bit
        self._state_key = state_key
        self._attr_translation_key = translation_key

    @property
    def is_on(self) -> bool | None:
        return (self.coordinator.data or {}).get(self._state_key)

    def _current_mask(self) -> int:
        mask = (self.coordinator.data or {}).get("compartments")
        if mask is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="state_unknown"
            )
        return mask

    async def async_turn_on(self, **kwargs: Any) -> None:
        mask = self._current_mask() | self._bit
        await self.coordinator.async_send(cmd_compartments(mask))

    async def async_turn_off(self, **kwargs: Any) -> None:
        mask = self._current_mask() & ~self._bit & (LEFT_BIT | RIGHT_BIT)
        if mask == 0:
            # Both compartments off has never been captured from the BougeRV
            # app, so it is not sent until it has been tested.
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="both_compartments_off"
            )
        await self.coordinator.async_send(cmd_compartments(mask))


class LiveCaptureSwitch(BougeRVEntity, SwitchEntity):
    """Hold the Bluetooth connection open and record every frame (for testing).

    While on, the BougeRV phone app cannot connect. Turns itself off after
    30 minutes.
    """

    _attr_translation_key = "live_capture"
    _attr_entity_registry_enabled_default = False  # hidden test tool
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "live_capture")

    @property
    def is_on(self) -> bool:
        return self.coordinator.client.live

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_start_live()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_stop_live()
