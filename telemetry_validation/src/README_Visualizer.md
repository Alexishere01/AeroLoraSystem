# Telemetry Visualizer Module

## Overview

The Telemetry Visualizer provides real-time and historical visualization of telemetry data with support for multiple metrics, violation highlighting, and multi-drone tracking.

## Features

- **Real-time Visualization**: Live graphs updated at 1 Hz (configurable)
- **Multiple Metrics**: RSSI, SNR, packet rate, battery voltage, binary protocol health
- **Violation Highlighting**: Red markers on graphs when validation rules are violated
- **Historical Data Viewing**: Load and display data from log files with time range filtering
- **Multi-Drone Support**: Track up to 4 drones simultaneously with color-coded graphs
- **Binary Protocol Health**: Monitor checksum errors and protocol success rate
- **Efficient Data Structures**: Uses deques for optimal performance

## Requirements

Satisfies requirements: 7.1, 7.2, 7.3, 7.4, 7.5

## Usage

### Basic Real-time Visualization

```python
from visualizer import TelemetryVisualizer, VisualizerConfig
from metrics_calculator import MetricsCalculator

# Create visualizer with default config
visualizer = TelemetryVisualizer()

# Or with custom config
config = VisualizerConfig(
    update_rate_hz=1.0,
    history_seconds=60,
    max_drones=4,
    show_violations=True
)
visualizer = TelemetryVisualizer(config)

# Initialize plots
visualizer.initialize_plots()

# Update with metrics (in your main loop)
metrics = metrics_calculator.get_metrics()
visualizer.update_data(metrics, system_id=1, battery_voltage=12.5)

# Add violations for highlighting
violation = validation_engine.validate_message(msg)
if violation:
    visualizer.add_violation(violation[0])

# Start real-time visualization
visualizer.start_realtime()
```

### Historical Data Viewing

```python
from visualizer import TelemetryVisualizer

# Create visualizer
visualizer = TelemetryVisualizer()

# Load historical data from CSV log
visualizer.load_historical_data('telemetry_logs/telemetry_20241026_120000.csv')

# Or with time range filtering
time_range = (1698336000.0, 1698339600.0)  # Unix timestamps
visualizer.load_historical_data('telemetry_logs/telemetry_20241026_120000.csv', 
                               time_range=time_range)
```

### Multi-Drone Tracking

```python
from visualizer import TelemetryVisualizer

visualizer = TelemetryVisualizer()
visualizer.initialize_plots()

# Update with data from multiple drones
for system_id in [1, 2, 3]:
    metrics = get_metrics_for_system(system_id)
    visualizer.update_data(metrics, system_id=system_id)

visualizer.start_realtime()
```

### Save Snapshot

```python
# Save current visualization to file
visualizer.save_snapshot('telemetry_snapshot.png')
```

## Configuration

### VisualizerConfig

```python
@dataclass
class VisualizerConfig:
    update_rate_hz: float = 1.0          # Update rate in Hz (requirement 7.5)
    history_seconds: int = 60            # Seconds of history to display
    max_drones: int = 4                  # Maximum number of drones to track
    show_violations: bool = True         # Highlight violations on graphs
    window_title: str = "Telemetry Validation - Real-time Monitor"
```

## Visualization Layout

The visualizer creates a 3x2 grid of subplots:

```
┌─────────────────┬─────────────────┐
│  RSSI (dBm)     │  SNR (dB)       │
├─────────────────┼─────────────────┤
│  Packet Rate    │  Battery Voltage│
│  (packets/s)    │  (V)            │
├─────────────────┼─────────────────┤
│  Checksum Errors│  Protocol       │
│  (errors/min)   │  Success (%)    │
└─────────────────┴─────────────────┘
```

## Violation Highlighting

When a validation rule is violated:
1. The violation is added to the visualizer via `add_violation()`
2. The corresponding data point is marked with `has_violation=True`
3. Red 'X' markers are displayed on the graph at violation points
4. Violations are annotated with timestamp and severity

## Multi-Drone Support

The visualizer automatically:
- Detects new system IDs and assigns colors from a palette
- Plots separate lines for each drone on the same graph
- Adds legends to distinguish between drones
- Supports up to 4 drones by default (configurable)

