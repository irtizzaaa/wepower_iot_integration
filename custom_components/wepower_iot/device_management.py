"""Device management for WePower IoT integration."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_DEVICE_ID, CONF_NAME
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.components.mqtt import async_publish, async_subscribe

from .const import (
    DOMAIN,
    DEVICE_TYPE_BLE,
    DEVICE_TYPE_ZIGBEE,
    DEVICE_CATEGORY_SENSOR,
    DEVICE_CATEGORY_SWITCH,
    DEVICE_CATEGORY_LIGHT,
    DEVICE_CATEGORY_DOOR,
    DEVICE_CATEGORY_TOGGLE,
    DEVICE_STATUS_CONNECTED,
    DEVICE_STATUS_OFFLINE,
    BLE_DISCOVERY_MODE_V0_MANUAL,
    BLE_DISCOVERY_MODE_V1_AUTO,
    SIGNAL_DEVICE_UPDATED,
)

_LOGGER = logging.getLogger(__name__)

# Signal for device updates
SIGNAL_DEVICE_ADDED = f"{DOMAIN}_device_added"
SIGNAL_DEVICE_REMOVED = f"{DOMAIN}_device_removed"

class WePowerIoTDeviceManager:
    """Manages WePower IoT devices."""

    def __init__(self, hass: HomeAssistant, config: Dict[str, Any]):
        """Initialize the device manager."""
        self.hass = hass
        self.config = config
        self.devices: Dict[str, Dict[str, Any]] = {}
        self.dongles: Dict[str, Dict[str, Any]] = {}
        self.entity_registry = er.async_get(hass)
        self._subscribers = {}
        self._mqtt_client = None
        self._created_entities = set()
        
    async def start(self):
        """Start the device manager."""
        # Subscribe to MQTT topics
        await self._subscribe_to_mqtt()
        
        # Start device discovery
        asyncio.create_task(self._device_discovery_loop())
        
        # Add some test devices for demonstration
        await self._add_test_devices()
        
    async def stop(self):
        """Stop the device manager."""
        # Cleanup tasks
        pass
        
    async def _add_test_devices(self):
        """Add some test devices for demonstration."""
        test_devices = [
            {
                "device_id": "test_ble_leak_sensor",
                "device_type": "ble",
                "category": "sensor",
                "name": "Test BLE Leak Sensor",
                "ble_discovery_mode": "v0_manual",
                "status": "connected"
            },
            {
                "device_id": "test_zigbee_light_switch",
                "device_type": "zigbee",
                "category": "light",
                "name": "Test Zigbee Light Switch",
                "ble_discovery_mode": "v1_auto",
                "status": "connected"
            },
            {
                "device_id": "test_ble_temperature",
                "device_type": "ble",
                "category": "sensor",
                "name": "Test BLE Temperature Sensor",
                "ble_discovery_mode": "v1_auto",
                "status": "connected"
            }
        ]
        
        for device_data in test_devices:
            await self.add_device(device_data)
            # Mark as created entity
            self._created_entities.add(device_data["device_id"])
            
    async def add_device(self, device_data: Dict[str, Any]) -> bool:
        """Add a new device manually."""
        try:
            device_id = device_data["device_id"]
            
            # Create device entry
            device = {
                "device_id": device_id,
                "device_type": device_data.get("device_type", "ble"),
                "category": device_data.get("category", "sensor"),
                "name": device_data.get("name", device_id),
                "ble_discovery_mode": device_data.get("ble_discovery_mode", "v0_manual"),
                "status": device_data.get("status", "disconnected"),
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "created_manually": True,
                "properties": {}
            }
            
            self.devices[device_id] = device
            
            # Notify subscribers - this is called from async context, so it's safe
            self.hass.async_create_task(
                self._async_notify_device_added(device)
            )
            
            _LOGGER.info(f"Device added: {device_id}")
            return True
            
        except Exception as e:
            _LOGGER.error(f"Error adding device: {e}")
            return False
            
    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get a device by ID."""
        return self.devices.get(device_id)
        
    def get_all_devices(self) -> List[Dict[str, Any]]:
        """Get all devices."""
        return list(self.devices.values())
        
    def get_devices_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get devices by category."""
        return [d for d in self.devices.values() if d.get("category") == category]
        
    def get_devices_by_type(self, device_type: str) -> List[Dict[str, Any]]:
        """Get devices by type."""
        return [d for d in self.devices.values() if d.get("device_type") == device_type]
        
    def get_devices_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get devices by status."""
        return [d for d in self.devices.values() if d.get("status") == status]
        
    def get_dongles(self) -> List[Dict[str, Any]]:
        """Get all dongles."""
        return list(self.dongles.values())
        
    async def _subscribe_to_mqtt(self):
        """Subscribe to relevant MQTT topics."""
        try:
            # Subscribe to MQTT topics for device updates
            await async_subscribe(
                self.hass,
                "wepower_iot/status",
                self._handle_status_message
            )
            await async_subscribe(
                self.hass,
                "wepower_iot/dongle/+/+",
                self._handle_dongle_message
            )
            await async_subscribe(
                self.hass,
                "wepower_iot/device/+/+",
                self._handle_device_message
            )
            await async_subscribe(
                self.hass,
                "wepower_iot/control/+/+",
                self._handle_control_message
            )
            _LOGGER.info("Device manager subscribed to MQTT topics")
        except Exception as e:
            _LOGGER.error(f"Error subscribing to MQTT: {e}")
            
    def _handle_status_message(self, msg):
        """Handle status messages from add-on."""
        try:
            data = json.loads(msg.payload)
            _LOGGER.info(f"Status message received: {data}")
        except Exception as e:
            _LOGGER.error(f"Error handling status message: {e}")
            
    def _handle_dongle_message(self, msg):
        """Handle dongle status messages."""
        try:
            data = json.loads(msg.payload)
            _LOGGER.info(f"Dongle message received: {data}")
            
            # Update dongle status
            port = data.get("port", "unknown")
            device_type = data.get("device_type", "unknown")
            status = data.get("status", "unknown")
            
            # Create or update dongle
            dongle_id = f"{device_type}_{port}"
            self.dongles[dongle_id] = {
                "port": port,
                "device_type": device_type,
                "status": status,
                "device_count": data.get("device_count", 0),
                "timestamp": data.get("timestamp")
            }
            
            # Schedule the dispatcher call in the main event loop
            self.hass.loop.call_soon_threadsafe(
                lambda: self.hass.async_create_task(
                    self._async_notify_dongle_update(self.dongles[dongle_id])
                )
            )
            
        except Exception as e:
            _LOGGER.error(f"Error handling dongle message: {e}")
            
    def _handle_device_message(self, msg):
        """Handle device messages."""
        try:
            data = json.loads(msg.payload)
            _LOGGER.info(f"Device message received: {data}")
            
            # Update device status
            device_id = data.get("device_id")
            if device_id:
                # Ensure device has all required fields
                if "name" not in data:
                    data["name"] = device_id
                if "last_seen" not in data:
                    from datetime import datetime, timezone
                    data["last_seen"] = datetime.now(timezone.utc).isoformat()
                if "properties" not in data:
                    data["properties"] = {}
                    
                self.devices[device_id] = data
                _LOGGER.info(f"Updated device {device_id} with status: {data.get('status')}")
                
                # Schedule the dispatcher call in the main event loop
                self.hass.loop.call_soon_threadsafe(
                    lambda: self.hass.async_create_task(
                        self._async_notify_device_update(data)
                    )
                )
                
        except Exception as e:
            _LOGGER.error(f"Error handling device message: {e}")
            
    def _handle_control_message(self, msg):
        """Handle control messages from add-on."""
        try:
            data = json.loads(msg.payload)
            _LOGGER.info(f"Control message received: {data}")
            
            # Handle different control actions
            action = data.get("action")
            if action == "toggle_ble":
                enabled = data.get("enabled", False)
                _LOGGER.info(f"BLE toggle command received: {enabled}")
                # Update BLE status in config
                self.config["enable_ble"] = enabled
                
            elif action == "toggle_zigbee":
                enabled = data.get("enabled", False)
                _LOGGER.info(f"Zigbee toggle command received: {enabled}")
                # Update Zigbee status in config
                self.config["enable_zigbee"] = enabled
                
        except Exception as e:
            _LOGGER.error(f"Error handling control message: {e}")
        
    async def publish_mqtt(self, topic: str, payload: str):
        """Publish MQTT message."""
        try:
            await async_publish(self.hass, topic, payload)
            _LOGGER.debug(f"Published MQTT message: {topic} -> {payload}")
        except Exception as e:
            _LOGGER.error(f"Failed to publish MQTT message: {e}")
            
    async def _async_notify_dongle_update(self, dongle_data):
        """Async helper to notify dongle updates."""
        async_dispatcher_send(self.hass, SIGNAL_DEVICE_UPDATED, dongle_data)
        
    async def _async_notify_device_update(self, device_data):
        """Async helper to notify device updates."""
        async_dispatcher_send(self.hass, SIGNAL_DEVICE_UPDATED, device_data)
        
        # Check if this is a new device that needs entity creation
        device_id = device_data.get("device_id")
        if device_id and device_id not in self._created_entities:
            self._created_entities.add(device_id)
            # Signal that a new device was added
            async_dispatcher_send(self.hass, SIGNAL_DEVICE_ADDED, device_data)
        
    async def _async_notify_device_added(self, device_data):
        """Async helper to notify device added."""
        async_dispatcher_send(self.hass, SIGNAL_DEVICE_ADDED, device_data)
            
    @property
    def mqtt_client(self):
        """Get MQTT client for compatibility."""
        return self
            
    async def _device_discovery_loop(self):
        """Main device discovery loop."""
        while True:
            try:
                # Update device statuses
                await self._update_device_statuses()
                
                # Wait before next scan
                await asyncio.sleep(30)
                
            except Exception as e:
                _LOGGER.error(f"Error in device discovery loop: {e}")
                await asyncio.sleep(60)
                
    async def _update_device_statuses(self):
        """Update status of all devices."""
        for device_id, device in self.devices.items():
            # Simulate some devices going offline
            if device.get("status") == "connected":
                # Randomly set some devices to offline for testing
                import random
                if random.random() < 0.1:  # 10% chance
                    device["status"] = "offline"
                    device["last_seen"] = datetime.now(timezone.utc).isoformat()
                    self.hass.async_create_task(
                        self._async_notify_device_update(device)
                    )
                    
    def subscribe_to_device_updates(self, device_id: str, callback):
        """Subscribe to device updates."""
        if device_id not in self._subscribers:
            self._subscribers[device_id] = []
        self._subscribers[device_id].append(callback)
        
        # Return unsubscribe function
        def unsubscribe():
            if device_id in self._subscribers:
                self._subscribers[device_id].remove(callback)
        return unsubscribe
        
    def subscribe_to_updates(self, callback):
        """Subscribe to general updates."""
        if "general" not in self._subscribers:
            self._subscribers["general"] = []
        self._subscribers["general"].append(callback)
        
        # Return unsubscribe function
        def unsubscribe():
            if "general" in self._subscribers:
                self._subscribers["general"].remove(callback)
        return unsubscribe
