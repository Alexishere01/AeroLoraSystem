## Mode Tracking and Comparison

The mode tracking and comparison modules provide comprehensive monitoring and analysis of operating mode changes between direct and relay communication modes. This functionality enables quantitative comparison of performance metrics to assess the impact of relay operations.

### Requirements

- **6.1**: Mode detection and transition logging
- **6.2**: Mode-specific metrics calculation
- **6.3**: Relay latency measurement
- **6.4**: Mode comparison reporting

### Architecture

The mode tracking system consists of three main components:

1. **ModeTracker**: Detects mode changes and logs transitions
2. **ModeSpecificMetricsCalculator**: Maintains separate metrics for each mode
3. **ModeComparator**: Compares metrics and generates reports

```
┌─────────────────────────────────────────────────────────────┐
│                    Binary Protocol Parser                    │
│                  (CMD_STATUS_REPORT packets)                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                      Mode Tracker                            │
│  - Detect mode from relay_active field                      │
│  - Log mode transitions with timestamps                     │
│  - Track time spent in each mode                            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│              Mode-Specific Metrics Calculator                │
│  - Separate metrics for direct and relay modes              │
│  - Track relay-specific metrics (packets_relayed, etc.)     │
│  - Measure relay latency vs direct latency                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                     Mode Comparator                          │
│  - Calculate percentage differences                          │
│  - Generate comparison reports                               │
│  - Provide overall performance assessment                    │
└─────────────────────────────────────────────────────────────┘
```

### Components

#### 1. ModeTracker

Monitors CMD_STATUS_REPORT packets to detect operating mode changes.

**Key Features:**
- Automatic mode detection from `relay_active` field
- Mode transition logging with timestamps
- Time tracking for each mode
- Mode history access

**Usage:**

```python
from src.mode_tracker import ModeTracker, OperatingMode

# Initialize tracker
tracker = ModeTracker()

# Update with status packets
tracker.update(status_packet)

# Get current mode
current_mode = tracker.get_current_mode()

# Get mode transitions
transitions = tracker.get_mode_transitions()

# Get statistics
stats = tracker.get_stats()
```

**Mode Detection:**

The mode is determined from the `relay_active` field in StatusPayload:
- `relay_active = False` → Direct Mode
- `relay_active = True` → Relay Mode

**Transition Logging:**

Each mode transition is recorded with:
- Timestamp
- From mode and to mode
- relay_active status
- packets_relayed count
- active_peer_relays count

#### 2. ModeSpecificMetricsCalculator

Maintains separate metric tracking for direct and relay modes.

**Key Features:**
- Independent metrics for each mode
- Relay-specific metrics (packets_relayed, bytes_relayed, etc.)
- Relay latency measurement (additional latency vs direct mode)
- Rolling window calculations per mode

**Usage:**

```python
from src.mode_specific_metrics import ModeSpecificMetricsCalculator

# Initialize calculator
metrics_calc = ModeSpecificMetricsCalculator()

# Set current mode
metrics_calc.set_mode(current_mode)

# Update with packets
metrics_calc.update_binary_packet(packet, current_mode)
metrics_calc.update_mavlink_message(msg, current_mode)

# Get metrics for a specific mode
direct_metrics = metrics_calc.get_mode_metrics(OperatingMode.DIRECT)
relay_metrics = metrics_calc.get_mode_metrics(OperatingMode.RELAY)
```

**Tracked Metrics (per mode):**

- Packet rates (1s, 10s, 60s windows)
- Link quality (RSSI, SNR)
- Packet loss rate
- Command latency
- Message type distribution
- Protocol health (checksum errors, success rate)

**Relay-Specific Metrics:**

- packets_relayed
- bytes_relayed
- active_peer_relays
- mesh_to_uart_packets/bytes
- uart_to_mesh_packets/bytes
- relay_latency_avg (additional latency in relay mode)

**Relay Latency Measurement:**

The relay latency is calculated as the additional latency introduced by the relay hop:

```
relay_additional_latency = relay_mode_latency - direct_mode_avg_latency
```

This provides a quantitative measure of the relay overhead.

#### 3. ModeComparator

Compares metrics between direct and relay modes and generates reports.

**Key Features:**
- Percentage difference calculation for all metrics
- Comprehensive comparison reports
- Overall performance assessment
- Formatted text output

**Usage:**

```python
from src.mode_comparison import ModeComparator

# Initialize comparator
comparator = ModeComparator()

# Compare modes
report = comparator.compare_modes(direct_metrics, relay_metrics)

# Format report
formatted_report = comparator.format_comparison_report(report)
print(formatted_report)

# Get summary dictionary
summary = comparator.get_comparison_summary(report)
```

**Comparison Report Contents:**

- Packet rate comparisons
- Link quality comparisons (RSSI, SNR)
- Packet loss comparison
- Latency comparison (including relay additional latency)
- Protocol health comparisons
- Time distribution (% in each mode)
- Relay-specific metrics
- Overall performance assessment

