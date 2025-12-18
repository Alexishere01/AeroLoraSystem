# Configuration Guide

This directory contains configuration files for the Telemetry Validation System.

## Files

- **config.json** - Main system configuration
- **validation_rules.json** - Telemetry validation rules
- **README.md** - This file
- **BINARY_PROTOCOL.md** - Binary protocol packet structure documentation

## config.json

The main configuration file controls all aspects of the telemetry validation system.

### Connection Settings

```json
"connection": {
  "type": "serial",           // Connection type: "serial" or "udp"
  "serial": {
    "port": "/dev/ttyUSB0",   // Serial port device
    "baudrate": 115200,       // Baud rate (115200 or 57600)
    "timeout": 1              // Read timeout in seconds
  },
  "udp": {
    "host": "0.0.0.0",        // UDP bind address
    "port": 14550,            // UDP port (14550 for MAVLink)
    "timeout": 1              // Read timeout in seconds
  },
  "reconnect_interval": 5,    // Seconds between reconnection attempts
  "auto_reconnect": true      // Automatically reconnect on disconnect
}
```

**Connection Types:**
- `serial` - Connect to Ground Station via USB/serial port
- `udp` - Listen for MAVLink packets on UDP socket

**Common Serial Ports:**
- Linux: `/dev/ttyUSB0`, `/dev/ttyACM0`
- macOS: `/dev/cu.usbserial-*`, `/dev/cu.usbmodem-*`
- Windows: `COM3`, `COM4`, etc.

### Protocol Settings

```json
"protocol": {
  "type": "binary",           // Protocol type: "binary" or "mavlink"
  "parse_mavlink": true,      // Extract MAVLink from binary packets
  "log_binary_packets": true, // Log raw binary packets to .binlog
  "validate_checksums": true  // Validate Fletcher-16 checksums
}
```

**Protocol Types:**
- `binary` - Parse custom binary protocol (default for dual-controller system)
- `mavlink` - Parse raw MAVLink packets directly

The binary protocol wraps MAVLink packets with RSSI/SNR metadata. See `BINARY_PROTOCOL.md` for details.

### Logging Settings

```json
"logging": {
  "log_dir": "./telemetry_logs",        // Directory for log files
  "max_file_size_mb": 100,              // Max file size before rotation
  "formats": ["csv", "json", "tlog", "binlog"],  // Output formats
  "buffer_size": 1000,                  // Number of messages to buffer
  "flush_interval_sec": 5               // Seconds between buffer flushes
}
```

**Log Formats:**
- `csv` - Human-readable CSV with decoded fields
- `json` - Structured JSON for programmatic analysis
- `tlog` - MAVLink .tlog format (compatible with QGC/MAVProxy)
- `binlog` - Raw binary protocol packets for replay/debugging

**File Rotation:**
Files are automatically rotated when they exceed `max_file_size_mb`. New files are created with sequence numbers.

### Validation Settings

```json
"validation": {
  "rules_file": "./config/validation_rules.json",  // Path to rules file
  "enable_builtin_rules": true,                    // Enable built-in rules
  "enable_gps_jump_detection": true,               // Detect GPS glitches
  "gps_jump_threshold_m": 50,                      // GPS jump threshold (meters)
  "enable_packet_loss_detection": true,            // Detect packet loss
  "packet_loss_threshold_percent": 20              // Packet loss alert threshold
}
```

**Built-in Rules:**
- GPS altitude jump detection (>50m in 1 second)
- Packet loss detection via sequence number gaps
- Battery voltage monitoring
- GPS fix quality monitoring

### Alert Settings

```json
"alerts": {
  "channels": ["console"],              // Alert channels: "console", "email", "sms"
  "throttle_interval_sec": 60,          // Minimum seconds between duplicate alerts
  "max_alerts_per_minute": 10,          // Maximum alerts per minute
  "email": {
    "enabled": false,                   // Enable email alerts
    "server": "smtp.gmail.com",         // SMTP server
    "port": 587,                        // SMTP port
    "from": "alerts@example.com",       // From address
    "to": "operator@example.com",       // To address
    "username": "",                     // SMTP username
    "password": "",                     // SMTP password
    "use_tls": true                     // Use TLS encryption
  }
}
```

