"""Binary sensors for BougeRV fridges."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import BougeRVEntity

# Below this, input power is treated as measurement noise.
CHARGING_THRESHOLD_W = 1


def _charging(data: dict[str, Any]) -> bool | None:
    inputs = [
        data.get(k)
        for k in ("dc_input", "usb_c_input", "solar_input", "input_3c", "input_3e")
    ]
    known = [w for w in inputs if w is not None]
    if not known:
        return None
    return any(w > CHARGING_THRESHOLD_W for w in known)


@dataclass(frozen=True, kw_only=True)
class BougeRVBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], bool | None]
    battery: bool = False


BINARY_SENSORS: tuple[BougeRVBinaryDescription, ...] = (
    BougeRVBinaryDescription(
        key="main_power_state",
        translation_key="main_power",
        device_class=BinarySensorDeviceClass.POWER,
        value_fn=lambda d: d.get("main_power"),
    ),
    BougeRVBinaryDescription(
        key="left_power_state",
        translation_key="left_power",
        device_class=BinarySensorDeviceClass.POWER,
        value_fn=lambda d: d.get("left_on"),
    ),
    BougeRVBinaryDescription(
        key="right_power_state",
        translation_key="right_power",
        device_class=BinarySensorDeviceClass.POWER,
        value_fn=lambda d: d.get("right_on"),
    ),
    BougeRVBinaryDescription(
        key="compressor",
        translation_key="compressor",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("compressor"),
    ),
    BougeRVBinaryDescription(
        key="external_power",
        translation_key="external_power",
        device_class=BinarySensorDeviceClass.PLUG,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("external_power"),
        battery=True,
    ),
    BougeRVBinaryDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=_charging,
        battery=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        BougeRVBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
        if coordinator.has_battery or not description.battery
    )


class BougeRVBinarySensor(BougeRVEntity, BinarySensorEntity):
    entity_description: BougeRVBinaryDescription

    def __init__(self, coordinator, description: BougeRVBinaryDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self.battery_entity = description.battery

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data or {})
