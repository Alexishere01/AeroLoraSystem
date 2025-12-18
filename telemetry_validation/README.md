# Telemetry Validation System

Automated telemetry validation system for the dual-controller LoRa relay system. This system provides comprehensive monitoring, logging, validation, and visualization of MAVLink telemetry data transmitted through a custom binary UART protocol.

## Overview

The Telemetry Validation System is a standalone Python application that connects to the Ground Control Station (or directly to the LoRa bridge) to capture, log, validate, and visualize MAVLink telemetry data in real-time. The system runs on a separate computer to avoid impacting drone operations and provides comprehensive telemetry analysis capabilities.

### Key Features

- **Binary Protocol Support**: Parse custom binary UART protocol with Fletcher-16 checksum validation
- **MAVLink Extraction**: Extract and decode MAVLink messages from binary protocol packets
- **Real-time Telemetry Logging**: Capture all packets to CSV, JSON, .tlog, and .binlog formats
- **Automated Validation**: Apply custom validation rules to detect anomalies and issues
- **Metrics Calculation**: Track packet rate, RSSI, SNR, latency, drop rate, and protocol health
- **Alert System**: Console, email alerts for critical issues with throttling and filtering
- **Real-time Visualization**: Live graphs of key telemetry metrics with violation highlighting
- **Multi-Drone Support**: Track up to 4 drones simultaneously with color-coded graphs
- **Mode Tracking**: Detect and compare direct vs relay mode performance
- **Historical Analysis**: Load and analyze data from log files with query tools

## Quick Start

### Installation

1. **Prerequisites**
   - Python 3.8 or higher
   - pip package manager

2. **Install Dependencies**
   ```bash
   cd telemetry_validation
   pip install -r requirements.txt
   ```

3. **Install Package** (optional)
   ```bash
   pip install -e .
   ```

For detailed installation instructions, see [INSTALLATION.md](INSTALLATION.md).

### Basic Usage

**Monitor serial port with binary protocol:**
```bash
python main.py --connection-type serial --port /dev/ttyUSB0 --baudrate 115200
```

**Monitor UDP with raw MAVLink:**
```bash
python main.py --connection-type udp --port 14550 --protocol-mode mavlink
```

**Use configuration file:**
```bash
python main.py --config config/config.json
```

See [USAGE.md](USAGE.md) for detailed usage instructions and examples.

## Documentation

For a complete index of all documentation, see [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md).

### User Documentation
- **[INSTALLATION.md](INSTALLATION.md)** - Installation guide for all platforms
- **[USAGE.md](USAGE.md)** - Complete usage guide with command-line options and examples
- **[EXAMPLES.md](EXAMPLES.md)** - Practical examples for common use cases
- **[config/README.md](config/README.md)** - Configuration file reference and examples
- **[VALIDATION_RULES.md](VALIDATION_RULES.md)** - Validation rule syntax and examples
- **[BINARY_PROTOCOL.md](BINARY_PROTOCOL.md)** - Binary protocol specification and parsing
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and solutions

### Component Documentation
- **[src/README_ConnectionManager.md](src/README_ConnectionManager.md)** - Connection management
- **[src/README_BinaryProtocolParser.md](src/README_BinaryProtocolParser.md)** - Binary protocol parsing
- **[src/README_MAVLinkParser.md](src/README_MAVLinkParser.md)** - MAVLink parsing
- **[src/README_TelemetryLogger.md](src/README_TelemetryLogger.md)** - Telemetry logging
- **[src/README_ValidationEngine.md](src/README_ValidationEngine.md)** - Validation engine
- **[src/README_MetricsCalculator.md](src/README_MetricsCalculator.md)** - Metrics calculation
- **[src/README_AlertManager.md](src/README_AlertManager.md)** - Alert management
- **[src/README_SerialMonitor.md](src/README_SerialMonitor.md)** - Serial monitoring
- **[src/README_ModeTracking.md](src/README_ModeTracking.md)** - Mode tracking
- **[src/README_ReportGenerator.md](src/README_ReportGenerator.md)** - Report generation
- **[src/README_Visualizer.md](src/README_Visualizer.md)** - Real-time visualization

