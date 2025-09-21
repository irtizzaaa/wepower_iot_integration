"""BLE coordinator for WePower IoT integration using Home Assistant's Bluetooth infrastructure."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfo,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_last_service_info,
)
from homeassistant.components.bluetooth.active_update_processor import (
    ActiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

FALLBACK_POLL_INTERVAL = timedelta(seconds=60)


class WePowerIoTBluetoothProcessorCoordinator(
    ActiveBluetoothProcessorCoordinator[dict[str, Any]]
):
    """Coordinator for WePower IoT Bluetooth devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the WePower IoT Bluetooth processor coordinator."""
        self._entry = entry
        address = entry.unique_id
        assert address is not None
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            address=address,
            mode=BluetoothScanningMode.ACTIVE,
            update_method=self._async_on_update,
            needs_poll_method=self._async_needs_poll,
            poll_method=self._async_poll_data,
            connectable=False,  # We only need to read advertisements
        )

    async def async_init(self) -> None:
        """Initialize the coordinator."""
        if not (service_info := async_last_service_info(self.hass, self.address)):
            raise ConfigEntryNotReady(
                f"No advertisement found for WePower IoT device {self.address}"
            )
        
        # Set up fallback polling for devices that don't advertise frequently
        self._entry.async_on_unload(
            async_track_time_interval(
                self.hass, self._async_schedule_poll, FALLBACK_POLL_INTERVAL
            )
        )

    async def _async_poll_data(
        self, last_service_info: BluetoothServiceInfoBleak
    ) -> dict[str, Any]:
        """Poll the device for data."""
        # For WePower IoT devices, we primarily rely on advertisement data
        # This method can be used for active polling if needed
        return self._parse_advertisement_data(last_service_info)

    @callback
    def _async_needs_poll(
        self, service_info: BluetoothServiceInfoBleak, last_poll: float | None
    ) -> bool:
        """Check if we need to poll the device."""
        if self.hass.is_stopping:
            return False
        
        # Poll if we haven't seen an advertisement in the last 30 seconds
        if last_poll is None:
            return True
            
        return (datetime.now().timestamp() - last_poll) > 30

    @callback
    def _async_on_update(self, service_info: BluetoothServiceInfo) -> dict[str, Any]:
        """Handle update callback from the BLE processor."""
        return self._parse_advertisement_data(service_info)

    def _parse_advertisement_data(self, service_info: BluetoothServiceInfo) -> dict[str, Any]:
        """Parse WePower IoT advertisement data."""
        data = {
            "address": service_info.address,
            "name": service_info.name or "Unknown WePower Device",
            "rssi": service_info.rssi,
            "timestamp": datetime.now().isoformat(),
            "device_type": "unknown",
            "sensor_data": {},
            "battery_level": None,
            "signal_strength": service_info.rssi,
        }
        
        # Parse manufacturer data for WePower IoT devices
        if service_info.manufacturer_data:
            for manufacturer_id, manufacturer_data in service_info.manufacturer_data.items():
                if manufacturer_id == 65535:  # WePower manufacturer ID
                    data.update(self._parse_wepower_manufacturer_data(manufacturer_data))
        
        # Parse service data
        if service_info.service_data:
            for service_uuid, service_data in service_info.service_data.items():
                if "180a" in service_uuid.lower():  # Device Information Service
                    data.update(self._parse_device_info_service(service_data))
        
        # Determine device type based on name patterns
        name = service_info.name or ""
        if "leak" in name.lower() or "water" in name.lower():
            data["device_type"] = "leak_sensor"
        elif "temp" in name.lower() or "temperature" in name.lower():
            data["device_type"] = "temperature_sensor"
        elif "humidity" in name.lower():
            data["device_type"] = "humidity_sensor"
        elif "vibration" in name.lower() or "motion" in name.lower():
            data["device_type"] = "vibration_sensor"
        elif "pressure" in name.lower():
            data["device_type"] = "pressure_sensor"
        elif "air" in name.lower() or "co2" in name.lower():
            data["device_type"] = "air_quality_sensor"
        elif "switch" in name.lower():
            data["device_type"] = "switch"
        elif "light" in name.lower():
            data["device_type"] = "light"
        
        return data

    def _parse_wepower_manufacturer_data(self, data: bytes) -> dict[str, Any]:
        """Parse WePower IoT manufacturer data."""
        if len(data) < 2:
            return {}
        
        parsed = {}
        
        # WePower IoT protocol parsing
        if data[0] == 87 and data[1] == 80:  # "WP" prefix
            if len(data) >= 4:
                # Device type
                device_type_code = data[2]
                parsed["device_type_code"] = device_type_code
                
                # Battery level (if available)
                if len(data) >= 5:
                    parsed["battery_level"] = data[3]
                
                # Sensor data (if available)
                if len(data) >= 8:
                    # Temperature (2 bytes, signed, in 0.1°C units)
                    temp_raw = int.from_bytes(data[4:6], byteorder='little', signed=True)
                    parsed["sensor_data"]["temperature"] = temp_raw / 10.0
                    
                    # Humidity (1 byte, percentage)
                    if len(data) >= 9:
                        parsed["sensor_data"]["humidity"] = data[6]
                    
                    # Additional sensor data
                    if len(data) >= 10:
                        parsed["sensor_data"]["pressure"] = int.from_bytes(data[7:9], byteorder='little')
        
        return parsed

    def _parse_device_info_service(self, data: bytes) -> dict[str, Any]:
        """Parse device information service data."""
        parsed = {}
        
        if len(data) >= 2:
            # Model number or firmware version
            parsed["firmware_version"] = data.hex()[:4]
        
        return parsed

    @callback
    def _async_schedule_poll(self, _: datetime) -> None:
        """Schedule a poll of the device."""
        if self._last_service_info and self._async_needs_poll(
            self._last_service_info, self._last_poll
        ):
            self._debounced_poll.async_schedule_call()
