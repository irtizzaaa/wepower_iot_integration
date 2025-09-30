"""Binary sensor platform for WePower IoT integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_CAPABILITIES,
    ATTR_DEVICE_ID,
    ATTR_DEVICE_STATUS,
    ATTR_DEVICE_TYPE,
    CAPABILITY_SENSOR,
    DEVICE_STATUS_ONLINE,
    DEVICE_STATUS_OFFLINE,
    DOMAIN,
    SENSOR_TYPE_LEAK,
    SENSOR_TYPE_VIBRATION,
)
from .coordinator import WePowerIoTCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WePower IoT binary sensor entities."""
    coordinator: WePowerIoTCoordinator = config_entry.runtime_data
    
    entities = []
    
    # Create binary sensors for each device with sensor capabilities
    for device_id, device_info in coordinator.devices.items():
        capabilities = device_info.get(ATTR_CAPABILITIES, [])
        
        if CAPABILITY_SENSOR in capabilities:
            entities.extend(create_binary_sensor_entities(coordinator, device_id, device_info))
    
    async_add_entities(entities)


def create_binary_sensor_entities(coordinator: WePowerIoTCoordinator, device_id: str, device_info: dict[str, Any]) -> list[BinarySensorEntity]:
    """Create binary sensor entities based on device capabilities."""
    entities = []
    capabilities = device_info.get(ATTR_CAPABILITIES, [])
    
    # Create generic binary sensor
    entities.append(WePowerIoTBinarySensor(coordinator, device_id))
    
    # Create specific binary sensor types if capabilities indicate them
    if any("leak" in cap.lower() for cap in capabilities):
        entities.append(WePowerIoTLeakBinarySensor(coordinator, device_id))
    
    if any("vibration" in cap.lower() for cap in capabilities):
        entities.append(WePowerIoTVibrationBinarySensor(coordinator, device_id))
    
    if any("motion" in cap.lower() for cap in capabilities):
        entities.append(WePowerIoTMotionBinarySensor(coordinator, device_id))
    
    if any("door" in cap.lower() for cap in capabilities):
        entities.append(WePowerIoTDoorBinarySensor(coordinator, device_id))
    
    if any("window" in cap.lower() for cap in capabilities):
        entities.append(WePowerIoTWindowBinarySensor(coordinator, device_id))
    
    if any("smoke" in cap.lower() for cap in capabilities):
        entities.append(WePowerIoTSmokeBinarySensor(coordinator, device_id))
    
    if any("carbon_monoxide" in cap.lower() for cap in capabilities):
        entities.append(WePowerIoTCarbonMonoxideBinarySensor(coordinator, device_id))
    
    return entities


class WePowerIoTBaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base class for WePower IoT binary sensors."""

    def __init__(self, coordinator: WePowerIoTCoordinator, device_id: str) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_should_poll = False
        self._attr_is_on = False

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        device = self.coordinator.get_device(self.device_id)
        if not device:
            return {}
        
        return {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": device.get("device_name", f"WePower IoT {self.device_id}"),
            "manufacturer": device.get("manufacturer", "WePower"),
            "model": device.get("model", "IoT Device"),
            "sw_version": device.get("firmware_version", "Unknown"),
        }

    @property
    def available(self) -> bool:
        """Return if the binary sensor is available."""
        device = self.coordinator.get_device(self.device_id)
        return device is not None and device.get(ATTR_DEVICE_STATUS) == DEVICE_STATUS_ONLINE


class WePowerIoTBinarySensor(WePowerIoTBaseBinarySensor):
    """Representation of a generic WePower IoT binary sensor."""

    def __init__(self, coordinator: WePowerIoTCoordinator, device_id: str) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, device_id)
        self._attr_name = f"Binary Sensor {device_id}"
        self._attr_unique_id = f"{device_id}_binary_sensor"
        self._attr_icon = "mdi:sensor"
        self._attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    @property
    def is_on(self) -> bool:
        """Return true if binary sensor is on."""
        device = self.coordinator.get_device(self.device_id)
        if device:
            raw_data = device.get("raw_data", {})
            if isinstance(raw_data, dict):
                # Try to extract a binary state from raw data
                for key in ["detected", "active", "triggered", "alarm", "alert"]:
                    if key in raw_data:
                        return bool(raw_data[key])
                if "value" in raw_data:
                    return bool(raw_data["value"])
            return device.get(ATTR_DEVICE_STATUS) == DEVICE_STATUS_ONLINE
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        device = self.coordinator.get_device(self.device_id)
        if not device:
            return {}
        
        return {
            "raw_data": device.get("raw_data", {}),
            "capabilities": device.get(ATTR_CAPABILITIES, []),
        }


class WePowerIoTLeakBinarySensor(WePowerIoTBaseBinarySensor):
    """Representation of a leak detection binary sensor."""

    def __init__(self, coordinator: WePowerIoTCoordinator, device_id: str) -> None:
        """Initialize the leak binary sensor."""
        super().__init__(coordinator, device_id)
        self._attr_name = f"Leak Detection {device_id}"
        self._attr_unique_id = f"{device_id}_leak_binary"
        self._attr_icon = "mdi:water-alert"
        self._attr_device_class = BinarySensorDeviceClass.MOISTURE

    @property
    def is_on(self) -> bool:
        """Return true if leak is detected."""
        device = self.coordinator.get_device(self.device_id)
        if device:
            raw_data = device.get("raw_data", {})
            if isinstance(raw_data, dict):
                # Check for leak detection in raw data
                if "leak_detected" in raw_data:
                    return bool(raw_data["leak_detected"])
                if "moisture_detected" in raw_data:
                    return bool(raw_data["moisture_detected"])
                if "water_detected" in raw_data:
                    return bool(raw_data["water_detected"])
                if "moisture" in raw_data:
                    return float(raw_data["moisture"]) > 80
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        device = self.coordinator.get_device(self.device_id)
        if not device:
            return {}
        
        raw_data = device.get("raw_data", {})
        if not isinstance(raw_data, dict):
            return {}
        
        attributes = {}
        
        # Extract leak-specific information
        if "moisture_level" in raw_data:
            attributes["moisture_level"] = raw_data["moisture_level"]
        if "leak_duration" in raw_data:
            attributes["leak_duration"] = raw_data["leak_duration"]
        if "last_dry" in raw_data:
            attributes["last_dry"] = raw_data["last_dry"]
        if "last_leak" in raw_data:
            attributes["last_leak"] = raw_data["last_leak"]
        
        return attributes


class WePowerIoTVibrationBinarySensor(WePowerIoTBaseBinarySensor):
    """Representation of a vibration detection binary sensor."""

    def __init__(self, coordinator: WePowerIoTCoordinator, device_id: str) -> None:
        """Initialize the vibration binary sensor."""
        super().__init__(coordinator, device_id)
        self._attr_name = f"Vibration Detection {device_id}"
        self._attr_unique_id = f"{device_id}_vibration_binary"
        self._attr_icon = "mdi:vibrate"
        self._attr_device_class = BinarySensorDeviceClass.VIBRATION

    @property
    def is_on(self) -> bool:
        """Return true if vibration is detected."""
        device = self.coordinator.get_device(self.device_id)
        if device:
            raw_data = device.get("raw_data", {})
            if isinstance(raw_data, dict):
                # Check for vibration detection in raw data
                if "vibration_detected" in raw_data:
                    return bool(raw_data["vibration_detected"])
                if "motion_detected" in raw_data:
                    return bool(raw_data["motion_detected"])
                if "acceleration" in raw_data:
                    return float(raw_data["acceleration"]) > 1.5
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        device = self.coordinator.get_device(self.device_id)
        if not device:
            return {}
        
        raw_data = device.get("raw_data", {})
        if not isinstance(raw_data, dict):
            return {}
        
        attributes = {}
        
        # Extract vibration-specific information
        if "acceleration" in raw_data:
            attributes["acceleration"] = raw_data["acceleration"]
        if "vibration_intensity" in raw_data:
            attributes["vibration_intensity"] = raw_data["vibration_intensity"]
        if "last_stable" in raw_data:
            attributes["last_stable"] = raw_data["last_stable"]
        if "last_vibration" in raw_data:
            attributes["last_vibration"] = raw_data["last_vibration"]
        
        return attributes


class WePowerIoTMotionBinarySensor(WePowerIoTBaseBinarySensor):
    """Representation of a motion detection binary sensor."""

    def __init__(self, coordinator: WePowerIoTCoordinator, device_id: str) -> None:
        """Initialize the motion binary sensor."""
        super().__init__(coordinator, device_id)
        self._attr_name = f"Motion Detection {device_id}"
        self._attr_unique_id = f"{device_id}_motion_binary"
        self._attr_icon = "mdi:motion-sensor"
        self._attr_device_class = BinarySensorDeviceClass.MOTION

    @property
    def is_on(self) -> bool:
        """Return true if motion is detected."""
        device = self.coordinator.get_device(self.device_id)
        if device:
            raw_data = device.get("raw_data", {})
            if isinstance(raw_data, dict):
                # Check for motion detection in raw data
                if "motion_detected" in raw_data:
                    return bool(raw_data["motion_detected"])
                if "occupancy" in raw_data:
                    return bool(raw_data["occupancy"])
                if "presence" in raw_data:
                    return bool(raw_data["presence"])
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        device = self.coordinator.get_device(self.device_id)
        if not device:
            return {}
        
        raw_data = device.get("raw_data", {})
        if not isinstance(raw_data, dict):
            return {}
        
        attributes = {}
        
        # Extract motion-specific information
        if "motion_count" in raw_data:
            attributes["motion_count"] = raw_data["motion_count"]
        if "last_motion" in raw_data:
            attributes["last_motion"] = raw_data["last_motion"]
        if "motion_duration" in raw_data:
            attributes["motion_duration"] = raw_data["motion_duration"]
        
        return attributes


class WePowerIoTDoorBinarySensor(WePowerIoTBaseBinarySensor):
    """Representation of a door state binary sensor."""

    def __init__(self, coordinator: WePowerIoTCoordinator, device_id: str) -> None:
        """Initialize the door binary sensor."""
        super().__init__(coordinator, device_id)
        self._attr_name = f"Door State {device_id}"
        self._attr_unique_id = f"{device_id}_door_binary"
        self._attr_icon = "mdi:door"
        self._attr_device_class = BinarySensorDeviceClass.DOOR

    @property
    def is_on(self) -> bool:
        """Return true if door is open."""
        device = self.coordinator.get_device(self.device_id)
        if device:
            raw_data = device.get("raw_data", {})
            if isinstance(raw_data, dict):
                # Check for door state in raw data
                if "door_open" in raw_data:
                    return bool(raw_data["door_open"])
                if "door_state" in raw_data:
                    return raw_data["door_state"] == "open"
                if "open" in raw_data:
                    return bool(raw_data["open"])
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        device = self.coordinator.get_device(self.device_id)
        if not device:
            return {}
        
        raw_data = device.get("raw_data", {})
        if not isinstance(raw_data, dict):
            return {}
        
        attributes = {}
        
        # Extract door-specific information
        if "door_type" in raw_data:
            attributes["door_type"] = raw_data["door_type"]
        if "lock_state" in raw_data:
            attributes["lock_state"] = raw_data["lock_state"]
        if "last_opened" in raw_data:
            attributes["last_opened"] = raw_data["last_opened"]
        if "last_closed" in raw_data:
            attributes["last_closed"] = raw_data["last_closed"]
        
        return attributes


class WePowerIoTWindowBinarySensor(WePowerIoTBaseBinarySensor):
    """Representation of a window state binary sensor."""

    def __init__(self, coordinator: WePowerIoTCoordinator, device_id: str) -> None:
        """Initialize the window binary sensor."""
        super().__init__(coordinator, device_id)
        self._attr_name = f"Window State {device_id}"
        self._attr_unique_id = f"{device_id}_window_binary"
        self._attr_icon = "mdi:window-open"
        self._attr_device_class = BinarySensorDeviceClass.WINDOW

    @property
    def is_on(self) -> bool:
        """Return true if window is open."""
        device = self.coordinator.get_device(self.device_id)
        if device:
            raw_data = device.get("raw_data", {})
            if isinstance(raw_data, dict):
                # Check for window state in raw data
                if "window_open" in raw_data:
                    return bool(raw_data["window_open"])
                if "window_state" in raw_data:
                    return raw_data["window_state"] == "open"
                if "open" in raw_data:
                    return bool(raw_data["open"])
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        device = self.coordinator.get_device(self.device_id)
        if not device:
            return {}
        
        raw_data = device.get("raw_data", {})
        if not isinstance(raw_data, dict):
            return {}
        
        attributes = {}
        
        # Extract window-specific information
        if "window_type" in raw_data:
            attributes["window_type"] = raw_data["window_type"]
        if "last_opened" in raw_data:
            attributes["last_opened"] = raw_data["last_opened"]
        if "last_closed" in raw_data:
            attributes["last_closed"] = raw_data["last_closed"]
        
        return attributes


class WePowerIoTSmokeBinarySensor(WePowerIoTBaseBinarySensor):
    """Representation of a smoke detection binary sensor."""

    def __init__(self, coordinator: WePowerIoTCoordinator, device_id: str) -> None:
        """Initialize the smoke binary sensor."""
        super().__init__(coordinator, device_id)
        self._attr_name = f"Smoke Detection {device_id}"
        self._attr_unique_id = f"{device_id}_smoke_binary"
        self._attr_icon = "mdi:smoke-detector"
        self._attr_device_class = BinarySensorDeviceClass.SMOKE

    @property
    def is_on(self) -> bool:
        """Return true if smoke is detected."""
        device = self.coordinator.get_device(self.device_id)
        if device:
            raw_data = device.get("raw_data", {})
            if isinstance(raw_data, dict):
                # Check for smoke detection in raw data
                if "smoke_detected" in raw_data:
                    return bool(raw_data["smoke_detected"])
                if "smoke_level" in raw_data:
                    return float(raw_data["smoke_level"]) > 50
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        device = self.coordinator.get_device(self.device_id)
        if not device:
            return {}
        
        raw_data = device.get("raw_data", {})
        if not isinstance(raw_data, dict):
            return {}
        
        attributes = {}
        
        # Extract smoke-specific information
        if "smoke_level" in raw_data:
            attributes["smoke_level"] = raw_data["smoke_level"]
        if "last_clear" in raw_data:
            attributes["last_clear"] = raw_data["last_clear"]
        if "last_detection" in raw_data:
            attributes["last_detection"] = raw_data["last_detection"]
        
        return attributes


class WePowerIoTCarbonMonoxideBinarySensor(WePowerIoTBaseBinarySensor):
    """Representation of a carbon monoxide detection binary sensor."""

    def __init__(self, coordinator: WePowerIoTCoordinator, device_id: str) -> None:
        """Initialize the carbon monoxide binary sensor."""
        super().__init__(coordinator, device_id)
        self._attr_name = f"Carbon Monoxide Detection {device_id}"
        self._attr_unique_id = f"{device_id}_co_binary"
        self._attr_icon = "mdi:molecule-co2"
        self._attr_device_class = BinarySensorDeviceClass.CO

    @property
    def is_on(self) -> bool:
        """Return true if carbon monoxide is detected."""
        device = self.coordinator.get_device(self.device_id)
        if device:
            raw_data = device.get("raw_data", {})
            if isinstance(raw_data, dict):
                # Check for CO detection in raw data
                if "co_detected" in raw_data:
                    return bool(raw_data["co_detected"])
                if "co_level" in raw_data:
                    return float(raw_data["co_level"]) > 35
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        device = self.coordinator.get_device(self.device_id)
        if not device:
            return {}
        
        raw_data = device.get("raw_data", {})
        if not isinstance(raw_data, dict):
            return {}
        
        attributes = {}
        
        # Extract CO-specific information
        if "co_level" in raw_data:
            attributes["co_level"] = raw_data["co_level"]
        if "last_clear" in raw_data:
            attributes["last_clear"] = raw_data["last_clear"]
        if "last_detection" in raw_data:
            attributes["last_detection"] = raw_data["last_detection"]
        
        return attributes
