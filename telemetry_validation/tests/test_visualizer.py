#!/usr/bin/env python3
"""
Unit tests for the Telemetry Visualizer module.

Tests the visualizer's data management, multi-drone support, violation
highlighting, and configuration.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
"""

import unittest
import sys
import os
import time
from collections import deque

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from visualizer import (
    TelemetryVisualizer, 
    VisualizerConfig, 
    MetricDataPoint
)
from metrics_calculator import TelemetryMetrics
from validation_engine import Violation, Severity


class TestVisualizerConfig(unittest.TestCase):
    """Test VisualizerConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = VisualizerConfig()
        
        self.assertEqual(config.update_rate_hz, 1.0)
        self.assertEqual(config.history_seconds, 60)
        self.assertEqual(config.max_drones, 4)
        self.assertTrue(config.show_violations)
        self.assertIn("Telemetry", config.window_title)
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = VisualizerConfig(
            update_rate_hz=2.0,
            history_seconds=120,
            max_drones=8,
            show_violations=False,
            window_title="Custom Title"
        )
        
        self.assertEqual(config.update_rate_hz, 2.0)
        self.assertEqual(config.history_seconds, 120)
        self.assertEqual(config.max_drones, 8)
        self.assertFalse(config.show_violations)
        self.assertEqual(config.window_title, "Custom Title")


class TestMetricDataPoint(unittest.TestCase):
    """Test MetricDataPoint dataclass."""
    
    def test_data_point_creation(self):
        """Test creating a metric data point."""
        timestamp = time.time()
        dp = MetricDataPoint(
            timestamp=timestamp,
            value=42.5,
            system_id=1,
            has_violation=False
        )
        
        self.assertEqual(dp.timestamp, timestamp)
        self.assertEqual(dp.value, 42.5)
        self.assertEqual(dp.system_id, 1)
        self.assertFalse(dp.has_violation)
    
    def test_data_point_defaults(self):
        """Test default values for data point."""
        dp = MetricDataPoint(timestamp=time.time(), value=10.0)
        
        self.assertEqual(dp.system_id, 0)
        self.assertFalse(dp.has_violation)


class TestTelemetryVisualizer(unittest.TestCase):
    """Test TelemetryVisualizer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = VisualizerConfig(
            update_rate_hz=1.0,
            history_seconds=10,
            max_drones=4
        )
        self.visualizer = TelemetryVisualizer(self.config)
    
    def test_initialization(self):
        """Test visualizer initialization."""
        self.assertIsNotNone(self.visualizer)
        self.assertEqual(self.visualizer.config.update_rate_hz, 1.0)
        self.assertEqual(self.visualizer.config.history_seconds, 10)
        self.assertEqual(len(self.visualizer.active_system_ids), 0)
        self.assertEqual(len(self.visualizer.violations), 0)
    
    def test_register_system_id(self):
        """Test registering new system IDs."""
        # Register first system
        self.visualizer._register_system_id(1)
        self.assertIn(1, self.visualizer.active_system_ids)
        self.assertIn(1, self.visualizer.system_colors)
        
        # Register second system
        self.visualizer._register_system_id(2)
        self.assertIn(2, self.visualizer.active_system_ids)
        self.assertIn(2, self.visualizer.system_colors)
        
        # Verify different colors
        self.assertNotEqual(
            self.visualizer.system_colors[1],
            self.visualizer.system_colors[2]
        )
    
    def test_max_drones_limit(self):
        """Test maximum drone limit."""
        # Register up to max_drones
        for i in range(1, self.config.max_drones + 1):
            self.visualizer._register_system_id(i)
        
        self.assertEqual(len(self.visualizer.active_system_ids), self.config.max_drones)
        
        # Try to register one more (should be rejected)
        initial_count = len(self.visualizer.active_system_ids)
        self.visualizer._register_system_id(self.config.max_drones + 1)
        self.assertEqual(len(self.visualizer.active_system_ids), initial_count)
    
    def test_update_data_single_system(self):
        """Test updating data for a single system."""
        system_id = 1
        
        # Create sample metrics
        metrics = TelemetryMetrics(
            binary_packet_rate_1s=10.0,
            binary_packet_rate_10s=9.5,
            binary_packet_rate_60s=9.0,
            mavlink_packet_rate_1s=5.0,
            mavlink_packet_rate_10s=4.8,
            mavlink_packet_rate_60s=4.5,
            avg_rssi=-75.0,
            avg_snr=12.0,
            drop_rate=2.5,
            packets_lost=10,
            packets_received=400,
            latency_avg=0.05,
            latency_min=0.01,
            latency_max=0.1,
            latency_samples=50,
            mavlink_msg_type_distribution={'HEARTBEAT': 100},
            binary_cmd_type_distribution={'CMD_BRIDGE_TX': 80},
            checksum_error_rate=1.0,
            parse_error_rate=0.5,
            protocol_success_rate=98.5,
            buffer_overflow_count=0,
            timeout_error_count=0,
            timestamp=time.time()
        )
        
        battery_voltage = 12.4
        
        # Update visualizer
        self.visualizer.update_data(metrics, system_id=system_id, battery_voltage=battery_voltage)
        
        # Verify system was registered
        self.assertIn(system_id, self.visualizer.active_system_ids)
        
        # Verify data was added
        self.assertIn(system_id, self.visualizer.rssi_data)
        self.assertEqual(len(self.visualizer.rssi_data[system_id]), 1)
        self.assertEqual(self.visualizer.rssi_data[system_id][0].value, -75.0)
        
        self.assertIn(system_id, self.visualizer.snr_data)
        self.assertEqual(len(self.visualizer.snr_data[system_id]), 1)
        self.assertEqual(self.visualizer.snr_data[system_id][0].value, 12.0)
        
        self.assertIn(system_id, self.visualizer.battery_voltage_data)
        self.assertEqual(len(self.visualizer.battery_voltage_data[system_id]), 1)
        self.assertEqual(self.visualizer.battery_voltage_data[system_id][0].value, 12.4)
        
        # Verify binary protocol health data
        self.assertEqual(len(self.visualizer.checksum_error_data), 1)
        self.assertEqual(self.visualizer.checksum_error_data[0].value, 1.0)
        
        self.assertEqual(len(self.visualizer.protocol_success_data), 1)
        self.assertEqual(self.visualizer.protocol_success_data[0].value, 98.5)
    
    def test_update_data_multiple_systems(self):
        """Test updating data for multiple systems."""
        # Create metrics for multiple systems
        for system_id in [1, 2, 3]:
            metrics = TelemetryMetrics(
                binary_packet_rate_1s=10.0,
                binary_packet_rate_10s=9.5,
                binary_packet_rate_60s=9.0,
                mavlink_packet_rate_1s=5.0,
                mavlink_packet_rate_10s=4.8,
                mavlink_packet_rate_60s=4.5,
                avg_rssi=-70.0 - (system_id * 5),  # Different RSSI per system
                avg_snr=10.0 + system_id,          # Different SNR per system
                drop_rate=2.5,
                packets_lost=10,
                packets_received=400,
                latency_avg=0.05,
                latency_min=0.01,
                latency_max=0.1,
                latency_samples=50,
                mavlink_msg_type_distribution={'HEARTBEAT': 100},
                binary_cmd_type_distribution={'CMD_BRIDGE_TX': 80},
                checksum_error_rate=1.0,
                parse_error_rate=0.5,
                protocol_success_rate=98.5,
                buffer_overflow_count=0,
                timeout_error_count=0,
                timestamp=time.time()
            )
            
            self.visualizer.update_data(metrics, system_id=system_id)
        
        # Verify all systems registered
        self.assertEqual(len(self.visualizer.active_system_ids), 3)
        
        # Verify data for each system
        for system_id in [1, 2, 3]:
            self.assertIn(system_id, self.visualizer.rssi_data)
            self.assertEqual(len(self.visualizer.rssi_data[system_id]), 1)
    
    def test_add_violation(self):
        """Test adding violations."""
        system_id = 1
        
        # Add some data first
        metrics = TelemetryMetrics(
            binary_packet_rate_1s=10.0,
            binary_packet_rate_10s=9.5,
            binary_packet_rate_60s=9.0,
            mavlink_packet_rate_1s=5.0,
            mavlink_packet_rate_10s=4.8,
            mavlink_packet_rate_60s=4.5,
            avg_rssi=-105.0,  # Bad RSSI
            avg_snr=12.0,
            drop_rate=2.5,
            packets_lost=10,
            packets_received=400,
            latency_avg=0.05,
            latency_min=0.01,
            latency_max=0.1,
            latency_samples=50,
            mavlink_msg_type_distribution={'HEARTBEAT': 100},
            binary_cmd_type_distribution={'CMD_BRIDGE_TX': 80},
            checksum_error_rate=1.0,
            parse_error_rate=0.5,
            protocol_success_rate=98.5,
            buffer_overflow_count=0,
            timeout_error_count=0,
            timestamp=time.time()
        )
        
        self.visualizer.update_data(metrics, system_id=system_id)
        
        # Create violation
        violation = Violation(
            timestamp=time.time(),
            rule_name="Low RSSI",
            msg_type="RADIO_STATUS",
            field="rssi",
            actual_value=-105.0,
            threshold=-100.0,
            severity=Severity.WARNING,
            description="RSSI below threshold",
            system_id=system_id
        )
        
        # Add violation
        self.visualizer.add_violation(violation)
        
        # Verify violation was added
        self.assertEqual(len(self.visualizer.violations), 1)
        self.assertEqual(self.visualizer.violations[0].rule_name, "Low RSSI")
        
        # Verify data point was marked
        self.assertTrue(self.visualizer.rssi_data[system_id][-1].has_violation)
    
    def test_data_deque_maxlen(self):
        """Test that data deques respect maxlen."""
        system_id = 1
        history_size = self.visualizer.history_size
        
        # Add more data points than history_size
        for i in range(history_size + 10):
            metrics = TelemetryMetrics(
                binary_packet_rate_1s=10.0,
                binary_packet_rate_10s=9.5,
                binary_packet_rate_60s=9.0,
                mavlink_packet_rate_1s=5.0,
                mavlink_packet_rate_10s=4.8,
                mavlink_packet_rate_60s=4.5,
                avg_rssi=-75.0,
                avg_snr=12.0,
                drop_rate=2.5,
                packets_lost=10,
                packets_received=400,
                latency_avg=0.05,
                latency_min=0.01,
                latency_max=0.1,
                latency_samples=50,
                mavlink_msg_type_distribution={'HEARTBEAT': 100},
                binary_cmd_type_distribution={'CMD_BRIDGE_TX': 80},
                checksum_error_rate=1.0,
                parse_error_rate=0.5,
                protocol_success_rate=98.5,
                buffer_overflow_count=0,
                timeout_error_count=0,
                timestamp=time.time()
            )
            
            self.visualizer.update_data(metrics, system_id=system_id)
        
        # Verify deque length doesn't exceed maxlen
        self.assertLessEqual(len(self.visualizer.rssi_data[system_id]), history_size)
        self.assertLessEqual(len(self.visualizer.snr_data[system_id]), history_size)
        self.assertLessEqual(len(self.visualizer.checksum_error_data), history_size)
    
    def test_clear_data(self):
        """Test clearing all data."""
        # Add some data
        system_id = 1
        metrics = TelemetryMetrics(
            binary_packet_rate_1s=10.0,
            binary_packet_rate_10s=9.5,
            binary_packet_rate_60s=9.0,
            mavlink_packet_rate_1s=5.0,
            mavlink_packet_rate_10s=4.8,
            mavlink_packet_rate_60s=4.5,
            avg_rssi=-75.0,
            avg_snr=12.0,
            drop_rate=2.5,
            packets_lost=10,
            packets_received=400,
            latency_avg=0.05,
            latency_min=0.01,
            latency_max=0.1,
            latency_samples=50,
            mavlink_msg_type_distribution={'HEARTBEAT': 100},
            binary_cmd_type_distribution={'CMD_BRIDGE_TX': 80},
            checksum_error_rate=1.0,
            parse_error_rate=0.5,
            protocol_success_rate=98.5,
            buffer_overflow_count=0,
            timeout_error_count=0,
            timestamp=time.time()
        )
        
        self.visualizer.update_data(metrics, system_id=system_id)
        
        # Verify data exists
        self.assertGreater(len(self.visualizer.active_system_ids), 0)
        
        # Clear data
        self.visualizer._clear_data()
        
        # Verify data is cleared
        self.assertEqual(len(self.visualizer.active_system_ids), 0)
        self.assertEqual(len(self.visualizer.rssi_data), 0)
        self.assertEqual(len(self.visualizer.snr_data), 0)
        self.assertEqual(len(self.visualizer.violations), 0)


