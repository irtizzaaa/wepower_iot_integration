"""BLE coordinator for WePower IoT integration using Home Assistant's Bluetooth infrastructure."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfo,
    BluetoothServiceInfoBleak,
    BluetoothChange,
    async_ble_device_from_address,
    async_last_service_info,
)
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothDataUpdateCoordinator,
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
    PassiveBluetoothDataUpdateCoordinator
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
            connectable=False,
        )
        self.data = {}
        self.last_update_success = True

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

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        super()._async_handle_bluetooth_event(service_info, change)
        try:
            _LOGGER.info("🔵 BLE EVENT: %s | RSSI: %s | Name: %s | Change: %s", 
                        self.address, service_info.rssi, service_info.name, change)
            
            # Parse the advertisement data and update our data
            parsed_data = self._parse_advertisement_data(service_info)
            self.data = parsed_data
            self.last_update_success = True
            
            _LOGGER.info("🟢 BLE DATA PARSED: %s | Data: %s", self.address, parsed_data)
            self.async_update_listeners()
            
        except Exception as e:
            self.last_update_success = False
            _LOGGER.error("🔴 BLE PARSE ERROR: %s | Error: %s", self.address, e)

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
            _LOGGER.info("📡 MANUFACTURER DATA: %s | IDs: %s", self.address, list(service_info.manufacturer_data.keys()))
            for manufacturer_id, manufacturer_data in service_info.manufacturer_data.items():
                _LOGGER.info("🏭 MANUFACTURER: %s | ID: 0x%04X | Data: %s", 
                            self.address, manufacturer_id, manufacturer_data.hex())
                if manufacturer_id == BLE_COMPANY_ID:  # WePower manufacturer ID (0x5750)
                    _LOGGER.info("✅ WEPOWER DEVICE DETECTED: %s | Parsing data...", self.address)
                    parsed_data = self._parse_wepower_manufacturer_data(manufacturer_data)
                    if parsed_data:
                        data.update(parsed_data)
                        _LOGGER.info("🎯 WEPOWER DATA PARSED: %s | Result: %s", self.address, parsed_data)
                    else:
                        _LOGGER.warning("⚠️ WEPOWER PARSE FAILED: %s | Data: %s", self.address, manufacturer_data.hex())
                else:
                    _LOGGER.debug("❌ NON-WEPOWER: %s | ID: 0x%04X", self.address, manufacturer_id)
        else:
            _LOGGER.warning("⚠️ NO MANUFACTURER DATA: %s", self.address)
        
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
        """Parse WePower IoT manufacturer data using 18-byte packet format."""
        _LOGGER.info("🔐 PARSING WEPOWER DATA: Length=%d | Data=%s", len(data), data.hex())
        
        if len(data) < 18:  # WePower packet format is 18 bytes
            _LOGGER.warning("⚠️ INVALID PACKET LENGTH: %d bytes (expected 18)", len(data))
            return {}
        
        # Get decryption key from config entry
        decryption_key = None
        if hasattr(self._entry, 'data') and CONF_DECRYPTION_KEY in self._entry.data:
            try:
                decryption_key = bytes.fromhex(self._entry.data[CONF_DECRYPTION_KEY])
                _LOGGER.info("🔑 DECRYPTION KEY: %s", self._entry.data[CONF_DECRYPTION_KEY])
            except ValueError:
                _LOGGER.error("🔴 INVALID DECRYPTION KEY FORMAT: %s", self._entry.data[CONF_DECRYPTION_KEY])
        else:
            _LOGGER.warning("⚠️ NO DECRYPTION KEY FOUND in config entry")
        
        # Parse the packet using the new parser
        _LOGGER.info("📦 CALLING PACKET PARSER: data=%s, key=%s", data.hex(), decryption_key.hex() if decryption_key else "None")
        parsed_packet = parse_wepower_packet(data, decryption_key)
        
        if not parsed_packet:
            _LOGGER.error("🔴 PACKET PARSER RETURNED EMPTY RESULT")
            return {}
        
        _LOGGER.info("✅ PACKET PARSED SUCCESSFULLY: %s", parsed_packet)
        
        result = {
            "company_id": parsed_packet['company_id'],
            "flags": parsed_packet['flags'],
            "crc": parsed_packet['crc'],
        }
        
        # Add decrypted data if available
        if 'decrypted_data' in parsed_packet:
            result['decrypted_data'] = parsed_packet['decrypted_data']
            _LOGGER.info("🔓 DECRYPTED DATA: %s", parsed_packet['decrypted_data'])
        
        # Add sensor data if available
        if 'sensor_data' in parsed_packet:
            result['sensor_data'] = parsed_packet['sensor_data']
            _LOGGER.info("📊 SENSOR DATA: %s", parsed_packet['sensor_data'])
            
            # Extract specific sensor values
            sensor_data = parsed_packet['sensor_data']
            if 'leak_detected' in sensor_data:
                result['leak_detected'] = sensor_data['leak_detected']
                _LOGGER.info("💧 LEAK DETECTED: %s", sensor_data['leak_detected'])
            if 'event_counter' in sensor_data:
                result['event_counter'] = sensor_data['event_counter']
                _LOGGER.info("🔢 EVENT COUNTER: %s", sensor_data['event_counter'])
            if 'sensor_event' in sensor_data:
                result['sensor_event'] = sensor_data['sensor_event']
                _LOGGER.info("📡 SENSOR EVENT: %s", sensor_data['sensor_event'])
        
        _LOGGER.info("🎯 FINAL RESULT: %s", result)
        return result

    @callback
    def _async_schedule_poll(self, _: datetime) -> None:
        """Schedule a poll of the device."""
        # Simple polling - just trigger an update if we have data
        if self.data:
            self.last_update_success = True
            self.async_update_listeners()
        else:
            # No data for a while, mark as potentially unavailable
            self.last_update_success = False