**Alert Channels:**
- `console` - Print alerts to console with color coding
- `email` - Send email alerts for CRITICAL severity
- `sms` - Send SMS alerts (requires Twilio configuration)

**Alert Throttling:**
Prevents alert spam by limiting duplicate alerts within `throttle_interval_sec`.

### Visualization Settings

```json
"visualization": {
  "enabled": true,                      // Enable real-time visualization
  "update_rate_hz": 1,                  // Graph update rate (Hz)
  "max_history_points": 300,            // Maximum data points to display
  "graphs": [                           // Graphs to display
    "rssi",
    "snr",
    "packet_rate",
    "battery_voltage",
    "altitude",
    "protocol_health"
  ]
}
```

**Available Graphs:**
- `rssi` - Received Signal Strength Indicator
- `snr` - Signal-to-Noise Ratio
- `packet_rate` - Packets per second
- `battery_voltage` - Battery voltage over time
- `altitude` - Altitude (relative to home)
- `protocol_health` - Binary protocol error rates

### Metrics Settings

```json
"metrics": {
  "rolling_windows": [1, 10, 60],       // Rolling window sizes (seconds)
  "track_message_distribution": true,   // Track message type distribution
  "track_command_latency": true,        // Track command response latency
  "track_binary_protocol_health": true  // Track protocol error rates
}
```

**Rolling Windows:**
Metrics are calculated over multiple time windows for trend analysis:
- 1 second - Real-time metrics
- 10 seconds - Short-term trends
- 60 seconds - Long-term trends

### Mode Tracking Settings

```json
"mode_tracking": {
  "enabled": true,                      // Enable mode tracking
  "detect_relay_mode": true,            // Detect relay mode from STATUS_REPORT
  "relay_latency_threshold_ms": 500,    // Alert if relay latency exceeds threshold
  "compare_modes": true                 // Compare direct vs relay mode metrics
}
```

**Mode Detection:**
The system automatically detects when the drone switches between direct and relay modes by monitoring `CMD_STATUS_REPORT` packets.

### Serial Monitor Settings

```json
"serial_monitor": {
  "enabled": true,                      // Enable serial monitor output
  "throttle_rate_hz": 10,               // Maximum output rate (Hz)
  "highlight_critical": true,           // Highlight critical messages
  "show_statistics": true,              // Show periodic statistics
  "critical_messages": [                // Messages to always display
    "HEARTBEAT",
    "GPS_RAW_INT",
    "ATTITUDE",
    "SYS_STATUS"
  ]
}
```

**Output Throttling:**
Prevents console overflow by limiting output to `throttle_rate_hz` messages per second while ensuring critical messages are always displayed.

### Debug Settings

```json
"debug": {
  "verbose": false,                     // Enable verbose logging
  "log_parse_errors": true,             // Log packet parse errors
  "log_checksum_errors": true,          // Log checksum validation errors
  "log_unknown_commands": true          // Log unknown command types
}
```

## validation_rules.json

Defines validation rules for telemetry data. Each rule specifies conditions that trigger alerts.

### Rule Structure

```json
{
  "name": "Rule Name",                  // Unique rule identifier
  "msg_type": "SYS_STATUS",             // MAVLink message type
  "field": "voltage_battery",           // Field to validate
  "operator": "<",                      // Comparison operator
  "threshold": 10500,                   // Threshold value
  "severity": "WARNING",                // Alert severity
  "description": "Human-readable description"
}
```

### Operators

- `<` - Less than
- `>` - Greater than
- `==` - Equal to
- `!=` - Not equal to
- `<=` - Less than or equal to
- `>=` - Greater than or equal to

### Severity Levels

- `INFO` - Informational, logged but no alert
- `WARNING` - Warning condition, console alert
- `CRITICAL` - Critical condition, all alert channels

### Common MAVLink Message Types

