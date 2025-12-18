# Relay Latency Alerts

## Overview

The Relay Latency Alert feature monitors relay mode operation and generates alerts when relay latency exceeds configured thresholds. This helps identify performance degradation in relay mode and ensures timely intervention when relay operations are experiencing delays.

**Requirements:** 9.5

## Features

- **Automatic Relay Mode Detection**: Detects relay mode activation/deactivation from `CMD_STATUS_REPORT` packets
- **Latency Monitoring**: Tracks relay latency using the `last_activity_sec` field from status reports
- **Configurable Threshold**: Default 500ms threshold, configurable via alert manager config
- **Alert Generation**: Generates WARNING severity alerts when latency exceeds threshold
- **Multi-System Support**: Tracks relay mode status independently for multiple systems
- **Alert Throttling**: Prevents alert spam using existing throttling infrastructure
- **Status Tracking**: Provides API to query current relay mode status

## Architecture

### Data Flow

```
CMD_STATUS_REPORT (Binary Protocol)
         ↓
   StatusPayload
         ↓
AlertManager.check_relay_latency()
         ↓
   Relay Mode Detection
         ↓
   Latency Calculation
         ↓
   Threshold Comparison
         ↓
   Alert Generation (if exceeded)
         ↓
   Alert Delivery (Console/Email)
```

### Components

1. **RelayLatencyAlert**: Dataclass representing a relay latency alert
2. **AlertManager.check_relay_latency()**: Method to check relay status and generate alerts
3. **AlertManager.get_relay_mode_status()**: Method to query current relay mode status
4. **Relay Mode Tracking**: Internal state tracking for relay mode per system

## Usage

### Basic Usage

```python
from alert_manager import AlertManager, AlertChannel
from binary_protocol_parser import BinaryProtocolParser, UartCommand

# Configure alert manager with relay latency threshold
config = {
    'channels': [AlertChannel.CONSOLE],
    'relay_latency_threshold_ms': 500.0,  # Alert if latency > 500ms
    'throttle_window': 60,
    'duplicate_window': 300
}

alert_manager = AlertManager(config)
parser = BinaryProtocolParser()

# Process incoming binary protocol packets
data = serial_port.read(1024)
packets = parser.parse_stream(data)

for packet in packets:
    # Check for status reports
    if packet.command == UartCommand.CMD_STATUS_REPORT:
        # Extract system ID from payload
        system_id = packet.payload.own_drone_sysid
        
        # Check relay latency and generate alerts if needed
        alert_manager.check_relay_latency(packet.payload, system_id)
```

### Querying Relay Mode Status

```python
# Get relay mode status for all systems
relay_status = alert_manager.get_relay_mode_status()
print(f"System 1 relay mode: {'ACTIVE' if relay_status.get(1) else 'INACTIVE'}")

# Get relay mode status for specific system
system1_status = alert_manager.get_relay_mode_status(system_id=1)
print(f"System 1: {system1_status}")
```

### Accessing Statistics

```python
# Get alert statistics
stats = alert_manager.get_stats()
print(f"Total relay latency alerts: {stats['relay_latency_alerts']}")
print(f"Total alerts: {stats['total_alerts']}")
```

## Configuration

### Alert Manager Configuration

```python
config = {
    # Alert delivery channels
    'channels': [AlertChannel.CONSOLE, AlertChannel.EMAIL],
    
    # Relay latency threshold in milliseconds (default: 500ms)
    'relay_latency_threshold_ms': 500.0,
    
    # Throttle window in seconds (default: 60s)
    'throttle_window': 60,
    
    # Duplicate prevention window in seconds (default: 300s)
    'duplicate_window': 300,
    
    # Maximum alerts per throttle window (default: 10)
    'max_alerts_per_window': 10,
    
    # Email configuration (for CRITICAL alerts)
    'email': {
        'server': 'smtp.gmail.com',
        'port': 587,
        'from': 'alerts@example.com',
        'to': 'operator@example.com',
        'username': 'alerts@example.com',
        'password': 'your-password'
    }
}
```

## Alert Format

### Console Alert

```
⚠ ALERT: [WARNING] [System 1] Relay Mode Latency: relay_latency = 750.0 (threshold: 500.0) - Relay mode latency exceeds 500.0ms threshold
```

### Alert Properties

- **Severity**: WARNING (configurable)
- **Rule Name**: "Relay Mode Latency"
- **Message Type**: "CMD_STATUS_REPORT"
- **Field**: "relay_latency"
- **Actual Value**: Measured latency in milliseconds
- **Threshold**: Configured threshold in milliseconds
- **System ID**: ID of the system reporting high latency

## Latency Calculation

The relay latency is calculated from the `last_activity_sec` field in the `StatusPayload`:

```python
latency_ms = status_payload.last_activity_sec * 1000.0
```

