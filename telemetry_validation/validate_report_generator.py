#!/usr/bin/env python3
"""
Validation Script for Report Generator

This script validates the Report Generator implementation by:
1. Creating sample data
2. Generating reports in text and HTML formats
3. Testing export functionality
4. Testing query tools
5. Verifying all features work correctly

Run this script to verify the Report Generator is working correctly.
"""

import sys
import json
import time
import tempfile
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from report_generator import ReportGenerator
from validation_engine import ValidationEngine, Violation, Severity
from metrics_calculator import MetricsCalculator


def create_sample_data():
    """Create sample telemetry data for testing"""
    print("Creating sample telemetry data...")
    
    now = time.time()
    sample_data = []
    
    # Generate 100 sample messages
    for i in range(100):
        timestamp = now - (100 - i)
        
        # Alternate between different message types
        if i % 3 == 0:
            msg_type = 'HEARTBEAT'
            fields = {'type': 2, 'autopilot': 3, 'base_mode': 81}
        elif i % 3 == 1:
            msg_type = 'GPS_RAW_INT'
            fields = {
                'lat': 123456789 + i * 100,
                'lon': -123456789 + i * 100,
                'alt': 50000 + i * 10
            }
        else:
            msg_type = 'ATTITUDE'
            fields = {
                'roll': 0.1 + i * 0.01,
                'pitch': 0.2 + i * 0.01,
                'yaw': 1.5 + i * 0.01
            }
        
        # Alternate between system IDs
        system_id = 1 if i % 2 == 0 else 2
        
        # Simulate varying RSSI/SNR
        rssi = -85.0 + (i % 10) - 5
        snr = 8.0 + (i % 5) - 2
        
        sample_data.append({
            'timestamp': timestamp,
            'msg_type': msg_type,
            'msg_id': i % 256,
            'system_id': system_id,
            'component_id': 1,
            'fields': fields,
            'rssi': rssi,
            'snr': snr
        })
    
    print(f"Created {len(sample_data)} sample messages")
    return sample_data


def test_report_generation(report_gen, temp_dir):
    """Test report generation in text and HTML formats"""
    print("\n" + "=" * 80)
    print("TEST 1: Report Generation")
    print("=" * 80)
    
    # Generate text report
    print("\nGenerating text report...")
    text_report = report_gen.generate_summary_report(format='text')
    
    # Verify text report content
    assert 'TELEMETRY VALIDATION SYSTEM' in text_report
    assert 'SUMMARY REPORT' in text_report
    print("✓ Text report generated successfully")
    
    # Save text report to file
    text_file = temp_dir / 'report.txt'
    report_gen.generate_summary_report(format='text', output_file=str(text_file))
    assert text_file.exists()
    print(f"✓ Text report saved to {text_file}")
    
    # Generate HTML report
    print("\nGenerating HTML report...")
    html_report = report_gen.generate_summary_report(format='html')
    
    # Verify HTML report content
    assert '<!DOCTYPE html>' in html_report
    assert '<html>' in html_report
    assert 'Telemetry Validation Report' in html_report
    print("✓ HTML report generated successfully")
    
    # Save HTML report to file
    html_file = temp_dir / 'report.html'
    report_gen.generate_summary_report(format='html', output_file=str(html_file))
    assert html_file.exists()
    print(f"✓ HTML report saved to {html_file}")
    
    print("\n✅ Report generation tests passed!")


