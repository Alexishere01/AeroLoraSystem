# Telemetry Validation System - Usage Guide

## Overview

The Telemetry Validation System is a comprehensive tool for monitoring, logging, validating, and visualizing MAVLink telemetry data from the dual-controller LoRa relay system. It supports both the custom binary UART protocol and raw MAVLink data streams.

## Quick Start

### Basic Usage

Monitor a serial port with binary protocol (default):
```bash
python3 main.py --connection-type serial --port /dev/ttyUSB0 --baudrate 115200
```

Monitor UDP with raw MAVLink:
```bash
python3 main.py --connection-type udp --port 14550 --protocol-mode mavlink
```

Use a configuration file:
```bash
python3 main.py --config config/config.json
```

### Command-Line Options

#### Connection Options
- `--connection-type {serial,udp}` or `-c`: Connection type (default: serial)
- `--port PORT` or `-p`: Serial port (e.g., /dev/ttyUSB0) or UDP port number (e.g., 14550)
- `--baudrate BAUDRATE` or `-b`: Serial baudrate (default: 115200)

#### Protocol Options
- `--protocol-mode {binary,mavlink}` or `-m`: Protocol parsing mode
  - `binary`: Custom UART protocol with MAVLink extraction (default)
  - `mavlink`: Raw MAVLink parsing

#### Logging Options
- `--log-dir LOG_DIR` or `-l`: Directory for log files (default: ./telemetry_logs)
- `--no-logging`: Disable telemetry logging

#### Validation Options
- `--rules-file RULES_FILE` or `-r`: Path to validation rules JSON file
- `--no-validation`: Disable telemetry validation

#### Visualization Options
- `--visualization` or `-v`: Enable real-time visualization
- `--no-visualization`: Disable visualization

#### General Options
- `--config CONFIG`: Path to configuration JSON file
- `--verbose`: Enable verbose logging
- `--quiet` or `-q`: Suppress non-error output
- `--help` or `-h`: Show help message

## Configuration File

The system can be configured using a JSON configuration file. See `config/config.json` for an example.

### Configuration Structure

```json
{
  "connection": {
    "type": "serial",
    "serial": {
      "port": "/dev/ttyUSB0",
      "baudrate": 115200
    },
    "udp": {
      "host": "0.0.0.0",
      "port": 14550
    },
    "reconnect_interval": 5
  },
  "logging": {
    "log_dir": "./telemetry_logs",
    "max_file_size_mb": 100,
    "formats": ["csv", "json", "tlog"]
  },
  "validation": {
    "rules_file": "./config/validation_rules.json",
    "enable_builtin_rules": true
  },
  "alerts": {
    "channels": ["console"],
    "email": {
      "enabled": false,
      "server": "smtp.gmail.com",
      "port": 587,
      "from": "alerts@example.com",
      "to": "operator@example.com",
      "username": "",
      "password": ""
    }
  },
  "visualization": {
    "enabled": true,
    "update_rate_hz": 1
  }
}
```

### Validation Rules

Validation rules are defined in a separate JSON file (default: `config/validation_rules.json`).

Example rule:
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
    }
  ]
}
```

Supported operators: `<`, `>`, `==`, `!=`, `<=`, `>=`
Supported severity levels: `INFO`, `WARNING`, `CRITICAL`

## Features

### Binary Protocol Support

The system can parse the custom binary UART protocol used between the Primary and Secondary controllers:

- Parses binary protocol packets with Fletcher-16 checksum validation
- Extracts MAVLink messages from BridgePayload structures
- Tracks RSSI/SNR metadata from binary protocol
- Monitors relay mode status and latency
- Detects binary protocol errors (checksum errors, buffer overflows, timeouts)

### MAVLink Parsing

- Parses MAVLink v1/v2 packets
- Extracts message fields and metadata
- Tracks sequence numbers for packet loss detection
- Supports all standard MAVLink message types

### Telemetry Logging

- Logs to multiple formats simultaneously:
  - CSV: Human-readable with decoded fields
  - JSON: Structured data for programmatic access
  - .tlog: Binary format compatible with QGC and MAVProxy
  - .binlog: Raw binary protocol packets for debugging
- Automatic file rotation at configurable size limit
- Timestamped filenames for easy organization

### Validation Engine

- Configurable validation rules from JSON file
- Automatic GPS altitude jump detection (>50m in 1s)
- Packet loss detection from sequence numbers
- Battery voltage monitoring
- Signal strength (RSSI) monitoring
- Custom field validation with multiple operators

### Metrics Calculation

- Packet rates (1s, 10s, 60s rolling windows)
- RSSI/SNR averaging
- Packet loss rate
- Command latency (COMMAND_LONG -> COMMAND_ACK)
- Message type distribution
- Binary protocol health metrics

### Alert Manager

- Console alerts with color coding
- Email alerts for critical issues (configurable)
- Duplicate alert prevention
- Alert throttling to prevent spam
- Relay mode latency alerts
- Binary protocol error alerts

### Serial Monitor

- Real-time console output of telemetry data
- Color-coded message types
- Critical message highlighting
- Output throttling to prevent buffer overflow
- Statistics display on demand

### Mode Tracking

- Detects relay mode activation/deactivation
- Tracks mode-specific metrics
- Calculates relay latency
- Compares direct vs relay mode performance

### Visualization (Optional)

- Real-time graphs of key metrics:
  - RSSI
  - SNR
  - Packet rate
  - Battery voltage
  - Binary protocol health
- Violation highlighting with red indicators
- Multi-drone support with color-coded graphs
- Historical data viewing from log files
- Configurable update rate (1 Hz default)

## Examples

### Monitor Serial Port with All Features

```bash
python3 main.py \
  --connection-type serial \
  --port /dev/ttyUSB0 \
  --baudrate 115200 \
  --protocol-mode binary \
  --log-dir ./logs \
  --rules-file config/validation_rules.json \
  --visualization
