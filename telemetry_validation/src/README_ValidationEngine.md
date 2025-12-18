# ValidationEngine Module

## Overview

The ValidationEngine module provides comprehensive telemetry validation capabilities with configurable rules, GPS altitude jump detection, and packet loss detection. It validates MAVLink messages against user-defined rules and automatically detects common telemetry issues.

## Features

### Configurable Validation Rules
- JSON-based rule configuration
- Support for multiple message types and fields
- Six comparison operators (LT, GT, EQ, NE, LTE, GTE)
- Three severity levels (INFO, WARNING, CRITICAL)
- Runtime rule reloading

### Automatic Detection
- **GPS Altitude Jumps**: Detects unrealistic altitude changes (>50m/s)
- **Packet Loss**: Tracks MAVLink sequence numbers to detect lost packets
- **Per-System Tracking**: Supports multiple drones simultaneously

### Statistics & Filtering
- Comprehensive violation tracking
- Statistics by severity and rule
- Filter violations by severity, system_id, or timestamp

## Classes

### Severity (Enum)
Severity levels for validation violations:
- `INFO`: Informational violations
- `WARNING`: Warning-level violations
- `CRITICAL`: Critical violations requiring immediate attention

### Operator (Enum)
Comparison operators for validation rules:
- `LT`: Less than (<)
- `GT`: Greater than (>)
- `EQ`: Equal to (==)
- `NE`: Not equal to (!=)
- `LTE`: Less than or equal to (<=)
- `GTE`: Greater than or equal to (>=)

### ValidationRule (Dataclass)
Defines a validation rule:
```python
@dataclass
class ValidationRule:
    name: str              # Human-readable rule name
    msg_type: str          # MAVLink message type (e.g., 'HEARTBEAT')
    field: str             # Field name to validate
    operator: Operator     # Comparison operator
    threshold: Any         # Threshold value
    severity: Severity     # Severity level
    description: str       # Human-readable description
```

### Violation (Dataclass)
Records a validation violation:
```python
@dataclass
class Violation:
    timestamp: float       # When violation occurred
    rule_name: str         # Name of violated rule
    msg_type: str          # MAVLink message type
    field: str             # Field that violated the rule
    actual_value: Any      # Actual value
    threshold: Any         # Expected threshold
    severity: Severity     # Severity level
    description: str       # Human-readable description
    system_id: int         # Source system ID (optional)
```

### ValidationEngine
Main validation engine class.

#### Initialization
```python
engine = ValidationEngine(config_file='config/validation_rules.json')
```

#### Methods

##### validate_message(msg: ParsedMessage) -> List[Violation]
Validates a message against all applicable rules.

**Parameters:**
- `msg`: ParsedMessage object from MAVLink parser

**Returns:**
- List of Violation objects for any rules that were violated

**Example:**
```python
violations = engine.validate_message(msg)
for violation in violations:
    print(f"{violation.rule_name}: {violation.description}")
```

##### load_rules()
Loads validation rules from JSON configuration file. Called automatically during initialization.

##### reload_rules()
Reloads validation rules from configuration file without restarting the system.

**Example:**
```python
engine.reload_rules()
```

##### get_violations(severity=None, system_id=None, since=None) -> List[Violation]
Gets violations with optional filtering.

**Parameters:**
- `severity`: Filter by severity level (optional)
- `system_id`: Filter by system ID (optional)
- `since`: Filter by timestamp - only violations after this time (optional)

**Returns:**
- List of Violation objects matching the filters

**Example:**
```python
# Get all critical violations
critical = engine.get_violations(severity=Severity.CRITICAL)

# Get violations for system 1
system1 = engine.get_violations(system_id=1)

# Get recent violations
recent = engine.get_violations(since=time.time() - 60)
```

##### get_stats() -> dict
Gets validation statistics.

**Returns:**
- Dictionary containing:
  - `total_checks`: Total validation checks performed
  - `total_violations`: Total violations detected
  - `violations_by_severity`: Count by severity level
  - `violations_by_rule`: Count by rule name

**Example:**
```python
stats = engine.get_stats()
print(f"Total checks: {stats['total_checks']}")
print(f"Total violations: {stats['total_violations']}")
```

##### clear_violations()
Clears all recorded violations.

##### reset_stats()
Resets all statistics counters.

## Configuration File Format

