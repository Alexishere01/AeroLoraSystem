# Documentation Index

Complete index of all documentation for the Telemetry Validation System.

## Quick Links

- **Getting Started**: [INSTALLATION.md](INSTALLATION.md) → [USAGE.md](USAGE.md) → [EXAMPLES.md](EXAMPLES.md)
- **Configuration**: [config/README.md](config/README.md) → [VALIDATION_RULES.md](VALIDATION_RULES.md)
- **Protocol**: [BINARY_PROTOCOL.md](BINARY_PROTOCOL.md) → [src/README_BinaryProtocolParser.md](src/README_BinaryProtocolParser.md)
- **Help**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md) → [FIELD_TESTING_GUIDE.md](FIELD_TESTING_GUIDE.md)

## User Documentation

### Getting Started

| Document | Description | Audience |
|----------|-------------|----------|
| [README.md](README.md) | Main documentation and overview | All users |
| [INSTALLATION.md](INSTALLATION.md) | Installation guide for all platforms | New users |
| [USAGE.md](USAGE.md) | Complete usage guide with CLI options | All users |
| [EXAMPLES.md](EXAMPLES.md) | Practical examples for common use cases | All users |

### Configuration

| Document | Description | Audience |
|----------|-------------|----------|
| [config/README.md](config/README.md) | Configuration file reference | All users |
| [VALIDATION_RULES.md](VALIDATION_RULES.md) | Validation rule syntax and examples | Users creating rules |
| [config/validation_rules.json](config/validation_rules.json) | Example validation rules | All users |
| [config/config.json](config/config.json) | Example configuration | All users |

### Protocol Documentation

| Document | Description | Audience |
|----------|-------------|----------|
| [BINARY_PROTOCOL.md](BINARY_PROTOCOL.md) | Binary protocol specification | Advanced users |
| [config/BINARY_PROTOCOL.md](config/BINARY_PROTOCOL.md) | Protocol packet structure reference | Advanced users |
| [VALIDATION_RULES.md](VALIDATION_RULES.md) | Validation rules (includes protocol info) | All users |

### Troubleshooting and Testing

| Document | Description | Audience |
|----------|-------------|----------|
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common issues and solutions | All users |
| [FIELD_TESTING_GUIDE.md](FIELD_TESTING_GUIDE.md) | Field testing procedures | Testers |
| [TEST_RESULTS_TEMPLATE.md](TEST_RESULTS_TEMPLATE.md) | Test results template | Testers |

## Component Documentation

### Core Components

| Component | Documentation | Example | Tests |
|-----------|---------------|---------|-------|
| Connection Manager | [src/README_ConnectionManager.md](src/README_ConnectionManager.md) | [examples/connection_manager_example.py](examples/connection_manager_example.py) | [tests/test_connection_manager.py](tests/test_connection_manager.py) |
| Binary Protocol Parser | [src/README_BinaryProtocolParser.md](src/README_BinaryProtocolParser.md) | [examples/binary_protocol_parser_example.py](examples/binary_protocol_parser_example.py) | [tests/test_binary_protocol_parser.py](tests/test_binary_protocol_parser.py) |
| MAVLink Parser | [src/README_MAVLinkParser.md](src/README_MAVLinkParser.md) | [examples/mavlink_parser_example.py](examples/mavlink_parser_example.py) | [tests/test_mavlink_parser.py](tests/test_mavlink_parser.py) |
| Telemetry Logger | [src/README_TelemetryLogger.md](src/README_TelemetryLogger.md) | [examples/telemetry_logger_example.py](examples/telemetry_logger_example.py) | [tests/test_telemetry_logger.py](tests/test_telemetry_logger.py) |
| Validation Engine | [src/README_ValidationEngine.md](src/README_ValidationEngine.md) | [examples/validation_engine_example.py](examples/validation_engine_example.py) | [tests/test_validation_engine.py](tests/test_validation_engine.py) |
| Metrics Calculator | [src/README_MetricsCalculator.md](src/README_MetricsCalculator.md) | [examples/metrics_calculator_example.py](examples/metrics_calculator_example.py) | [tests/test_metrics_calculator.py](tests/test_metrics_calculator.py) |

### Alert and Monitoring

