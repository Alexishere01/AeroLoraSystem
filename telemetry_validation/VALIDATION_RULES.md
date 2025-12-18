# Validation Rules Reference

This document describes the validation rule syntax and provides examples for common use cases in the Telemetry Validation System.

## Overview

Validation rules allow you to define conditions that telemetry data must satisfy. When a rule is violated, the system generates an alert and logs the violation for later analysis.

## Rule Structure

Validation rules are defined in JSON format in `config/validation_rules.json`. Each rule has the following structure:

```json
{
  "name": "Rule Name",
  "msg_type": "MAVLINK_MESSAGE_TYPE",
  "field": "field_name",
  "operator": "<|>|==|!=|<=|>=",
  "threshold": value,
  "severity": "INFO|WARNING|CRITICAL",
  "description": "Human-readable description"
}
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique identifier for the rule |
| `msg_type` | string | Yes | MAVLink message type (e.g., "HEARTBEAT", "GPS_RAW_INT") |
| `field` | string | Yes | Field name within the message to validate |
| `operator` | string | Yes | Comparison operator: `<`, `>`, `==`, `!=`, `<=`, `>=` |
| `threshold` | number/string | Yes | Value to compare against |
| `severity` | string | Yes | Alert severity: `INFO`, `WARNING`, or `CRITICAL` |
| `description` | string | No | Human-readable description of the rule |

## Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `<` | Less than | `voltage_battery < 10000` |
| `>` | Greater than | `alt > 100000` |
| `==` | Equal to | `fix_type == 0` |
| `!=` | Not equal to | `satellites_visible != 0` |
| `<=` | Less than or equal | `rssi <= -100` |
| `>=` | Greater than or equal | `temperature >= 60` |

## Severity Levels

### INFO
- Informational alerts for non-critical conditions
- Logged but not highlighted
- No email/SMS alerts
- Example: GPS satellite count below optimal

### WARNING
- Potential issues that should be monitored
- Highlighted in console output (yellow)
- Logged with warning flag
- Optional email alerts
- Example: Battery voltage getting low, weak signal

### CRITICAL
- Serious issues requiring immediate attention
- Highlighted in console output (red)
- Logged with critical flag
- Email/SMS alerts sent immediately
- Example: Battery critically low, GPS fix lost

## Common MAVLink Message Types

### HEARTBEAT
- `type`: Vehicle type
- `autopilot`: Autopilot type
- `base_mode`: System mode bitmap
- `custom_mode`: Custom mode (flight mode)
- `system_status`: System status flag
- `mavlink_version`: MAVLink protocol version

### SYS_STATUS
- `voltage_battery`: Battery voltage (mV)
- `current_battery`: Battery current (cA, -1 if not available)
- `battery_remaining`: Battery remaining (%)
- `drop_rate_comm`: Communication drop rate (%)
- `errors_comm`: Communication errors
- `load`: CPU load (%)

### GPS_RAW_INT
- `fix_type`: GPS fix type (0=no fix, 3=3D fix)
- `lat`: Latitude (degE7)
- `lon`: Longitude (degE7)
- `alt`: Altitude (mm)
- `eph`: GPS HDOP
- `epv`: GPS VDOP
- `vel`: Ground speed (cm/s)
- `cog`: Course over ground (cdeg)
- `satellites_visible`: Number of satellites visible

### ATTITUDE
- `roll`: Roll angle (rad)
- `pitch`: Pitch angle (rad)
- `yaw`: Yaw angle (rad)
- `rollspeed`: Roll angular speed (rad/s)
- `pitchspeed`: Pitch angular speed (rad/s)
- `yawspeed`: Yaw angular speed (rad/s)

### RADIO_STATUS
- `rssi`: Local signal strength (dBm)
- `remrssi`: Remote signal strength (dBm)
- `txbuf`: Transmit buffer usage (%)
- `noise`: Background noise level
- `remnoise`: Remote background noise level
- `rxerrors`: Receive errors
- `fixed`: Count of error corrected packets

## Example Rules

### Battery Monitoring

**Low Battery Warning**
```json
{
  "name": "Low Battery Warning",
  "msg_type": "SYS_STATUS",
  "field": "voltage_battery",
  "operator": "<",
  "threshold": 10500,
  "severity": "WARNING",
  "description": "Battery voltage below 10.5V (3S LiPo at ~3.5V/cell)"
}
```

**Critical Battery**
```json
{
  "name": "Critical Battery",
  "msg_type": "SYS_STATUS",
  "field": "voltage_battery",
  "operator": "<",
  "threshold": 10000,
  "severity": "CRITICAL",
  "description": "Battery voltage critically low (<10V, 3S LiPo at ~3.3V/cell)"
}
```

**Battery Percentage Low**
```json
{
  "name": "Battery Percentage Low",
  "msg_type": "SYS_STATUS",
  "field": "battery_remaining",
  "operator": "<",
  "threshold": 20,
  "severity": "WARNING",
  "description": "Battery remaining below 20%"
}
```

### GPS Monitoring

**GPS Fix Lost**
```json
{
  "name": "GPS Fix Lost",
  "msg_type": "GPS_RAW_INT",
  "field": "fix_type",
  "operator": "<",
  "threshold": 2,
  "severity": "CRITICAL",
  "description": "GPS fix type below 2D (0=no fix, 1=no fix, 2=2D, 3=3D)"
}
```

**Low Satellite Count**
```json
{
  "name": "Low Satellite Count",
  "msg_type": "GPS_RAW_INT",
  "field": "satellites_visible",
  "operator": "<",
  "threshold": 6,
  "severity": "WARNING",
  "description": "Less than 6 GPS satellites visible"
}
```

**GPS Altitude Jump**
```json
{
  "name": "GPS Altitude Jump",
  "msg_type": "GPS_RAW_INT",
  "field": "alt",
  "operator": ">",
  "threshold": 50000,
  "severity": "WARNING",
  "description": "GPS altitude changed >50m (handled by built-in jump detection)"
}
```

### Signal Quality Monitoring

**Weak RSSI**
```json
{
  "name": "Weak RSSI",
  "msg_type": "RADIO_STATUS",
  "field": "rssi",
  "operator": "<",
  "threshold": -100,
  "severity": "WARNING",
  "description": "Local RSSI below -100 dBm (weak signal)"
}
```

**Critical RSSI**
```json
{
  "name": "Critical RSSI",
  "msg_type": "RADIO_STATUS",
  "field": "rssi",
  "operator": "<",
  "threshold": -110,
  "severity": "CRITICAL",
  "description": "Local RSSI below -110 dBm (very weak signal, link may fail)"
}
```

**High Packet Loss**
```json
{
  "name": "High Packet Loss",
  "msg_type": "RADIO_STATUS",
  "field": "rxerrors",
  "operator": ">",
  "threshold": 100,
  "severity": "WARNING",
  "description": "Receive errors exceed 100"
}
```

### System Health Monitoring

**High CPU Load**
```json
{
  "name": "High CPU Load",
  "msg_type": "SYS_STATUS",
  "field": "load",
  "operator": ">",
  "threshold": 800,
  "severity": "WARNING",
  "description": "CPU load above 80% (load is in 0.1% units, so 800 = 80%)"
}
```

**Communication Errors**
```json
{
  "name": "Communication Errors",
  "msg_type": "SYS_STATUS",
  "field": "errors_comm",
  "operator": ">",
  "threshold": 50,
  "severity": "WARNING",
  "description": "Communication errors exceed 50"
}
```

**High Drop Rate**
```json
{
  "name": "High Drop Rate",
  "msg_type": "SYS_STATUS",
  "field": "drop_rate_comm",
  "operator": ">",
  "threshold": 20,
  "severity": "WARNING",
  "description": "Communication drop rate above 20%"
}
```

## Built-in Validation

In addition to custom rules, the system includes built-in validation:

### GPS Altitude Jump Detection
Automatically detects when GPS altitude changes by more than 50 meters in 1 second, which may indicate a GPS glitch.

### Packet Loss Detection
Tracks sequence numbers from HEARTBEAT messages and detects gaps, calculating packet loss rate.

### Binary Protocol Health
Monitors checksum errors, parse errors, and buffer overflows in the binary UART protocol.

### Relay Latency Monitoring
Alerts when relay mode latency exceeds 500ms threshold.

## Configuration File Example

Complete `config/validation_rules.json` example:

```json
{
  "rules": [
    {
      "name": "Low Battery Warning",
      "msg_type": "SYS_STATUS",
      "field": "voltage_battery",
      "operator": "<",
      "threshold": 10500,
      "severity": "WARNING",
      "description": "Battery voltage below 10.5V"
    },
    {
      "name": "Critical Battery",
      "msg_type": "SYS_STATUS",
      "field": "voltage_battery",
      "operator": "<",
      "threshold": 10000,
      "severity": "CRITICAL",
      "description": "Battery voltage critically low"
    },
    {
      "name": "GPS Fix Lost",
      "msg_type": "GPS_RAW_INT",
      "field": "fix_type",
      "operator": "<",
      "threshold": 2,
      "severity": "CRITICAL",
      "description": "GPS fix type below 2D"
    },
    {
      "name": "Low Satellite Count",
      "msg_type": "GPS_RAW_INT",
      "field": "satellites_visible",
      "operator": "<",
      "threshold": 6,
      "severity": "WARNING",
      "description": "Less than 6 GPS satellites visible"
    },
    {
      "name": "Weak RSSI",
      "msg_type": "RADIO_STATUS",
      "field": "rssi",
      "operator": "<",
      "threshold": -100,
      "severity": "WARNING",
      "description": "Local RSSI below -100 dBm"
    },
    {
      "name": "Critical RSSI",
      "msg_type": "RADIO_STATUS",
      "field": "rssi",
      "operator": "<",
      "threshold": -110,
      "severity": "CRITICAL",
      "description": "Local RSSI below -110 dBm"
    }
  ]
}
```

## Runtime Rule Reload

The validation engine supports runtime rule reloading without restarting the system:

1. Edit `config/validation_rules.json`
2. Save the file
3. The system will automatically detect changes and reload rules
4. Check console output for "Loaded N validation rules" message

## Best Practices

### Rule Design
1. **Be Specific**: Use descriptive names and detailed descriptions
2. **Set Appropriate Thresholds**: Test thresholds with real flight data
3. **Use Severity Wisely**: Reserve CRITICAL for issues requiring immediate action
4. **Avoid Redundancy**: Don't create multiple rules for the same condition
5. **Document Units**: Include units in descriptions (mV, %, dBm, etc.)

### Testing Rules
1. **Test with Historical Data**: Use log files to validate rule behavior
2. **Monitor False Positives**: Adjust thresholds if too many false alerts
3. **Check Coverage**: Ensure critical parameters are monitored
4. **Review Regularly**: Update rules based on operational experience

### Performance
1. **Limit Rule Count**: Too many rules can impact performance
2. **Optimize Operators**: Simple comparisons are faster than complex logic
3. **Use Built-in Validation**: Leverage built-in features when possible

## Troubleshooting

### Rule Not Triggering
- Verify message type matches exactly (case-sensitive)
- Check field name matches MAVLink specification
- Confirm threshold value is correct type (number vs string)
- Enable debug logging to see rule evaluation

### False Positives
- Adjust threshold values based on real data
- Consider using different severity level
- Add hysteresis by creating separate rules for different thresholds
- Review message frequency and timing

### Rule Syntax Errors
- Validate JSON syntax with online validator
- Check for missing commas, quotes, or brackets
- Ensure operator is one of: `<`, `>`, `==`, `!=`, `<=`, `>=`
- Verify severity is one of: `INFO`, `WARNING`, `CRITICAL`

## See Also

- [config/README.md](config/README.md) - Configuration file reference
- [USAGE.md](USAGE.md) - Usage guide with examples
- [src/README_ValidationEngine.md](src/README_ValidationEngine.md) - Validation engine implementation
- [examples/validation_engine_example.py](examples/validation_engine_example.py) - Example code
