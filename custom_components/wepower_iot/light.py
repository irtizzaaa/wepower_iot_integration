"""Light platform for WePower IoT integration."""

import logging
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timezone
import json

from homeassistant.components.light import (
    LightEntity,
    ColorMode,
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ATTR_COLOR_TEMP,
    ATTR_TRANSITION,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_NAME,
)

from .const import (
    DOMAIN,
    DEVICE_CATEGORY_LIGHT,
    DEVICE_STATUS_CONNECTED,
    DEVICE_STATUS_OFFLINE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WePower IoT lights from a config entry."""
    
    # Get device manager
    device_manager = hass.data[DOMAIN][config_entry.entry_id].get("device_manager")
    if not device_manager:
        return
        
    # Get all light devices
    light_devices = device_manager.get_devices_by_category(DEVICE_CATEGORY_LIGHT)
    
    # Create light entities
    entities = []
    for device in light_devices:
        light_entity = WePowerIoTLight(device_manager, device)
        entities.append(light_entity)
        
    if entities:
        async_add_entities(entities)


class WePowerIoTLight(LightEntity):
    """Representation of a WePower IoT light."""

    def __init__(self, device_manager, device: Dict[str, Any]):
        """Initialize the light."""
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
        
        # Set light properties
        self._set_light_properties()
        
        # Set initial state
        self._update_state()
        
    def _set_light_properties(self):
        """Set light properties based on device capabilities."""
        # Default light properties
        self._attr_supported_color_modes = {ColorMode.RGB, ColorMode.COLOR_TEMP, ColorMode.WHITE}
        self._attr_color_mode = ColorMode.RGB
        self._attr_brightness = 255
        self._attr_rgb_color = (255, 255, 255)
        self._attr_color_temp = 4000
        self._attr_min_mireds = 153  # 6500K
        self._attr_max_mireds = 500  # 2000K
        self._attr_supported_features = 0  # No special features for now
        
    def _update_state(self):
        """Update light state from device data."""
        status = self.device.get("status", DEVICE_STATUS_OFFLINE)
        
        if status == DEVICE_STATUS_CONNECTED:
            # Get light state from device properties
            light_state = self.device.get("light_state", False)
            self._attr_is_on = bool(light_state)
            
            # Get brightness if available
            brightness = self.device.get("brightness")
            if brightness is not None:
                self._attr_brightness = brightness
                
            # Get RGB color if available
            rgb_color = self.device.get("rgb_color")
            if rgb_color:
                self._attr_rgb_color = tuple(rgb_color)
                
            # Get color temperature if available
            color_temp = self.device.get("color_temp")
            if color_temp is not None:
                self._attr_color_temp = color_temp
                
        else:
            # Device is offline
            self._attr_is_on = False
            
        # Update available state
        self._attr_available = status == DEVICE_STATUS_CONNECTED
        
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        try:
            # Prepare turn on message
            turn_on_message = {
                "command": "turn_on",
                "device_id": self.device_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Handle brightness
            if ATTR_BRIGHTNESS in kwargs:
                brightness = kwargs[ATTR_BRIGHTNESS]
                turn_on_message["brightness"] = brightness
                self._attr_brightness = brightness
                
            # Handle RGB color
            if ATTR_RGB_COLOR in kwargs:
                rgb_color = kwargs[ATTR_RGB_COLOR]
                turn_on_message["rgb_color"] = list(rgb_color)
                self._attr_rgb_color = rgb_color
                self._attr_color_mode = ColorMode.RGB
                
            # Handle color temperature
            if ATTR_COLOR_TEMP in kwargs:
                color_temp = kwargs[ATTR_COLOR_TEMP]
                turn_on_message["color_temp"] = color_temp
                self._attr_color_temp = color_temp
                self._attr_color_mode = ColorMode.COLOR_TEMP
                
            # Handle transition
            if ATTR_TRANSITION in kwargs:
                transition = kwargs[ATTR_TRANSITION]
                turn_on_message["transition"] = transition
                
            # Send command
            await self.device_manager.publish_mqtt(
                f"wepower_iot/device/{self.device_id}/command",
                json.dumps(turn_on_message)
            )
            
            # Log the command for debugging
            _LOGGER.info(f"Light command sent: {turn_on_message}")
            
            # Update local state
            self._attr_is_on = True
            self.async_write_ha_state()
            
        except Exception as e:
            _LOGGER.error(f"Error turning on light {self.device_id}: {e}")
            
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        try:
            # Send turn off command
            turn_off_message = {
                "command": "turn_off",
                "device_id": self.device_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Handle transition
            if ATTR_TRANSITION in kwargs:
                transition = kwargs[ATTR_TRANSITION]
                turn_off_message["transition"] = transition
                
            await self.device_manager.publish_mqtt(
                f"wepower_iot/device/{self.device_id}/command",
                json.dumps(turn_off_message)
            )
            
            # Update local state
            self._attr_is_on = False
            self.async_write_ha_state()
            
        except Exception as e:
            _LOGGER.error(f"Error turning off light {self.device_id}: {e}")
            
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
            "color_mode": self._attr_color_mode,
            "rgb_color": self._attr_rgb_color,
            "brightness": self._attr_brightness,
            "color_temp": self._attr_color_temp,
            "min_mireds": self._attr_min_mireds,
            "max_mireds": self._attr_max_mireds,
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
        """Update light state."""
        # Get latest device data
        updated_device = self.device_manager.get_device(self.device_id)
        if updated_device:
            self.device = updated_device
            self._update_state()
            
    @property
    def is_on(self) -> bool:
        """Return true if the light is on."""
        return self._attr_is_on
        
    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_available
        
    @property
    def brightness(self) -> Optional[int]:
        """Return the brightness of this light between 0..255."""
        return self._attr_brightness
        
    @property
    def rgb_color(self) -> Optional[Tuple[int, int, int]]:
        """Return the rgb color value [int, int, int]."""
        return self._attr_rgb_color
        
    @property
    def color_temp(self) -> Optional[int]:
        """Return the color temperature in mireds."""
        return self._attr_color_temp
        
    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        return self._attr_color_mode
        
    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported features."""
        return self._attr_supported_color_modes
        
    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports."""
        return self._attr_min_mireds
        
    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports."""
        return self._attr_max_mireds
