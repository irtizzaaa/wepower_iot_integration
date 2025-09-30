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
    }
)

STEP_DEVICE_SELECTION_SCHEMA = vol.Schema(
    {
        vol.Required("device_address"): vol.In({}),
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
        """Handle the initial step - decryption key input."""
        if user_input is not None:
            decryption_key = user_input[CONF_DECRYPTION_KEY]
            
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
            
            # Store decryption key and proceed to device selection
            self._decryption_key = decryption_key
            return await self.async_step_device_selection()
            
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            description_placeholders={
                "message": "Enter your WePower IoT decryption key. This will be used to decrypt beacon data from your devices.\n\nDecryption Key: 32-character hex string (16 bytes)"
            }
        )

    async def async_step_device_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle device selection from discovered devices."""
        if user_input is not None:
            device_address = user_input["device_address"]
            
            if device_address not in self._discovered_devices:
                return self.async_show_form(
                    step_id="device_selection",
                    data_schema=STEP_DEVICE_SELECTION_SCHEMA,
                    errors={"base": "device_not_found"},
                )
            
            discovery_info = self._discovered_devices[device_address]
            
            # Check if already configured
            await self.async_set_unique_id(device_address)
            self._abort_if_unique_id_configured()
            
            # Get device type and name from beacon data
            device_type = self._get_device_type_from_beacon(discovery_info)
            device_name = self._get_device_name_from_type(device_type, device_address)
            
            # Create the config entry
            return self.async_create_entry(
                title=device_name,
                data={
                    CONF_NAME: device_name,
                    CONF_ADDRESS: device_address,
                    CONF_DECRYPTION_KEY: self._decryption_key,
                    CONF_DEVICE_NAME: device_name,
                    CONF_SENSOR_TYPE: device_type,
                },
            )
        
        # Build device options from discovered devices
        device_options = {}
        for address, discovery_info in self._discovered_devices.items():
            device_type = self._get_device_type_from_beacon(discovery_info)
            device_name = self._get_device_name_from_type(device_type, address)
            device_options[address] = f"{device_name} ({address})"
        
        if not device_options:
            return self.async_show_form(
                step_id="device_selection",
                data_schema=vol.Schema({}),
                errors={"base": "no_devices_found"},
                description_placeholders={
                    "message": "No WePower IoT devices found. Make sure your devices are powered on and within range."
                }
            )
        
        # Update schema with discovered devices
        schema = vol.Schema({
            vol.Required("device_address"): vol.In(device_options),
        })
        
        return self.async_show_form(
            step_id="device_selection",
            data_schema=schema,
            description_placeholders={
                "message": f"Found {len(device_options)} WePower IoT device(s). Select the device you want to add:"
            }
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> FlowResult:
        """Handle the bluetooth discovery step - store discovered devices."""
        # Check if this looks like a WePower IoT device
        if not self._is_wepower_device(discovery_info):
            return self.async_abort(reason="not_supported")
        
        # Store the device info for later selection
        self._discovered_devices[discovery_info.address] = discovery_info
        return self.async_abort(reason="already_in_progress")

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

    def _get_device_type_from_beacon(self, discovery_info: BluetoothServiceInfo) -> int:
        """Extract device type from beacon manufacturer data."""
        if discovery_info.manufacturer_data:
            for manufacturer_id, data in discovery_info.manufacturer_data.items():
                if manufacturer_id == BLE_COMPANY_ID and len(data) >= 20:
                    # Extract sensor type from manufacturer data
                    # Assuming sensor type is in the first few bytes after company ID
                    try:
                        sensor_type = data[2] if len(data) > 2 else 4  # Default to leak sensor
                        return sensor_type
                    except (IndexError, ValueError):
                        pass
        
        # Default to leak sensor if we can't determine type
        return 4

    def _get_device_name_from_type(self, device_type: int, address: str) -> str:
        """Generate professional device name based on type and address."""
        # Extract last 3 characters of MAC address for unit ID
        unit_id = address.replace(":", "")[-3:].upper()
        
        device_type_names = {
            1: "Temperature Sensor",
            2: "Humidity Sensor", 
            3: "Pressure Sensor",
            4: "Leak Sensor",
            5: "Vibration Sensor",
            6: "On/Off Switch",
            7: "Light Switch",
            8: "Door Switch",
            9: "Toggle Switch",
        }
        
        device_name = device_type_names.get(device_type, "IoT Sensor")
        return f"WePower {device_name} Unit-{unit_id}"

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(import_data)

