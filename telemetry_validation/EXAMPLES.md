# Usage Examples

This document provides practical examples for common use cases of the Telemetry Validation System.

## Table of Contents

- [Basic Usage](#basic-usage)
- [Connection Examples](#connection-examples)
- [Validation Examples](#validation-examples)
- [Logging Examples](#logging-examples)
- [Monitoring Examples](#monitoring-examples)
- [Analysis Examples](#analysis-examples)
- [Advanced Examples](#advanced-examples)

## Basic Usage

### Monitor Serial Port

Monitor telemetry from a serial port with default settings:

```bash
python main.py --connection-type serial --port /dev/ttyUSB0 --baudrate 115200
```

### Monitor UDP Port

Monitor telemetry from UDP (e.g., from QGroundControl):

```bash
python main.py --connection-type udp --port 14550
```

### Use Configuration File

Use a configuration file for all settings:

```bash
python main.py --config config/config.json
```

## Connection Examples

### Serial Connection with Custom Baud Rate

```bash
# 57600 baud
python main.py --connection-type serial --port /dev/ttyUSB0 --baudrate 57600

# 9600 baud
python main.py --connection-type serial --port /dev/ttyUSB0 --baudrate 9600
```

### Serial Connection on Different Platforms

**Linux**:
```bash
# USB serial adapter
python main.py --connection-type serial --port /dev/ttyUSB0 --baudrate 115200

# Built-in serial port
python main.py --connection-type serial --port /dev/ttyS0 --baudrate 115200

# USB modem
python main.py --connection-type serial --port /dev/ttyACM0 --baudrate 115200
```

**macOS**:
```bash
# USB serial adapter
python main.py --connection-type serial --port /dev/cu.usbserial-1420 --baudrate 115200

# USB modem
python main.py --connection-type serial --port /dev/cu.usbmodem14201 --baudrate 115200
```

**Windows**:
```cmd
# COM port
python main.py --connection-type serial --port COM3 --baudrate 115200
```

### UDP Connection with Custom Port

```bash
# Custom UDP port
python main.py --connection-type udp --port 14551

# Bind to specific interface
python main.py --connection-type udp --host 192.168.1.100 --port 14550
```

### Protocol Mode Selection

```bash
# Binary protocol (default)
python main.py --connection-type serial --port /dev/ttyUSB0 --protocol-mode binary

# Raw MAVLink (no binary protocol wrapper)
python main.py --connection-type serial --port /dev/ttyUSB0 --protocol-mode mavlink
```

## Validation Examples

### Enable Validation with Custom Rules

```bash
# Use custom validation rules file
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --validation-rules config/my_rules.json
```

### Disable Validation

```bash
# Run without validation
python main.py --connection-type serial --port /dev/ttyUSB0 --no-validation
```

### Custom Validation Rules

Create `config/my_rules.json`:

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
      "name": "GPS Fix Lost",
      "msg_type": "GPS_RAW_INT",
      "field": "fix_type",
      "operator": "<",
      "threshold": 2,
      "severity": "CRITICAL",
      "description": "GPS fix type below 2D"
    }
  ]
}
```

Run with custom rules:

```bash
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --validation-rules config/my_rules.json
```

## Logging Examples

### Enable Specific Log Formats

```bash
# CSV only
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --log-csv --no-log-json --no-log-tlog --no-log-binlog

# CSV and .tlog
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --log-csv --log-tlog

# All formats
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --log-csv --log-json --log-tlog --log-binlog
```

### Custom Log Directory

```bash
# Specify log directory
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --log-dir /path/to/logs

# Use date-based directory
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --log-dir logs/$(date +%Y%m%d)
```

### File Rotation Settings

```bash
# Rotate at 50 MB
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --max-file-size 50

# Disable rotation
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --no-rotate-files
```

## Monitoring Examples

### Real-time Console Monitoring

```bash
# Enable serial monitor output
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --enable-serial-monitor

# Disable serial monitor
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --no-serial-monitor
```

### Visualization

```bash
# Enable real-time visualization
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --enable-visualization

# Disable visualization
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --no-visualization

# Custom update rate (0.5 Hz)
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --enable-visualization --viz-update-rate 0.5
```

### Filter by System ID

```bash
# Monitor only system ID 1
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --filter-system-id 1

# Monitor multiple system IDs
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --filter-system-id 1,2,3
```

## Analysis Examples

### Generate Summary Report

```bash
# Generate report after session
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --generate-report

# Specify report output file
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --generate-report --report-file report.html
```

### Query Historical Logs

```python
from src.report_generator import ReportGenerator

# Load log file
generator = ReportGenerator()
generator.load_csv('telemetry_logs/telemetry_20241026_120000.csv')

# Query by time range
messages = generator.query_by_time_range(
    start_time=1698336000.0,
    end_time=1698339600.0
)

# Query by message type
heartbeats = generator.query_by_message_type('HEARTBEAT')

# Query by system ID
drone1_msgs = generator.query_by_system_id(1)

# Generate summary
summary = generator.generate_summary()
print(summary)
```

### Export Data

```python
from src.report_generator import ReportGenerator

generator = ReportGenerator()
generator.load_csv('telemetry_logs/telemetry_20241026_120000.csv')

# Export to JSON
generator.export_json('output.json')

# Export to .tlog
generator.export_tlog('output.tlog')

# Export filtered data
messages = generator.query_by_time_range(start_time, end_time)
generator.export_csv('filtered.csv', messages)
```

## Advanced Examples

### Multi-Drone Monitoring

Monitor multiple drones simultaneously:

```bash
python main.py --connection-type udp --port 14550 \
  --enable-visualization \
  --filter-system-id 1,2,3,4
```

Configuration for multi-drone:

```json
{
  "visualization": {
    "enabled": true,
    "max_drones": 4,
    "drone_colors": ["red", "blue", "green", "orange"],
    "separate_graphs": true
  }
}
```

### Mode Comparison

Compare direct mode vs relay mode performance:

```bash
# Run during flight with mode changes
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --enable-mode-tracking \
  --generate-report
```

After flight, analyze mode comparison:

```python
from src.mode_comparison import ModeComparison

comparison = ModeComparison()
comparison.load_from_file('telemetry_logs/telemetry_20241026_120000.csv')

# Get mode-specific metrics
direct_metrics = comparison.get_mode_metrics('direct')
relay_metrics = comparison.get_mode_metrics('relay')

# Calculate differences
differences = comparison.calculate_differences()
print(f"Latency increase in relay mode: {differences['latency_diff']:.1f}%")
print(f"Packet rate change: {differences['packet_rate_diff']:.1f}%")

# Generate comparison report
report = comparison.generate_report()
print(report)
```

### Custom Alert Configuration

Configure alerts with email notifications:

```json
{
  "alerts": {
    "enabled": true,
    "channels": ["console", "email"],
    "throttle_seconds": 60,
    "max_alerts_per_minute": 10,
    "email": {
      "server": "smtp.gmail.com",
      "port": 587,
      "username": "your-email@gmail.com",
      "password": "your-app-password",
      "from": "your-email@gmail.com",
      "to": "recipient@example.com"
    }
  }
}
```

Run with email alerts:

```bash
python main.py --config config/config.json
```

### Binary Protocol Debugging

Debug binary protocol parsing issues:

```bash
# Enable debug logging
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --log-level DEBUG \
  --log-binlog

# Log raw binary packets
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --log-binlog --binlog-file debug.binlog
```

Analyze logged packets:

```python
from src.binary_protocol_parser import BinaryProtocolParser

# Load and replay packets
parser = BinaryProtocolParser(debug=True)

with open('debug.binlog', 'rb') as f:
    data = f.read()
    packets = parser.parse_stream(data)
    
    for packet in packets:
        print(f"Command: {packet.command}")
        print(f"Checksum Valid: {packet.checksum_valid}")
        print(f"Payload: {packet.payload}")
        print()

# Get statistics
stats = parser.get_stats()
print(f"Success rate: {stats['success_rate']:.1f}%")
print(f"Checksum errors: {stats['checksum_errors']}")
```

### Performance Optimization

Optimize for low-resource systems (e.g., Raspberry Pi):

```json
{
  "logging": {
    "csv": true,
    "json": false,
    "tlog": false,
    "binlog": false,
    "buffer_size": 1000,
    "buffer_flush_interval_s": 10
  },
  "visualization": {
    "enabled": false
  },
  "metrics": {
    "window_1s_size": 100,
    "window_10s_size": 1000,
    "window_60s_size": 6000
  },
  "validation": {
    "enabled": true,
    "max_violations": 1000
  }
}
```

Run with optimized settings:

```bash
python main.py --config config/optimized.json
```

### Automated Testing

Run automated validation tests:

```bash
# Test connection
python validate_connection_manager.py

# Test binary protocol parser
python validate_binary_protocol_parser.py

# Test validation engine
python validate_validation_engine.py

# Test all components
python validate_all.py
```

### Integration with External Tools

**Export to QGroundControl**:

```bash
# Generate .tlog file
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --log-tlog --tlog-file flight.tlog

# Open in QGC
qgroundcontrol --log flight.tlog
```

**Export to MAVProxy**:

```bash
# Generate .tlog file
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --log-tlog --tlog-file flight.tlog

# Replay in MAVProxy
mavproxy.py --master=flight.tlog
```

**Export to CSV for Excel/Python**:

```bash
# Generate CSV
python main.py --connection-type serial --port /dev/ttyUSB0 \
  --log-csv --csv-file telemetry.csv

# Analyze in Python
import pandas as pd
df = pd.read_csv('telemetry.csv')
print(df.describe())
```

### Continuous Monitoring

Run as background service:

**Linux (systemd)**:

Create `/etc/systemd/system/telemetry-validation.service`:

```ini
[Unit]
Description=Telemetry Validation System
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/telemetry_validation
ExecStart=/usr/bin/python3 main.py --config config/config.json
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable telemetry-validation
sudo systemctl start telemetry-validation
sudo systemctl status telemetry-validation
```

**Using screen (Linux/macOS)**:

```bash
# Start in screen session
screen -S telemetry
python main.py --config config/config.json

# Detach: Ctrl+A, D
# Reattach: screen -r telemetry
```

**Using tmux (Linux/macOS)**:

```bash
# Start in tmux session
tmux new -s telemetry
python main.py --config config/config.json

# Detach: Ctrl+B, D
# Reattach: tmux attach -t telemetry
```

## Component Examples

For detailed component-specific examples, see:

- [examples/connection_manager_example.py](examples/connection_manager_example.py)
- [examples/binary_protocol_parser_example.py](examples/binary_protocol_parser_example.py)
- [examples/mavlink_parser_example.py](examples/mavlink_parser_example.py)
- [examples/telemetry_logger_example.py](examples/telemetry_logger_example.py)
- [examples/validation_engine_example.py](examples/validation_engine_example.py)
- [examples/metrics_calculator_example.py](examples/metrics_calculator_example.py)
- [examples/alert_manager_example.py](examples/alert_manager_example.py)
- [examples/serial_monitor_example.py](examples/serial_monitor_example.py)
- [examples/mode_tracking_example.py](examples/mode_tracking_example.py)
- [examples/report_generator_example.py](examples/report_generator_example.py)
- [examples/visualizer_example.py](examples/visualizer_example.py)

## See Also

- [README.md](README.md) - Main documentation
- [USAGE.md](USAGE.md) - Complete usage guide
- [VALIDATION_RULES.md](VALIDATION_RULES.md) - Validation rule reference
- [BINARY_PROTOCOL.md](BINARY_PROTOCOL.md) - Binary protocol specification
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Troubleshooting guide
- [config/README.md](config/README.md) - Configuration reference
