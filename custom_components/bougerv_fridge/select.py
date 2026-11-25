"""Mode, battery protection and unit selects for BougeRV fridges."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import BougeRVEntity
from .protocol import (
    MODES,
    PROTECTION_LEVELS,
    UNITS,
    cmd_mode,
    cmd_protection,
    cmd_unit,
)


@dataclass(frozen=True, kw_only=True)
class BougeRVSelectDescription(SelectEntityDescription):
    state_key: str
    command_fn: Callable[[str], bytes]


SELECTS: tuple[BougeRVSelectDescription, ...] = (
    BougeRVSelectDescription(
        key="mode",
        translation_key="mode",
        options=list(MODES.values()),
        state_key="mode",
        command_fn=cmd_mode,
    ),
    BougeRVSelectDescription(
        key="protection",
        translation_key="protection",
        options=list(PROTECTION_LEVELS.values()),
        entity_category=EntityCategory.CONFIG,
        state_key="protection",
        command_fn=cmd_protection,
    ),
    BougeRVSelectDescription(
        key="units",
        translation_key="units",
        options=list(UNITS.values()),
        entity_category=EntityCategory.CONFIG,
        state_key="unit",
        command_fn=cmd_unit,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(BougeRVSelect(coordinator, d) for d in SELECTS)


class BougeRVSelect(BougeRVEntity, SelectEntity):
    entity_description: BougeRVSelectDescription

    def __init__(self, coordinator, description: BougeRVSelectDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def current_option(self) -> str | None:
        return (self.coordinator.data or {}).get(self.entity_description.state_key)

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_send(self.entity_description.command_fn(option))