| Component | Documentation | Example | Tests |
|-----------|---------------|---------|-------|
| Alert Manager | [src/README_AlertManager.md](src/README_AlertManager.md) | [examples/alert_manager_example.py](examples/alert_manager_example.py) | [tests/test_alert_manager.py](tests/test_alert_manager.py) |
| Serial Monitor | [src/README_SerialMonitor.md](src/README_SerialMonitor.md) | [examples/serial_monitor_example.py](examples/serial_monitor_example.py) | [tests/test_serial_monitor.py](tests/test_serial_monitor.py) |
| Visualizer | [src/README_Visualizer.md](src/README_Visualizer.md) | [examples/visualizer_example.py](examples/visualizer_example.py) | [tests/test_visualizer.py](tests/test_visualizer.py) |

### Analysis and Reporting

| Component | Documentation | Example | Tests |
|-----------|---------------|---------|-------|
| Mode Tracker | [src/README_ModeTracking.md](src/README_ModeTracking.md) | [examples/mode_tracking_example.py](examples/mode_tracking_example.py) | [tests/test_mode_tracker.py](tests/test_mode_tracker.py) |
| Report Generator | [src/README_ReportGenerator.md](src/README_ReportGenerator.md) | [examples/report_generator_example.py](examples/report_generator_example.py) | [tests/test_report_generator.py](tests/test_report_generator.py) |

### Feature-Specific Documentation

| Feature | Documentation | Example |
|---------|---------------|---------|
| Binary Packet Logging | [src/README_BinaryPacketLogging.md](src/README_BinaryPacketLogging.md) | [examples/binary_packet_logging_example.py](examples/binary_packet_logging_example.py) |
| Binary Protocol Error Alerts | [src/README_BinaryProtocolErrorAlerts.md](src/README_BinaryProtocolErrorAlerts.md) | [examples/binary_protocol_error_alerts_example.py](examples/binary_protocol_error_alerts_example.py) |
| Relay Latency Alerts | [src/README_RelayLatencyAlerts.md](src/README_RelayLatencyAlerts.md) | [examples/relay_latency_alert_example.py](examples/relay_latency_alert_example.py) |

## Developer Documentation

### Source Code

| File | Description |
|------|-------------|
| [main.py](main.py) | Main application entry point |
| [setup.py](setup.py) | Package installation script |
| [requirements.txt](requirements.txt) | Python dependencies |

### Source Modules

| Module | Description |
|--------|-------------|
| [src/connection_manager.py](src/connection_manager.py) | Connection management |
| [src/binary_protocol_parser.py](src/binary_protocol_parser.py) | Binary protocol parsing |
| [src/mavlink_parser.py](src/mavlink_parser.py) | MAVLink parsing |
| [src/telemetry_logger.py](src/telemetry_logger.py) | Telemetry logging |
| [src/validation_engine.py](src/validation_engine.py) | Validation engine |
| [src/metrics_calculator.py](src/metrics_calculator.py) | Metrics calculation |
| [src/alert_manager.py](src/alert_manager.py) | Alert management |
| [src/serial_monitor.py](src/serial_monitor.py) | Serial monitoring |
| [src/mode_tracker.py](src/mode_tracker.py) | Mode tracking |
| [src/mode_specific_metrics.py](src/mode_specific_metrics.py) | Mode-specific metrics |
| [src/mode_comparison.py](src/mode_comparison.py) | Mode comparison |
| [src/report_generator.py](src/report_generator.py) | Report generation |
| [src/visualizer.py](src/visualizer.py) | Real-time visualization |

### Testing

| Type | Files |
|------|-------|
| Unit Tests | [tests/test_*.py](tests/) |
| Validation Scripts | [validate_*.py](.) |
| Integration Tests | [tests/test_integration.py](tests/test_integration.py) |
| Field Testing | [FIELD_TESTING_GUIDE.md](FIELD_TESTING_GUIDE.md) |

## Task Completion Documentation

| Task | Completion Document |
|------|---------------------|
| Task 2 | [TASK_2_COMPLETE.md](TASK_2_COMPLETE.md) |
| Task 3 | [TASK_3_COMPLETE.md](TASK_3_COMPLETE.md) |
| Task 3.5 | [TASK_3_5_COMPLETE.md](TASK_3_5_COMPLETE.md) |
| Task 4.5 | [TASK_4_5_COMPLETE.md](TASK_4_5_COMPLETE.md) |
| Task 5 | [TASK_5_COMPLETE.md](TASK_5_COMPLETE.md) |
| Task 6 | [TASK_6_COMPLETE.md](TASK_6_COMPLETE.md) |
| Task 7.3 | [TASK_7_3_COMPLETE.md](TASK_7_3_COMPLETE.md) |
| Task 7.4 | [TASK_7_4_COMPLETE.md](TASK_7_4_COMPLETE.md) |
| Task 7.5 | [TASK_7_5_COMPLETE.md](TASK_7_5_COMPLETE.md) |
| Task 8 | [TASK_8_COMPLETE.md](TASK_8_COMPLETE.md) |
| Task 9 | [TASK_9_COMPLETE.md](TASK_9_COMPLETE.md) |
| Task 10 | [TASK_10_COMPLETE.md](TASK_10_COMPLETE.md) |
| Task 11 | [TASK_11_COMPLETE.md](TASK_11_COMPLETE.md) |
| Task 12 | [TASK_12_COMPLETE.md](TASK_12_COMPLETE.md) |
| Task 15 | [TASK_15_COMPLETE.md](TASK_15_COMPLETE.md) |

