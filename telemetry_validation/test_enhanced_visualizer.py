#!/usr/bin/env python3
"""
Test script for enhanced visualizer functionality.

This script tests the new enhanced metric visualizations including:
- Throughput plotting
- Latency distribution
- Queue depth monitoring
- Error rate correlation
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from csv_utils import EnhancedLogEntry
from visualizer import TelemetryVisualizer, VisualizerConfig
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_test_entries():
    """Create test entries with enhanced format data."""
    entries = []
    
    # Create 100 test entries with varying metrics
    for i in range(100):
        entry = EnhancedLogEntry(
            timestamp_ms=i * 1000,  # 1 second intervals
            sequence_number=i,
            message_id=24,  # GPS_RAW_INT
            system_id=1,
            rssi_dbm=-75.0 - (i % 20),  # Varying RSSI
            snr_db=8.0 + (i % 5),
            relay_active=False,
            event='TX',
            packet_size=48 + (i % 10),  # Varying packet sizes
            tx_timestamp=(i - 1) * 1000 if i > 0 else 0,  # Previous timestamp
            queue_depth=i % 25,  # Queue depth varies, some > 20
            errors=i // 10  # Cumulative errors
        )
        entries.append(entry)
    
    return entries


def test_enhanced_visualizations():
    """Test enhanced visualization methods."""
    logger.info("Creating test entries...")
    entries = create_test_entries()
    
    logger.info("Initializing visualizer...")
    config = VisualizerConfig(
        update_rate_hz=1.0,
        history_seconds=120,
        window_title="Enhanced Visualizer Test"
    )
    visualizer = TelemetryVisualizer(config)
    visualizer.initialize_plots()
    
    logger.info("Testing throughput visualization...")
    visualizer.update_throughput_plot(entries)
    
    logger.info("Testing latency visualization...")
    visualizer.update_latency_plot(entries)
    
    logger.info("Testing queue depth visualization...")
    visualizer.update_queue_depth_plot(entries)
    
    logger.info("Testing error rate visualization...")
    visualizer.update_error_rate_plot(entries)
    
    logger.info("All visualization methods executed successfully!")
    
    # Test with empty entries (legacy format simulation)
    logger.info("\nTesting legacy format handling...")
    visualizer.update_throughput_plot([])
    visualizer.update_latency_plot([])
    visualizer.update_queue_depth_plot([])
    visualizer.update_error_rate_plot([])
    
    logger.info("Legacy format handling successful!")
    
    return True


if __name__ == '__main__':
    try:
        success = test_enhanced_visualizations()
        if success:
            logger.info("\n✓ All tests passed!")
            sys.exit(0)
        else:
            logger.error("\n✗ Tests failed!")
            sys.exit(1)
    except Exception as e:
        logger.error(f"\n✗ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
