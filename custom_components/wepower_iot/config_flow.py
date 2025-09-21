"""Config flow for WePower IoT integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
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
                            "ble": "Bluetooth Low Energy (BLE)"
                        }),
                    }
                ),
            )

        integration_type = user_input["integration_type"]
        
        if integration_type == "ble":
            # Redirect to BLE config flow
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
        return self.async_show_form(
            step_id="ble_info",
            data_schema=vol.Schema({}),
            description_placeholders={
                "message": "BLE devices are automatically discovered by Home Assistant's Bluetooth integration. No manual configuration needed!"
            }
        )
    
    async def async_step_ble_info(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Show BLE information and complete."""
        return self.async_create_entry(
            title="WePower IoT BLE (Auto-Discovery)",
            data={
                "integration_type": "ble",
                "auto_discovery": True
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