- `HEARTBEAT` - System heartbeat (1 Hz)
- `SYS_STATUS` - System status (battery, sensors)
- `GPS_RAW_INT` - GPS position and fix quality
- `ATTITUDE` - Roll, pitch, yaw angles
- `GLOBAL_POSITION_INT` - Global position and altitude
- `VFR_HUD` - Airspeed, ground speed, heading
- `RC_CHANNELS` - RC channel values and RSSI
- `RADIO_STATUS` - Telemetry radio status

### Example Rules

**Battery Monitoring:**
```json
{
  "name": "Low Battery Warning",
  "msg_type": "SYS_STATUS",
  "field": "voltage_battery",
  "operator": "<",
  "threshold": 10500,
  "severity": "WARNING",
  "description": "Battery voltage below 10.5V"
}
```

**GPS Quality:**
```json
{
  "name": "GPS Fix Lost",
  "msg_type": "GPS_RAW_INT",
  "field": "fix_type",
  "operator": "<",
  "threshold": 2,
  "severity": "WARNING",
  "description": "GPS fix quality degraded (no 3D fix)"
}
```

**Attitude Limits:**
```json
{
  "name": "Attitude Roll Limit",
  "msg_type": "ATTITUDE",
  "field": "roll",
  "operator": ">",
  "threshold": 0.785,
  "severity": "WARNING",
  "description": "Roll angle exceeds 45 degrees (0.785 rad)"
}
```

## Usage Examples

### Basic Usage

```bash
# Connect via serial port
python main.py --connection serial --port /dev/ttyUSB0 --baudrate 115200

# Connect via UDP
python main.py --connection udp --port 14550

# Use custom config file
python main.py --config /path/to/config.json
```

### Validation Only

```bash
# Run validation without visualization
python main.py --no-visualization --validation-only
```

### Replay Logs

```bash
# Replay binary protocol logs
python main.py --replay telemetry_logs/telemetry_20231026_120000.binlog
```

## Troubleshooting

### Connection Issues

**Problem:** Cannot connect to serial port
- Check port name: `ls /dev/tty*` (Linux/macOS) or Device Manager (Windows)
- Check permissions: `sudo chmod 666 /dev/ttyUSB0`
- Verify baud rate matches Ground Station configuration

**Problem:** No data received
- Check that Ground Station is powered on and transmitting
- Verify correct protocol type in config (binary vs mavlink)
- Enable debug logging: `"verbose": true`

### Validation Issues

**Problem:** Too many false alerts
- Adjust thresholds in `validation_rules.json`
- Increase `throttle_interval_sec` in alert settings
- Disable specific rules by removing them from the rules file

**Problem:** Missing alerts
- Check rule syntax (operator, field names)
- Verify message type matches MAVLink message name
- Enable debug logging to see validation checks

### Performance Issues

**Problem:** High CPU usage
- Reduce visualization update rate: `"update_rate_hz": 0.5`
- Disable visualization: `--no-visualization`
- Reduce buffer size: `"buffer_size": 100`

**Problem:** Disk space filling up
- Reduce `max_file_size_mb`
- Disable unused log formats
- Implement log rotation/cleanup script

## Advanced Configuration

### Custom Validation Rules

Create application-specific rules by adding entries to `validation_rules.json`:

```json
{
  "name": "Custom Rule",
  "msg_type": "CUSTOM_MESSAGE",
  "field": "custom_field",
  "operator": ">",
  "threshold": 100,
  "severity": "WARNING",
  "description": "Custom validation rule"
}
```

### Email Alerts

Configure email alerts for critical conditions:

1. Enable email in config: `"enabled": true`
2. Configure SMTP settings (Gmail example):
   - Server: `smtp.gmail.com`
   - Port: `587`
   - Enable "Less secure app access" or use App Password
3. Test with: `python -m src.alert_manager`

### Multi-Drone Monitoring

Monitor multiple drones by system ID:

```json
"visualization": {
  "multi_drone": true,
  "system_ids": [1, 2, 3]
}
```

Each drone will have separate graphs color-coded by system ID.

## See Also

- [BINARY_PROTOCOL.md](BINARY_PROTOCOL.md) - Binary protocol specification
- [../README.md](../README.md) - Main project documentation
- [../USAGE.md](../USAGE.md) - Usage guide and examples