**Performance Assessment:**

The comparator generates an overall assessment based on:
- Packet rate changes (>10% threshold)
- RSSI/SNR changes (>10% threshold)
- Packet loss changes (>10% threshold)
- Latency changes (>10% threshold)

Example assessments:
- "Relay mode performing well: packet rate increased by 5.2%, latency decreased by 8.1%"
- "Relay mode has minor issues: RSSI degraded by 12.3%"
- "Relay mode shows degraded performance: packet loss increased by 25.4%, latency increased by 45.2%"

### Data Flow

1. **Status Report Reception**:
   ```
   CMD_STATUS_REPORT → ModeTracker.update()
   ```

2. **Mode Detection**:
   ```
   relay_active field → Determine OperatingMode
   ```

3. **Transition Detection**:
   ```
   Mode change detected → Record ModeTransition
   ```

4. **Metrics Update**:
   ```
   Packet received → ModeSpecificMetricsCalculator.update_*()
                  → Update metrics for current mode
   ```

5. **Comparison**:
   ```
   Get metrics for both modes → ModeComparator.compare_modes()
                              → Generate ModeComparisonReport
   ```

### Example Output

```
================================================================================
MODE COMPARISON REPORT: DIRECT vs RELAY
================================================================================

Time Distribution:
  Direct Mode: 120.5s (55.2%)
  Relay Mode:  97.8s (44.8%)

Packet Rates:
  Binary Packet Rate (1s): Direct=10.50pkt/s, Relay=9.80pkt/s, Diff=-6.7%
  MAVLink Packet Rate (1s): Direct=50.20pkt/s, Relay=45.30pkt/s, Diff=-9.8%

Link Quality:
  Average RSSI: Direct=-80.00dBm, Relay=-85.00dBm, Diff=-6.2%
  Average SNR: Direct=10.00dB, Relay=8.00dB, Diff=-20.0%

Packet Loss:
  Packet Drop Rate: Direct=0.50%, Relay=1.20%, Diff=+140.0%

Latency:
  Average Latency: Direct=45.20ms, Relay=78.50ms, Diff=+73.7%
  Relay Additional Latency: Direct=0.00ms, Relay=33.30ms, Diff=+100.0%

Protocol Health:
  Checksum Error Rate: Direct=0.10err/min, Relay=0.15err/min, Diff=+50.0%
  Protocol Success Rate: Direct=99.90%, Relay=99.85%, Diff=-0.1%

Relay-Specific Metrics:
  Packets Relayed: 1250
  Bytes Relayed: 125000
  Active Peer Relays: 2

Overall Assessment:
  Relay mode has minor issues: RSSI degraded by 6.2%, latency increased by 73.7%

================================================================================
```

### Integration Example

```python
from src.mode_tracker import ModeTracker
from src.mode_specific_metrics import ModeSpecificMetricsCalculator
from src.mode_comparison import ModeComparator

# Initialize components
mode_tracker = ModeTracker()
metrics_calc = ModeSpecificMetricsCalculator()
comparator = ModeComparator()

# Main processing loop
while True:
    # Receive packet
    packet = receive_packet()
    
    # Update mode tracker
    mode_tracker.update(packet)
    current_mode = mode_tracker.get_current_mode()
    
    # Update mode-specific metrics
    metrics_calc.set_mode(current_mode)
    
    if isinstance(packet, ParsedBinaryPacket):
        metrics_calc.update_binary_packet(packet, current_mode)
    elif isinstance(packet, ParsedMessage):
        metrics_calc.update_mavlink_message(packet, current_mode)
    
    # Periodically generate comparison report
    if should_generate_report():
        direct_metrics = metrics_calc.get_mode_metrics(OperatingMode.DIRECT)
        relay_metrics = metrics_calc.get_mode_metrics(OperatingMode.RELAY)
        
        if direct_metrics and relay_metrics:
            report = comparator.compare_modes(direct_metrics, relay_metrics)
            print(comparator.format_comparison_report(report))
```

### Testing

Run the unit tests:

```bash
cd telemetry_validation
python -m pytest tests/test_mode_tracker.py -v
```

Run the example:

```bash
cd telemetry_validation
python examples/mode_tracking_example.py
```

### Performance Considerations

- Mode transitions are detected in real-time with minimal overhead
- Metrics are calculated using efficient rolling windows
- Comparison reports can be generated on-demand without impacting real-time processing
- Memory usage is bounded by deque maxlen parameters

### Limitations

- Requires CMD_STATUS_REPORT packets for mode detection
- Relay latency measurement requires baseline direct mode data
- Comparison accuracy depends on sufficient data in both modes
- Mode detection latency is limited by status report frequency

### Future Enhancements

1. Automatic mode transition alerts
2. Historical mode comparison over multiple sessions
3. Machine learning-based performance prediction
4. Real-time mode recommendation based on link quality
5. Integration with visualization dashboard
