"""Config flow for BougeRV fridges."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback

from .const import (
    CONF_HAS_BATTERY,
    CONF_INITIAL_UNIT,
    CONF_SCAN_INTERVAL,
    CONF_TEST_TOOLS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOCAL_NAME_PREFIX,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

UNIT_CHOICES = {"°C": "Celsius (°C)", "°F": "Fahrenheit (°F)"}

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HAS_BATTERY, default=False): bool,
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
        ),
        vol.Required(CONF_TEST_TOOLS, default=False): bool,
    }
)


def _is_bougerv(info: BluetoothServiceInfoBleak) -> bool:
    return (info.name or "").upper().startswith(LOCAL_NAME_PREFIX)


def _title(info: BluetoothServiceInfoBleak | None) -> str:
    return "BougeRV Fridge" if info is None else f"BougeRV {info.name or 'Fridge'}"


class BougeRVConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a BougeRV fridge, discovered or picked from a list."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._found: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name or "BougeRV"}
        return await self.async_step_setup()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            self._discovery = self._found[address]
            self.context["title_placeholders"] = {
                "name": self._discovery.name or "BougeRV"
            }
            return await self.async_step_setup()

        configured = self._async_current_ids(include_ignore=False)
        for info in async_discovered_service_info(self.hass, connectable=True):
            if info.address not in configured and _is_bougerv(info):
                self._found[info.address] = info
        if not self._found:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            address: f"{info.name or 'BougeRV'} ({address})"
                            for address, info in sorted(self._found.items())
                        }
                    )
                }
            ),
        )

    async def async_step_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask about the optional internal battery and the temperature unit."""
        assert self._discovery is not None
        if user_input is not None:
            return self.async_create_entry(
                title=_title(self._discovery),
                data={
                    CONF_ADDRESS: self._discovery.address,
                    # Applied to the fridge once, on first start-up, then removed.
                    CONF_INITIAL_UNIT: user_input[CONF_INITIAL_UNIT],
                },
                options={
                    CONF_HAS_BATTERY: user_input[CONF_HAS_BATTERY],
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                },
            )
        default_unit = "°F" if self.hass.config.units.temperature_unit == "°F" else "°C"
        return self.async_show_form(
            step_id="setup",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HAS_BATTERY, default=False): bool,
                    vol.Required(CONF_INITIAL_UNIT, default=default_unit): vol.In(
                        UNIT_CHOICES
                    ),
                }
            ),
            description_placeholders={"name": self._discovery.name or "BougeRV"},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return BougeRVOptionsFlow()


class BougeRVOptionsFlow(OptionsFlow):
    """Change the battery option or polling interval later."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