def test_csv_export(report_gen, log_file, temp_dir):
    """Test CSV export functionality"""
    print("\n" + "=" * 80)
    print("TEST 2: CSV Export")
    print("=" * 80)
    
    # Export all data
    print("\nExporting all data to CSV...")
    csv_file = temp_dir / 'export_all.csv'
    count = report_gen.export_to_csv(
        log_file=str(log_file),
        output_file=str(csv_file)
    )
    assert count == 100
    assert csv_file.exists()
    print(f"✓ Exported {count} records to CSV")
    
    # Export with message type filter
    print("\nExporting HEARTBEAT messages only...")
    csv_heartbeat = temp_dir / 'export_heartbeat.csv'
    count = report_gen.export_to_csv(
        log_file=str(log_file),
        output_file=str(csv_heartbeat),
        msg_type='HEARTBEAT'
    )
    assert count > 0
    assert count < 100
    print(f"✓ Exported {count} HEARTBEAT messages")
    
    # Export with system ID filter
    print("\nExporting system ID 1 only...")
    csv_sysid = temp_dir / 'export_sysid1.csv'
    count = report_gen.export_to_csv(
        log_file=str(log_file),
        output_file=str(csv_sysid),
        system_id=1
    )
    assert count == 50  # Half of the messages
    print(f"✓ Exported {count} messages from system ID 1")
    
    # Export with time range filter
    print("\nExporting last 50 seconds...")
    csv_range = temp_dir / 'export_range.csv'
    start_time = time.time() - 50
    count = report_gen.export_to_csv(
        log_file=str(log_file),
        output_file=str(csv_range),
        start_time=start_time
    )
    assert count > 0
    print(f"✓ Exported {count} messages from time range")
    
    print("\n✅ CSV export tests passed!")


def test_json_export(report_gen, log_file, temp_dir):
    """Test JSON export functionality"""
    print("\n" + "=" * 80)
    print("TEST 3: JSON Export")
    print("=" * 80)
    
    # Export to JSON
    print("\nExporting to JSON with metadata...")
    json_file = temp_dir / 'export.json'
    count = report_gen.export_to_json(
        log_file=str(log_file),
        output_file=str(json_file)
    )
    assert count == 100
    assert json_file.exists()
    print(f"✓ Exported {count} records to JSON")
    
    # Verify JSON structure
    with open(json_file, 'r') as f:
        data = json.load(f)
        assert 'metadata' in data
        assert 'messages' in data
        assert data['metadata']['record_count'] == 100
    print("✓ JSON structure verified (includes metadata)")
    
    # Export with filters
    print("\nExporting GPS messages with filters...")
    json_filtered = temp_dir / 'export_gps.json'
    count = report_gen.export_to_json(
        log_file=str(log_file),
        output_file=str(json_filtered),
        msg_type='GPS_RAW_INT',
        system_id=1
    )
    assert count > 0
    print(f"✓ Exported {count} filtered GPS messages")
    
    print("\n✅ JSON export tests passed!")


def test_query_tools(report_gen, log_file):
    """Test query functionality"""
    print("\n" + "=" * 80)
    print("TEST 4: Query Tools")
    print("=" * 80)
    
    # Query all data
    print("\nQuerying all data...")
    results = report_gen.query_logs(log_file=str(log_file))
    assert len(results) == 100
    print(f"✓ Retrieved {len(results)} records")
    
    # Query with message type filter
    print("\nQuerying HEARTBEAT messages...")
    results = report_gen.query_logs(
        log_file=str(log_file),
        msg_type='HEARTBEAT'
    )
    assert len(results) > 0
    assert all(r['msg_type'] == 'HEARTBEAT' for r in results)
    print(f"✓ Retrieved {len(results)} HEARTBEAT messages")
    
    # Query with system ID filter
    print("\nQuerying system ID 1...")
    results = report_gen.query_logs(
        log_file=str(log_file),
        system_id=1
    )
    assert len(results) == 50
    assert all(r['system_id'] == 1 for r in results)
    print(f"✓ Retrieved {len(results)} messages from system ID 1")
    
    # Query with time range
    print("\nQuerying last 50 seconds...")
    start_time = time.time() - 50
    results = report_gen.query_logs(
        log_file=str(log_file),
        start_time=start_time
    )
    assert len(results) > 0
    print(f"✓ Retrieved {len(results)} messages from time range")
    
    # Query with multiple filters
    print("\nQuerying with multiple filters...")
    results = report_gen.query_logs(
        log_file=str(log_file),
        msg_type='GPS_RAW_INT',
        system_id=1
    )
    assert len(results) > 0
    assert all(r['msg_type'] == 'GPS_RAW_INT' and r['system_id'] == 1 for r in results)
    print(f"✓ Retrieved {len(results)} messages with multiple filters")
    
    print("\n✅ Query tools tests passed!")


