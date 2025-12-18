"""
Report Generator Example

This example demonstrates how to use the ReportGenerator class to:
1. Generate summary reports in text and HTML formats
2. Export telemetry data to various formats (CSV, JSON, .tlog, .binlog)
3. Query logs with filtering
4. Compare metrics between time ranges

Requirements: 5.2, 5.3, 10.1, 10.2, 10.3, 10.4, 10.5
"""

import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from report_generator import ReportGenerator
from validation_engine import ValidationEngine, Severity
from metrics_calculator import MetricsCalculator
from binary_protocol_parser import UartCommand


def example_generate_summary_reports():
    """Example: Generate summary reports in text and HTML formats"""
    print("=" * 80)
    print("Example 1: Generate Summary Reports")
    print("=" * 80)
    
    # Create validation engine and metrics calculator with some sample data
    validation_engine = ValidationEngine('config/validation_rules.json')
    metrics_calculator = MetricsCalculator()
    
    # Create report generator
    report_gen = ReportGenerator(
        validation_engine=validation_engine,
        metrics_calculator=metrics_calculator
    )
    
    # Generate text report
    print("\n--- Text Report ---")
    text_report = report_gen.generate_summary_report(format='text')
    print(text_report)
    
    # Save text report to file
    report_gen.generate_summary_report(
        format='text',
        output_file='telemetry_logs/summary_report.txt'
    )
    print("\nText report saved to: telemetry_logs/summary_report.txt")
    
    # Generate HTML report
    print("\n--- HTML Report ---")
    report_gen.generate_summary_report(
        format='html',
        output_file='telemetry_logs/summary_report.html'
    )
    print("HTML report saved to: telemetry_logs/summary_report.html")
    print("Open this file in a web browser to view the formatted report")


def example_export_to_csv():
    """Example: Export telemetry data to CSV with filtering"""
    print("\n" + "=" * 80)
    print("Example 2: Export to CSV")
    print("=" * 80)
    
    report_gen = ReportGenerator()
    
    # Export all data
    print("\n--- Export All Data ---")
    count = report_gen.export_to_csv(
        log_file='telemetry_logs/telemetry_20241026_120000.json',
        output_file='telemetry_logs/export_all.csv'
    )
    print(f"Exported {count} records to export_all.csv")
    
    # Export with time range filter
    print("\n--- Export with Time Range Filter ---")
    start_time = time.time() - 3600  # Last hour
    end_time = time.time()
    
    count = report_gen.export_to_csv(
        log_file='telemetry_logs/telemetry_20241026_120000.json',
        output_file='telemetry_logs/export_last_hour.csv',
        start_time=start_time,
        end_time=end_time
    )
    print(f"Exported {count} records from last hour")
    
    # Export with message type filter
    print("\n--- Export HEARTBEAT Messages Only ---")
    count = report_gen.export_to_csv(
        log_file='telemetry_logs/telemetry_20241026_120000.json',
        output_file='telemetry_logs/export_heartbeat.csv',
        msg_type='HEARTBEAT'
    )
    print(f"Exported {count} HEARTBEAT messages")
    
    # Export with system ID filter
    print("\n--- Export System ID 1 Only ---")
    count = report_gen.export_to_csv(
        log_file='telemetry_logs/telemetry_20241026_120000.json',
        output_file='telemetry_logs/export_sysid1.csv',
        system_id=1
    )
    print(f"Exported {count} messages from system ID 1")


def example_export_to_json():
    """Example: Export telemetry data to JSON with structured format"""
    print("\n" + "=" * 80)
    print("Example 3: Export to JSON")
    print("=" * 80)
    
    report_gen = ReportGenerator()
    
    # Export with multiple filters
    print("\n--- Export GPS Messages from Last 10 Minutes ---")
    start_time = time.time() - 600  # Last 10 minutes
    end_time = time.time()
    
    count = report_gen.export_to_json(
        log_file='telemetry_logs/telemetry_20241026_120000.json',
        output_file='telemetry_logs/export_gps.json',
        start_time=start_time,
        end_time=end_time,
        msg_type='GPS_RAW_INT'
    )
    print(f"Exported {count} GPS messages to structured JSON")
    print("JSON includes metadata about filters and export time")


