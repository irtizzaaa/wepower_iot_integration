"""The WePower IoT integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import WePowerIoTCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.SWITCH, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WePower IoT from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    try:
        coordinator = WePowerIoTCoordinator(hass, entry)
        await coordinator.async_config_entry_first_refresh()
        
        hass.data[DOMAIN][entry.entry_id] = coordinator
        entry.runtime_data = coordinator
        
        # Set up platforms
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        
        # Set up options listener
        entry.async_on_unload(entry.add_update_listener(async_reload_entry))
        
        return True
        
    except Exception as ex:
        _LOGGER.error("Failed to set up WePower IoT integration: %s", ex)
        raise ConfigEntryNotReady from ex


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        coordinator: WePowerIoTCoordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_shutdown()
        del hass.data[DOMAIN][entry.entry_id]
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
