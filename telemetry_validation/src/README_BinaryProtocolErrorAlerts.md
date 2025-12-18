# Binary Protocol Error Alerts

## Overview

The Binary Protocol Error Alerts feature provides automated monitoring and alerting for communication errors in the custom binary UART protocol used between the Primary and Secondary controllers. This feature helps detect and diagnose UART communication issues before they impact system reliability.

## Features

### 1. Checksum Error Rate Monitoring

Monitors the rate of Fletcher-16 checksum validation failures and generates alerts when the error rate exceeds a configurable threshold.

**Default Threshold**: 50 errors per minute

**Alert Severity**: WARNING

**Use Case**: High checksum error rates indicate:
- Electrical noise on UART lines
- Baud rate mismatch
- Cable quality issues
- EMI interference

### 2. Buffer Overflow Detection

Detects when the UART receive buffer overflows, indicating that data is arriving faster than it can be processed.

**Threshold**: Any overflow event triggers an alert

**Alert Severity**: CRITICAL

**Use Case**: Buffer overflows indicate:
- Processing bottleneck
- Insufficient buffer size
- Burst traffic exceeding capacity
- System resource constraints

### 3. Communication Timeout Detection

Monitors for communication timeouts when incomplete packets are not completed within the expected timeframe.

**Threshold**: Any timeout event triggers an alert

**Alert Severity**: WARNING

**Use Case**: Timeouts indicate:
- Intermittent connection issues
- Partial packet transmission
- Hardware communication problems
- Cable disconnection

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Binary Protocol Parser                      │
│  - Tracks checksum errors                                   │
│  - Tracks buffer overflows                                  │
│  - Tracks timeout events                                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                  Metrics Calculator                          │
│  - Calculates checksum error rate (errors/min)             │
│  - Accumulates buffer overflow count                        │
│  - Accumulates timeout error count                          │
│  - Exposes metrics in TelemetryMetrics                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                    Alert Manager                             │
│  - check_binary_protocol_errors()                           │
│  - Compares metrics against thresholds                      │
│  - Generates BinaryProtocolErrorAlert objects               │
│  - Applies throttling to prevent alert spam                 │
└─────────────────────────────────────────────────────────────┘
```

## Usage

### Basic Usage

```python
from alert_manager import AlertManager, AlertChannel
from metrics_calculator import MetricsCalculator

# Create alert manager with custom threshold
config = {
    'channels': [AlertChannel.CONSOLE],
    'checksum_error_threshold': 50.0  # errors per minute
}
alert_manager = AlertManager(config)

# Create metrics calculator
metrics_calc = MetricsCalculator()

# In your main loop, record errors as they occur
# (typically done by the binary protocol parser)
metrics_calc.record_checksum_error()
metrics_calc.record_buffer_overflow()
metrics_calc.record_timeout_error()

# Get current metrics
metrics = metrics_calc.get_metrics()

# Check for binary protocol errors and generate alerts
alerts = alert_manager.check_binary_protocol_errors(
    metrics,
    system_id=1
)

# alerts is a list of booleans: [checksum_alert, buffer_overflow_alert, timeout_alert]
if any(alerts):
    print(f"Generated {sum(alerts)} binary protocol error alerts")
```

### Integration with Binary Protocol Parser

```python
from binary_protocol_parser import BinaryProtocolParser
from metrics_calculator import MetricsCalculator
from alert_manager import AlertManager

# Create components
parser = BinaryProtocolParser()
metrics_calc = MetricsCalculator()
alert_manager = AlertManager()

# Parse incoming data
data = serial_port.read(1024)
packets = parser.parse_stream(data)

# Get parser statistics
parser_stats = parser.get_stats()

# Record errors in metrics calculator
for _ in range(parser_stats['checksum_errors']):
    metrics_calc.record_checksum_error()

for _ in range(parser_stats['buffer_overflow']):
    metrics_calc.record_buffer_overflow()

for _ in range(parser_stats['timeout_errors']):
    metrics_calc.record_timeout_error()

# Check for errors and generate alerts
metrics = metrics_calc.get_metrics()
alert_manager.check_binary_protocol_errors(metrics, system_id=1)
```

## Configuration

### Alert Manager Configuration

```python
config = {
    # Alert channels
    'channels': [AlertChannel.CONSOLE, AlertChannel.EMAIL],
    
    # Checksum error threshold (errors per minute)
    'checksum_error_threshold': 50.0,
    
    # Throttling settings
    'throttle_window': 60,  # seconds
    'duplicate_window': 300,  # seconds
    'max_alerts_per_window': 10,
    
    # Email configuration (for CRITICAL alerts)
    'email': {
        'server': 'smtp.gmail.com',
        'port': 587,
        'username': 'your_email@gmail.com',
        'password': 'your_password',
        'from': 'alerts@yourdomain.com',
        'to': 'operator@yourdomain.com'
    }
}