## Related Documentation

### C++ Implementation

| File | Description |
|------|-------------|
| [../include/BinaryProtocol.h](../include/BinaryProtocol.h) | C++ binary protocol implementation |
| [../include/shared_protocol.h](../include/shared_protocol.h) | Protocol structures |
| [../include/README_BinaryProtocol.md](../include/README_BinaryProtocol.md) | C++ documentation |

### Project Documentation

| File | Description |
|------|-------------|
| [../PROJECT_STATUS.md](../PROJECT_STATUS.md) | Overall project status |
| [../DUAL_CONTROLLER_CONTEXT.md](../DUAL_CONTROLLER_CONTEXT.md) | Dual-controller system context |

## Documentation by Use Case

### I want to install the system

1. [INSTALLATION.md](INSTALLATION.md) - Installation guide
2. [requirements.txt](requirements.txt) - Dependencies
3. [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Installation issues

### I want to start using the system

1. [USAGE.md](USAGE.md) - Usage guide
2. [EXAMPLES.md](EXAMPLES.md) - Practical examples
3. [config/README.md](config/README.md) - Configuration

### I want to create validation rules

1. [VALIDATION_RULES.md](VALIDATION_RULES.md) - Rule syntax
2. [config/validation_rules.json](config/validation_rules.json) - Example rules
3. [src/README_ValidationEngine.md](src/README_ValidationEngine.md) - Engine details

### I want to understand the binary protocol

1. [BINARY_PROTOCOL.md](BINARY_PROTOCOL.md) - Protocol specification
2. [src/README_BinaryProtocolParser.md](src/README_BinaryProtocolParser.md) - Parser details
3. [config/BINARY_PROTOCOL.md](config/BINARY_PROTOCOL.md) - Packet structure

### I want to troubleshoot issues

1. [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues
2. [USAGE.md](USAGE.md) - Usage guide
3. Component-specific README files in [src/](src/)

### I want to analyze telemetry data

1. [src/README_ReportGenerator.md](src/README_ReportGenerator.md) - Report generation
2. [src/README_MetricsCalculator.md](src/README_MetricsCalculator.md) - Metrics
3. [src/README_ModeTracking.md](src/README_ModeTracking.md) - Mode comparison

### I want to develop or extend the system

1. Component README files in [src/](src/)
2. Example scripts in [examples/](examples/)
3. Unit tests in [tests/](tests/)
4. [setup.py](setup.py) - Package structure

### I want to test the system

1. [FIELD_TESTING_GUIDE.md](FIELD_TESTING_GUIDE.md) - Field testing
2. [TEST_RESULTS_TEMPLATE.md](TEST_RESULTS_TEMPLATE.md) - Test template
3. [tests/](tests/) - Unit tests
4. [validate_*.py](.) - Validation scripts

## Documentation Standards

All documentation follows these standards:

- **Markdown Format**: All documentation in Markdown (.md)
- **Clear Structure**: Hierarchical organization with table of contents
- **Code Examples**: Practical, runnable examples
- **Cross-References**: Links to related documentation
- **Platform-Specific**: Instructions for Linux, macOS, Windows
- **Troubleshooting**: Common issues and solutions included

## Contributing to Documentation

When adding new features:

1. Update relevant component README in [src/](src/)
2. Add example script in [examples/](examples/)
3. Add unit tests in [tests/](tests/)
4. Update [USAGE.md](USAGE.md) if CLI changes
5. Update [EXAMPLES.md](EXAMPLES.md) with use cases
6. Update this index

## Getting Help

If you can't find what you need:

1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Search this documentation index
3. Review component-specific README files
4. Check example scripts
5. Enable debug logging: `python main.py --log-level DEBUG`

## Documentation Feedback

To improve documentation:

1. Report unclear sections
2. Suggest additional examples
3. Report errors or outdated information
4. Request new documentation topics