Color palette:
- System 1: Blue (#1f77b4)
- System 2: Orange (#ff7f0e)
- System 3: Green (#2ca02c)
- System 4: Red (#d62728)

## Performance Optimization

The visualizer is optimized for real-time performance:

1. **Efficient Data Structures**: Uses `deque` with `maxlen` for automatic memory management
2. **Update Rate Limiting**: Updates at 1 Hz by default (requirement 7.5)
3. **Minimal Redraws**: Only redraws changed data
4. **NumPy Arrays**: Uses NumPy for efficient array operations

## Data Structures

### MetricDataPoint

```python
@dataclass
class MetricDataPoint:
    timestamp: float          # Unix timestamp
    value: float             # Metric value
    system_id: int = 0       # System ID (for multi-drone)
    has_violation: bool = False  # Violation flag
```

## Integration with Other Components

### With MetricsCalculator

```python
# Get metrics from calculator
metrics = metrics_calculator.get_metrics()

# Update visualizer
visualizer.update_data(metrics, system_id=1)
```

### With ValidationEngine

```python
# Validate message
violations = validation_engine.validate_message(msg)

# Add violations to visualizer
for violation in violations:
    visualizer.add_violation(violation)
```

### With TelemetryLogger

```python
# Load historical data from logger's CSV files
visualizer.load_historical_data(logger.csv_file)
```

## Error Handling

The visualizer handles errors gracefully:
- Missing data: Skips plotting for missing metrics
- Invalid system IDs: Logs warning and continues
- File loading errors: Logs error and returns
- Plot errors: Logs error and attempts recovery

## Logging

The visualizer logs important events:
- Initialization
- System ID registration
- Data loading
- Errors and warnings

## Example: Complete Integration

```python
from visualizer import TelemetryVisualizer, VisualizerConfig
from metrics_calculator import MetricsCalculator
from validation_engine import ValidationEngine
from binary_protocol_parser import BinaryProtocolParser
from mavlink_parser import MAVLinkParser

# Initialize components
config = VisualizerConfig(update_rate_hz=1.0, history_seconds=60)
visualizer = TelemetryVisualizer(config)
metrics_calc = MetricsCalculator()
validation_engine = ValidationEngine()
binary_parser = BinaryProtocolParser()
mavlink_parser = MAVLinkParser()

# Initialize plots
visualizer.initialize_plots()

# Main loop (simplified)
while True:
    # Parse binary protocol packets
    data = connection.read()
    binary_packets = binary_parser.parse_stream(data)
    
    for packet in binary_packets:
        # Update metrics
        metrics_calc.update_binary_packet(packet)
        
        # Extract MAVLink if present
        if packet.command in (CMD_BRIDGE_TX, CMD_BRIDGE_RX):
            mavlink_msg = mavlink_parser.parse(packet.payload.data)
            
            if mavlink_msg:
                # Update metrics
                metrics_calc.update_mavlink_message(mavlink_msg)
                
                # Validate
                violations = validation_engine.validate_message(mavlink_msg)
                
                # Add violations to visualizer
                for violation in violations:
                    visualizer.add_violation(violation)
                
                # Extract battery voltage
                battery_voltage = None
                if mavlink_msg.msg_type == 'SYS_STATUS':
                    battery_voltage = mavlink_msg.fields['voltage_battery'] / 1000.0
                
                # Update visualizer
                metrics = metrics_calc.get_metrics()
                visualizer.update_data(metrics, 
                                      system_id=mavlink_msg.system_id,
                                      battery_voltage=battery_voltage)
    
    time.sleep(0.1)

# Start visualization (blocking)
visualizer.start_realtime()
```

## Testing

See `tests/test_visualizer.py` for unit tests and `examples/visualizer_example.py` for usage examples.

## Requirements Mapping

- **7.1**: Real-time graphs of RSSI, SNR, packet rate, battery voltage, binary protocol health
- **7.2**: Violation highlighting with red indicators
- **7.3**: Historical data viewing with time range selection
- **7.4**: Multi-drone support with color-coded graphs
- **7.5**: 1 Hz update rate for optimal performance