def example_export_to_tlog():
    """Example: Export MAVLink data to .tlog format"""
    print("\n" + "=" * 80)
    print("Example 4: Export to .tlog Format")
    print("=" * 80)
    
    report_gen = ReportGenerator()
    
    # Export to .tlog for QGroundControl replay
    print("\n--- Export to .tlog for QGC Replay ---")
    count = report_gen.export_to_tlog(
        log_file='telemetry_logs/telemetry_20241026_120000.json',
        output_file='telemetry_logs/replay.tlog'
    )
    print(f"Exported {count} MAVLink messages to .tlog format")
    print("This file can be opened in QGroundControl for replay and analysis")
    
    # Export specific time range
    print("\n--- Export Specific Flight Segment ---")
    flight_start = time.time() - 1800  # 30 minutes ago
    flight_end = time.time() - 900     # 15 minutes ago
    
    count = report_gen.export_to_tlog(
        log_file='telemetry_logs/telemetry_20241026_120000.json',
        output_file='telemetry_logs/flight_segment.tlog',
        start_time=flight_start,
        end_time=flight_end
    )
    print(f"Exported {count} messages from flight segment")


def example_export_to_binlog():
    """Example: Export binary protocol packets to .binlog format"""
    print("\n" + "=" * 80)
    print("Example 5: Export to .binlog Format")
    print("=" * 80)
    
    report_gen = ReportGenerator()
    
    # Export all binary protocol packets
    print("\n--- Export All Binary Protocol Packets ---")
    count = report_gen.export_to_binlog(
        binary_log_file='telemetry_logs/binary_protocol_20241026_120000.json',
        output_file='telemetry_logs/binary_replay.binlog'
    )
    print(f"Exported {count} binary protocol packets")
    print("This file can be used for debugging and protocol replay")
    
    # Export specific command types
    print("\n--- Export STATUS_REPORT Commands Only ---")
    count = report_gen.export_to_binlog(
        binary_log_file='telemetry_logs/binary_protocol_20241026_120000.json',
        output_file='telemetry_logs/status_reports.binlog',
        command_type=UartCommand.CMD_STATUS_REPORT
    )
    print(f"Exported {count} STATUS_REPORT packets")


def example_query_logs():
    """Example: Query logs with various filters"""
    print("\n" + "=" * 80)
    print("Example 6: Query Logs")
    print("=" * 80)
    
    report_gen = ReportGenerator()
    
    # Query all data
    print("\n--- Query All Data ---")
    results = report_gen.query_logs(
        log_file='telemetry_logs/telemetry_20241026_120000.json'
    )
    print(f"Found {len(results)} total records")
    
    # Query with time range
    print("\n--- Query Last 5 Minutes ---")
    start_time = time.time() - 300
    results = report_gen.query_logs(
        log_file='telemetry_logs/telemetry_20241026_120000.json',
        start_time=start_time
    )
    print(f"Found {len(results)} records from last 5 minutes")
    
    # Query specific message type
    print("\n--- Query ATTITUDE Messages ---")
    results = report_gen.query_logs(
        log_file='telemetry_logs/telemetry_20241026_120000.json',
        msg_type='ATTITUDE'
    )
    print(f"Found {len(results)} ATTITUDE messages")
    
    if results:
        # Display first result
        print("\nFirst ATTITUDE message:")
        print(f"  Timestamp: {results[0].get('timestamp')}")
        print(f"  System ID: {results[0].get('system_id')}")
        print(f"  Fields: {results[0].get('fields')}")
    
    # Query with multiple filters
    print("\n--- Query GPS from System ID 1 in Last Hour ---")
    start_time = time.time() - 3600
    results = report_gen.query_logs(
        log_file='telemetry_logs/telemetry_20241026_120000.json',
        start_time=start_time,
        msg_type='GPS_RAW_INT',
        system_id=1
    )
    print(f"Found {len(results)} matching records")


