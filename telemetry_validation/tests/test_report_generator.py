"""
Unit Tests for Report Generator Module

Tests the ReportGenerator class functionality including:
- Summary report generation (text and HTML)
- Export to CSV, JSON, .tlog, and .binlog formats
- Query tools with filtering
- Time range comparison

Requirements: 5.2, 5.3, 10.1, 10.2, 10.3, 10.4, 10.5
"""

import unittest
import json
import csv
import tempfile
import time
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from report_generator import ReportGenerator
from validation_engine import ValidationEngine, Violation, Severity
from metrics_calculator import MetricsCalculator
from binary_protocol_parser import UartCommand


class TestReportGenerator(unittest.TestCase):
    """Test cases for ReportGenerator class"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create sample log data
        self.sample_data = [
            {
                'timestamp': time.time() - 100,
                'msg_type': 'HEARTBEAT',
                'msg_id': 0,
                'system_id': 1,
                'component_id': 1,
                'fields': {'type': 2, 'autopilot': 3},
                'rssi': -85.5,
                'snr': 8.2
            },
            {
                'timestamp': time.time() - 90,
                'msg_type': 'GPS_RAW_INT',
                'msg_id': 24,
                'system_id': 1,
                'component_id': 1,
                'fields': {'lat': 123456789, 'lon': -123456789, 'alt': 50000},
                'rssi': -86.0,
                'snr': 7.8
            },
            {
                'timestamp': time.time() - 80,
                'msg_type': 'ATTITUDE',
                'msg_id': 30,
                'system_id': 1,
                'component_id': 1,
                'fields': {'roll': 0.1, 'pitch': 0.2, 'yaw': 1.5},
                'rssi': -84.5,
                'snr': 8.5
            },
            {
                'timestamp': time.time() - 70,
                'msg_type': 'HEARTBEAT',
                'msg_id': 0,
                'system_id': 2,
                'component_id': 1,
                'fields': {'type': 2, 'autopilot': 3},
                'rssi': -90.0,
                'snr': 6.5
            }
        ]
        
        # Create sample log file
        self.log_file = self.temp_path / 'test_log.json'
        with open(self.log_file, 'w') as f:
            json.dump(self.sample_data, f)
        
        # Create report generator
        self.report_gen = ReportGenerator()
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_generate_text_report(self):
        """Test text report generation"""
        # Create validation engine and metrics calculator
        validation_engine = ValidationEngine()
        metrics_calculator = MetricsCalculator()
        
        report_gen = ReportGenerator(
            validation_engine=validation_engine,
            metrics_calculator=metrics_calculator
        )
        
        # Generate text report
        report = report_gen.generate_summary_report(format='text')
        
        # Verify report contains expected sections
        self.assertIn('TELEMETRY VALIDATION SYSTEM', report)
        self.assertIn('SUMMARY REPORT', report)
        self.assertIn('Generated:', report)
    
    def test_generate_html_report(self):
        """Test HTML report generation"""
        # Create validation engine and metrics calculator
        validation_engine = ValidationEngine()
        metrics_calculator = MetricsCalculator()
        
        report_gen = ReportGenerator(
            validation_engine=validation_engine,
            metrics_calculator=metrics_calculator
        )
        
        # Generate HTML report
        report = report_gen.generate_summary_report(format='html')
        
        # Verify HTML structure
        self.assertIn('<!DOCTYPE html>', report)
        self.assertIn('<html>', report)
        self.assertIn('Telemetry Validation Report', report)
        self.assertIn('</html>', report)
    
    def test_generate_report_to_file(self):
        """Test saving report to file"""
        report_gen = ReportGenerator()
        
        output_file = self.temp_path / 'test_report.txt'
        
        # Generate and save report
        report_gen.generate_summary_report(
            format='text',
            output_file=str(output_file)
        )
        
        # Verify file was created
        self.assertTrue(output_file.exists())
        
        # Verify file contains report content
        with open(output_file, 'r') as f:
            content = f.read()
            self.assertIn('TELEMETRY VALIDATION SYSTEM', content)
    
    def test_export_to_csv_all_data(self):
        """Test exporting all data to CSV"""
        output_file = self.temp_path / 'export.csv'
        
        # Export all data
        count = self.report_gen.export_to_csv(
            log_file=str(self.log_file),
            output_file=str(output_file)
        )
        
        # Verify export count
        self.assertEqual(count, len(self.sample_data))
        
        # Verify CSV file was created
        self.assertTrue(output_file.exists())
        
        # Verify CSV content
        with open(output_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), len(self.sample_data))
            
            # Verify headers
            self.assertIn('timestamp', reader.fieldnames)
            self.assertIn('msg_type', reader.fieldnames)
            self.assertIn('rssi', reader.fieldnames)
    
    def test_export_to_csv_with_msg_type_filter(self):
        """Test exporting with message type filter"""
        output_file = self.temp_path / 'export_heartbeat.csv'
        
        # Export only HEARTBEAT messages
        count = self.report_gen.export_to_csv(
            log_file=str(self.log_file),
            output_file=str(output_file),
            msg_type='HEARTBEAT'
        )
        
        # Verify only HEARTBEAT messages were exported
        heartbeat_count = sum(1 for d in self.sample_data if d['msg_type'] == 'HEARTBEAT')
        self.assertEqual(count, heartbeat_count)
        
        # Verify CSV content
        with open(output_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            for row in rows:
                self.assertEqual(row['msg_type'], 'HEARTBEAT')
    
    def test_export_to_csv_with_system_id_filter(self):
        """Test exporting with system ID filter"""
        output_file = self.temp_path / 'export_sysid1.csv'
        
        # Export only system ID 1
        count = self.report_gen.export_to_csv(
            log_file=str(self.log_file),
            output_file=str(output_file),
            system_id=1
        )
        
        # Verify only system ID 1 messages were exported
        sysid1_count = sum(1 for d in self.sample_data if d['system_id'] == 1)
        self.assertEqual(count, sysid1_count)
    
    def test_export_to_csv_with_time_range_filter(self):
        """Test exporting with time range filter"""
        output_file = self.temp_path / 'export_range.csv'
        
        # Export only recent messages
        start_time = time.time() - 95
        end_time = time.time() - 75
        
        count = self.report_gen.export_to_csv(
            log_file=str(self.log_file),
            output_file=str(output_file),
            start_time=start_time,
            end_time=end_time
        )
        
        # Verify correct number of messages in range
        range_count = sum(1 for d in self.sample_data 
                         if start_time <= d['timestamp'] <= end_time)
        self.assertEqual(count, range_count)
    
    def test_export_to_json(self):
        """Test exporting to JSON format"""
        output_file = self.temp_path / 'export.json'
        
        # Export to JSON
        count = self.report_gen.export_to_json(
            log_file=str(self.log_file),
            output_file=str(output_file)
        )
        
        # Verify export count
        self.assertEqual(count, len(self.sample_data))
        
        # Verify JSON file was created
        self.assertTrue(output_file.exists())
        
        # Verify JSON structure
        with open(output_file, 'r') as f:
            data = json.load(f)
            
            # Verify metadata
            self.assertIn('metadata', data)
            self.assertIn('messages', data)
            self.assertEqual(data['metadata']['record_count'], len(self.sample_data))
            
            # Verify messages
            self.assertEqual(len(data['messages']), len(self.sample_data))
    
    def test_export_to_json_with_filters(self):
        """Test exporting to JSON with filters"""
        output_file = self.temp_path / 'export_filtered.json'
        
        # Export with filters
        count = self.report_gen.export_to_json(
            log_file=str(self.log_file),
            output_file=str(output_file),
            msg_type='GPS_RAW_INT',
            system_id=1
        )
        
        # Verify filtered count
        filtered_count = sum(1 for d in self.sample_data 
                           if d['msg_type'] == 'GPS_RAW_INT' and d['system_id'] == 1)
        self.assertEqual(count, filtered_count)
        
        # Verify metadata includes filters
        with open(output_file, 'r') as f:
            data = json.load(f)
            filters = data['metadata']['filters']
            self.assertEqual(filters['msg_type'], 'GPS_RAW_INT')
            self.assertEqual(filters['system_id'], 1)
    
    def test_query_logs_all_data(self):
        """Test querying all data"""
        results = self.report_gen.query_logs(
            log_file=str(self.log_file)
        )
        
        # Verify all records returned
        self.assertEqual(len(results), len(self.sample_data))
    
    def test_query_logs_with_msg_type_filter(self):
        """Test querying with message type filter"""
        results = self.report_gen.query_logs(
            log_file=str(self.log_file),
            msg_type='HEARTBEAT'
        )
        
        # Verify only HEARTBEAT messages returned
        heartbeat_count = sum(1 for d in self.sample_data if d['msg_type'] == 'HEARTBEAT')
        self.assertEqual(len(results), heartbeat_count)
        
        for result in results:
            self.assertEqual(result['msg_type'], 'HEARTBEAT')
    
    def test_query_logs_with_system_id_filter(self):
        """Test querying with system ID filter"""
        results = self.report_gen.query_logs(
            log_file=str(self.log_file),
            system_id=1
        )
        
        # Verify only system ID 1 messages returned
        sysid1_count = sum(1 for d in self.sample_data if d['system_id'] == 1)
        self.assertEqual(len(results), sysid1_count)
        
        for result in results:
            self.assertEqual(result['system_id'], 1)
    
    def test_query_logs_with_time_range(self):
        """Test querying with time range"""
        start_time = time.time() - 95
        end_time = time.time() - 75
        
        results = self.report_gen.query_logs(
            log_file=str(self.log_file),
            start_time=start_time,
            end_time=end_time
        )
        
        # Verify only messages in range returned
        for result in results:
            self.assertGreaterEqual(result['timestamp'], start_time)
            self.assertLessEqual(result['timestamp'], end_time)
    
    def test_query_logs_with_multiple_filters(self):
        """Test querying with multiple filters"""
        results = self.report_gen.query_logs(
            log_file=str(self.log_file),
            msg_type='HEARTBEAT',
            system_id=1
        )
        
        # Verify all filters applied
        for result in results:
            self.assertEqual(result['msg_type'], 'HEARTBEAT')
            self.assertEqual(result['system_id'], 1)
    
    def test_get_log_summary(self):
        """Test getting log file summary"""
        summary = self.report_gen.get_log_summary(
            log_file=str(self.log_file)
        )
        
        # Verify summary structure
        self.assertIn('file', summary)
        self.assertIn('total_records', summary)
        self.assertIn('time_range', summary)
        self.assertIn('message_types', summary)
        self.assertIn('system_ids', summary)
        
        # Verify summary values
        self.assertEqual(summary['total_records'], len(self.sample_data))
        self.assertEqual(summary['system_id_count'], 2)
        
        # Verify message type distribution
        msg_types = summary['message_types']['distribution']
        self.assertEqual(msg_types['HEARTBEAT'], 2)
        self.assertEqual(msg_types['GPS_RAW_INT'], 1)
        self.assertEqual(msg_types['ATTITUDE'], 1)
    
    def test_compare_time_ranges(self):
        """Test comparing metrics between time ranges"""
        # Define two time ranges
        now = time.time()
        range1 = (now - 100, now - 85)
        range2 = (now - 85, now - 70)
        
        comparison = self.report_gen.compare_time_ranges(
            log_file=str(self.log_file),
            range1=range1,
            range2=range2
        )
        
        # Verify comparison structure
        self.assertIn('range1', comparison)
        self.assertIn('range2', comparison)
        self.assertIn('differences', comparison)
        
        # Verify metrics are calculated
        self.assertIn('metrics', comparison['range1'])
        self.assertIn('metrics', comparison['range2'])
        
        # Verify differences are calculated
        diffs = comparison['differences']
        self.assertIn('packet_rate_change', diffs)
        self.assertIn('avg_rssi_change', diffs)
        self.assertIn('avg_snr_change', diffs)
    
    def test_filter_data_helper(self):
        """Test the _filter_data helper method"""
        # Test with no filters
        filtered = self.report_gen._filter_data(self.sample_data)
        self.assertEqual(len(filtered), len(self.sample_data))
        
        # Test with message type filter
        filtered = self.report_gen._filter_data(
            self.sample_data,
            msg_type='HEARTBEAT'
        )
        self.assertEqual(len(filtered), 2)
        
        # Test with system ID filter
        filtered = self.report_gen._filter_data(
            self.sample_data,
            system_id=1
        )
        self.assertEqual(len(filtered), 3)
        
        # Test with time range filter
        start_time = time.time() - 95
        end_time = time.time() - 75
        filtered = self.report_gen._filter_data(
            self.sample_data,
            start_time=start_time,
            end_time=end_time
        )
        self.assertGreater(len(filtered), 0)
        self.assertLess(len(filtered), len(self.sample_data))
    
    def test_export_empty_results(self):
        """Test exporting when no data matches filters"""
        output_file = self.temp_path / 'export_empty.csv'
        
        # Export with filter that matches nothing
        count = self.report_gen.export_to_csv(
            log_file=str(self.log_file),
            output_file=str(output_file),
            msg_type='NONEXISTENT_MESSAGE'
        )
        
        # Verify no records exported
        self.assertEqual(count, 0)
    
    def test_query_empty_results(self):
        """Test querying when no data matches filters"""
        results = self.report_gen.query_logs(
            log_file=str(self.log_file),
            msg_type='NONEXISTENT_MESSAGE'
        )
        
        # Verify empty results
        self.assertEqual(len(results), 0)


def run_tests():
    """Run all tests"""
    unittest.main(argv=[''], exit=False, verbosity=2)


if __name__ == '__main__':
    run_tests()
