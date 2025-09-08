"""Data coordinator for WePower IoT integration."""

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, SIGNAL_DEVICE_UPDATED

_LOGGER = logging.getLogger(__name__)


class WePowerIoTDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the WePower IoT device manager."""

    def __init__(self, hass: HomeAssistant, device_manager) -> None:
        """Initialize the coordinator."""
        self.device_manager = device_manager
        self.hass = hass
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update data via device manager."""
        try:
            # Get current device data
            devices = self.device_manager.get_all_devices()
            dongles = self.device_manager.get_dongles()
            
            return {
                "devices": devices,
                "dongles": dongles,
                "last_update": self.device_manager.devices,
            }
        except Exception as err:
            raise UpdateFailed(f"Error communicating with device manager: {err}")

    async def async_setup(self) -> None:
        """Set up the coordinator."""
        # Listen for device updates
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, SIGNAL_DEVICE_UPDATED, self._handle_device_update
        )
        
    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        if hasattr(self, '_unsub_dispatcher') and self._unsub_dispatcher:
            self._unsub_dispatcher()

    def _handle_device_update(self, device_data: Dict[str, Any]) -> None:
        """Handle device update from dispatcher."""
        # Trigger a data update when devices change
        self.async_set_updated_data({
            "devices": self.device_manager.get_all_devices(),
            "dongles": self.device_manager.get_dongles(),
            "last_update": self.device_manager.devices,
        })

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        if hasattr(self, '_unsub_dispatcher') and self._unsub_dispatcher:
            self._unsub_dispatcher()
