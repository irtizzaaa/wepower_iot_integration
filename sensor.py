"""Sensor platform for WePower IoT integration."""

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

from .const import (
    DOMAIN,
    DEVICE_CATEGORY_SENSOR,
    DEVICE_STATUS_CONNECTED,
    DEVICE_STATUS_OFFLINE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WePower IoT sensors from a config entry."""
    
    # Get device manager
    device_manager = hass.data[DOMAIN][config_entry.entry_id].get("device_manager")
    if not device_manager:
        return
        
    # Get all sensor devices
    sensor_devices = device_manager.get_devices_by_category(DEVICE_CATEGORY_SENSOR)
    
    # Create sensor entities
    entities = []
    for device in sensor_devices:
        sensor_entity = WePowerIoTSensor(device_manager, device)
        entities.append(sensor_entity)
        
    if entities:
        async_add_entities(entities)


class WePowerIoTSensor(SensorEntity):
    """Representation of a WePower IoT sensor."""

    def __init__(self, device_manager, device: Dict[str, Any]):
        """Initialize the sensor."""
        self.device_manager = device_manager
        self.device = device
        self.device_id = device.get("device_id")
        self._attr_name = device.get("name", self.device_id)
        self._attr_unique_id = f"{DOMAIN}_{self.device_id}"
        self._attr_should_poll = False
        
        # Set device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            name=self._attr_name,
            manufacturer="WePower",
            model=device.get("device_type", "Unknown"),
            sw_version=device.get("firmware_version", "1.0.0"),
        )
        
        # Set sensor properties based on device type
        self._set_sensor_properties()
        
    def _set_sensor_properties(self):
        """Set sensor properties based on device type and category."""
        device_type = self.device.get("device_type", "")
        device_category = self.device.get("category", "")
        
        # Default properties
        self._attr_device_class = SensorDeviceClass.GENERIC
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = None
        
        # Set properties based on device type
        if "leak" in device_type.lower() or "water" in device_type.lower():
            self._attr_device_class = SensorDeviceClass.MOISTURE
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT
            
        elif "vibration" in device_type.lower() or "motion" in device_type.lower():
            self._attr_device_class = SensorDeviceClass.VIBRATION
            self._attr_native_unit_of_measurement = "m/s²"
            self._attr_state_class = SensorStateClass.MEASUREMENT
            
        elif "temperature" in device_type.lower() or "temp" in device_type.lower():
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_state_class = SensorStateClass.MEASUREMENT
            
        elif "humidity" in device_type.lower() or "moisture" in device_type.lower():
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT
            
        elif "pressure" in device_type.lower():
            self._attr_device_class = SensorDeviceClass.PRESSURE
            self._attr_native_unit_of_measurement = UnitOfPressure.HPA
            self._attr_state_class = SensorStateClass.MEASUREMENT
            
        elif "air_quality" in device_type.lower() or "co2" in device_type.lower():
            self._attr_device_class = SensorDeviceClass.CO2
            self._attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
            self._attr_state_class = SensorStateClass.MEASUREMENT
            
        # Set initial state
        self._update_state()
        
    def _update_state(self):
        """Update sensor state from device data."""
        status = self.device.get("status", DEVICE_STATUS_OFFLINE)
        
        if status == DEVICE_STATUS_CONNECTED:
            # Get sensor value from device properties
            sensor_value = self.device.get("sensor_value")
            if sensor_value is not None:
                self._attr_native_value = sensor_value
            else:
                # Simulate sensor value if not available
                self._attr_native_value = self._simulate_sensor_value()
        else:
            # Device is offline
            self._attr_native_value = None
            
        # Update available state
        self._attr_available = status == DEVICE_STATUS_CONNECTED
        
    def _simulate_sensor_value(self):
        """Simulate sensor value for testing purposes."""
        device_type = self.device.get("device_type", "")
        
        if "leak" in device_type.lower():
            # Simulate moisture level (0-100%)
            return 15.5
            
        elif "vibration" in device_type.lower():
            # Simulate vibration level (0-10 m/s²)
            return 2.3
            
        elif "temperature" in device_type.lower():
            # Simulate temperature (20-25°C)
            return 22.5
            
        elif "humidity" in device_type.lower():
            # Simulate humidity (40-60%)
            return 52.0
            
        elif "pressure" in device_type.lower():
            # Simulate pressure (1000-1020 hPa)
            return 1013.2
            
        elif "air_quality" in device_type.lower():
            # Simulate CO2 level (400-800 ppm)
            return 450
            
        # Default value
        return 0.0
        
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            "device_id": self.device_id,
            "device_type": self.device.get("device_type"),
            "status": self.device.get("status"),
            "last_seen": self.device.get("last_seen"),
            "ble_discovery_mode": self.device.get("ble_discovery_mode"),
            "pairing_status": self.device.get("pairing_status"),
            "firmware_version": self.device.get("firmware_version"),
            "created_manually": self.device.get("created_manually", False),
        }
        
    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        # Subscribe to device updates
        self.async_on_remove(
            self.device_manager.subscribe_to_device_updates(
                self.device_id, self._handle_device_update
            )
        )
        
    def _handle_device_update(self, device: Dict[str, Any]):
        """Handle device updates."""
        self.device = device
        self._update_state()
        self.async_write_ha_state()
        
    async def async_update(self) -> None:
        """Update sensor state."""
        # Get latest device data
        updated_device = self.device_manager.get_device(self.device_id)
        if updated_device:
            self.device = updated_device
            self._update_state()
