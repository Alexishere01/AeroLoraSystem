# Report Generator Module

## Overview

The Report Generator module provides comprehensive reporting, export, and query capabilities for the telemetry validation system. It generates summary reports with key metrics, validation results, and binary protocol health metrics in both text and HTML formats. It also supports exporting data to various formats and querying logs with flexible filtering.

## Features

- **Summary Reports**: Generate comprehensive reports with metrics, violations, and system health
- **Multiple Formats**: Text and HTML report formats
- **Data Export**: Export to CSV, JSON, .tlog (MAVLink), and .binlog (binary protocol) formats
- **Query Tools**: Filter logs by time range, message type, system ID, and command type
- **Time Range Comparison**: Compare metrics between different time periods
- **Log Summaries**: Get quick statistics about log files

## Requirements

This module implements the following requirements:
- **5.2**: Generate summary reports with key metrics
- **5.3**: Query logs by time range and message type
- **10.1**: Export to CSV with time range filtering
- **10.2**: Export to JSON with structured data
- **10.3**: Export to .tlog format (MAVLink only)
- **10.4**: Export to .binlog format (binary protocol packets)
- **10.5**: Implement query tools with filtering

## Usage

### Basic Report Generation

```python
from report_generator import ReportGenerator
from validation_engine import ValidationEngine
from metrics_calculator import MetricsCalculator

# Create components
validation_engine = ValidationEngine('config/validation_rules.json')
metrics_calculator = MetricsCalculator()

# Create report generator
report_gen = ReportGenerator(
    validation_engine=validation_engine,
    metrics_calculator=metrics_calculator
)

# Generate text report
text_report = report_gen.generate_summary_report(format='text')
print(text_report)

# Generate HTML report and save to file
report_gen.generate_summary_report(
    format='html',
    output_file='telemetry_logs/report.html'
)
```

### Export to CSV

```python
# Export all data
count = report_gen.export_to_csv(
    log_file='telemetry_logs/telemetry_20241026_120000.json',
    output_file='telemetry_logs/export.csv'
)

# Export with time range filter
import time
start_time = time.time() - 3600  # Last hour
count = report_gen.export_to_csv(
    log_file='telemetry_logs/telemetry_20241026_120000.json',
    output_file='telemetry_logs/last_hour.csv',
    start_time=start_time
)

# Export specific message type
count = report_gen.export_to_csv(
    log_file='telemetry_logs/telemetry_20241026_120000.json',
    output_file='telemetry_logs/heartbeat.csv',
    msg_type='HEARTBEAT'
)

# Export specific system ID
count = report_gen.export_to_csv(
    log_file='telemetry_logs/telemetry_20241026_120000.json',
    output_file='telemetry_logs/sysid1.csv',
    system_id=1
)
```

### Export to JSON

```python
# Export with structured format and metadata
count = report_gen.export_to_json(
    log_file='telemetry_logs/telemetry_20241026_120000.json',
    output_file='telemetry_logs/export.json',
    start_time=start_time,
    end_time=end_time,
    msg_type='GPS_RAW_INT'
)
```

The JSON export includes metadata:
```json
{
  "metadata": {
    "export_time": "2024-10-26T12:00:00",
    "source_file": "telemetry_logs/telemetry_20241026_120000.json",
    "filters": {
      "start_time": 1729944000.0,
      "end_time": 1729947600.0,
      "msg_type": "GPS_RAW_INT",
      "system_id": null
    },
    "record_count": 1234
  },
  "messages": [...]
}
```

### Export to .tlog Format

```python
# Export MAVLink messages for QGroundControl replay
count = report_gen.export_to_tlog(
    log_file='telemetry_logs/telemetry_20241026_120000.json',
    output_file='telemetry_logs/replay.tlog'
)

# Export specific time range
count = report_gen.export_to_tlog(
    log_file='telemetry_logs/telemetry_20241026_120000.json',
    output_file='telemetry_logs/flight_segment.tlog',
    start_time=flight_start,
    end_time=flight_end,
    system_id=1
)
```

### Export to .binlog Format

```python
from binary_protocol_parser import UartCommand

# Export all binary protocol packets
count = report_gen.export_to_binlog(
    binary_log_file='telemetry_logs/binary_20241026_120000.json',
    output_file='telemetry_logs/replay.binlog'
)

# Export specific command types
count = report_gen.export_to_binlog(
    binary_log_file='telemetry_logs/binary_20241026_120000.json',
    output_file='telemetry_logs/status_reports.binlog',
    command_type=UartCommand.CMD_STATUS_REPORT
)
```

### Query Logs