def example_log_summary():
    """Example: Get log file summary"""
    print("\n" + "=" * 80)
    print("Example 7: Log File Summary")
    print("=" * 80)
    
    report_gen = ReportGenerator()
    
    # Get summary of log file
    print("\n--- Log File Summary ---")
    summary = report_gen.get_log_summary(
        log_file='telemetry_logs/telemetry_20241026_120000.json'
    )
    
    print(f"File: {summary.get('file')}")
    print(f"Total Records: {summary.get('total_records')}")
    
    time_range = summary.get('time_range', {})
    print(f"\nTime Range:")
    print(f"  Start: {time_range.get('start')}")
    print(f"  End: {time_range.get('end')}")
    print(f"  Duration: {time_range.get('duration_seconds')} seconds")
    
    msg_types = summary.get('message_types', {})
    print(f"\nMessage Types:")
    print(f"  Unique Types: {msg_types.get('unique_count')}")
    print(f"  Distribution:")
    for msg_type, count in sorted(msg_types.get('distribution', {}).items(), 
                                  key=lambda x: x[1], reverse=True)[:10]:
        print(f"    {msg_type}: {count}")
    
    print(f"\nSystem IDs: {summary.get('system_ids')}")


def example_compare_time_ranges():
    """Example: Compare metrics between two time ranges"""
    print("\n" + "=" * 80)
    print("Example 8: Compare Time Ranges")
    print("=" * 80)
    
    report_gen = ReportGenerator()
    
    # Compare first half vs second half of log
    print("\n--- Compare First Half vs Second Half ---")
    
    # Define time ranges (example timestamps)
    now = time.time()
    range1 = (now - 3600, now - 1800)  # First half hour
    range2 = (now - 1800, now)          # Second half hour
    
    comparison = report_gen.compare_time_ranges(
        log_file='telemetry_logs/telemetry_20241026_120000.json',
        range1=range1,
        range2=range2
    )
    
    print("\nRange 1 Metrics:")
    metrics1 = comparison.get('range1', {}).get('metrics', {})
    print(f"  Record Count: {metrics1.get('record_count')}")
    print(f"  Packet Rate: {metrics1.get('packet_rate'):.2f} pps")
    print(f"  Avg RSSI: {metrics1.get('avg_rssi'):.1f} dBm")
    print(f"  Avg SNR: {metrics1.get('avg_snr'):.1f} dB")
    
    print("\nRange 2 Metrics:")
    metrics2 = comparison.get('range2', {}).get('metrics', {})
    print(f"  Record Count: {metrics2.get('record_count')}")
    print(f"  Packet Rate: {metrics2.get('packet_rate'):.2f} pps")
    print(f"  Avg RSSI: {metrics2.get('avg_rssi'):.1f} dBm")
    print(f"  Avg SNR: {metrics2.get('avg_snr'):.1f} dB")
    
    print("\nDifferences:")
    diffs = comparison.get('differences', {})
    print(f"  Packet Rate Change: {diffs.get('packet_rate_change'):.2f} pps "
          f"({diffs.get('packet_rate_change_pct'):.1f}%)")
    print(f"  RSSI Change: {diffs.get('avg_rssi_change'):.1f} dBm")
    print(f"  SNR Change: {diffs.get('avg_snr_change'):.1f} dB")


def main():
    """Run all examples"""
    print("\n")
    print("*" * 80)
    print("REPORT GENERATOR EXAMPLES")
    print("*" * 80)
    
    try:
        example_generate_summary_reports()
        example_export_to_csv()
        example_export_to_json()
        example_export_to_tlog()
        example_export_to_binlog()
        example_query_logs()
        example_log_summary()
        example_compare_time_ranges()
        
        print("\n" + "=" * 80)
        print("All examples completed successfully!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
