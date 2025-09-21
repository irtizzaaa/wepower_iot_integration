"""Config flow for WePower IoT BLE integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.bluetooth import (
    BluetoothServiceInfo,
    async_discovered_service_info,
    async_process_advertisements,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_ADDRESS): str,
    }
)


class WePowerIoTBluetoothConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WePower IoT BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, BluetoothServiceInfo] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        
        # Check if this looks like a WePower IoT device
        if not self._is_wepower_device(discovery_info):
            return self.async_abort(reason="not_supported")
        
        self._discovered_devices[discovery_info.address] = discovery_info
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return await self.async_step_user()

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self._discovered_devices[self.unique_id].name or "Unknown WePower Device",
                "address": self.unique_id,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS].upper()
            name = user_input[CONF_NAME]
            
            # Check if already configured
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            
            # Create the config entry
            return self.async_create_entry(
                title=name,
                data={
                    CONF_NAME: name,
                    CONF_ADDRESS: address,
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
        )

    def _is_wepower_device(self, discovery_info: BluetoothServiceInfo) -> bool:
        """Check if this is a WePower IoT device."""
        name = discovery_info.name or ""
        
        # Check name patterns
        if any(pattern in name.upper() for pattern in ["WEPOWER", "WP"]):
            return True
        
        # Check manufacturer data
        if discovery_info.manufacturer_data:
            for manufacturer_id, data in discovery_info.manufacturer_data.items():
                if manufacturer_id == 65535 and len(data) >= 2 and data[0] == 87 and data[1] == 80:
                    return True
        
        # Check service UUIDs
        if discovery_info.service_uuids:
            for uuid in discovery_info.service_uuids:
                if "180a" in uuid.lower():  # Device Information Service
                    return True
        
        return False

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(import_data)
