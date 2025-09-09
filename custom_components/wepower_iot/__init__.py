"""The WePower IoT integration."""

import json
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import service

from .const import DOMAIN
from .device_management import WePowerIoTDeviceManager
from .coordinator import WePowerIoTDataCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.LIGHT,
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WePower IoT from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Create device manager
    device_manager = WePowerIoTDeviceManager(hass, entry.data)
    await device_manager.start()
    
    # Create coordinator
    coordinator = WePowerIoTDataCoordinator(hass, device_manager)
    await coordinator.async_setup()
    
    # Store device manager and coordinator in hass data
    hass.data[DOMAIN][entry.entry_id] = {
        "device_manager": device_manager,
        "coordinator": coordinator,
        "config": entry.data
    }

    # Register services
    await _register_services(hass, device_manager)

    # Forward the setup to the relevant platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Clean up device manager and coordinator
        if entry.entry_id in hass.data[DOMAIN]:
            device_manager = hass.data[DOMAIN][entry.entry_id].get("device_manager")
            coordinator = hass.data[DOMAIN][entry.entry_id].get("coordinator")
            if device_manager:
                await device_manager.stop()
            if coordinator:
                await coordinator.async_shutdown()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _register_services(hass: HomeAssistant, device_manager: WePowerIoTDeviceManager):
    """Register WePower IoT services."""
    
    async def add_device(service_call):
        """Add a new device."""
        data = service_call.data
        await device_manager.add_device(data)
    
    async def remove_device(service_call):
        """Remove a device."""
        device_id = service_call.data.get("device_id")
        if device_id and device_id in device_manager.devices:
            del device_manager.devices[device_id]
            hass.bus.async_fire(f"{DOMAIN}_device_removed", {"device_id": device_id})
    
    async def toggle_ble(service_call):
        """Toggle BLE functionality."""
        enabled = service_call.data.get("enabled", True)
        # Send MQTT command to toggle BLE
        await device_manager.publish_mqtt(
            "wepower_iot/control/ble/toggle",
            json.dumps({"action": "toggle_ble", "enabled": enabled})
        )
        _LOGGER.info(f"Sent BLE toggle command: enabled={enabled}")
        hass.bus.async_fire(f"{DOMAIN}_ble_toggled", {"enabled": enabled})
    
    async def toggle_zigbee(service_call):
        """Toggle Zigbee functionality."""
        enabled = service_call.data.get("enabled", True)
        # Send MQTT command to toggle Zigbee
        await device_manager.publish_mqtt(
            "wepower_iot/control/zigbee/toggle",
            json.dumps({"action": "toggle_zigbee", "enabled": enabled})
        )
        _LOGGER.info(f"Sent Zigbee toggle command: enabled={enabled}")
        hass.bus.async_fire(f"{DOMAIN}_zigbee_toggled", {"enabled": enabled})
    
    async def scan_devices(service_call):
        """Scan for devices."""
        dongle_id = service_call.data.get("dongle_id", "all")
        # Send MQTT command to scan for devices
        await device_manager.publish_mqtt(
            "wepower_iot/command/scan",
            json.dumps({"dongle_id": dongle_id})
        )
        _LOGGER.info(f"Sent scan command for dongle: {dongle_id}")
        hass.bus.async_fire(f"{DOMAIN}_scan_triggered", {"dongle_id": dongle_id})
    
    async def create_entities_for_devices(service_call):
        """Create entities for all devices in device manager."""
        # Get all devices and create entities for them
        all_devices = device_manager.get_all_devices()
        _LOGGER.info(f"Found {len(all_devices)} devices to create entities for")
        
        # Trigger platform reload to create entities for new devices
        await hass.config_entries.async_reload(config_entry.entry_id)
    
    # Register services
    hass.services.async_register(DOMAIN, "add_device", add_device)
    hass.services.async_register(DOMAIN, "remove_device", remove_device)
    hass.services.async_register(DOMAIN, "toggle_ble", toggle_ble)
    hass.services.async_register(DOMAIN, "toggle_zigbee", toggle_zigbee)
    hass.services.async_register(DOMAIN, "scan_devices", scan_devices)
    hass.services.async_register(DOMAIN, "create_entities", create_entities_for_devices)