alert_manager = AlertManager(config)
```

## Alert Throttling

To prevent alert spam, the system implements intelligent throttling:

### Checksum Error Alerts
- **Throttle Window**: 60 seconds
- **Behavior**: Only one alert per system per minute

### Buffer Overflow Alerts
- **Throttle Window**: 300 seconds (5 minutes)
- **Behavior**: Only one alert per system per 5 minutes
- **Severity**: CRITICAL (may trigger email alerts)

### Timeout Alerts
- **Throttle Window**: 120 seconds (2 minutes)
- **Behavior**: Only one alert per system per 2 minutes

## Alert Format

### Console Output

```
⚠ ALERT: [WARNING] [System 1] Binary Protocol Checksum Error: checksum = 75.0 (threshold: 50.0) - Checksum error rate 75.0/min exceeds threshold 50.0/min

⚠ ALERT: [CRITICAL] [System 1] Binary Protocol Buffer Overflow Error: buffer_overflow = 3.0 (threshold: 0.0) - UART buffer overflow detected (3 events)

⚠ ALERT: [WARNING] [System 1] Binary Protocol Timeout Error: timeout = 5.0 (threshold: 0.0) - Communication timeout detected (5 events)
```

### Alert History

```python
# Get alert history
history = alert_manager.get_alert_history(
    severity=Severity.CRITICAL,
    system_id=1,
    limit=10
)

for timestamp, message, severity, rule_name, system_id in history:
    print(f"{timestamp}: {message}")
```

## Statistics

### Alert Statistics

```python
stats = alert_manager.get_stats()

print(f"Total alerts: {stats['total_alerts']}")
print(f"Binary protocol error alerts: {stats['binary_protocol_error_alerts']}")
print(f"Filtered duplicates: {stats['filtered_duplicates']}")
print(f"Throttled alerts: {stats['throttled_alerts']}")
```

### Metrics Statistics

```python
metrics = metrics_calc.get_metrics()

print(f"Checksum error rate: {metrics.checksum_error_rate:.1f}/min")
print(f"Buffer overflow count: {metrics.buffer_overflow_count}")
print(f"Timeout error count: {metrics.timeout_error_count}")
print(f"Protocol success rate: {metrics.protocol_success_rate:.1f}%")
```

## Troubleshooting

### High Checksum Error Rate

**Symptoms**: Frequent checksum error alerts

**Possible Causes**:
1. Electrical noise on UART lines
2. Baud rate mismatch between controllers
3. Poor quality or damaged cables
4. EMI from nearby electronics

**Solutions**:
1. Verify baud rate configuration matches on both ends
2. Use shielded cables for UART connections
3. Add ferrite beads to reduce EMI
4. Check for loose connections
5. Reduce cable length if possible

### Buffer Overflow

**Symptoms**: CRITICAL buffer overflow alerts

**Possible Causes**:
1. Processing bottleneck in main loop
2. Burst traffic exceeding buffer capacity
3. Insufficient buffer size
4. Blocking operations in packet handler

**Solutions**:
1. Increase buffer size in BinaryProtocolParser
2. Optimize packet processing code
3. Use non-blocking I/O operations
4. Implement flow control if possible
5. Reduce packet transmission rate

### Communication Timeouts

**Symptoms**: Frequent timeout alerts

**Possible Causes**:
1. Intermittent connection issues
2. Partial packet transmission
3. Hardware communication problems
4. Cable disconnection

**Solutions**:
1. Check physical connections
2. Verify power supply stability
3. Test with different cables
4. Check for loose connectors
5. Monitor for environmental factors (vibration, temperature)

## Testing

Run the test suite to verify binary protocol error alerts:

```bash
python telemetry_validation/test_binary_protocol_error_alerts.py
```

The test suite validates:
1. Checksum error rate alerts
2. Buffer overflow alerts
3. Communication timeout alerts
4. Multiple simultaneous errors
5. MetricsCalculator integration

## Requirements Satisfied

- **Requirement 3.2**: Binary protocol health metrics tracking
- **Requirement 9.2**: Alert on degraded UART communication

## Related Documentation

- [Binary Protocol Specification](../../include/README_BinaryProtocol.md)
- [Alert Manager](README_AlertManager.md)
- [Metrics Calculator](README_MetricsCalculator.md)
- [Binary Protocol Parser](README_BinaryProtocolParser.md)