This field represents the time (in seconds) since the last relay activity, providing a measure of relay responsiveness.

## Alert Throttling

Relay latency alerts use the same throttling mechanism as other alerts:

1. **Duplicate Prevention**: Identical alerts within the duplicate window (default 300s) are filtered
2. **Rate Limiting**: Maximum number of alerts per throttle window (default 10 per 60s)
3. **Per-System Throttling**: Throttling is applied per system ID

This prevents alert spam while ensuring critical issues are reported.

## Integration with Main Application

### In Main Loop

```python
# Main telemetry processing loop
while running:
    # Read data from connection
    data = connection.read(1024)
    
    # Parse binary protocol packets
    packets = binary_parser.parse_stream(data)
    
    for packet in packets:
        # Update metrics
        metrics_calculator.update_binary_packet(packet)
        
        # Check for status reports
        if packet.command == UartCommand.CMD_STATUS_REPORT:
            system_id = packet.payload.own_drone_sysid
            
            # Check relay latency and generate alerts
            alert_manager.check_relay_latency(packet.payload, system_id)
        
        # Extract and process MAVLink if present
        if packet.command in (UartCommand.CMD_BRIDGE_TX, UartCommand.CMD_BRIDGE_RX):
            mavlink_msg = mavlink_extractor.extract_mavlink(packet)
            if mavlink_msg:
                # Validate and log MAVLink message
                violations = validation_engine.validate_message(mavlink_msg)
                for violation in violations:
                    alert_manager.send_alert(violation)
```

## Testing

### Unit Tests

```python
def test_relay_latency_alert():
    """Test relay latency alert generation."""
    config = {
        'channels': [AlertChannel.CONSOLE],
        'relay_latency_threshold_ms': 500.0
    }
    alert_manager = AlertManager(config)
    
    # Create status payload with high latency
    status = StatusPayload(
        relay_active=True,
        own_drone_sysid=1,
        last_activity_sec=0.75,  # 750ms - exceeds threshold
        # ... other fields
    )
    
    # Check relay latency
    alert_generated = alert_manager.check_relay_latency(status, system_id=1)
    
    assert alert_generated
    assert alert_manager.stats['relay_latency_alerts'] == 1
```

### Integration Testing

Run the example script to test the feature:

```bash
python examples/relay_latency_alert_example.py
```

Run the comprehensive test suite:

```bash
python test_relay_latency_alerts.py
```

## Troubleshooting

### No Alerts Generated

**Problem**: Relay latency exceeds threshold but no alerts are generated.

**Solutions**:
1. Verify relay mode is active: `relay_status = alert_manager.get_relay_mode_status()`
2. Check threshold configuration: `alert_manager.relay_latency_threshold_ms`
3. Verify `CMD_STATUS_REPORT` packets are being received
4. Check if alerts are being throttled: `stats['throttled_alerts']`

### Too Many Alerts

**Problem**: Receiving excessive relay latency alerts.

**Solutions**:
1. Increase threshold: `config['relay_latency_threshold_ms'] = 1000.0`
2. Adjust throttle window: `config['throttle_window'] = 120`
3. Reduce max alerts per window: `config['max_alerts_per_window'] = 5`

### Alerts Not Cleared When Latency Improves

**Problem**: Alerts continue after latency returns to normal.

**Explanation**: This is expected behavior. Alerts are generated when latency exceeds the threshold. When latency improves, no new alerts are generated, but previous alerts remain in history.

**Solution**: Monitor alert history with time filtering:
```python
recent_alerts = alert_manager.get_alert_history(since=time.time() - 300)
```

## Performance Considerations

- **Memory Usage**: Relay mode tracking uses minimal memory (one boolean per system)
- **CPU Usage**: Latency checking is O(1) operation
- **Alert Overhead**: Alert generation reuses existing infrastructure
- **Cleanup**: Old tracking data is automatically cleaned up via `cleanup_old_tracking()`

## Future Enhancements

1. **Latency Trends**: Track latency over time and detect degradation trends
2. **Adaptive Thresholds**: Adjust thresholds based on historical performance
3. **Latency Histograms**: Generate latency distribution statistics
4. **Predictive Alerts**: Alert before latency exceeds threshold based on trends
5. **Multi-Hop Latency**: Track latency across multiple relay hops

## Related Documentation

- [Alert Manager](README_AlertManager.md) - Main alert manager documentation
- [Binary Protocol Parser](README_BinaryProtocolParser.md) - Binary protocol parsing
- [Metrics Calculator](README_MetricsCalculator.md) - Metrics calculation
- [Validation Engine](README_ValidationEngine.md) - Validation rules

## References

- Task 7.4: Add relay mode latency alerts
- Requirement 9.5: Relay mode latency monitoring
- Binary Protocol Specification: `include/BinaryProtocol.h`
- Status Payload Structure: `include/shared_protocol.h`
