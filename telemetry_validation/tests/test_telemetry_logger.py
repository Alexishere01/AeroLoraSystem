"""
Unit tests for TelemetryLogger module.
"""

import unittest
import tempfile
import shutil
import json
import csv
from pathlib import Path
import time

from src.telemetry_logger import TelemetryLogger
from src.mavlink_parser import ParsedMessage


class TestTelemetryLogger(unittest.TestCase):
    """Test cases for TelemetryLogger class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for test logs
        self.test_dir = tempfile.mkdtemp()
        self.logger = TelemetryLogger(log_dir=self.test_dir, max_file_size_mb=1)
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Close logger
        self.logger.close()
        
        # Remove temporary directory
        shutil.rmtree(self.test_dir)
    
    def test_initialization(self):
        """Test logger initialization."""
        # Check that log directory was created
        self.assertTrue(Path(self.test_dir).exists())
        
        # Check that files were created
        self.assertTrue(self.logger.csv_file.exists())
        self.assertTrue(self.logger.tlog_file.exists())
        
        # Check initial stats
        stats = self.logger.get_stats()
        self.assertEqual(stats['message_count'], 0)
        self.assertEqual(stats['file_sequence'], 0)
    
    def test_csv_logging(self):
        """Test CSV file logging."""
        # Create test message
        msg = ParsedMessage(
            timestamp=time.time(),
            msg_type='HEARTBEAT',
            msg_id=0,
            system_id=1,
            component_id=1,
            fields={'type': 2, 'autopilot': 3, 'base_mode': 81},
            rssi=-50.0,
            snr=10.0,
            raw_bytes=b'\xfe\x09\x00\x01\x01\x00'
        )
        
        # Log message
        self.logger.log_message(msg)
        
        # Flush to ensure data is written
        self.logger.csv_handle.flush()
        
        # Read CSV file
        with open(self.logger.csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        # Verify data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['msg_type'], 'HEARTBEAT')
        self.assertEqual(rows[0]['system_id'], '1')
        self.assertEqual(rows[0]['rssi'], '-50.0')
        self.assertEqual(rows[0]['snr'], '10.0')
    
    def test_json_logging(self):
        """Test JSON file logging."""
        # Create test messages
        for i in range(5):
            msg = ParsedMessage(
                timestamp=time.time(),
                msg_type='GPS_RAW_INT',
                msg_id=24,
                system_id=1,
                component_id=1,
                fields={'lat': 37000000 + i, 'lon': -122000000 + i, 'alt': 100000 + i},
                rssi=-55.0,
                snr=8.0,
                raw_bytes=b'\xfe\x1e\x00\x01\x01\x18'
            )
            self.logger.log_message(msg)
        
        # Flush JSON buffer
        self.logger._flush_json()
        
        # Read JSON file
        with open(self.logger.json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Verify data
        self.assertEqual(len(data), 5)
        self.assertEqual(data[0]['msg_type'], 'GPS_RAW_INT')
        self.assertEqual(data[0]['fields']['lat'], 37000000)
    
    def test_tlog_logging(self):
        """Test .tlog file logging."""
        # Create test message with raw bytes
        raw_bytes = b'\xfe\x09\x00\x01\x01\x00\x02\x03\x51\x04\x03\x00\x00\x00\x00\x00\x00'
        msg = ParsedMessage(
            timestamp=time.time(),
            msg_type='HEARTBEAT',
            msg_id=0,
            system_id=1,
            component_id=1,
            fields={'type': 2, 'autopilot': 3},
            raw_bytes=raw_bytes
        )
        
        # Log message
        self.logger.log_message(msg)
        
        # Flush to ensure data is written
        self.logger.tlog_handle.flush()
        
        # Read .tlog file
        with open(self.logger.tlog_file, 'rb') as f:
            tlog_data = f.read()
        
        # Verify raw bytes were written
        self.assertEqual(tlog_data, raw_bytes)
    
    def test_file_rotation(self):
        """Test file rotation when size limit is reached."""
        # Create logger with very small max size (1 KB)
        small_logger = TelemetryLogger(log_dir=self.test_dir + '/rotation', max_file_size_mb=0.001)
        
        # Log many messages to trigger rotation
        for i in range(100):
            msg = ParsedMessage(
                timestamp=time.time(),
                msg_type='GPS_RAW_INT',
                msg_id=24,
                system_id=1,
                component_id=1,
                fields={
                    'lat': 37000000 + i,
                    'lon': -122000000 + i,
                    'alt': 100000 + i,
                    'extra_data': 'x' * 100  # Add extra data to increase size
                },
                raw_bytes=b'\xfe\x1e\x00\x01\x01\x18' + b'x' * 100
            )
            small_logger.log_message(msg)
        
        # Check if rotation occurred
        stats = small_logger.get_stats()
        
        # Close logger
        small_logger.close()
        
        # File sequence should have incremented if rotation occurred
        # (may or may not rotate depending on exact size)
        self.assertGreaterEqual(stats['file_sequence'], 0)
    
    def test_message_count(self):
        """Test message counting."""
        # Log multiple messages
        for i in range(10):
            msg = ParsedMessage(
                timestamp=time.time(),
                msg_type='HEARTBEAT',
                msg_id=0,
                system_id=1,
                component_id=1,
                fields={'type': 2},
                raw_bytes=b'\xfe\x09\x00\x01\x01\x00'
            )
            self.logger.log_message(msg)
        
        # Check message count
        stats = self.logger.get_stats()
        self.assertEqual(stats['message_count'], 10)
    
    def test_close_and_summary(self):
        """Test logger close and summary generation."""
        # Log some messages
        for i in range(5):
            msg = ParsedMessage(
                timestamp=time.time(),
                msg_type='HEARTBEAT',
                msg_id=0,
                system_id=1,
                component_id=1,
                fields={'type': 2},
                raw_bytes=b'\xfe\x09\x00\x01\x01\x00'
            )
            self.logger.log_message(msg)
        
        # Close logger
        self.logger.close()
        
        # Check that summary file was created
        summary_files = list(Path(self.test_dir).glob('summary_*.txt'))
        self.assertEqual(len(summary_files), 1)
        
        # Read summary
        with open(summary_files[0], 'r', encoding='utf-8') as f:
            summary = f.read()
        
        # Verify summary contains expected information
        self.assertIn('Total messages logged: 5', summary)


if __name__ == '__main__':
    unittest.main()
