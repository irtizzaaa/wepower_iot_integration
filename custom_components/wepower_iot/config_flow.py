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
        """Handle BLE configuration step."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS].upper()
            name = user_input[CONF_NAME]
            decryption_key = user_input[CONF_DECRYPTION_KEY]
            device_name = user_input.get(CONF_DEVICE_NAME, name)
            sensor_type = int(user_input.get(CONF_SENSOR_TYPE, "4"))
            
            # Validate decryption key format
            try:
                bytes.fromhex(decryption_key)
                if len(decryption_key) != 32:  # 16 bytes = 32 hex chars
                    return self.async_show_form(
                        step_id="ble",
                        data_schema=vol.Schema({
                            vol.Required(CONF_NAME, default=name): str,
                            vol.Required(CONF_ADDRESS, default=address): str,
                            vol.Required(CONF_DECRYPTION_KEY, default=decryption_key): str,
                            vol.Optional(CONF_DEVICE_NAME, default=device_name): str,
                            vol.Optional(CONF_SENSOR_TYPE, default="4"): vol.In({
                                "1": "Temperature Sensor",
                                "2": "Humidity Sensor", 
                                "3": "Pressure Sensor",
                                "4": "Leak Sensor (Default)"
                            }),
                        }),
                        errors={"base": "invalid_decryption_key_length"},
                    )
            except ValueError:
                return self.async_show_form(
                    step_id="ble",
                    data_schema=vol.Schema({
                        vol.Required(CONF_NAME, default=name): str,
                        vol.Required(CONF_ADDRESS, default=address): str,
                        vol.Required(CONF_DECRYPTION_KEY, default=decryption_key): str,
                        vol.Optional(CONF_DEVICE_NAME, default=device_name): str,
                        vol.Optional(CONF_SENSOR_TYPE, default="4"): vol.In({
                            "1": "Temperature Sensor",
                            "2": "Humidity Sensor", 
                            "3": "Pressure Sensor",
                            "4": "Leak Sensor (Default)"
                        }),
                    }),
                    errors={"base": "invalid_decryption_key_format"},
                )
            
            # Check if already configured
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            
            # Create the config entry
            return self.async_create_entry(
                title=device_name,
                data={
                    CONF_NAME: name,
                    CONF_ADDRESS: address,
                    CONF_DECRYPTION_KEY: decryption_key,
                    CONF_DEVICE_NAME: device_name,
                    CONF_SENSOR_TYPE: sensor_type,
                },
            )

        return self.async_show_form(
            step_id="ble",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_ADDRESS): str,
                vol.Required(CONF_DECRYPTION_KEY): str,
                vol.Optional(CONF_DEVICE_NAME): str,
                vol.Optional(CONF_SENSOR_TYPE, default="4"): vol.In({
                    "1": "Temperature Sensor",
                    "2": "Humidity Sensor", 
                    "3": "Pressure Sensor",
                    "4": "Leak Sensor (Default)"
                }),
            }),
            description_placeholders={
                "message": "Manually provision a WePower IoT device by entering its MAC address and decryption key.\n\nSensor Types:\n• Type 1: Temperature Sensor\n• Type 2: Humidity Sensor\n• Type 3: Pressure Sensor\n• Type 4: Leak Sensor (Default)\n\nDecryption Key: 32-character hex string (16 bytes)"
            }
        )

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