```python
# Query all data
results = report_gen.query_logs(
    log_file='telemetry_logs/telemetry_20241026_120000.json'
)

# Query with time range
results = report_gen.query_logs(
    log_file='telemetry_logs/telemetry_20241026_120000.json',
    start_time=start_time,
    end_time=end_time
)

# Query specific message type
results = report_gen.query_logs(
    log_file='telemetry_logs/telemetry_20241026_120000.json',
    msg_type='ATTITUDE'
)

# Query with multiple filters
results = report_gen.query_logs(
    log_file='telemetry_logs/telemetry_20241026_120000.json',
    start_time=start_time,
    msg_type='GPS_RAW_INT',
    system_id=1
)

# Process results
for record in results:
    print(f"Timestamp: {record['timestamp']}")
    print(f"Message: {record['msg_type']}")
    print(f"Fields: {record['fields']}")
```

### Log Summary

```python
# Get summary statistics
summary = report_gen.get_log_summary(
    log_file='telemetry_logs/telemetry_20241026_120000.json'
)

print(f"Total Records: {summary['total_records']}")
print(f"Time Range: {summary['time_range']}")
print(f"Message Types: {summary['message_types']}")
print(f"System IDs: {summary['system_ids']}")
```

### Compare Time Ranges

```python
# Compare metrics between two time periods
range1 = (start_time1, end_time1)
range2 = (start_time2, end_time2)

comparison = report_gen.compare_time_ranges(
    log_file='telemetry_logs/telemetry_20241026_120000.json',
    range1=range1,
    range2=range2
)

# Access comparison results
metrics1 = comparison['range1']['metrics']
metrics2 = comparison['range2']['metrics']
differences = comparison['differences']

print(f"Packet Rate Change: {differences['packet_rate_change']:.2f} pps")
print(f"RSSI Change: {differences['avg_rssi_change']:.1f} dBm")
```

## Report Formats

### Text Report

The text report includes:
- Packet rates (binary protocol and MAVLink)
- Link quality metrics (RSSI, SNR, packet loss)
- Command latency statistics
- Binary protocol health metrics
- Message type distribution
- Validation results and violations
- Recent violations with details

Example output:
```
================================================================================
TELEMETRY VALIDATION SYSTEM - SUMMARY REPORT
================================================================================
Generated: 2024-10-26 12:00:00

--------------------------------------------------------------------------------
TELEMETRY METRICS
--------------------------------------------------------------------------------

Packet Rates:
  Binary Protocol (1s/10s/60s): 15.2 / 14.8 / 15.1 pps
  MAVLink Messages (1s/10s/60s): 12.5 / 12.3 / 12.4 pps

Link Quality:
  Average RSSI: -85.3 dBm
  Average SNR: 8.2 dB
  Packet Loss Rate: 1.23%
  Packets Lost: 45
  Packets Received: 3655

Binary Protocol Health:
  Checksum Error Rate: 0.12 errors/min
  Parse Error Rate: 0.05 errors/min
  Protocol Success Rate: 99.87%
  Buffer Overflows: 0
  Timeout Errors: 2
```

### HTML Report

The HTML report provides:
- Styled, responsive layout
- Color-coded severity indicators
- Metric cards with visual hierarchy
- Tables for message distribution
- Highlighted violations
- Professional appearance for sharing

The HTML report can be opened in any web browser and includes CSS styling for a professional appearance.

## Filter Options

All export and query functions support the following filters:

- **start_time**: Unix timestamp for start of time range
- **end_time**: Unix timestamp for end of time range
- **msg_type**: MAVLink message type (e.g., 'HEARTBEAT', 'GPS_RAW_INT')
- **system_id**: MAVLink system ID (integer)
- **command_type**: Binary protocol command type (UartCommand enum or string)

Filters can be combined for precise data selection.

## Integration with Other Components

The Report Generator integrates with:

- **ValidationEngine**: Retrieves violation data and statistics
- **MetricsCalculator**: Retrieves telemetry metrics
- **TelemetryLogger**: Reads log files for export and query
- **BinaryProtocolParser**: Handles binary protocol command types

## Performance Considerations

- Large log files are processed efficiently using streaming
- Filters are applied during reading to minimize memory usage
- JSON export includes metadata for traceability
- Binary exports preserve raw packet data for replay

## Error Handling

The module includes comprehensive error handling:
- Invalid file paths are logged and return empty results
- Malformed JSON is handled gracefully
- Missing fields in records are skipped
- Export failures are logged with details

## Examples

See `examples/report_generator_example.py` for complete working examples of all features.

## Testing

Run the example script to verify functionality:

```bash
cd telemetry_validation
python examples/report_generator_example.py
```

## Future Enhancements

Potential improvements:
- PDF report generation
- Automated report scheduling
- Email report delivery
- Custom report templates
- Real-time report updates
- Database export support
