"""Constants for the WePower IoT integration."""
from typing import Final

DOMAIN: Final = "wepower_iot"

# Configuration keys
CONF_MQTT_BROKER: Final = "mqtt_broker"
CONF_MQTT_USERNAME: Final = "mqtt_username"
CONF_MQTT_PASSWORD: Final = "mqtt_password"
CONF_ENABLE_BLE: Final = "enable_ble"
CONF_ENABLE_ZIGBEE: Final = "enable_zigbee"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_HEARTBEAT_INTERVAL: Final = "heartbeat_interval"

# Default values
DEFAULT_MQTT_BROKER: Final = "mqtt://homeassistant:1883"
DEFAULT_SCAN_INTERVAL: Final = 0.02
DEFAULT_HEARTBEAT_INTERVAL: Final = 10.0
DEFAULT_ENABLE_BLE: Final = True
DEFAULT_ENABLE_ZIGBEE: Final = True

# MQTT Topics
MQTT_TOPIC_STATUS: Final = "wepower_iot/status"
MQTT_TOPIC_CONTROL: Final = "wepower_iot/control"
MQTT_TOPIC_DEVICE: Final = "wepower_iot/device"
MQTT_TOPIC_DONGLE: Final = "wepower_iot/dongle"

# Device types
DEVICE_TYPE_BLE: Final = "ble"
DEVICE_TYPE_ZIGBEE: Final = "zigbee"
DEVICE_TYPE_ZWAVE: Final = "zwave"
DEVICE_TYPE_MATTER: Final = "matter"
DEVICE_TYPE_GENERIC: Final = "generic"

# Device categories
DEVICE_CATEGORY_SENSOR: Final = "sensor"
DEVICE_CATEGORY_SWITCH: Final = "switch"
DEVICE_CATEGORY_LIGHT: Final = "light"
DEVICE_CATEGORY_DOOR: Final = "door"
DEVICE_CATEGORY_TOGGLE: Final = "toggle"

# Device statuses
DEVICE_STATUS_DISCONNECTED: Final = "disconnected"
DEVICE_STATUS_CONNECTING: Final = "connecting"
DEVICE_STATUS_CONNECTED: Final = "connected"
DEVICE_STATUS_IDENTIFIED: Final = "identified"
DEVICE_STATUS_PAIRED: Final = "paired"
DEVICE_STATUS_OFFLINE: Final = "offline"
DEVICE_STATUS_ERROR: Final = "error"

# BLE discovery modes
BLE_DISCOVERY_MODE_V0_MANUAL: Final = "v0_manual"
BLE_DISCOVERY_MODE_V1_AUTO: Final = "v1_auto"

# Integration name and version
INTEGRATION_NAME: Final = "WePower IoT"
INTEGRATION_VERSION: Final = "1.0.0"
