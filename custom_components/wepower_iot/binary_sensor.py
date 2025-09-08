"""Binary sensor platform for WePower IoT integration."""

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
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_NAME,
)

from .const import (
    DOMAIN,
    DEVICE_STATUS_CONNECTED,
    DEVICE_STATUS_OFFLINE,
    SIGNAL_DEVICE_UPDATED,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WePower IoT binary sensors from a config entry."""
    
    # Get device manager
    device_manager = hass.data[DOMAIN][config_entry.entry_id].get("device_manager")
    if not device_manager:
        return
        
    # Create binary sensor entities for dongle status
    entities = []
    
    # BLE Connection Status
    ble_sensor = WePowerIoTBLESensor(device_manager)
    entities.append(ble_sensor)
    
    # Zigbee Connection Status
    zigbee_sensor = WePowerIoTZigbeeSensor(device_manager)
    entities.append(zigbee_sensor)
    
    if entities:
        async_add_entities(entities)


class WePowerIoTBLESensor(BinarySensorEntity):
    """Representation of BLE connection status."""

    def __init__(self, device_manager):
        """Initialize the BLE sensor."""
        self.device_manager = device_manager
        self._attr_name = "WePower IoT BLE Connected"
        self._attr_unique_id = f"{DOMAIN}_ble_connected"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_icon = "mdi:bluetooth"
        self._attr_should_poll = False
        
        # Set device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "ble_dongle")},
            name="WePower IoT BLE Dongle",
            manufacturer="WePower",
            model="BLE Dongle",
            sw_version="1.0.0",
        )
        
        # Set initial state
        self._update_state()
        
    def _update_state(self):
        """Update sensor state from device manager."""
        # Check if any BLE dongles are connected
        ble_dongles = [d for d in self.device_manager.get_dongles() 
                      if d.get("device_type") == "ble" and 
                      d.get("status") == DEVICE_STATUS_CONNECTED]
        
        self._attr_is_on = len(ble_dongles) > 0
        
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        ble_dongles = [d for d in self.device_manager.get_dongles() 
                      if d.get("device_type") == "ble"]
        
        return {
            "dongle_count": len(ble_dongles),
            "connected_dongles": [d.get("port") for d in ble_dongles 
                                if d.get("status") == DEVICE_STATUS_CONNECTED],
            "offline_dongles": [d.get("port") for d in ble_dongles 
                               if d.get("status") == DEVICE_STATUS_OFFLINE],
            "last_update": datetime.now(timezone.utc).isoformat(),
        }
        
    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        # Subscribe to device manager updates
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_DEVICE_UPDATED, self._handle_update
            )
        )
        
    def _handle_update(self, data):
        """Handle device manager updates."""
        self._update_state()
        # Schedule the state write in the main event loop
        self.hass.loop.call_soon_threadsafe(
            lambda: self.hass.async_create_task(self._async_write_state())
        )
        
    async def _async_write_state(self):
        """Async helper to write state."""
        self.async_write_ha_state()
        
    async def async_update(self) -> None:
        """Update sensor state."""
        self._update_state()


class WePowerIoTZigbeeSensor(BinarySensorEntity):
    """Representation of Zigbee connection status."""

    def __init__(self, device_manager):
        """Initialize the Zigbee sensor."""
        self.device_manager = device_manager
        self._attr_name = "WePower IoT Zigbee Connected"
        self._attr_unique_id = f"{DOMAIN}_zigbee_connected"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_icon = "mdi:zigbee"
        self._attr_should_poll = False
        
        # Set device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "zigbee_dongle")},
            name="WePower IoT Zigbee Dongle",
            manufacturer="WePower",
            model="Zigbee Dongle",
            sw_version="1.0.0",
        )
        
        # Set initial state
        self._update_state()
        
    def _update_state(self):
        """Update sensor state from device manager."""
        # Check if any Zigbee dongles are connected
        zigbee_dongles = [d for d in self.device_manager.get_dongles() 
                         if d.get("device_type") == "zigbee" and 
                         d.get("status") == DEVICE_STATUS_CONNECTED]
        
        self._attr_is_on = len(zigbee_dongles) > 0
        
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        zigbee_dongles = [d for d in self.device_manager.get_dongles() 
                         if d.get("device_type") == "zigbee"]
        
        return {
            "dongle_count": len(zigbee_dongles),
            "connected_dongles": [d.get("port") for d in zigbee_dongles 
                                if d.get("status") == DEVICE_STATUS_CONNECTED],
            "offline_dongles": [d.get("port") for d in zigbee_dongles 
                               if d.get("status") == DEVICE_STATUS_OFFLINE],
            "last_update": datetime.now(timezone.utc).isoformat(),
        }
        
    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        # Subscribe to device manager updates
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_DEVICE_UPDATED, self._handle_update
            )
        )
        
    def _handle_update(self, data):
        """Handle device manager updates."""
        self._update_state()
        # Schedule the state write in the main event loop
        self.hass.loop.call_soon_threadsafe(
            lambda: self.hass.async_create_task(self._async_write_state())
        )
        
    async def _async_write_state(self):
        """Async helper to write state."""
        self.async_write_ha_state()
        
    async def async_update(self) -> None:
        """Update sensor state."""
        self._update_state()
