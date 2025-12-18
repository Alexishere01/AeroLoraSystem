#!/usr/bin/env python3
"""
Integration test for enhanced visualizer with CSV loading.

This test creates sample CSV files in both enhanced and legacy formats,
then tests the visualizer's ability to load and display them correctly.
"""

import sys
import os
import csv
import tempfile

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from csv_utils import load_flight_log, detect_csv_format
from visualizer import TelemetryVisualizer, VisualizerConfig
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_enhanced_csv(filename):
    """Create a sample enhanced format CSV file."""
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Write header (12 fields)
        writer.writerow([
            'timestamp_ms', 'sequence_number', 'message_id', 'system_id',
            'rssi_dbm', 'snr_db', 'relay_active', 'event',
            'packet_size', 'tx_timestamp', 'queue_depth', 'errors'
        ])
        
        # Write sample data
        for i in range(50):
            writer.writerow([
                i * 1000,  # timestamp_ms
                i,  # sequence_number
                24,  # message_id (GPS_RAW_INT)
                1,  # system_id
                -75.0 - (i % 15),  # rssi_dbm
                8.0 + (i % 5),  # snr_db
                0,  # relay_active
                'TX',  # event
                48 + (i % 10),  # packet_size
                (i - 1) * 1000 if i > 0 else 0,  # tx_timestamp
                i % 25,  # queue_depth (some > 20)
                i // 5  # errors (cumulative)
            ])
    
    logger.info(f"Created enhanced CSV: {filename}")


def create_legacy_csv(filename):
    """Create a sample legacy format CSV file."""
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Write header (8 fields)
        writer.writerow([
            'timestamp_ms', 'sequence_number', 'message_id', 'system_id',
            'rssi_dbm', 'snr_db', 'relay_active', 'event'
        ])
        
        # Write sample data
        for i in range(50):
            writer.writerow([
                i * 1000,  # timestamp_ms
                i,  # sequence_number
                24,  # message_id
                1,  # system_id
                -75.0 - (i % 15),  # rssi_dbm
                8.0 + (i % 5),  # snr_db
                0,  # relay_active
                'TX'  # event
            ])
    
    logger.info(f"Created legacy CSV: {filename}")