class TestVisualizerIntegration(unittest.TestCase):
    """Integration tests for visualizer with other components."""
    
    def test_metrics_calculator_integration(self):
        """Test integration with MetricsCalculator."""
        from metrics_calculator import MetricsCalculator
        
        visualizer = TelemetryVisualizer()
        metrics_calc = MetricsCalculator()
        
        # Get metrics from calculator
        metrics = metrics_calc.get_metrics()
        
        # Update visualizer (should not raise exception)
        visualizer.update_data(metrics, system_id=1)
        
        # Verify data was added
        self.assertIn(1, visualizer.active_system_ids)
    
    def test_validation_engine_integration(self):
        """Test integration with ValidationEngine."""
        from validation_engine import ValidationEngine
        
        visualizer = TelemetryVisualizer()
        
        # Create a violation
        violation = Violation(
            timestamp=time.time(),
            rule_name="Test Rule",
            msg_type="TEST",
            field="test_field",
            actual_value=100,
            threshold=50,
            severity=Severity.WARNING,
            description="Test violation",
            system_id=1
        )
        
        # Add violation (should not raise exception)
        visualizer.add_violation(violation)
        
        # Verify violation was added
        self.assertEqual(len(visualizer.violations), 1)


def run_tests():
    """Run all tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestVisualizerConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestMetricDataPoint))
    suite.addTests(loader.loadTestsFromTestCase(TestTelemetryVisualizer))
    suite.addTests(loader.loadTestsFromTestCase(TestVisualizerIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