### Examples
- **[examples/](examples/)** - Example scripts for each component

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Ground Control Station                        │
│                    (Heltec V3 @ 915 MHz)                        │
└────────────────────────────┬────────────────────────────────────┘
                             │ Serial/USB or UDP
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│              Telemetry Validation System (Python)                │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Binary      │→ │  MAVLink     │→ │  Telemetry   │          │
│  │  Protocol    │  │  Parser      │  │  Logger      │          │
│  │  Parser      │  └──────────────┘  └──────────────┘          │
│  └──────────────┘         ↓                  ↓                   │
│         ↓          ┌──────────────┐  ┌──────────────┐          │
│  ┌──────────────┐  │  Validation  │  │  Metrics     │          │
│  │  Protocol    │  │  Engine      │  │  Calculator  │          │
│  │  Health      │  └──────────────┘  └──────────────┘          │
│  └──────────────┘         ↓                  ↓                   │
│         ↓          ┌──────────────┐  ┌──────────────┐          │
│  ┌──────────────┐  │  Alert       │  │  Mode        │          │
│  │  Serial      │  │  Manager     │  │  Tracker     │          │
│  │  Monitor     │  └──────────────┘  └──────────────┘          │
│  └──────────────┘         ↓                  ↓                   │
│         ↓          ┌──────────────┐  ┌──────────────┐          │
│  ┌──────────────┐  │  Real-time   │  │  Report      │          │
│  │  Visualizer  │  │  Visualizer  │  │  Generator   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

## Features in Detail

### Binary Protocol Support

The system parses the custom binary UART protocol used between Primary and Secondary controllers:

- **Fletcher-16 Checksum Validation**: Detects corrupted packets
- **State Machine Parser**: Robust parsing with error recovery
- **MAVLink Extraction**: Extracts embedded MAVLink from BridgePayload structures
- **RSSI/SNR Metadata**: Tracks signal quality from binary protocol
- **Protocol Health Monitoring**: Tracks checksum errors, parse errors, timeouts
- **Multiple Command Types**: Supports INIT, BRIDGE_TX/RX, STATUS_REPORT, RELAY commands

See [BINARY_PROTOCOL.md](BINARY_PROTOCOL.md) for detailed protocol specification.

### Telemetry Logging

Multi-format logging with automatic file rotation:

- **CSV Format**: Human-readable with decoded message fields
- **JSON Format**: Structured data for programmatic analysis
- **.tlog Format**: Binary MAVLink log compatible with QGC and MAVProxy
- **.binlog Format**: Raw binary protocol packets for debugging and replay
- **Automatic Rotation**: Rotate files at configurable size limit (default: 100 MB)
- **Buffered Writes**: Minimize I/O overhead with configurable buffer size

### Validation Engine

Flexible rule-based validation with built-in anomaly detection:

- **Custom Rules**: Define rules in JSON with multiple operators and severity levels
- **GPS Jump Detection**: Detect altitude changes >50m in 1 second
- **Packet Loss Detection**: Track sequence number gaps
- **Battery Monitoring**: Alert on low voltage
- **Signal Quality**: Monitor RSSI/SNR thresholds
- **Runtime Reload**: Update rules without restarting

See [VALIDATION_RULES.md](VALIDATION_RULES.md) for rule syntax and examples.

### Metrics Calculation

Comprehensive metrics with rolling time windows:

- **Packet Rates**: 1s, 10s, 60s rolling windows
- **RSSI/SNR Averaging**: Track signal quality trends
- **Packet Loss Rate**: Calculate from sequence number gaps
- **Command Latency**: Track COMMAND_LONG → COMMAND_ACK timing
- **Message Distribution**: Count messages by type
- **Protocol Health**: Checksum error rate, parse error rate, success rate

### Alert System

Multi-channel alerts with intelligent filtering:

- **Console Alerts**: Color-coded output (INFO=blue, WARNING=yellow, CRITICAL=red)
- **Email Alerts**: SMTP support for critical issues
- **Alert Throttling**: Prevent duplicate alerts within time window
- **Rate Limiting**: Maximum alerts per minute
- **Relay Latency Alerts**: Alert if relay latency exceeds threshold
- **Protocol Error Alerts**: Alert on high checksum error rate or buffer overflow

### Mode Tracking

Automatic detection and comparison of operating modes:

- **Mode Detection**: Detect relay mode from CMD_STATUS_REPORT
- **Mode-Specific Metrics**: Separate metrics for direct and relay modes
- **Relay Latency Measurement**: Track additional latency in relay mode
- **Mode Comparison**: Calculate percentage differences between modes
- **Transition Logging**: Log mode changes with timestamps

### Real-time Visualization

Live graphs with multi-drone support:

- **Multiple Graphs**: RSSI, SNR, packet rate, battery voltage, altitude, protocol health
- **Violation Highlighting**: Red markers when validation rules violated
- **Multi-Drone Support**: Up to 4 drones with color-coded graphs
- **Historical Data**: Load and display data from log files
- **Configurable Update Rate**: 1 Hz default for optimal performance

## Configuration

The system is configured through two JSON files:

### config/config.json

Main system configuration:
- Connection settings (serial/UDP)
- Protocol settings (binary/mavlink)
- Logging settings (formats, rotation)
- Validation settings (rules file, built-in rules)
- Alert settings (channels, throttling)
- Visualization settings (graphs, update rate)
- Metrics settings (rolling windows)
- Mode tracking settings