def test_csv_format_detection():
    """Test CSV format detection."""
    logger.info("\n=== Testing CSV Format Detection ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test enhanced format
        enhanced_file = os.path.join(tmpdir, 'enhanced.csv')
        create_enhanced_csv(enhanced_file)
        
        with open(enhanced_file, 'r') as f:
            header = f.readline()
            format_type = detect_csv_format(header)
            assert format_type == 'enhanced', f"Expected 'enhanced', got '{format_type}'"
            logger.info(f"✓ Enhanced format detected correctly")
        
        # Test legacy format
        legacy_file = os.path.join(tmpdir, 'legacy.csv')
        create_legacy_csv(legacy_file)
        
        with open(legacy_file, 'r') as f:
            header = f.readline()
            format_type = detect_csv_format(header)
            assert format_type == 'legacy', f"Expected 'legacy', got '{format_type}'"
            logger.info(f"✓ Legacy format detected correctly")
    
    return True


def test_csv_loading():
    """Test CSV loading with both formats."""
    logger.info("\n=== Testing CSV Loading ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test enhanced format loading
        enhanced_file = os.path.join(tmpdir, 'enhanced.csv')
        create_enhanced_csv(enhanced_file)
        
        entries, format_type = load_flight_log(enhanced_file)
        assert format_type == 'enhanced', f"Expected 'enhanced', got '{format_type}'"
        assert len(entries) == 50, f"Expected 50 entries, got {len(entries)}"
        assert entries[0].packet_size > 0, "Enhanced format should have packet_size"
        assert entries[0].tx_timestamp >= 0, "Enhanced format should have tx_timestamp"
        assert entries[0].queue_depth >= 0, "Enhanced format should have queue_depth"
        assert entries[0].errors >= 0, "Enhanced format should have errors"
        logger.info(f"✓ Enhanced CSV loaded: {len(entries)} entries")
        
        # Test legacy format loading
        legacy_file = os.path.join(tmpdir, 'legacy.csv')
        create_legacy_csv(legacy_file)
        
        entries, format_type = load_flight_log(legacy_file)
        assert format_type == 'legacy', f"Expected 'legacy', got '{format_type}'"
        assert len(entries) == 50, f"Expected 50 entries, got {len(entries)}"
        assert entries[0].packet_size == 0, "Legacy format should have packet_size=0"
        assert entries[0].tx_timestamp == 0, "Legacy format should have tx_timestamp=0"
        assert entries[0].queue_depth == 0, "Legacy format should have queue_depth=0"
        assert entries[0].errors == 0, "Legacy format should have errors=0"
        logger.info(f"✓ Legacy CSV loaded: {len(entries)} entries with defaults")
    
    return True


def test_visualizer_with_enhanced_format():
    """Test visualizer with enhanced format CSV."""
    logger.info("\n=== Testing Visualizer with Enhanced Format ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        enhanced_file = os.path.join(tmpdir, 'enhanced.csv')
        create_enhanced_csv(enhanced_file)
        
        # Load entries
        entries, format_type = load_flight_log(enhanced_file)
        
        # Initialize visualizer
        config = VisualizerConfig(window_title="Enhanced Format Test")
        visualizer = TelemetryVisualizer(config)
        visualizer.initialize_plots()
        
        # Test all enhanced visualization methods
        visualizer.update_throughput_plot(entries)
        logger.info("✓ Throughput plot rendered")
        
        visualizer.update_latency_plot(entries)
        logger.info("✓ Latency plot rendered")
        
        visualizer.update_queue_depth_plot(entries)
        logger.info("✓ Queue depth plot rendered")
        
        visualizer.update_error_rate_plot(entries)
        logger.info("✓ Error rate plot rendered")
    
    return True


def test_visualizer_with_legacy_format():
    """Test visualizer with legacy format CSV."""
    logger.info("\n=== Testing Visualizer with Legacy Format ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        legacy_file = os.path.join(tmpdir, 'legacy.csv')
        create_legacy_csv(legacy_file)
        
        # Load entries
        entries, format_type = load_flight_log(legacy_file)
        
        # Initialize visualizer
        config = VisualizerConfig(window_title="Legacy Format Test")
        visualizer = TelemetryVisualizer(config)
        visualizer.initialize_plots()
        
        # Test all visualization methods with legacy data
        # Should show "no data" messages gracefully
        visualizer.update_throughput_plot(entries)
        logger.info("✓ Throughput plot handled legacy format")
        
        visualizer.update_latency_plot(entries)
        logger.info("✓ Latency plot handled legacy format")
        
        visualizer.update_queue_depth_plot(entries)
        logger.info("✓ Queue depth plot handled legacy format")
        
        visualizer.update_error_rate_plot(entries)
        logger.info("✓ Error rate plot handled legacy format")
    
    return True


def run_all_tests():
    """Run all integration tests."""
    tests = [
        ("Format Detection", test_csv_format_detection),
        ("CSV Loading", test_csv_loading),
        ("Enhanced Format Visualization", test_visualizer_with_enhanced_format),
        ("Legacy Format Visualization", test_visualizer_with_legacy_format),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            logger.info(f"\nRunning: {test_name}")
            if test_func():
                passed += 1
                logger.info(f"✓ {test_name} PASSED")
        except Exception as e:
            failed += 1
            logger.error(f"✗ {test_name} FAILED: {e}")
            import traceback
            traceback.print_exc()
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Test Results: {passed} passed, {failed} failed")
    logger.info(f"{'='*60}")
    
    return failed == 0


if __name__ == '__main__':
    try:
        success = run_all_tests()
        if success:
            logger.info("\n✓ All integration tests passed!")
            sys.exit(0)
        else:
            logger.error("\n✗ Some tests failed!")
            sys.exit(1)
    except Exception as e:
        logger.error(f"\n✗ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