def test_log_summary(report_gen, log_file):
    """Test log summary functionality"""
    print("\n" + "=" * 80)
    print("TEST 5: Log Summary")
    print("=" * 80)
    
    print("\nGenerating log summary...")
    summary = report_gen.get_log_summary(log_file=str(log_file))
    
    # Verify summary structure
    assert 'file' in summary
    assert 'total_records' in summary
    assert 'time_range' in summary
    assert 'message_types' in summary
    assert 'system_ids' in summary
    
    # Verify summary values
    assert summary['total_records'] == 100
    assert summary['system_id_count'] == 2
    assert len(summary['system_ids']) == 2
    
    print(f"✓ Total records: {summary['total_records']}")
    print(f"✓ System IDs: {summary['system_ids']}")
    print(f"✓ Message types: {summary['message_types']['unique_count']}")
    
    print("\n✅ Log summary tests passed!")


def test_time_range_comparison(report_gen, log_file):
    """Test time range comparison"""
    print("\n" + "=" * 80)
    print("TEST 6: Time Range Comparison")
    print("=" * 80)
    
    print("\nComparing two time ranges...")
    now = time.time()
    range1 = (now - 100, now - 50)
    range2 = (now - 50, now)
    
    comparison = report_gen.compare_time_ranges(
        log_file=str(log_file),
        range1=range1,
        range2=range2
    )
    
    # Verify comparison structure
    assert 'range1' in comparison
    assert 'range2' in comparison
    assert 'differences' in comparison
    
    # Verify metrics are calculated
    assert 'metrics' in comparison['range1']
    assert 'metrics' in comparison['range2']
    
    # Verify differences are calculated
    diffs = comparison['differences']
    assert 'packet_rate_change' in diffs
    assert 'avg_rssi_change' in diffs
    assert 'avg_snr_change' in diffs
    
    print(f"✓ Range 1 records: {comparison['range1']['metrics']['record_count']}")
    print(f"✓ Range 2 records: {comparison['range2']['metrics']['record_count']}")
    print(f"✓ Packet rate change: {diffs['packet_rate_change']:.2f} pps")
    
    print("\n✅ Time range comparison tests passed!")


def main():
    """Run all validation tests"""
    print("\n" + "*" * 80)
    print("REPORT GENERATOR VALIDATION")
    print("*" * 80)
    
    try:
        # Create temporary directory for test files
        temp_dir = Path(tempfile.mkdtemp())
        print(f"\nUsing temporary directory: {temp_dir}")
        
        # Create sample data
        sample_data = create_sample_data()
        
        # Save sample data to JSON file
        log_file = temp_dir / 'test_log.json'
        with open(log_file, 'w') as f:
            json.dump(sample_data, f)
        print(f"Sample data saved to: {log_file}")
        
        # Create report generator with mock components
        validation_engine = ValidationEngine()
        metrics_calculator = MetricsCalculator()
        report_gen = ReportGenerator(
            validation_engine=validation_engine,
            metrics_calculator=metrics_calculator
        )
        
        # Run all tests
        test_report_generation(report_gen, temp_dir)
        test_csv_export(report_gen, log_file, temp_dir)
        test_json_export(report_gen, log_file, temp_dir)
        test_query_tools(report_gen, log_file)
        test_log_summary(report_gen, log_file)
        test_time_range_comparison(report_gen, log_file)
        
        print("\n" + "=" * 80)
        print("✅ ALL VALIDATION TESTS PASSED!")
        print("=" * 80)
        print(f"\nTest files saved in: {temp_dir}")
        print("You can inspect the generated reports and exports.")
        
        return 0
        
    except AssertionError as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
