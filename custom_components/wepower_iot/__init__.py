"""The WePower IoT integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import service

from .const import DOMAIN
from .device_management import WePowerIoTDeviceManager
from .coordinator import WePowerIoTDataCoordinator

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
    
    async def create_entities_for_devices(service_call):
        """Create entities for all devices in device manager."""
        # Get all devices and create entities for them
        all_devices = device_manager.get_all_devices()
        for device in all_devices:
            device_id = device.get("device_id")
            if device_id and device_id not in device_manager._created_entities:
                device_manager._created_entities.add(device_id)
                # Trigger entity creation by calling platform setup
                await _create_entity_for_device(hass, config_entry, device)
    
    # Register services
    hass.services.async_register(DOMAIN, "add_device", add_device)
    hass.services.async_register(DOMAIN, "remove_device", remove_device)
    hass.services.async_register(DOMAIN, "toggle_ble", toggle_ble)
    hass.services.async_register(DOMAIN, "toggle_zigbee", toggle_zigbee)
    hass.services.async_register(DOMAIN, "scan_devices", scan_devices)
    hass.services.async_register(DOMAIN, "create_entities", create_entities_for_devices)


async def _create_entity_for_device(hass: HomeAssistant, config_entry: ConfigEntry, device: dict):
    """Create entity for a specific device."""
    from homeassistant.helpers.entity_platform import async_get_platforms
    
    category = device.get("category", "sensor")
    
    # Get the appropriate platform
    if category == "sensor":
        platform = async_get_platforms(hass, DOMAIN, "sensor")
    elif category == "light":
        platform = async_get_platforms(hass, DOMAIN, "light")
    elif category == "switch":
        platform = async_get_platforms(hass, DOMAIN, "switch")
    else:
        return
    
    if platform:
        # Create the entity
        from .sensor import WePowerIoTSensor
        from .light import WePowerIoTLight
        from .switch import WePowerIoTSwitch
        
        device_manager = hass.data[DOMAIN][config_entry.entry_id].get("device_manager")
        
        if category == "sensor":
            entity = WePowerIoTSensor(device_manager, device)
        elif category == "light":
            entity = WePowerIoTLight(device_manager, device)
        elif category == "switch":
            entity = WePowerIoTSwitch(device_manager, device)
        
        # Add the entity to the platform
        platform[0].async_add_entities([entity])