The validation rules are defined in a JSON file:

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
      "name": "Weak Signal",
      "msg_type": "RADIO_STATUS",
      "field": "rssi",
      "operator": "<",
      "threshold": -100,
      "severity": "WARNING",
      "description": "RSSI below -100 dBm"
    }
  ]
}
```

### Rule Fields

- **name**: Human-readable name for the rule
- **msg_type**: MAVLink message type to validate (e.g., 'HEARTBEAT', 'GPS_RAW_INT', 'SYS_STATUS')
- **field**: Field name within the message to check
- **operator**: Comparison operator as string ('<', '>', '==', '!=', '<=', '>=')
- **threshold**: Threshold value for comparison (number or string)
- **severity**: Severity level as string ('INFO', 'WARNING', 'CRITICAL')
- **description**: Human-readable description of the rule (optional)

## GPS Altitude Jump Detection

The engine automatically detects unrealistic GPS altitude changes:

- Tracks altitude history per system_id
- Calculates rate of change between consecutive GPS_RAW_INT messages
- Flags violations when altitude changes >50m in 1 second
- Maintains history of last 10 readings per system

**Note:** GPS altitude in MAVLink is in millimeters, automatically converted to meters.

## Packet Loss Detection

The engine automatically detects packet loss:

- Tracks MAVLink sequence numbers from packet headers
- Detects gaps in sequence numbers (0-255, wraps around)
- Generates violations when packets are lost
- Ignores large gaps (>200) that indicate system restart
- Per-system tracking for multi-drone support

**Note:** Packet loss detection works on HEARTBEAT messages but tracks the MAVLink packet sequence number, not message-specific fields.

## Usage Example

```python
from validation_engine import ValidationEngine, Severity
from mavlink_parser import MAVLinkParser

# Initialize components
parser = MAVLinkParser()
engine = ValidationEngine(config_file='config/validation_rules.json')

# Parse and validate messages
data = serial_port.read(1024)
messages = parser.parse_stream(data)

for msg in messages:
    # Validate message
    violations = engine.validate_message(msg)
    
    # Handle violations
    for violation in violations:
        if violation.severity == Severity.CRITICAL:
            print(f"CRITICAL: {violation.rule_name}")
            print(f"  {violation.description}")
            # Send alert, log to file, etc.
        elif violation.severity == Severity.WARNING:
            print(f"WARNING: {violation.rule_name}")

# Get statistics
stats = engine.get_stats()
print(f"Validation checks: {stats['total_checks']}")
print(f"Violations: {stats['total_violations']}")

# Get filtered violations
critical_violations = engine.get_violations(severity=Severity.CRITICAL)
system1_violations = engine.get_violations(system_id=1)
```

## Integration with Other Modules

### With MAVLinkParser
```python
from mavlink_parser import MAVLinkParser
from validation_engine import ValidationEngine

parser = MAVLinkParser()
engine = ValidationEngine()

# Parse and validate
messages = parser.parse_stream(data)
for msg in messages:
    violations = engine.validate_message(msg)
```

### With TelemetryLogger
```python
from telemetry_logger import TelemetryLogger
from validation_engine import ValidationEngine

logger = TelemetryLogger()
engine = ValidationEngine()

# Log messages and violations
for msg in messages:
    logger.log_message(msg)
    violations = engine.validate_message(msg)
    for violation in violations:
        logger.log_violation(violation)
```

### With AlertManager
```python
from validation_engine import ValidationEngine, Severity
from alert_manager import AlertManager

engine = ValidationEngine()
alerts = AlertManager()

# Send alerts for critical violations
violations = engine.validate_message(msg)
for violation in violations:
    if violation.severity == Severity.CRITICAL:
        alerts.send_alert(violation)
```

## Error Handling

The ValidationEngine handles errors gracefully:

- **Missing config file**: Logs warning and runs with no rules
- **Invalid JSON**: Logs error and runs with no rules
- **Invalid rules**: Logs error for each invalid rule and skips it
- **Missing fields**: Skips validation for messages without required fields
- **Comparison errors**: Logs debug message and treats as no violation

## Performance Considerations

- Rules are evaluated only for matching message types
- GPS altitude history limited to last 10 readings per system
- Sequence number tracking uses simple dictionary lookup
- Statistics use efficient counters
- No blocking operations

## Testing

Run the validation script to verify implementation:
```bash
python3 validate_validation_engine.py
```

Run unit tests:
```bash
python3 -m pytest tests/test_validation_engine.py -v
```

Run examples:
```bash
python3 examples/validation_engine_example.py
```

## Requirements Satisfied

- ✅ 3.1: Automated validation of telemetry data
- ✅ 3.2: Violation logging with details
- ✅ 3.3: GPS altitude jump detection
- ✅ 3.5: Validation statistics tracking
- ✅ 4.1: Load rules from JSON configuration
- ✅ 4.2: Rule specification with operators and thresholds
- ✅ 4.3: Runtime configuration reload
- ✅ 4.4: Graceful handling of invalid rules
- ✅ 9.4: Packet loss detection
