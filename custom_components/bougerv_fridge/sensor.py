"""Sensors for BougeRV fridges."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import BougeRVEntity


@dataclass(frozen=True, kw_only=True)
class BougeRVSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]
    battery: bool = False
    temperature: bool = False


def _get(key: str) -> Callable[[dict[str, Any]], Any]:
    return lambda data: data.get(key)


SENSORS: tuple[BougeRVSensorDescription, ...] = (
    BougeRVSensorDescription(
        key="left_actual",
        translation_key="left_actual",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_get("left_actual"),
        temperature=True,
    ),
    BougeRVSensorDescription(
        key="right_actual",
        translation_key="right_actual",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_get("right_actual"),
        temperature=True,
    ),
    BougeRVSensorDescription(
        key="voltage",
        translation_key="input_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        value_fn=_get("voltage"),
    ),
    # --- optional internal battery -------------------------------------------
    BougeRVSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=_get("battery"),
        battery=True,
    ),
    BougeRVSensorDescription(
        key="dc_input",
        translation_key="dc_input",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=_get("dc_input"),
        battery=True,
    ),
    BougeRVSensorDescription(
        key="usb_c_input",
        translation_key="usb_c_input",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=_get("usb_c_input"),
        battery=True,
    ),
    BougeRVSensorDescription(
        key="pack_voltage",
        translation_key="pack_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_get("pack_voltage"),
        battery=True,
    ),
    BougeRVSensorDescription(
        key="battery_current",
        translation_key="battery_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        value_fn=_get("battery_current"),
        battery=True,
    ),
    BougeRVSensorDescription(
        key="battery_power",
        translation_key="battery_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=_get("battery_power"),
        battery=True,
    ),
    BougeRVSensorDescription(
        key="battery_temperature",
        translation_key="battery_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,  # exact sensor location unknown
        value_fn=_get("battery_temperature"),
        battery=True,
    ),
    *(
        BougeRVSensorDescription(
            key=key,
            translation_key=key,
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            suggested_display_precision=3,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=_get(key),
            battery=True,
        )
        for key in ("cell_min", "cell_max")
    ),
    *(
        BougeRVSensorDescription(
            key=f"cell_{n}",
            translation_key=f"cell_{n}",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            suggested_display_precision=3,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            value_fn=lambda d, i=n - 1: (d.get("cell_voltages") or [None] * 5)[i],
            battery=True,
        )
        for n in range(1, 6)
    ),
    BougeRVSensorDescription(
        key="port_power",
        translation_key="port_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_get("port_power"),
        battery=True,
    ),
    # Input-power fields that have read 0 W in every capture so far; one is
    # expected to be the solar input. Disabled by default until identified.
    *(
        BougeRVSensorDescription(
            key=f"input_{suffix}",
            translation_key=f"input_{suffix}",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.WATT,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            value_fn=_get(f"input_{suffix}"),
            battery=True,
        )
        for suffix in ("3c", "3d", "3e")
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        BougeRVSensor(coordinator, description)
        for description in SENSORS
        if coordinator.has_battery or not description.battery
    )


class BougeRVSensor(BougeRVEntity, SensorEntity):
    entity_description: BougeRVSensorDescription

    def __init__(self, coordinator, description: BougeRVSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self.battery_entity = description.battery

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data or {})

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.temperature:
            return (self.coordinator.data or {}).get("unit", "°C")
        return self.entity_description.native_unit_of_measurement
