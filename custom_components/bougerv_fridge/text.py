"""Hidden test tools: a capture note, and a raw setting command for decoding."""

from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import BougeRVEntity
from .protocol import CMD_SETTINGS, TYPE_ENUM, build_frame, build_record


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    if entry.runtime_data.test_tools:
        async_add_entities(
            [CaptureNote(entry.runtime_data), TestCommand(entry.runtime_data)]
        )


class CaptureNote(BougeRVEntity, TextEntity):
    """Whatever is typed here is stamped into the capture history."""

    _attr_translation_key = "capture_note"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_max = 100

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "capture_note")
        self._attr_native_value = ""

    async def async_set_value(self, value: str) -> None:
        self.coordinator.client.note(value)
        self._attr_native_value = value
        self.async_write_ha_state()


class TestCommand(BougeRVEntity, TextEntity):
    """Send one raw setting to the fridge, for decoding unknown values.

    Type the field and value in hex, e.g. ``12 01``. It is sent as a one-byte
    setting (``55AA 0121 0005 <field> 04 0001 <value> <checksum>``) and
    recorded in the capture history like any other command.
    """

    _attr_translation_key = "test_command"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_max = 20

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "test_command")
        self._attr_native_value = ""

    async def async_set_value(self, value: str) -> None:
        try:
            field, setting = (int(part, 16) for part in value.split())
        except ValueError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="bad_test_command"
            ) from err
        self.coordinator.client.note(f"test command {field:02X} = {setting:02X}")
        await self.coordinator.async_send(
            build_frame(CMD_SETTINGS, build_record(field, TYPE_ENUM, bytes([setting])))
        )
        self._attr_native_value = value
        self.async_write_ha_state()