See [config/README.md](config/README.md) for complete reference.

### config/validation_rules.json

Validation rules:
- Rule name and description
- MAVLink message type
- Field to validate
- Comparison operator (<, >, ==, !=, <=, >=)
- Threshold value
- Severity level (INFO, WARNING, CRITICAL)

See [VALIDATION_RULES.md](VALIDATION_RULES.md) for syntax and examples.

## Project Structure

```
telemetry_validation/
├── main.py                         # Main application entry point
├── setup.py                        # Package installation
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── USAGE.md                        # Usage guide
├── VALIDATION_RULES.md             # Validation rule reference
├── BINARY_PROTOCOL.md              # Binary protocol specification
├── TROUBLESHOOTING.md              # Troubleshooting guide
│
├── src/                            # Source code
│   ├── __init__.py
│   ├── connection_manager.py      # Connection management
│   ├── binary_protocol_parser.py  # Binary protocol parsing
│   ├── mavlink_parser.py          # MAVLink parsing
│   ├── telemetry_logger.py        # Telemetry logging
│   ├── validation_engine.py       # Validation engine
│   ├── metrics_calculator.py      # Metrics calculation
│   ├── alert_manager.py           # Alert management
│   ├── serial_monitor.py          # Serial monitoring
│   ├── mode_tracker.py            # Mode tracking
│   ├── mode_specific_metrics.py   # Mode-specific metrics
│   ├── mode_comparison.py         # Mode comparison
│   ├── report_generator.py        # Report generation
│   ├── visualizer.py              # Real-time visualization
│   └── README_*.md                # Component documentation
│
├── config/                         # Configuration files
│   ├── config.json                # Main configuration
│   ├── validation_rules.json      # Validation rules
│   ├── README.md                  # Configuration reference
│   └── BINARY_PROTOCOL.md         # Protocol packet structure
│
├── examples/                       # Example scripts
│   ├── connection_manager_example.py
│   ├── binary_protocol_parser_example.py
│   ├── mavlink_parser_example.py
│   ├── telemetry_logger_example.py
│   ├── validation_engine_example.py
│   ├── metrics_calculator_example.py
│   ├── alert_manager_example.py
│   ├── serial_monitor_example.py
│   ├── mode_tracking_example.py
│   ├── report_generator_example.py
│   └── visualizer_example.py
│
├── tests/                          # Unit tests
│   ├── test_connection_manager.py
│   ├── test_mavlink_parser.py
│   ├── test_telemetry_logger.py
│   ├── test_validation_engine.py
│   ├── test_metrics_calculator.py
│   ├── test_alert_manager.py
│   ├── test_serial_monitor.py
│   ├── test_mode_tracker.py
│   ├── test_report_generator.py
│   └── test_visualizer.py
│
└── validate_*.py                   # Validation scripts
```

## Development

### Running Tests

Run all unit tests:
```bash
python -m pytest tests/
```

Run specific test:
```bash
python tests/test_validation_engine.py
```

Run validation scripts:
```bash
python validate_connection_manager.py
python validate_binary_protocol_parser.py
python validate_validation_engine.py
```

### Adding Validation Rules

1. Edit `config/validation_rules.json`
2. Add new rule with required fields
3. Reload configuration (or restart system)

Example:
```json
{
  "name": "Custom Rule",
  "msg_type": "SYS_STATUS",
  "field": "voltage_battery",
  "operator": "<",
  "threshold": 10500,
  "severity": "WARNING",
  "description": "Battery voltage below 10.5V"
}
```

### Extending the System

To add new features:

1. Create new module in `src/`
2. Add component documentation in `src/README_*.md`
3. Create example script in `examples/`
4. Add unit tests in `tests/`
5. Update main.py to integrate component

## Requirements

- Python 3.8+
- pymavlink (MAVLink parsing)
- pyserial (Serial communication)
- matplotlib (Visualization)
- numpy (Numerical operations)

Install all dependencies:
```bash
pip install -r requirements.txt
```

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues and solutions:

- Connection issues (serial port, UDP)
- No data received
- Validation false positives
- Performance issues (CPU, memory)
- Binary protocol parsing errors
- Checksum validation failures

## License

Copyright (c) 2024 AeroLoRa Team

## See Also

- [USAGE.md](USAGE.md) - Complete usage guide
- [VALIDATION_RULES.md](VALIDATION_RULES.md) - Validation rule reference
- [BINARY_PROTOCOL.md](BINARY_PROTOCOL.md) - Binary protocol specification
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Troubleshooting guide
- [config/README.md](config/README.md) - Configuration reference
- [../include/BinaryProtocol.h](../include/BinaryProtocol.h) - C++ binary protocol implementation
- [../include/shared_protocol.h](../include/shared_protocol.h) - Protocol structures
