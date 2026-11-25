"""BougeRV fridge integration for Home Assistant (local Bluetooth)."""

from __future__ import annotations

import logging

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .ble import BougeRVClient
from .const import CONF_INITIAL_UNIT, DOMAIN
from .coordinator import BougeRVCoordinator
from .protocol import cmd_unit

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
]

# Unique-ID suffixes of entities that only exist with the internal battery.
BATTERY_KEYS = (
    "battery",
    "charging",
    "dc_input",
    "usb_c_input",
    "port_power",
    "input_3c",
    "input_3d",
    "input_3e",
    "pack_voltage",
    "battery_current",
    "battery_power",
    "battery_temperature",
    "cell_min",
    "cell_max",
    "cell_1",
    "cell_2",
    "cell_3",
    "cell_4",
    "cell_5",
    "external_power",
)

type BougeRVConfigEntry = ConfigEntry[BougeRVCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: BougeRVConfigEntry) -> bool:
    address: str = entry.data[CONF_ADDRESS].upper()
    if not bluetooth.async_ble_device_from_address(hass, address, connectable=True):
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="not_in_range",
            translation_placeholders={"address": address},
        )

    coordinator = BougeRVCoordinator(hass, entry, BougeRVClient(hass, address))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    if not coordinator.has_battery:
        _remove_battery_entities(hass, entry, address)

    await _apply_initial_unit(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BougeRVConfigEntry) -> bool:
    await entry.runtime_data.async_stop_live()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(
    hass: HomeAssistant, entry: BougeRVConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def _apply_initial_unit(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: BougeRVCoordinator
) -> None:
    """Send the unit chosen during setup to the fridge, once.

    Runs before the options listener is registered, so removing the value
    from the entry data does not trigger a reload.
    """
    unit = entry.data.get(CONF_INITIAL_UNIT)
    if unit is None:
        return
    if (coordinator.data or {}).get("unit") != unit:
        try:
            await coordinator.async_send(cmd_unit(unit))
        except HomeAssistantError as err:
            # Not fatal: keep the request and try again on the next start-up.
            _LOGGER.warning("Could not set the fridge to %s yet: %s", unit, err)
            return
    hass.config_entries.async_update_entry(
        entry, data={k: v for k, v in entry.data.items() if k != CONF_INITIAL_UNIT}
    )


def _remove_battery_entities(
    hass: HomeAssistant, entry: ConfigEntry, address: str
) -> None:
    """Battery switched off in the options: delete its entities rather than leave them unavailable."""
    registry = er.async_get(hass)
    wanted = {f"{DOMAIN}_{address}_{key}" for key in BATTERY_KEYS}
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.unique_id in wanted:
            registry.async_remove(entity.entity_id)
