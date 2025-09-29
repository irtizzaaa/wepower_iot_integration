"""Packet parser for WePower IoT BLE devices with new packet format."""

import struct
from typing import Any, Dict, Optional
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import logging

_LOGGER = logging.getLogger(__name__)

# Constants from the new packet format
COMPANY_ID = 0x5750  # WePower company ID
PACKET_LENGTH = 16  # Encrypted data size (HA BLE driver filters company ID)
ENCRYPTED_DATA_SIZE = 16

class WePowerPacketFlags:
    """Flags field parser for WePower packets."""
    
    def __init__(self, flags_byte: int):
        self.encrypt_status = flags_byte & 0x01
        self.self_external_power = (flags_byte >> 1) & 0x01
        self.event_counter_lsb = (flags_byte >> 2) & 0x03
        self.payload_length = (flags_byte >> 4) & 0x0F

class WePowerEncryptedData:
    """Encrypted data structure for WePower packets."""
    
    def __init__(self, data: bytes):
        if len(data) != ENCRYPTED_DATA_SIZE:
            raise ValueError(f"Encrypted data must be {ENCRYPTED_DATA_SIZE} bytes")
        
        # Store the raw data bytes
        self.data_bytes = data
        
        # Parse the encrypted data according to the packet format
        self.src_id = data[0:3]  # 3 bytes - Source ID (truncated serial number)
        self.nwk_id = data[3:5]  # 2 bytes - Network ID
        self.fw_version = data[5]  # 1 byte - Firmware version
        self.sensor_type = data[6:8]  # 2 bytes - Sensor type
        self.payload = data[8:16]  # 8 bytes - Custom payload

class WePowerPacket:
    """Parser for WePower IoT BLE packets."""
    
    def __init__(self, raw_data: bytes):
        """Initialize packet parser with encrypted data only (HA BLE driver filters company ID)."""
        if len(raw_data) < PACKET_LENGTH:
            raise ValueError(f"Packet data must be at least {PACKET_LENGTH} bytes")
        
        self.raw_data = raw_data
        # Since HA BLE driver filters company ID, we only receive encrypted data
        # The encrypted data structure:
        # Encrypted data (16 bytes) - Contains src_id, nwk_id, fw_version, sensor_type, payload
        self.company_id = COMPANY_ID  # WePower company ID (filtered by HA)
        self.flags = None  # Flags are handled separately in BLE coordinator
        self.encrypted_data = WePowerEncryptedData(raw_data)  # 16 bytes of encrypted data
        self.crc = None  # CRC is handled separately in BLE coordinator
    
    def is_valid_company_id(self) -> bool:
        """Check if this is a WePower packet."""
        return self.company_id == COMPANY_ID
    
    def validate_crc(self) -> bool:
        """Validate CRC checksum (handled separately in BLE coordinator)."""
        # CRC validation is handled in the BLE coordinator
        # since we only receive encrypted data here
        return True
    
    def _calculate_crc8(self, data: bytes) -> int:
        """Calculate CRC8 checksum using the same algorithm as the C code."""
        # CRC-8 with polynomial 0x07, initial value 0x00, no reflection
        # This matches the C implementation: crc8(data, len, 0x07, 0x00, false)
        crc = 0x00  # Initial value
        
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ 0x07
                else:
                    crc <<= 1
                crc &= 0xFF
        
        return crc
    
    def decrypt_payload(self, decryption_key: bytes) -> Optional[Dict[str, Any]]:
        """Decrypt the encrypted data using AES-ECB."""
        try:
            # Check if decryption is needed based on encrypt_status flag
            if self.flags.encrypt_status == 1:
                # Data is not encrypted, return as-is
                decrypted_data = self.encrypted_data.data_bytes
            else:
                # Data is encrypted, decrypt it
                cipher = Cipher(
                    algorithms.AES(decryption_key),
                    modes.ECB(),
                    backend=default_backend()
                )
                decryptor = cipher.decryptor()
                decrypted_data = decryptor.update(self.encrypted_data.data_bytes) + decryptor.finalize()
            
            # Parse decrypted data
            decrypted_packet = WePowerEncryptedData(decrypted_data)
            
            return {
                'src_id': decrypted_packet.src_id.hex().upper(),
                'nwk_id': decrypted_packet.nwk_id.hex().upper(),
                'fw_version': decrypted_packet.fw_version,
                'sensor_type': decrypted_packet.sensor_type.hex().upper(),
                'payload': decrypted_packet.payload.hex().upper(),
                'event_counter_lsb': self.flags.event_counter_lsb,
                'payload_length': self.flags.payload_length,
                'encrypt_status': self.flags.encrypt_status,
                'power_status': self.flags.self_external_power,
            }
        except Exception as e:
            _LOGGER.error(f"Decryption failed: {e}")
            return None
    
    def parse_sensor_data(self, decrypted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse sensor-specific data based on sensor type."""
        sensor_type = int(decrypted_data['sensor_type'], 16)
        payload = bytes.fromhex(decrypted_data['payload'])
        
        sensor_data = {
            'sensor_type': sensor_type,
            'event_counter_lsb': decrypted_data['event_counter_lsb'],
            'payload_length': decrypted_data['payload_length'],
            'encrypt_status': decrypted_data['encrypt_status'],
            'power_status': decrypted_data['power_status'],
        }
        
        # Parse based on sensor type
        if sensor_type == 4:  # Leak sensor
            if len(payload) >= 4:
                # Event Counter (3 bytes) + Sensor Event Report (1 byte)
                event_counter = struct.unpack('<I', payload[0:3] + b'\x00')[0]  # Pad to 4 bytes
                sensor_event = payload[3]
                
                sensor_data.update({
                    'event_counter': event_counter,
                    'sensor_event': sensor_event,
                    'leak_detected': sensor_event == 1,  # Assuming 1 means leak detected
                })
        
        return sensor_data

def parse_wepower_packet(manufacturer_data: bytes, decryption_key: Optional[bytes] = None) -> Optional[Dict[str, Any]]:
    """Parse WePower packet from manufacturer data."""
    try:
        packet = WePowerPacket(manufacturer_data)
        
        if not packet.is_valid_company_id():
            return None
        
        # Validate CRC before processing
        if not packet.validate_crc():
            _LOGGER.warning("CRC validation failed for WePower packet")
            return None
        
        result = {
            'company_id': packet.company_id,
            'flags': {
                'encrypt_status': packet.flags.encrypt_status,
                'self_external_power': packet.flags.self_external_power,
                'event_counter_lsb': packet.flags.event_counter_lsb,
                'payload_length': packet.flags.payload_length,
            },
            'crc': packet.crc,
        }
        
        # If decryption key is provided, decrypt the data
        if decryption_key:
            decrypted_data = packet.decrypt_payload(decryption_key)
            if decrypted_data:
                result['decrypted_data'] = decrypted_data
                result['sensor_data'] = packet.parse_sensor_data(decrypted_data)
        
        return result
        
    except Exception as e:
        _LOGGER.error(f"Failed to parse WePower packet: {e}")
        return None
