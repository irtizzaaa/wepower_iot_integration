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

from .const import DOMAIN, BLE_COMPANY_ID, CONF_DECRYPTION_KEY
from .packet_parser import parse_wepower_packet

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
        """Parse WePower IoT advertisement data using new packet format."""
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
        
        # Parse manufacturer data for WePower IoT devices using new packet format
        if service_info.manufacturer_data:
            for manufacturer_id, manufacturer_data in service_info.manufacturer_data.items():
                if manufacturer_id == BLE_COMPANY_ID:  # WePower manufacturer ID (0x5750)
                    parsed_data = self._parse_wepower_manufacturer_data(manufacturer_data)
                    if parsed_data:
                        data.update(parsed_data)
        
        # Determine device type based on sensor type
        if 'sensor_data' in data and 'sensor_type' in data['sensor_data']:
            sensor_type = data['sensor_data']['sensor_type']
            if sensor_type == 4:
                data["device_type"] = "leak_sensor"
            elif sensor_type == 1:
                data["device_type"] = "temperature_sensor"
            elif sensor_type == 2:
                data["device_type"] = "humidity_sensor"
            elif sensor_type == 3:
                data["device_type"] = "pressure_sensor"
        
        return data

    def _parse_wepower_manufacturer_data(self, data: bytes) -> dict[str, Any]:
        """Parse WePower IoT manufacturer data using new packet format."""
        if len(data) < 20:  # New packet format is 20 bytes
            return {}
        
        # Get decryption key from config entry
        decryption_key = None
        if hasattr(self._entry, 'data') and CONF_DECRYPTION_KEY in self._entry.data:
            try:
                decryption_key = bytes.fromhex(self._entry.data[CONF_DECRYPTION_KEY])
            except ValueError:
                _LOGGER.warning("Invalid decryption key format")
        
        # Parse the packet using the new parser
        parsed_packet = parse_wepower_packet(data, decryption_key)
        
        if not parsed_packet:
            return {}
        
        result = {
            "company_id": parsed_packet['company_id'],
            "flags": parsed_packet['flags'],
            "crc": parsed_packet['crc'],
        }
        
        # Add decrypted data if available
        if 'decrypted_data' in parsed_packet:
            result['decrypted_data'] = parsed_packet['decrypted_data']
        
        # Add sensor data if available
        if 'sensor_data' in parsed_packet:
            result['sensor_data'] = parsed_packet['sensor_data']
            
            # Extract specific sensor values
            sensor_data = parsed_packet['sensor_data']
            if 'leak_detected' in sensor_data:
                result['leak_detected'] = sensor_data['leak_detected']
            if 'event_counter' in sensor_data:
                result['event_counter'] = sensor_data['event_counter']
            if 'sensor_event' in sensor_data:
                result['sensor_event'] = sensor_data['sensor_event']
        
        return result

    @callback
    def _async_schedule_poll(self, _: datetime) -> None:
        """Schedule a poll of the device."""
        if self._last_service_info and self._async_needs_poll(
            self._last_service_info, self._last_poll
        ):
            self._debounced_poll.async_schedule_call()

