"""BLE coordinator for WePower IoT integration using Home Assistant's Bluetooth infrastructure."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
import struct

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfo,
    BluetoothServiceInfoBleak,
    BluetoothChange,
    async_ble_device_from_address,
    async_last_service_info,
    async_discovered_service_info,
)
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, BLE_COMPANY_ID, CONF_DECRYPTION_KEY, CONF_ADDRESS
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
        # Always check config data first for real MAC address
        real_address = entry.data.get(CONF_ADDRESS)
        _LOGGER.info("🔍 Config data: %s", entry.data)
        _LOGGER.info("🔍 Unique ID: %s", entry.unique_id)
        _LOGGER.info("🔍 Address from config: %s", real_address)
        
        # Use real MAC address if available, otherwise use discovery identifier
        if real_address and real_address != "00:00:00:00:00:00":
            address = real_address.upper()
            _LOGGER.info("🎯 Using real MAC address: %s", address)
        else:
            address = f"wepower_discovery_{entry.entry_id}"
            _LOGGER.info("🔍 Using discovery identifier: %s", address)
        
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
        _LOGGER.info("🔍 Coordinator async_init with address: %s", self.address)
        
        # If we're using discovery identifier, try to discover devices
        if self.address.startswith("wepower_discovery_"):
            _LOGGER.warning("Using discovery identifier, will discover real device")
            await self._discover_and_update_address()
            return
        
        # Try to connect to the real MAC address
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
        # Get professional device ID
        clean_address = service_info.address.replace(":", "").upper()
        last_6 = clean_address[-6:]
        device_number = int(last_6, 16) % 1000  # Get a number between 0-999
        professional_id = f"Unit-{device_number:03d}"
        
        data = {
            "address": service_info.address,
            "name": service_info.name or f"WePower IoT Device {professional_id}",
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
            _LOGGER.info("🔍 SENSOR TYPE DETECTION: sensor_type=%d (0x%04X)", sensor_type, sensor_type)
            if sensor_type == 1:
                data["device_type"] = "temperature_sensor"
                data["name"] = f"WePower Temperature Sensor {professional_id}"
                _LOGGER.info("  ✅ Identified as: temperature_sensor")
            elif sensor_type == 2:
                data["device_type"] = "humidity_sensor"
                data["name"] = f"WePower Humidity Sensor {professional_id}"
                _LOGGER.info("  ✅ Identified as: humidity_sensor")
            elif sensor_type == 3:
                data["device_type"] = "pressure_sensor"
                data["name"] = f"WePower Pressure Sensor {professional_id}"
                _LOGGER.info("  ✅ Identified as: pressure_sensor")
            elif sensor_type == 4:
                data["device_type"] = "leak_sensor"
                data["name"] = f"WePower Leak Sensor {professional_id}"
                _LOGGER.info("  ✅ Identified as: leak_sensor")
            elif sensor_type == 5:
                data["device_type"] = "vibration_sensor"
                data["name"] = f"WePower Vibration Sensor {professional_id}"
                _LOGGER.info("  ✅ Identified as: vibration_sensor")
            elif sensor_type == 6:
                data["device_type"] = "on_off_switch"
                data["name"] = f"WePower On/Off Switch {professional_id}"
                _LOGGER.info("  ✅ Identified as: on_off_switch")
            elif sensor_type == 7:
                data["device_type"] = "light_switch"
                data["name"] = f"WePower Light Switch {professional_id}"
                _LOGGER.info("  ✅ Identified as: light_switch")
            elif sensor_type == 8:
                data["device_type"] = "door_switch"
                data["name"] = f"WePower Door Switch {professional_id}"
                _LOGGER.info("  ✅ Identified as: door_switch")
            elif sensor_type == 9:
                data["device_type"] = "toggle_switch"
                data["name"] = f"WePower Toggle Switch {professional_id}"
                _LOGGER.info("  ✅ Identified as: toggle_switch")
            else:
                _LOGGER.warning("  ⚠️ Unknown sensor type: %d (0x%04X)", sensor_type, sensor_type)
        
        return data

    def _parse_wepower_manufacturer_data(self, data: bytes) -> dict[str, Any]:
        """Parse WePower IoT manufacturer data using 18-byte packet format."""
        _LOGGER.info("🔐 PARSING WEPOWER DATA: Length=%d | Data=%s", len(data), data.hex())
        
        if len(data) < 18:  # WePower packet format is 18 bytes
            _LOGGER.warning("⚠️ INVALID PACKET LENGTH: %d bytes (expected 18)", len(data))
            return {}
        
        # Parse packet structure: HA BLE driver filters out Company ID (2 bytes)
        # So we receive: Flags (1) + Encrypted Data (16) + CRC (1) = 18 bytes
        if len(data) < 18:
            _LOGGER.error("🔴 PACKET TOO SHORT: %d bytes (need 18)", len(data))
            return {}
        
        _LOGGER.info("🔍 PACKET DEBUG: Length=%d, Data=%s", len(data), data.hex())
        
        try:
            # Company ID is already filtered by HA BLE driver (0x5750)
            company_id = 0x5750  # WePower company ID (filtered by HA)
            flags = data[0]  # 1 byte
            encrypted_data = data[1:17]  # 16 bytes (positions 1-16)
            crc = data[17]  # 1 byte (position 17, last byte)
            
            _LOGGER.info("📦 PACKET STRUCTURE: Company ID=0x%04X (filtered by HA), Flags=0x%02X, CRC=0x%02X", 
                        company_id, flags, crc)
            _LOGGER.info("🔐 ENCRYPTED DATA (%d bytes): %s", len(encrypted_data), encrypted_data.hex())
            
        except (IndexError, struct.error) as e:
            _LOGGER.error("🔴 PACKET PARSING ERROR: %s", e)
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
        
        # Parse the full 18-byte packet using the parser
        _LOGGER.info("📦 CALLING PACKET PARSER: packet_data=%s, key=%s", 
                    data.hex(), decryption_key.hex() if decryption_key else "None")
        
        parsed_packet = parse_wepower_packet(data, decryption_key)
        
        if not parsed_packet:
            _LOGGER.error("🔴 PACKET PARSER RETURNED EMPTY RESULT")
            return {}
        
        _LOGGER.info("✅ PACKET PARSED SUCCESSFULLY: %s", parsed_packet)
        
        result = {
            "company_id": company_id,
            "flags": flags,
            "crc": crc,
            "packet_structure": {
                "company_id": company_id,
                "flags": flags,
                "encrypted_data_length": len(encrypted_data),
                "crc": crc,
            }
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
    
    async def _discover_and_update_address(self) -> None:
        """Discover WePower devices and update the address if found."""
        try:
            _LOGGER.info("🔍 Discovering WePower devices...")
            discovered_devices = async_discovered_service_info(self.hass)
            
            for device in discovered_devices:
                if self._is_wepower_device(device):
                    _LOGGER.info("🎯 Found WePower device: %s (%s)", device.name, device.address)
                    # Update the config entry with the real MAC address
                    new_data = self._entry.data.copy()
                    new_data[CONF_ADDRESS] = device.address.upper()
                    self.hass.config_entries.async_update_entry(self._entry, data=new_data)
                    _LOGGER.info("✅ Updated config entry with real MAC address: %s", device.address)
                    
                    # Update coordinator address dynamically
                    await self._update_coordinator_address(device.address.upper())
                    break
            else:
                _LOGGER.warning("⚠️ No WePower devices found during discovery")
                
        except Exception as e:
            _LOGGER.error("🔴 Discovery error: %s", e)
    
    def _is_wepower_device(self, discovery_info: BluetoothServiceInfo) -> bool:
        """Check if this is a WePower IoT device."""
        # Check manufacturer data for WePower Company ID (22352)
        if discovery_info.manufacturer_data:
            for manufacturer_id, data in discovery_info.manufacturer_data.items():
                if manufacturer_id == BLE_COMPANY_ID and len(data) >= 20:
                    return True
        
        # Check name patterns as fallback
        name = discovery_info.name or ""
        if any(pattern in name.upper() for pattern in ["WEPOWER", "WP"]):
            return True
        
        return False
    
    async def _update_coordinator_address(self, new_address: str) -> None:
        """Update the coordinator's address dynamically."""
        try:
            _LOGGER.info("🔄 Updating coordinator address from %s to %s", self.address, new_address)
            
            # Update the address
            self.address = new_address
            
            # Try to connect to the new address
            if service_info := async_last_service_info(self.hass, self.address):
                _LOGGER.info("✅ Successfully connected to device at %s", self.address)
                # Process the advertisement data
                parsed_data = self._parse_advertisement_data(service_info)
                self.data = parsed_data
                self.last_update_success = True
                self.async_update_listeners()
                _LOGGER.info("🎯 Device data updated: %s", parsed_data)
            else:
                _LOGGER.warning("⚠️ No advertisement found for device at %s", self.address)
                
        except Exception as e:
            _LOGGER.error("🔴 Error updating coordinator address: %s", e)
    
    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        _LOGGER.info("🔴 Shutting down WePower IoT BLE coordinator")
        # Clean up any resources if needed
        self.data = {}
        self.last_update_success = False

