"""Capture marker button for decoding tests."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import BougeRVEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    if entry.runtime_data.test_tools:
        async_add_entities([MarkerButton(entry.runtime_data)])


class MarkerButton(BougeRVEntity, ButtonEntity):
    """Drops a numbered marker into the capture history (MARKER 1, MARKER 2 ...).

    Press it at the moment you do something (lid open, lid closed, panel
    connected) so the change can be found in the diagnostics download.
    """

    _attr_translation_key = "marker"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "marker")

    async def async_press(self) -> None:
        self.coordinator.add_marker()
