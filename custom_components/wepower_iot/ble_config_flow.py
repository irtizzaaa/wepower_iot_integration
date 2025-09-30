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
            "4": "Leak Sensor (Default)",
            "5": "Vibration Sensor",
            "6": "On/Off Switch",
            "7": "Light Switch",
            "8": "Door Switch",
            "9": "Toggle Switch"
        }),
    }
)

STEP_DISCOVERY_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DECRYPTION_KEY): str,
        vol.Optional(CONF_DEVICE_NAME): str,
        vol.Optional(CONF_SENSOR_TYPE, default=4): vol.In({
            "1": "Temperature Sensor",
            "2": "Humidity Sensor", 
            "3": "Pressure Sensor",
            "4": "Leak Sensor (Default)",
            "5": "Vibration Sensor",
            "6": "On/Off Switch",
            "7": "Light Switch",
            "8": "Door Switch",
            "9": "Toggle Switch"
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
        """Handle the initial step - discover and configure device."""
        if user_input is not None:
            decryption_key = user_input[CONF_DECRYPTION_KEY]
            device_name = user_input.get(CONF_DEVICE_NAME, "")
            sensor_type = int(user_input.get(CONF_SENSOR_TYPE, "4"))  # Convert string to int, default to leak sensor
            
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
            
            # Store user input and proceed to device selection
            self._user_input = user_input
            return await self.async_step_device_selection()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            description_placeholders={
                "message": "Configure WePower IoT device discovery. Enter your decryption key and select the sensor type.\n\nSensor Types:\n• Type 1: Temperature Sensor\n• Type 2: Humidity Sensor\n• Type 3: Pressure Sensor\n• Type 4: Leak Sensor (Default)\n\nDecryption Key: 32-character hex string (16 bytes)\n\nAfter entering the key, we'll scan for available devices."
            }
        )

    async def async_step_device_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle device selection from discovered devices."""
        if user_input is not None:
            selected_address = user_input["device_address"]
            device_info = self._discovered_devices[selected_address]
            
            # Check if already configured
            await self.async_set_unique_id(selected_address)
            self._abort_if_unique_id_configured()
            
            # Get device type from beacon data
            device_type = self._get_device_type_from_beacon(device_info)
            device_name = self._get_device_name_from_type(device_type, selected_address)
            
            # Create the config entry
            return self.async_create_entry(
                title=device_name,
                data={
                    CONF_NAME: device_name,
                    CONF_ADDRESS: selected_address,
                    CONF_DECRYPTION_KEY: self._user_input[CONF_DECRYPTION_KEY],
                    CONF_DEVICE_NAME: device_name,
                    CONF_SENSOR_TYPE: self._user_input.get(CONF_SENSOR_TYPE, 4),
                },
            )
        
        # Show discovered devices
        if not self._discovered_devices:
            return self.async_show_form(
                step_id="device_selection",
                data_schema=vol.Schema({}),
                errors={"base": "no_devices_found"},
                description_placeholders={
                    "message": "No WePower IoT devices found. Please ensure:\n• Your device is powered on\n• Bluetooth is enabled\n• The device is within range\n\nClick 'Submit' to scan again."
                }
            )
        
        # Create device selection schema
        device_options = {}
        for address, device_info in self._discovered_devices.items():
            device_type = self._get_device_type_from_beacon(device_info)
            device_name = self._get_device_name_from_type(device_type, address)
            device_options[address] = f"{device_name} ({address})"
        
        schema = vol.Schema({
            vol.Required("device_address"): vol.In(device_options)
        })
        
        return self.async_show_form(
            step_id="device_selection",
            data_schema=schema,
            description_placeholders={
                "message": f"Found {len(self._discovered_devices)} WePower IoT device(s). Select the device you want to configure:"
            }
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        # Check if this looks like a WePower IoT device
        if not self._is_wepower_device(discovery_info):
            return self.async_abort(reason="not_supported")
        
        # Store the device info for later selection
        self._discovered_devices[discovery_info.address] = discovery_info
        
        # If we're in the device selection step, update the form
        if hasattr(self, '_user_input'):
            return await self.async_step_device_selection()
        
        return self.async_abort(reason="manual_provisioning_required")

    def _is_wepower_device(self, discovery_info: BluetoothServiceInfo) -> bool:
        """Check if this is a WePower IoT device using new packet format."""
        # Check manufacturer data for new Company ID
        if discovery_info.manufacturer_data:
            for manufacturer_id, data in discovery_info.manufacturer_data.items():
                if manufacturer_id == BLE_COMPANY_ID and len(data) >= 18:
                    return True
        
        # Check name patterns as fallback
        name = discovery_info.name or ""
        if any(pattern in name.upper() for pattern in ["WEPOWER", "WP"]):
            return True
        
        return False

    def _get_device_type_from_beacon(self, discovery_info: BluetoothServiceInfo) -> str:
        """Extract device type from beacon data."""
        # Try to parse manufacturer data to get sensor type
        if discovery_info.manufacturer_data:
            for manufacturer_id, data in discovery_info.manufacturer_data.items():
                if manufacturer_id == BLE_COMPANY_ID and len(data) >= 18:
                    try:
                        # Parse sensor type from encrypted data (bytes 6-7)
                        sensor_type_bytes = data[7:9]  # bytes 6-7 (0-indexed)
                        sensor_type = int.from_bytes(sensor_type_bytes, byteorder='little')
                        
                        if sensor_type == 1:
                            return "temperature_sensor"
                        elif sensor_type == 2:
                            return "humidity_sensor"
                        elif sensor_type == 3:
                            return "pressure_sensor"
                        elif sensor_type == 4:
                            return "leak_sensor"
                        elif sensor_type == 5:
                            return "vibration_sensor"
                        elif sensor_type == 6:
                            return "on_off_switch"
                        elif sensor_type == 7:
                            return "light_switch"
                        elif sensor_type == 8:
                            return "door_switch"
                        elif sensor_type == 9:
                            return "toggle_switch"
                    except (IndexError, ValueError):
                        pass
        
        # Fallback to name-based detection
        name = discovery_info.name or ""
        name_upper = name.upper()
        
        if "TEMP" in name_upper or "TEMPERATURE" in name_upper:
            return "temperature_sensor"
        elif "HUMIDITY" in name_upper or "HUMID" in name_upper:
            return "humidity_sensor"
        elif "PRESSURE" in name_upper or "PRESS" in name_upper:
            return "pressure_sensor"
        elif "LEAK" in name_upper or "WATER" in name_upper:
            return "leak_sensor"
        elif "VIBRATION" in name_upper or "VIBRATE" in name_upper:
            return "vibration_sensor"
        elif "SWITCH" in name_upper and "LIGHT" in name_upper:
            return "light_switch"
        elif "SWITCH" in name_upper and "DOOR" in name_upper:
            return "door_switch"
        elif "SWITCH" in name_upper and "TOGGLE" in name_upper:
            return "toggle_switch"
        elif "SWITCH" in name_upper:
            return "on_off_switch"
        
        return "unknown_device"

    def _get_device_name_from_type(self, device_type: str, address: str) -> str:
        """Generate device name based on type and address."""
        # Get professional device ID
        clean_address = address.replace(":", "").upper()
        last_6 = clean_address[-6:]
        device_number = int(last_6, 16) % 1000  # Get a number between 0-999
        professional_id = f"Unit-{device_number:03d}"
        
        type_names = {
            "temperature_sensor": "Temperature Sensor",
            "humidity_sensor": "Humidity Sensor", 
            "pressure_sensor": "Pressure Sensor",
            "leak_sensor": "Leak Sensor",
            "vibration_sensor": "Vibration Sensor",
            "on_off_switch": "On/Off Switch",
            "light_switch": "Light Switch",
            "door_switch": "Door Switch",
            "toggle_switch": "Toggle Switch",
            "unknown_device": "IoT Device"
        }
        
        base_name = type_names.get(device_type, "IoT Device")
        return f"WePower {base_name} {professional_id}"

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(import_data)

