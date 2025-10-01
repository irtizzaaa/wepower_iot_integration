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

from .const import DOMAIN, BLE_COMPANY_ID, CONF_DECRYPTION_KEY, CONF_DEVICE_NAME, CONF_SENSOR_TYPE

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DECRYPTION_KEY): str,
        vol.Optional(CONF_DEVICE_NAME): str,
        vol.Optional(CONF_SENSOR_TYPE, default=4): vol.In({
            "1": "Temperature Sensor",
            "2": "Humidity Sensor", 
            "3": "Pressure Sensor",
            "4": "Leak Sensor (Default)"
        }),
    }
)

STEP_DEVICE_SELECTION_SCHEMA = vol.Schema(
    {
        vol.Required("device_address"): vol.In({}),
        vol.Required(CONF_DECRYPTION_KEY): str,
        vol.Optional(CONF_DEVICE_NAME): str,
        vol.Optional(CONF_SENSOR_TYPE, default=4): vol.In({
            "1": "Temperature Sensor",
            "2": "Humidity Sensor", 
            "3": "Pressure Sensor",
            "4": "Leak Sensor (Default)"
        }),
    }
)


class WePowerIoTBluetoothConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WePower IoT BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, BluetoothServiceInfo] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - auto-configure with discovered device."""
        # If no devices discovered yet, show a message
        if not self._discovered_devices:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "message": "No WePower IoT devices detected yet. Please make sure your device is powered on and broadcasting. The integration will automatically detect WePower devices when they are discovered."
                }
            )
        
        # Get the discovered device (should be only one when called from bluetooth step)
        discovery_info = next(iter(self._discovered_devices.values()))
        address = discovery_info.address.upper()
        name = discovery_info.name or "WePower IoT Device"
        
        # If user input is provided, process it
        if user_input is not None:
            decryption_key = user_input[CONF_DECRYPTION_KEY]
            device_name = user_input.get(CONF_DEVICE_NAME, name)
            sensor_type = int(user_input.get(CONF_SENSOR_TYPE, "4"))
            
            # Validate decryption key format
            try:
                bytes.fromhex(decryption_key)
                if len(decryption_key) != 32:  # 16 bytes = 32 hex chars
                    return self.async_show_form(
                        step_id="user",
                        data_schema=STEP_USER_DATA_SCHEMA,
                        errors={"base": "invalid_decryption_key_length"},
                    )
            except ValueError:
                return self.async_show_form(
                    step_id="user",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors={"base": "invalid_decryption_key_format"},
                )
            
            # Create the config entry with auto-populated MAC address
            return self.async_create_entry(
                title=device_name,
                data={
                    CONF_NAME: name,
                    CONF_ADDRESS: address,  # Auto-populated from beacon!
                    CONF_DECRYPTION_KEY: decryption_key,
                    CONF_DEVICE_NAME: device_name,
                    CONF_SENSOR_TYPE: sensor_type,
                },
            )
        
        # Show the form with device info pre-filled
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            description_placeholders={
                "message": f"WePower IoT device detected!\n\nDevice: {name}\nMAC Address: {address}\n\nEnter your decryption key to complete setup.\n\nSensor Types:\n• Type 1: Temperature Sensor\n• Type 2: Humidity Sensor\n• Type 3: Pressure Sensor\n• Type 4: Leak Sensor (Default)\n\nDecryption Key: 32-character hex string (16 bytes)"
            }
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> FlowResult:
        """Handle the bluetooth discovery step - auto-configure the device."""
        # Check if this looks like a WePower IoT device
        if not self._is_wepower_device(discovery_info):
            return self.async_abort(reason="not_supported")
        
        # Check if already configured
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        
        # Store the device info
        self._discovered_devices[discovery_info.address] = discovery_info
        
        # Show the user form to enter decryption key only
        return await self.async_step_user()

    def _is_wepower_device(self, discovery_info: BluetoothServiceInfo) -> bool:
        """Check if this is a WePower IoT device using new packet format."""
        # Check manufacturer data for new Company ID
        if discovery_info.manufacturer_data:
            for manufacturer_id, data in discovery_info.manufacturer_data.items():
                if manufacturer_id == BLE_COMPANY_ID and len(data) >= 20:
                    return True
        
        # Check name patterns as fallback
        name = discovery_info.name or ""
        if any(pattern in name.upper() for pattern in ["WEPOWER", "WP"]):
            return True
        
        return False

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(import_data)
    
    async def async_step_device_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle device selection step."""
        return await self.async_step_user(user_input)

