"""BLE sensor platform for WePower IoT integration."""

import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfPressure,
    CONCENTRATION_PARTS_PER_MILLION,
)

from .const import DOMAIN
from .ble_coordinator import WePowerIoTBluetoothProcessorCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WePower IoT BLE sensors from a config entry."""
    _LOGGER.info("Setting up BLE sensor for entry %s", config_entry.entry_id)
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
    
    _LOGGER.info("BLE coordinator found for entry %s, creating sensor entities", config_entry.entry_id)
    
    # Create sensor entities based on device type
    entities = []
    
    # Create a generic sensor entity that will adapt based on the device type
    sensor_entity = WePowerIoTBLESensor(coordinator, config_entry)
    entities.append(sensor_entity)
    
    if entities:
        async_add_entities(entities)


class WePowerIoTBLESensor(SensorEntity):
    """Representation of a WePower IoT BLE sensor."""

    def __init__(
        self,
        coordinator: WePowerIoTBluetoothProcessorCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the BLE sensor."""
        self.coordinator = coordinator
        self.config_entry = config_entry
        self.address = config_entry.unique_id
        
        # Set up basic entity properties
        self._attr_name = config_entry.data.get(CONF_NAME, f"WePower IoT {self.address}")
        self._attr_unique_id = f"{DOMAIN}_{self.address}"
        self._attr_should_poll = False
        
        # Set device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.address)},
            name=self._attr_name,
            manufacturer="WePower",
            model="BLE Sensor",
            sw_version="1.0.0",
        )
        
        # Initialize sensor properties
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = None
        self._attr_native_value = None
        self._attr_available = False
        
        # Device type will be determined from coordinator data
        self._device_type = "unknown"
        
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self._attr_available

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
        self._update_from_coordinator()
        self.async_write_ha_state()

    def _update_from_coordinator(self) -> None:
        """Update sensor state from coordinator data."""
        if not self.coordinator.data:
            self._attr_available = False
            _LOGGER.debug("BLE sensor %s: No coordinator data", self.address)
            return
            
        data = self.coordinator.data
        
        # Update device type
        self._device_type = data.get("device_type", "unknown")
        
        # Set sensor properties based on device type
        self._set_sensor_properties()
        
        # Extract sensor value
        self._extract_sensor_value(data)
        
        # Update availability
        self._attr_available = True
        _LOGGER.debug("BLE sensor %s: Updated with data, available=%s, value=%s, BLE_active=%s", 
                     self.address, self._attr_available, self._attr_native_value, self.coordinator.available)
        
    def _set_sensor_properties(self) -> None:
        """Set sensor properties based on device type."""
        device_type = self._device_type.lower()
        
        # Reset to defaults
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = None
        
        # Set properties based on device type
        if "leak" in device_type:
            self._attr_device_class = SensorDeviceClass.MOISTURE
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_name = f"WePower Leak Sensor {self.address}"
            
        elif "temperature" in device_type:
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_name = f"WePower Temperature Sensor {self.address}"
            
        elif "humidity" in device_type:
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_name = f"WePower Humidity Sensor {self.address}"
            
        elif "pressure" in device_type:
            self._attr_device_class = SensorDeviceClass.PRESSURE
            self._attr_native_unit_of_measurement = UnitOfPressure.HPA
            self._attr_name = f"WePower Pressure Sensor {self.address}"
            
        else:
            # Generic sensor
            self._attr_name = f"WePower IoT Sensor {self.address}"
            
    def _extract_sensor_value(self, data: Dict[str, Any]) -> None:
        """Extract sensor value from coordinator data."""
        # Try to get sensor value from sensor_data
        sensor_data = data.get("sensor_data", {})
        
        if "leak_detected" in sensor_data:
            # For leak sensors, return 100 if leak detected, 0 if not
            self._attr_native_value = 100.0 if sensor_data["leak_detected"] else 0.0
            
        elif "temperature" in sensor_data:
            self._attr_native_value = sensor_data["temperature"]
            
        elif "humidity" in sensor_data:
            self._attr_native_value = sensor_data["humidity"]
            
        elif "pressure" in sensor_data:
            self._attr_native_value = sensor_data["pressure"]
            
        elif "battery_level" in data and data["battery_level"] is not None:
            # Use battery level as a fallback sensor value
            self._attr_native_value = data["battery_level"]
            
        else:
            # No specific sensor value found, use RSSI as a signal strength indicator
            rssi = data.get("rssi")
            if rssi is not None:
                # Convert RSSI to a percentage (rough approximation)
                # RSSI typically ranges from -100 (very weak) to -30 (very strong)
                signal_percentage = max(0, min(100, (rssi + 100) * 100 / 70))
                self._attr_native_value = round(signal_percentage, 1)
            else:
                self._attr_native_value = None

    async def async_update(self) -> None:
        """Update sensor state."""
        await self.coordinator.async_request_refresh()
