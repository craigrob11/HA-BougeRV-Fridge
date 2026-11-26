"""Base entity for BougeRV."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import BougeRVCoordinator


def _battery_version(coordinator: BougeRVCoordinator) -> str | None:
    version = (coordinator.data or {}).get("battery_firmware")
    return (
        f"Battery firmware {version}" if version and coordinator.has_battery else None
    )


class BougeRVEntity(CoordinatorEntity[BougeRVCoordinator]):
    """Common device info and availability."""

    _attr_has_entity_name = True
    battery_entity = False

    def __init__(self, coordinator: BougeRVCoordinator, key: str) -> None:
        super().__init__(coordinator)
        address = coordinator.client.address
        self._attr_unique_id = f"{DOMAIN}_{address}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            connections={(CONNECTION_BLUETOOTH, address)},
            name=coordinator.config_entry.title,
            manufacturer=MANUFACTURER,
            model="CRD2 2.0",
            sw_version=(coordinator.data or {}).get("firmware"),
            hw_version=_battery_version(coordinator),
        )

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if self.battery_entity:
            return self.coordinator.battery_available
        return True
