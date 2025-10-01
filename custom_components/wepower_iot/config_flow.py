"""Config flow for WePower IoT integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, CONF_NAME, CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_MQTT_BROKER,
    CONF_MQTT_USERNAME,
    CONF_MQTT_PASSWORD,
    CONF_ENABLE_ZIGBEE,
    CONF_SCAN_INTERVAL,
    CONF_HEARTBEAT_INTERVAL,
    DEFAULT_MQTT_BROKER,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_ENABLE_ZIGBEE,
    DOMAIN,
    CONF_DECRYPTION_KEY,
    CONF_DEVICE_NAME,
    CONF_SENSOR_TYPE,
)

_LOGGER = logging.getLogger(__name__)


class WePowerIoTConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WePower IoT."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("integration_type"): vol.In({
                            "mqtt": "MQTT-based (Traditional)",
                            "ble": "Bluetooth Low Energy (BLE) - Manual Provisioning"
                        }),
                    }
                ),
            )

        integration_type = user_input["integration_type"]
        
        if integration_type == "ble":
            # Redirect to BLE config flow for manual provisioning
            return await self.async_step_ble()
        else:
            # Continue with MQTT setup
            return await self.async_step_mqtt()

    async def async_step_mqtt(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle MQTT configuration step."""
        if user_input is None:
            return self.async_show_form(
                step_id="mqtt",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_MQTT_BROKER, default=DEFAULT_MQTT_BROKER
                        ): str,
                        vol.Optional(CONF_MQTT_USERNAME): str,
                        vol.Optional(CONF_MQTT_PASSWORD): str,
                        vol.Required(
                            CONF_ENABLE_ZIGBEE, default=DEFAULT_ENABLE_ZIGBEE
                        ): bool,
                        vol.Required(
                            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                        ): vol.Coerce(float),
                        vol.Required(
                            CONF_HEARTBEAT_INTERVAL, default=DEFAULT_HEARTBEAT_INTERVAL
                        ): vol.Coerce(float),
                    }
                ),
            )

        # Validate MQTT broker URL
        mqtt_broker = user_input[CONF_MQTT_BROKER]
        if not mqtt_broker.startswith(("mqtt://", "mqtts://")):
            return self.async_show_form(
                step_id="mqtt",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_MQTT_BROKER, default=mqtt_broker
                        ): str,
                        vol.Optional(CONF_MQTT_USERNAME): str,
                        vol.Optional(CONF_MQTT_PASSWORD): str,
                        vol.Required(
                            CONF_ENABLE_ZIGBEE, default=user_input[CONF_ENABLE_ZIGBEE]
                        ): bool,
                        vol.Required(
                            CONF_SCAN_INTERVAL, default=user_input[CONF_SCAN_INTERVAL]
                        ): vol.Coerce(float),
                        vol.Required(
                            CONF_HEARTBEAT_INTERVAL, default=user_input[CONF_HEARTBEAT_INTERVAL]
                        ): vol.Coerce(float),
                    }
                ),
                errors={"base": "invalid_mqtt_broker"},
            )

        # Create the config entry
        return self.async_create_entry(
            title="WePower IoT (MQTT)",
            data={
                CONF_MQTT_BROKER: mqtt_broker,
                CONF_MQTT_USERNAME: user_input.get(CONF_MQTT_USERNAME, ""),
                CONF_MQTT_PASSWORD: user_input.get(CONF_MQTT_PASSWORD, ""),
                CONF_ENABLE_ZIGBEE: user_input[CONF_ENABLE_ZIGBEE],
                CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                CONF_HEARTBEAT_INTERVAL: user_input[CONF_HEARTBEAT_INTERVAL],
            },
        )

    async def async_step_ble(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle BLE configuration step with dynamic discovery."""
        if user_input is not None:
            decryption_key = user_input[CONF_DECRYPTION_KEY]
            
            # Validate decryption key format
            try:
                bytes.fromhex(decryption_key)
                if len(decryption_key) != 32:  # 16 bytes = 32 hex chars
                    return self.async_show_form(
                        step_id="ble",
                        data_schema=vol.Schema({
                            vol.Required(CONF_DECRYPTION_KEY, default=decryption_key): str,
                        }),
                        errors={"base": "invalid_decryption_key_length"},
                    )
            except ValueError:
                return self.async_show_form(
                    step_id="ble",
                    data_schema=vol.Schema({
                        vol.Required(CONF_DECRYPTION_KEY, default=decryption_key): str,
                    }),
                    errors={"base": "invalid_decryption_key_format"},
                )
            
            # Store decryption key and proceed to device selection
            self._decryption_key = decryption_key
            return await self.async_step_device_selection()

        return self.async_show_form(
            step_id="ble",
            data_schema=vol.Schema({
                vol.Required(CONF_DECRYPTION_KEY): str,
            }),
            description_placeholders={
                "message": "Enter your WePower IoT decryption key. This will be used to decrypt beacon data from your devices.\n\nDecryption Key: 32-character hex string (16 bytes)"
            }
        )

    async def async_step_device_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle device selection from discovered devices."""
        if user_input is not None:
            # Check if this is a fallback mode selection
            if "fallback_mode" in user_input:
                if user_input["fallback_mode"] == "retry":
                    # Go back to device selection to retry discovery
                    return await self.async_step_device_selection()
                elif user_input["fallback_mode"] == "manual":
                    # Go to manual device entry
                    return await self.async_step_manual_device()
            
            # Check if device_address exists in user_input
            if "device_address" not in user_input:
                return self.async_show_form(
                    step_id="device_selection",
                    data_schema=vol.Schema({}),
                    errors={"base": "no_device_selected"},
                    description_placeholders={
                        "message": "No device selected. Please try again."
                    }
                )
            
            device_address = user_input["device_address"]
            
            if device_address not in self._discovered_devices:
                return self.async_show_form(
                    step_id="device_selection",
                    data_schema=vol.Schema({}),
                    errors={"base": "device_not_found"},
                    description_placeholders={
                        "message": "Selected device not found. Please try again."
                    }
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
                data_schema=vol.Schema({
                    vol.Required("fallback_mode"): vol.In({
                        "retry": "Retry Discovery",
                        "manual": "Enter Device Manually"
                    }),
                }),
                errors={"base": "no_devices_found"},
                description_placeholders={
                    "message": "No WePower IoT devices found. Make sure your devices are powered on and within range. You can also try going back and entering the decryption key again."
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

    async def async_step_manual_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual device entry as fallback."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS].upper()
            device_name = user_input.get(CONF_DEVICE_NAME, f"WePower IoT Device {address[-6:]}")
            sensor_type = int(user_input.get(CONF_SENSOR_TYPE, "4"))
            
            # Check if already configured
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            
            # Create the config entry
            return self.async_create_entry(
                title=device_name,
                data={
                    CONF_NAME: device_name,
                    CONF_ADDRESS: address,
                    CONF_DECRYPTION_KEY: self._decryption_key,
                    CONF_DEVICE_NAME: device_name,
                    CONF_SENSOR_TYPE: sensor_type,
                },
            )

        return self.async_show_form(
            step_id="manual_device",
            data_schema=vol.Schema({
                vol.Required(CONF_ADDRESS): str,
                vol.Optional(CONF_DEVICE_NAME): str,
                vol.Optional(CONF_SENSOR_TYPE, default="4"): vol.In({
                    "1": "Temperature Sensor",
                    "2": "Humidity Sensor", 
                    "3": "Pressure Sensor",
                    "4": "Leak Sensor (Default)",
                    "5": "Vibration Sensor",
                    "6": "On/Off Switch",
                    "7": "Light Switch",
                    "8": "Door Switch",
                    "9": "Toggle Switch",
                }),
            }),
            description_placeholders={
                "message": "Enter device details manually. This is a fallback option when automatic discovery fails."
            }
        )

    def _get_device_type_from_beacon(self, discovery_info) -> int:
        """Extract device type from beacon manufacturer data."""
        # Import here to avoid circular imports
        from homeassistant.components.bluetooth import BluetoothServiceInfo
        from .const import BLE_COMPANY_ID
        
        if discovery_info.manufacturer_data:
            for manufacturer_id, data in discovery_info.manufacturer_data.items():
                if manufacturer_id == BLE_COMPANY_ID and len(data) >= 18:
                    # Extract sensor type from manufacturer data
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

    async def async_step_bluetooth(
        self, discovery_info: Any
    ) -> FlowResult:
        """Handle the bluetooth discovery step - store discovered devices."""
        # Import here to avoid circular imports
        from homeassistant.components.bluetooth import BluetoothServiceInfo
        from .const import BLE_COMPANY_ID
        
        # Check if this looks like a WePower IoT device
        if not self._is_wepower_device(discovery_info):
            return self.async_abort(reason="not_supported")
        
        # Store the device info for later selection
        self._discovered_devices[discovery_info.address] = discovery_info
        return self.async_abort(reason="already_in_progress")

    def _is_wepower_device(self, discovery_info: Any) -> bool:
        """Check if this is a WePower IoT device using new packet format."""
        # Import here to avoid circular imports
        from .const import BLE_COMPANY_ID
        
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

    async def async_step_import(self, import_info: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(import_info)

    async def async_step_add_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle adding a new device."""
        if user_input is None:
            return self.async_show_form(
                step_id="add_device",
                data_schema=vol.Schema(
                    {
                        vol.Required("device_id"): str,
                        vol.Required("device_type"): vol.In(["ble", "zigbee"]),
                        vol.Required("device_category"): vol.In(["sensor", "switch", "light", "door", "toggle"]),
                        vol.Required("ble_discovery_mode"): vol.In(["v0_manual", "v1_auto"]),
                        vol.Optional("device_name"): str,
                        vol.Optional("network_key"): str,
                    }
                ),
            )

        # Add device logic would go here
        # For now, just return to main flow
        return self.async_abort(reason="device_added")
