"""BLE binary sensor platform for WePower IoT integration."""

import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, CONF_ADDRESS
from .ble_coordinator import WePowerIoTBluetoothProcessorCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WePower IoT BLE binary sensors from a config entry."""
    _LOGGER.info("Setting up BLE binary sensor for entry %s", config_entry.entry_id)
    address = config_entry.unique_id
    if not address:
        _LOGGER.error("No address found in config entry")
        return

    # Get the BLE coordinator from runtime_data
    coordinator = config_entry.runtime_data
    if not coordinator:
        # Fallback: try to get from hass.data
        _LOGGER.warning("No coordinator in runtime_data, trying hass.data for entry %s", config_entry.entry_id)
        try:
            coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
        except KeyError:
            _LOGGER.error("No coordinator found in runtime_data or hass.data for entry %s", config_entry.entry_id)
            return
    
    _LOGGER.info("BLE coordinator found for entry %s, creating binary sensor entities", config_entry.entry_id)
    
    # Create binary sensor entities based on device type
    entities = []
    
    # Create a binary sensor entity for leak detection
    binary_sensor_entity = WePowerIoTBLEBinarySensor(coordinator, config_entry)
    entities.append(binary_sensor_entity)
    
    if entities:
        async_add_entities(entities)


class WePowerIoTBLEBinarySensor(BinarySensorEntity):
    """Representation of a WePower IoT BLE binary sensor."""

    def __init__(
        self,
        coordinator: WePowerIoTBluetoothProcessorCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the BLE binary sensor."""
        self.coordinator = coordinator
        self.config_entry = config_entry
        # Get the current MAC address from config data (may have been updated by discovery)
        self.address = config_entry.data.get(CONF_ADDRESS, config_entry.unique_id)
        
        # Set up basic entity properties
        self._attr_name = config_entry.data.get("name", f"WePower IoT {self.address}")
        self._attr_unique_id = f"{DOMAIN}_{self.address}_binary"
        self._attr_should_poll = False
        
        # Set device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.address)},
            name=self._attr_name,
            manufacturer="WePower",
            model="BLE Sensor",
            sw_version="1.0.0",
        )
        
        # Initialize binary sensor properties
        self._attr_device_class = None
        self._attr_is_on = None
        self._attr_available = False
        
        # Device type will be determined from coordinator data
        self._device_type = "unknown"
        
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.available and self._attr_available

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        attrs = {
            "address": self.address,
            "device_type": self._device_type,
            "rssi": None,
            "signal_strength": None,
            "battery_level": None,
            "last_seen": None,
            "ble_active": False,
            "ble_connected": False,
            "ble_status": "inactive",
        }
        
        # Add data from coordinator if available
        if self.coordinator.data:
            attrs.update({
                "rssi": self.coordinator.data.get("rssi"),
                "signal_strength": self.coordinator.data.get("signal_strength"),
                "battery_level": self.coordinator.data.get("battery_level"),
                "last_seen": self.coordinator.data.get("timestamp"),
                "ble_active": True,  # If we have data, BLE is active
                "ble_connected": self.coordinator.available,  # Use coordinator availability
                "ble_status": "active" if self.coordinator.available else "inactive",
                "last_update_success": getattr(self.coordinator, 'last_update_success', True),
            })
            
            # Add sensor-specific attributes
            if "sensor_data" in self.coordinator.data:
                sensor_data = self.coordinator.data["sensor_data"]
                if "leak_detected" in sensor_data:
                    attrs["leak_detected"] = sensor_data["leak_detected"]
                if "event_counter" in sensor_data:
                    attrs["event_counter"] = sensor_data["event_counter"]
                if "sensor_event" in sensor_data:
                    attrs["sensor_event"] = sensor_data["sensor_event"]
        
        return attrs

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()
        # Register with coordinator to receive updates
        self._unsub_coordinator = self.coordinator.async_add_listener(self._handle_coordinator_update)
        # Set up cleanup when entity is removed
        self.async_on_remove(self._unsub_coordinator)

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            # Store previous state to detect changes
            previous_state = self._attr_is_on
            
            self._update_from_coordinator()
            
            # Check if state changed and log for automation debugging
            if previous_state != self._attr_is_on:
                _LOGGER.info("🔄 BINARY SENSOR STATE CHANGED: %s | Previous: %s | New: %s", 
                           self.address, previous_state, self._attr_is_on)
            
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error handling coordinator update for %s: %s", self.address, e)

    def _update_from_coordinator(self) -> None:
        """Update binary sensor state from coordinator data."""
        if not self.coordinator.data:
            self._attr_available = False
            _LOGGER.debug("BLE binary sensor %s: No coordinator data", self.address)
            return
            
        data = self.coordinator.data
        _LOGGER.info("🔄 UPDATING BINARY SENSOR: %s | Coordinator data: %s", self.address, data)
        
        # Update device type
        self._device_type = data.get("device_type", "unknown")
        _LOGGER.info("🏷️ DEVICE TYPE: %s | Type: %s", self.address, self._device_type)
        
        # Set sensor properties based on device type
        self._set_sensor_properties()
        
        # Update device info with proper name and model
        self._update_device_info()
        
        # Extract binary sensor value
        self._extract_binary_sensor_value(data)
        
        # Update availability
        self._attr_available = True
        _LOGGER.info("✅ BINARY SENSOR UPDATED: %s | Available: %s | Value: %s | BLE_active: %s | Coordinator_available: %s", 
                     self.address, self._attr_available, self._attr_is_on, True, self.coordinator.available)
        
    def _set_sensor_properties(self) -> None:
        """Set binary sensor properties based on device type."""
        device_type = self._device_type.lower()
        
        # Get short address for display
        short_address = self.address.replace(":", "")[-6:].upper()
        
        # Set properties based on device type
        if "leak" in device_type:
            self._attr_device_class = BinarySensorDeviceClass.MOISTURE
            self._attr_name = f"WePower Leak Detection {self._get_professional_device_id()}"
            self._attr_icon = "mdi:water"
            
        elif "temperature" in device_type:
            self._attr_device_class = BinarySensorDeviceClass.COLD
            self._attr_name = f"WePower Temperature Alert {self._get_professional_device_id()}"
            self._attr_icon = "mdi:thermometer-alert"
            
        elif "humidity" in device_type:
            self._attr_device_class = BinarySensorDeviceClass.MOISTURE
            self._attr_name = f"WePower Humidity Alert {self._get_professional_device_id()}"
            self._attr_icon = "mdi:water-alert"
            
        elif "pressure" in device_type:
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM
            self._attr_name = f"WePower Pressure Alert {self._get_professional_device_id()}"
            self._attr_icon = "mdi:gauge-alert"
            
        elif "vibration" in device_type:
            self._attr_device_class = BinarySensorDeviceClass.VIBRATION
            self._attr_name = f"WePower Vibration Alert {self._get_professional_device_id()}"
            self._attr_icon = "mdi:vibrate"
            
        elif "door" in device_type:
            self._attr_device_class = BinarySensorDeviceClass.DOOR
            self._attr_name = f"WePower Door Status {self._get_professional_device_id()}"
            self._attr_icon = "mdi:door"
            
        elif "switch" in device_type:
            # Skip switch devices - they should be handled by switch platform
            return
            
        else:
            # Generic binary sensor
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM
            self._attr_name = f"WePower IoT Alert {self._get_professional_device_id()}"
            self._attr_icon = "mdi:alert"

    def _update_device_info(self) -> None:
        """Update device info with proper name and model."""
        device_type = self._device_type.lower()
        
        # Set model based on device type
        model_map = {
            "leak_sensor": "Leak Sensor",
            "temperature_sensor": "Temperature Sensor",
            "humidity_sensor": "Humidity Sensor",
            "pressure_sensor": "Pressure Sensor",
            "vibration_sensor": "Vibration Sensor",
            "on_off_switch": "On/Off Switch",
            "light_switch": "Light Switch",
            "door_switch": "Door Switch",
            "toggle_switch": "Toggle Switch",
            "unknown_device": "IoT Device"
        }
        
        model = model_map.get(device_type, "IoT Sensor")
        
        # Update device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.address)},
            name=self._attr_name,
            manufacturer="WePower",
            model=model,
            sw_version="1.0.0",
        )

    def _get_professional_device_id(self) -> str:
        """Generate a professional device identifier from MAC address."""
        # Remove colons and get last 6 characters
        clean_address = self.address.replace(":", "").upper()
        last_6 = clean_address[-6:]
        
        # Convert to a more professional format
        device_number = int(last_6, 16) % 1000  # Get a number between 0-999
        return f"Unit-{device_number:03d}"
            
    def _extract_binary_sensor_value(self, data: Dict[str, Any]) -> None:
        """Extract binary sensor value from coordinator data."""
        _LOGGER.info("🔍 EXTRACTING BINARY SENSOR VALUE: %s | Data: %s", self.address, data)
        
        # Try to get sensor value from sensor_data
        sensor_data = data.get("sensor_data", {})
        _LOGGER.info("📊 SENSOR DATA: %s | Sensor data: %s", self.address, sensor_data)
        
        if "leak_detected" in sensor_data:
            # For leak sensors, return True if leak detected, False if not
            self._attr_is_on = sensor_data["leak_detected"]
            _LOGGER.info("💧 LEAK BINARY SENSOR: %s | Leak detected: %s | Value: %s", 
                        self.address, sensor_data["leak_detected"], self._attr_is_on)
            
        elif "vibration_detected" in sensor_data:
            # For vibration sensors, return True if vibration detected
            self._attr_is_on = sensor_data["vibration_detected"]
            _LOGGER.info("📳 VIBRATION BINARY SENSOR: %s | Vibration detected: %s | Value: %s", 
                        self.address, sensor_data["vibration_detected"], self._attr_is_on)
            
        elif "door_open" in sensor_data:
            # For door switches, return True if door is open
            self._attr_is_on = sensor_data["door_open"]
            _LOGGER.info("🚪 DOOR BINARY SENSOR: %s | Door open: %s | Value: %s", 
                        self.address, sensor_data["door_open"], self._attr_is_on)
            
        elif "switch_on" in sensor_data:
            # For switches, return True if switch is on
            self._attr_is_on = sensor_data["switch_on"]
            _LOGGER.info("🔌 SWITCH BINARY SENSOR: %s | Switch on: %s | Value: %s", 
                        self.address, sensor_data["switch_on"], self._attr_is_on)
            
        elif "sensor_event" in sensor_data:
            # For other sensors, use sensor_event as binary state
            self._attr_is_on = sensor_data["sensor_event"] > 0
            _LOGGER.info("📡 SENSOR EVENT BINARY: %s | Event: %s | Value: %s", 
                        self.address, sensor_data["sensor_event"], self._attr_is_on)
            
        else:
            # No specific binary value found, check if this is a leak sensor
            if "leak" in self._device_type.lower():
                # For leak sensors without data, assume no leak (False)
                self._attr_is_on = False
                _LOGGER.info("💧 LEAK SENSOR DEFAULT: %s | No leak data, assuming no leak (False)", self.address)
            else:
                # For other sensors, default to False
                self._attr_is_on = False
                _LOGGER.warning("⚠️ NO BINARY VALUE: %s | No leak detection or sensor event found", self.address)

    async def async_update(self) -> None:
        """Update binary sensor state."""
        await self.coordinator.async_request_refresh()
