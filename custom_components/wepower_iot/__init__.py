"""The WePower IoT integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import service

from .const import DOMAIN
from .device_management import WePowerIoTDeviceManager

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.LIGHT,
    Platform.INPUT_BOOLEAN,
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WePower IoT from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Create device manager
    device_manager = WePowerIoTDeviceManager(hass, entry.data)
    await device_manager.start()
    
    # Store device manager in hass data
    hass.data[DOMAIN][entry.entry_id] = {
        "device_manager": device_manager,
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
        # Clean up device manager
        if entry.entry_id in hass.data[DOMAIN]:
            device_manager = hass.data[DOMAIN][entry.entry_id].get("device_manager")
            if device_manager:
                await device_manager.stop()
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
        enabled = service_call.data.get("enabled", False)
        # Update config
        device_manager.config["enable_ble"] = enabled
        hass.bus.async_fire(f"{DOMAIN}_ble_toggled", {"enabled": enabled})
    
    async def toggle_zigbee(service_call):
        """Toggle Zigbee functionality."""
        enabled = service_call.data.get("enabled", False)
        # Update config
        device_manager.config["enable_zigbee"] = enabled
        hass.bus.async_fire(f"{DOMAIN}_zigbee_toggled", {"enabled": enabled})
    
    async def scan_devices(service_call):
        """Scan for devices."""
        dongle_id = service_call.data.get("dongle_id")
        # Trigger device scan
        hass.bus.async_fire(f"{DOMAIN}_scan_triggered", {"dongle_id": dongle_id})
    
    # Register services
    hass.services.async_register(DOMAIN, "add_device", add_device)
    hass.services.async_register(DOMAIN, "remove_device", remove_device)
    hass.services.async_register(DOMAIN, "toggle_ble", toggle_ble)
    hass.services.async_register(DOMAIN, "toggle_zigbee", toggle_zigbee)
    hass.services.async_register(DOMAIN, "scan_devices", scan_devices)
