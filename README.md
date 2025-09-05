# WePower IoT Home Assistant Integration

A comprehensive Home Assistant integration for managing WePower IoT devices including BLE and Zigbee sensors, switches, and lights.

## Features

### 🔌 **Multi-Protocol Support**
- **BLE (Bluetooth Low Energy)** - V0 manual and V1 automatic discovery modes
- **Zigbee** - Automatic device pairing and management
- **Serial Port Scanning** - Automatic dongle detection via "Who are you?" protocol
- **MQTT Communication** - Two-way communication with the WePower IoT add-on

### 📱 **Device Types**
- **Sensors**: Leak sensors, vibration sensors, temperature, humidity, pressure, air quality
- **Switches**: On/off switches, door switches, toggle switches
- **Lights**: RGB color lights with brightness and color temperature control
- **Binary Sensors**: BLE and Zigbee connection status

### 🎛️ **Control Features**
- **BLE/Zigbee Toggles** - Enable/disable protocols via UI
- **Manual Device Addition** - Add devices manually through forms
- **Device Status Tracking** - Real-time device status monitoring
- **Automatic Offline Detection** - Devices show as offline when inactive

## Installation

### Option 1: HACS (Recommended)
1. Install [HACS](https://hacs.xyz/)
2. Add this repository as a custom repository
3. Install "WePower IoT" integration
4. Restart Home Assistant

### Option 2: Manual Installation
1. Copy the `integration` folder to your `config/custom_components/` directory
2. Restart Home Assistant
3. Go to **Settings** → **Devices & Services** → **Integrations**
4. Click **+ Add Integration** and search for "WePower IoT"

## Configuration

### UI Configuration (Recommended)
1. Go to **Settings** → **Devices & Services** → **Integrations**
2. Click on **WePower IoT** integration
3. Configure the following settings:
   - **MQTT Broker URL**: Your MQTT broker address
   - **MQTT Username/Password**: Optional authentication
   - **Enable BLE**: Toggle BLE functionality
   - **Enable Zigbee**: Toggle Zigbee functionality
   - **Scan Interval**: Device discovery frequency
   - **Heartbeat Interval**: Connection monitoring frequency

### YAML Configuration
```yaml
# Example configuration.yaml
wepower_iot:
  mqtt_broker: "mqtt://homeassistant:1883"
  enable_ble: true
  enable_zigbee: true
  scan_interval: 0.02
  heartbeat_interval: 10.0
```

## Usage

### Adding Devices

#### Automatic Discovery
- Devices are automatically discovered when connected to BLE/Zigbee dongles
- The integration scans for new devices every 30 seconds
- Device status is updated in real-time via MQTT

#### Manual Device Addition
1. Go to **Settings** → **Devices & Services** → **WePower IoT**
2. Click **Add Device**
3. Fill in the device information:
   - **Device ID**: Unique identifier
   - **Device Name**: Display name
   - **Device Type**: BLE, Zigbee, or Generic
   - **Category**: Sensor, Switch, Light, Door, or Toggle
   - **BLE Discovery Mode**: V0 Manual or V1 Auto (for BLE devices)

### Controlling Devices

#### Sensors
- **Leak Sensors**: Show moisture levels (0-100%)
- **Vibration Sensors**: Display motion/vibration data
- **Temperature/Humidity**: Standard environmental readings
- **Air Quality**: CO2 and other air quality metrics

#### Switches
- **On/Off Switches**: Basic on/off control
- **Door Switches**: Door open/close status
- **Toggle Switches**: State-based switching

#### Lights
- **RGB Control**: Full color spectrum control
- **Brightness**: 0-255 brightness levels
- **Color Temperature**: Warm to cool white adjustment
- **Transitions**: Smooth color/brightness changes

### BLE and Zigbee Management

#### Protocol Toggles
- Use the integration's configuration options to enable/disable BLE or Zigbee
- Toggles are available in the integration settings
- Changes take effect immediately

#### Connection Status
- **Binary Sensors**: Show BLE and Zigbee connection status
- **Real-time Updates**: Status changes are reflected immediately
- **Dongle Information**: View connected dongle details

## MQTT Topics

### Status Topics
- `wepower_iot/status` - Integration status updates
- `wepower_iot/dongle/{port}` - Dongle status information
- `wepower_iot/device/{device_id}` - Device updates

### Control Topics
- `wepower_iot/control/ble` - BLE toggle commands
- `wepower_iot/control/zigbee` - Zigbee toggle commands
- `wepower_iot/device/{device_id}/command` - Device-specific commands

### Command Format
```json
{
  "command": "turn_on",
  "device_id": "device_123",
  "timestamp": "2024-01-01T12:00:00Z",
  "brightness": 255,
  "rgb_color": [255, 0, 0]
}
```

## Device Status

### Status Types
- **Connected**: Device is actively communicating
- **Offline**: Device is not responding (automatic after 5 minutes)
- **Connecting**: Device is in pairing mode
- **Identified**: Device is recognized but not fully paired
- **Paired**: Device is fully paired and managed
- **Error**: Device has encountered an error

### Offline Behavior
- Devices automatically show as offline after 5 minutes of inactivity
- This simulates real-world device behavior
- Status updates are sent via MQTT for real-time monitoring

## Troubleshooting

### Common Issues

#### Integration Not Loading
- Check that all required files are in the correct directory
- Verify MQTT broker is accessible
- Check Home Assistant logs for error messages

#### Devices Not Appearing
- Ensure BLE/Zigbee toggles are enabled
- Check MQTT connection status
- Verify dongles are connected and responding

#### MQTT Connection Issues
- Verify MQTT broker URL and credentials
- Check network connectivity
- Ensure MQTT integration is working in Home Assistant

### Debug Mode
Enable debug logging in Home Assistant:
```yaml
logger:
  default: info
  logs:
    custom_components.wepower_iot: debug
```

## Development

### Architecture
- **Device Manager**: Handles device discovery and management
- **MQTT Client**: Manages communication with the add-on
- **Platform Entities**: Home Assistant entity implementations
- **Configuration Flow**: UI-based setup and configuration

### Adding New Device Types
1. Create new platform file (e.g., `fan.py`)
2. Implement required entity methods
3. Add to platform list in `__init__.py`
4. Update constants and translations

### Testing
- Use the integration with the WePower IoT add-on
- Test device discovery and control
- Verify MQTT communication
- Check entity state updates

## Support

### Documentation
- [Home Assistant Integration Documentation](https://developers.home-assistant.io/)
- [MQTT Integration Guide](https://www.home-assistant.io/integrations/mqtt/)
- [Custom Component Development](https://developers.home-assistant.io/docs/creating_component_index/)

### Issues and Feature Requests
- Report bugs via GitHub issues
- Request new features through GitHub discussions
- Contribute improvements via pull requests

## License

This integration is licensed under the MIT License. See the LICENSE file for details.

## Changelog

### Version 1.0.0
- Initial release
- BLE and Zigbee support
- Multi-device type support
- MQTT communication
- UI-based configuration
- Device management interface