```

### Monitor UDP with Minimal Features

```bash
python3 main.py \
  --connection-type udp \
  --port 14550 \
  --protocol-mode mavlink \
  --no-validation \
  --no-visualization
```

### Use Configuration File

```bash
python3 main.py --config config/config.json
```

### Debug Mode with Verbose Logging

```bash
python3 main.py \
  --connection-type serial \
  --port /dev/ttyUSB0 \
  --verbose
```

### Quiet Mode (Errors Only)

```bash
python3 main.py \
  --connection-type serial \
  --port /dev/ttyUSB0 \
  --quiet
```

## Graceful Shutdown

The system handles interrupt signals (Ctrl+C) gracefully:

1. Closes all connections
2. Flushes and closes log files
3. Writes summary statistics
4. Stops visualization
5. Cleans up resources

Press `Ctrl+C` to stop the system at any time.

## Output Files

### Log Files

All log files are stored in the configured log directory (default: `./telemetry_logs`):

- `telemetry_YYYYMMDD_HHMMSS.csv`: CSV log with decoded messages
- `telemetry_YYYYMMDD_HHMMSS.json`: JSON log with structured data
- `telemetry_YYYYMMDD_HHMMSS.tlog`: Binary MAVLink log (QGC compatible)
- `telemetry_YYYYMMDD_HHMMSS.binlog`: Raw binary protocol packets
- `summary_YYYYMMDD_HHMMSS.txt`: Session summary with statistics

### File Rotation

When log files exceed the configured size limit (default: 100 MB), they are automatically rotated with sequence numbers:

- `telemetry_YYYYMMDD_HHMMSS_1.csv`
- `telemetry_YYYYMMDD_HHMMSS_2.csv`
- etc.

## Troubleshooting

### Connection Issues

If the system fails to connect:

1. Check that the serial port or UDP port is correct
2. Verify the device is connected and powered on
3. Check permissions (serial ports may require sudo or user group membership)
4. Try increasing the reconnect interval in the configuration

### No Data Received

If connected but no data is received:

1. Verify the baudrate matches the device (for serial)
2. Check that the device is transmitting data
3. Try the opposite protocol mode (binary vs mavlink)
4. Enable verbose logging to see connection details

### High CPU Usage

If CPU usage is high:

1. Disable visualization (`--no-visualization`)
2. Reduce the visualization update rate in config
3. Disable logging if not needed (`--no-logging`)
4. Increase the serial monitor throttle limit

### Memory Usage

If memory usage grows over time:

1. Reduce the log file size limit
2. Disable JSON logging (modify config)
3. Reduce the metrics rolling window sizes (requires code modification)

## Requirements

- Python 3.7+
- pymavlink
- pyserial
- matplotlib (for visualization)
- numpy (for visualization)

Install dependencies:
```bash
pip install -r requirements.txt
```

## See Also

- [README.md](README.md): Project overview and setup
- [config/config.json](config/config.json): Example configuration file
- [config/validation_rules.json](config/validation_rules.json): Example validation rules
- [include/BinaryProtocol.h](../include/BinaryProtocol.h): Binary protocol specification
- [include/shared_protocol.h](../include/shared_protocol.h): Protocol structures
