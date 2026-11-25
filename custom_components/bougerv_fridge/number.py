"""Temperature setpoints for BougeRV fridges."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import BougeRVEntity
from .protocol import SETPOINT_LIMITS, cmd_setpoint


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            SetpointNumber(coordinator, right=False),
            SetpointNumber(coordinator, right=True),
        ]
    )


class SetpointNumber(BougeRVEntity, NumberEntity):
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_mode = NumberMode.SLIDER
    _attr_native_step = 1

    def __init__(self, coordinator, right: bool) -> None:
        # Unique ID suffixes 03/05 are the protocol field numbers.
        super().__init__(coordinator, "05_setpoint" if right else "03_setpoint")
        self._right = right
        self._key = "right_setpoint" if right else "left_setpoint"
        self._attr_translation_key = "right_setpoint" if right else "left_setpoint"

    @property
    def _unit(self) -> str:
        return (self.coordinator.data or {}).get("unit", "°C")

    @property
    def native_unit_of_measurement(self) -> str:
        return self._unit

    @property
    def native_min_value(self) -> float:
        return SETPOINT_LIMITS[self._unit][0]

    @property
    def native_max_value(self) -> float:
        return SETPOINT_LIMITS[self._unit][1]

    @property
    def native_value(self) -> int | None:
        return (self.coordinator.data or {}).get(self._key)

    async def async_set_native_value(self, value: float) -> None:
        low, high = SETPOINT_LIMITS[self._unit]
        target = max(low, min(high, round(value)))
        await self.coordinator.async_send(cmd_setpoint(self._right, target))
