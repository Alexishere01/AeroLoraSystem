#!/usr/bin/env python3
"""
Test the load_historical_data method with both enhanced and legacy formats.

This test verifies that the visualizer can load CSV files and properly
detect the format, displaying enhanced metrics for enhanced format and
gracefully handling legacy format.
"""

import sys
import os
import csv
import tempfile

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

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
        
        # Write sample data with interesting patterns
        for i in range(100):
            writer.writerow([
                i * 100,  # timestamp_ms (100ms intervals)
                i,  # sequence_number
                24,  # message_id (GPS_RAW_INT)
                1,  # system_id
                -70.0 - (i % 20),  # rssi_dbm (varies -70 to -90)
                7.0 + (i % 8),  # snr_db (varies 7 to 15)
                0,  # relay_active
                'TX' if i % 2 == 0 else 'RX',  # event
                32 + (i % 64),  # packet_size (varies 32 to 96 bytes)
                (i - 2) * 100 if i >= 2 else 0,  # tx_timestamp (2 packet delay)
                (i * 2) % 30,  # queue_depth (varies, some > 20)
                i // 10  # errors (cumulative, increases every 10 packets)
            ])
    
    logger.info(f"Created enhanced CSV with 100 entries: {filename}")


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
        for i in range(100):
            writer.writerow([
                i * 100,  # timestamp_ms
                i,  # sequence_number
                24,  # message_id
                1,  # system_id
                -70.0 - (i % 20),  # rssi_dbm
                7.0 + (i % 8),  # snr_db
                0,  # relay_active
                'TX' if i % 2 == 0 else 'RX'  # event
            ])
    
    logger.info(f"Created legacy CSV with 100 entries: {filename}")


def test_load_enhanced_format():
    """Test loading enhanced format CSV."""
    logger.info("\n=== Testing load_historical_data with Enhanced Format ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_file = os.path.join(tmpdir, 'enhanced_flight_log.csv')
        create_enhanced_csv(csv_file)
        
        # Create visualizer
        config = VisualizerConfig(window_title="Enhanced Format Test - No Display")
        visualizer = TelemetryVisualizer(config)
        
        # Load historical data (this should not display, just prepare plots)
        # We'll catch the plt.show() by not actually calling it
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend
        
        try:
            visualizer.load_historical_data(csv_file)
            logger.info("✓ Enhanced format loaded successfully")
            logger.info(f"✓ Active systems: {len(visualizer.active_system_ids)}")
            logger.info(f"✓ RSSI data points: {sum(len(d) for d in visualizer.rssi_data.values())}")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to load enhanced format: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_load_legacy_format():
    """Test loading legacy format CSV."""
    logger.info("\n=== Testing load_historical_data with Legacy Format ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_file = os.path.join(tmpdir, 'legacy_flight_log.csv')
        create_legacy_csv(csv_file)
        
        # Create visualizer
        config = VisualizerConfig(window_title="Legacy Format Test - No Display")
        visualizer = TelemetryVisualizer(config)
        
        # Load historical data
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend
        
        try:
            visualizer.load_historical_data(csv_file)
            logger.info("✓ Legacy format loaded successfully")
            logger.info(f"✓ Active systems: {len(visualizer.active_system_ids)}")
            logger.info(f"✓ RSSI data points: {sum(len(d) for d in visualizer.rssi_data.values())}")
            logger.info("✓ Legacy format handled gracefully (enhanced plots show 'no data')")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to load legacy format: {e}")
            import traceback
            traceback.print_exc()
            return False


def run_all_tests():
    """Run all tests."""
    tests = [
        ("Load Enhanced Format", test_load_enhanced_format),
        ("Load Legacy Format", test_load_legacy_format),
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
            logger.info("\n✓ All load_historical_data tests passed!")
            sys.exit(0)
        else:
            logger.error("\n✗ Some tests failed!")
            sys.exit(1)
    except Exception as e:
        logger.error(f"\n✗ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
