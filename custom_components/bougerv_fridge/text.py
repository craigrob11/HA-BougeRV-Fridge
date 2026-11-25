"""Capture note: type what you are doing during a decoding test."""

from __future__ import annotations

from homeassistant.components.text import TextEntity
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
    async_add_entities([CaptureNote(entry.runtime_data)])


class CaptureNote(BougeRVEntity, TextEntity):
    """Whatever is typed here is stamped into the capture history."""

    _attr_translation_key = "capture_note"
    _attr_entity_registry_enabled_default = False  # hidden test tool
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_max = 100

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "capture_note")
        self._attr_native_value = ""

    async def async_set_value(self, value: str) -> None:
        self.coordinator.client.note(value)
        self._attr_native_value = value
        self.async_write_ha_state()
