"""
Unit tests for AlertManager module.

Tests alert filtering, throttling, and delivery functionality.
"""

import unittest
import time
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from alert_manager import AlertManager, AlertChannel, Severity


class MockViolation:
    """Mock violation object for testing."""
    def __init__(self, rule_name, system_id, severity, field="test_field", 
                 actual_value=100, threshold=50, msg_type="TEST", 
                 description="Test violation", timestamp=None):
        self.rule_name = rule_name
        self.system_id = system_id
        self.severity = severity
        self.field = field
        self.actual_value = actual_value
        self.threshold = threshold
        self.msg_type = msg_type
        self.description = description
        self.timestamp = timestamp or time.time()


class TestAlertManager(unittest.TestCase):
    """Test cases for AlertManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'channels': [AlertChannel.CONSOLE],
            'throttle_window': 60,
            'duplicate_window': 300,
            'max_alerts_per_window': 3
        }
        self.manager = AlertManager(self.config)
    
    def test_initialization(self):
        """Test AlertManager initialization."""
        self.assertEqual(self.manager.throttle_window, 60)
        self.assertEqual(self.manager.duplicate_window, 300)
        self.assertEqual(self.manager.max_alerts_per_window, 3)
        self.assertEqual(len(self.manager.alert_history), 0)
    
    def test_send_alert_basic(self):
        """Test basic alert sending."""
        violation = MockViolation("Test Rule", 1, Severity.WARNING)
        
        with patch('builtins.print') as mock_print:
            result = self.manager.send_alert(violation)
        
        self.assertTrue(result)
        self.assertEqual(self.manager.stats['total_alerts'], 1)
        self.assertEqual(self.manager.stats['alerts_by_severity'][Severity.WARNING], 1)
        self.assertEqual(len(self.manager.alert_history), 1)
    
    def test_duplicate_filtering(self):
        """Test that duplicate alerts are filtered within time window."""
        violation1 = MockViolation("Test Rule", 1, Severity.WARNING)
        violation2 = MockViolation("Test Rule", 1, Severity.WARNING)
        
        with patch('builtins.print'):
            # First alert should go through
            result1 = self.manager.send_alert(violation1)
            self.assertTrue(result1)
            
            # Second identical alert should be filtered
            result2 = self.manager.send_alert(violation2)
            self.assertFalse(result2)
        
        self.assertEqual(self.manager.stats['total_alerts'], 1)
        self.assertEqual(self.manager.stats['filtered_duplicates'], 1)
    
    def test_duplicate_filtering_different_systems(self):
        """Test that alerts from different systems are not considered duplicates."""
        violation1 = MockViolation("Test Rule", 1, Severity.WARNING)
        violation2 = MockViolation("Test Rule", 2, Severity.WARNING)
        
        with patch('builtins.print'):
            result1 = self.manager.send_alert(violation1)
            result2 = self.manager.send_alert(violation2)
        
        self.assertTrue(result1)
        self.assertTrue(result2)
        self.assertEqual(self.manager.stats['total_alerts'], 2)
        self.assertEqual(self.manager.stats['filtered_duplicates'], 0)
    
    def test_duplicate_filtering_different_severity(self):
        """Test that alerts with different severity are not considered duplicates."""
        violation1 = MockViolation("Test Rule", 1, Severity.WARNING)
        violation2 = MockViolation("Test Rule", 1, Severity.CRITICAL)
        
        with patch('builtins.print'):
            result1 = self.manager.send_alert(violation1)
            result2 = self.manager.send_alert(violation2)
        
        self.assertTrue(result1)
        self.assertTrue(result2)
        self.assertEqual(self.manager.stats['total_alerts'], 2)
    
    def test_throttling(self):
        """Test that high-frequency alerts are throttled."""
        with patch('builtins.print'):
            # Send max_alerts_per_window alerts with different field values (should all go through)
            for i in range(self.config['max_alerts_per_window']):
                violation = MockViolation(
                    "Test Rule", 1, Severity.WARNING,
                    actual_value=100 + i,  # Different values to avoid duplicate detection
                    timestamp=time.time() + i * 0.1
                )
                result = self.manager.send_alert(violation)
                self.assertTrue(result, f"Alert {i+1} should not be throttled")
            
            # Next alert should be throttled (even with different value)
            violation = MockViolation("Test Rule", 1, Severity.WARNING, actual_value=200)
            result = self.manager.send_alert(violation)
            self.assertFalse(result, "Alert should be throttled")
        
        self.assertEqual(self.manager.stats['total_alerts'], 3)
        self.assertEqual(self.manager.stats['throttled_alerts'], 1)
    
    def test_throttling_different_rules(self):
        """Test that throttling is per-rule."""
        with patch('builtins.print'):
            # Send max alerts for Rule 1 with different values
            for i in range(self.config['max_alerts_per_window']):
                violation = MockViolation(
                    "Rule 1", 1, Severity.WARNING,
                    actual_value=100 + i,  # Different values to avoid duplicate detection
                    timestamp=time.time() + i * 0.1
                )
                self.manager.send_alert(violation)
            
            # Alert for Rule 2 should still go through
            violation = MockViolation("Rule 2", 1, Severity.WARNING)
            result = self.manager.send_alert(violation)
            self.assertTrue(result)
        
        self.assertEqual(self.manager.stats['total_alerts'], 4)
    
    def test_throttling_window_expiry(self):
        """Test that throttling resets after window expires."""
        # Create manager with short throttle window for testing
        config = self.config.copy()
        config['throttle_window'] = 1  # 1 second
        manager = AlertManager(config)
        
        with patch('builtins.print'):
            # Fill up the throttle window with different values
            for i in range(config['max_alerts_per_window']):
                violation = MockViolation("Test Rule", 1, Severity.WARNING, actual_value=100 + i)
                manager.send_alert(violation)
            
            # Next alert should be throttled
            violation = MockViolation("Test Rule", 1, Severity.WARNING, actual_value=200)
            result = manager.send_alert(violation)
            self.assertFalse(result)
            
            # Wait for window to expire
            time.sleep(1.1)
            
            # Alert should now go through (use different value to avoid duplicate detection)
            violation = MockViolation("Test Rule", 1, Severity.WARNING, actual_value=300)
            result = manager.send_alert(violation)
            self.assertTrue(result)
    
    def test_console_alert_formatting(self):
        """Test console alert message formatting."""
        violation = MockViolation(
            "Test Rule", 1, Severity.WARNING,
            field="voltage", actual_value=10.5, threshold=11.0
        )
        
        with patch('builtins.print') as mock_print:
            self.manager.send_alert(violation)
            
            # Check that print was called
            mock_print.assert_called_once()
            
            # Check message format
            call_args = mock_print.call_args[0][0]
            self.assertIn("WARNING", call_args)
            self.assertIn("Test Rule", call_args)
            self.assertIn("voltage", call_args)
            self.assertIn("10.5", call_args)
    
    def test_get_alert_history(self):
        """Test retrieving alert history."""
        with patch('builtins.print'):
            violation1 = MockViolation("Rule 1", 1, Severity.WARNING)
            violation2 = MockViolation("Rule 2", 2, Severity.CRITICAL)
            
            self.manager.send_alert(violation1)
            self.manager.send_alert(violation2)
        
        # Get all alerts
        history = self.manager.get_alert_history()
        self.assertEqual(len(history), 2)
        
        # Filter by severity
        critical_alerts = self.manager.get_alert_history(severity=Severity.CRITICAL)
        self.assertEqual(len(critical_alerts), 1)
        
        # Filter by system_id
        system1_alerts = self.manager.get_alert_history(system_id=1)
        self.assertEqual(len(system1_alerts), 1)
    
    def test_get_alert_history_with_limit(self):
        """Test alert history with limit."""
        with patch('builtins.print'):
            for i in range(5):
                violation = MockViolation(f"Rule {i}", 1, Severity.WARNING)
                self.manager.send_alert(violation)
        
        # Get only 3 most recent
        history = self.manager.get_alert_history(limit=3)
        self.assertEqual(len(history), 3)
    
    def test_cleanup_old_tracking(self):
        """Test cleanup of old tracking data."""
        with patch('builtins.print'):
            violation = MockViolation("Test Rule", 1, Severity.WARNING)
            self.manager.send_alert(violation)
        
        # Verify tracking data exists
        self.assertGreater(len(self.manager.last_alert_time), 0)
        
        # Clean up with very short max_age
        self.manager.cleanup_old_tracking(max_age=0.001)
        time.sleep(0.01)
        
        # Tracking data should be cleaned up
        self.manager.cleanup_old_tracking(max_age=0.001)
        self.assertEqual(len(self.manager.last_alert_time), 0)
    
    def test_stats_tracking(self):
        """Test statistics tracking."""
        with patch('builtins.print'):
            # Send various alerts
            self.manager.send_alert(MockViolation("Rule 1", 1, Severity.INFO))
            self.manager.send_alert(MockViolation("Rule 2", 1, Severity.WARNING))
            self.manager.send_alert(MockViolation("Rule 3", 1, Severity.CRITICAL))
            
            # Trigger a duplicate
            self.manager.send_alert(MockViolation("Rule 1", 1, Severity.INFO))
        
        stats = self.manager.get_stats()
        self.assertEqual(stats['total_alerts'], 3)
        self.assertEqual(stats['alerts_by_severity'][Severity.INFO], 1)
        self.assertEqual(stats['alerts_by_severity'][Severity.WARNING], 1)
        self.assertEqual(stats['alerts_by_severity'][Severity.CRITICAL], 1)
        self.assertEqual(stats['filtered_duplicates'], 1)
    
    def test_reset_stats(self):
        """Test resetting statistics."""
        with patch('builtins.print'):
            self.manager.send_alert(MockViolation("Rule 1", 1, Severity.WARNING))
        
        self.assertEqual(self.manager.stats['total_alerts'], 1)
        
        self.manager.reset_stats()
        self.assertEqual(self.manager.stats['total_alerts'], 0)
    
    def test_clear_history(self):
        """Test clearing alert history."""
        with patch('builtins.print'):
            self.manager.send_alert(MockViolation("Rule 1", 1, Severity.WARNING))
        
        self.assertEqual(len(self.manager.alert_history), 1)
        
        self.manager.clear_history()
        self.assertEqual(len(self.manager.alert_history), 0)


class TestRelayLatencyAlerts(unittest.TestCase):
    """Test cases for relay mode latency alerts."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Import here to avoid circular dependency
        from binary_protocol_parser import StatusPayload
        self.StatusPayload = StatusPayload
        
        self.config = {
            'channels': [AlertChannel.CONSOLE],
            'relay_latency_threshold_ms': 500.0,
            'throttle_window': 60,
            'duplicate_window': 300
        }
        self.manager = AlertManager(self.config)
    
    def test_relay_latency_threshold_initialization(self):
        """Test that relay latency threshold is properly initialized."""
        self.assertEqual(self.manager.relay_latency_threshold_ms, 500.0)
    
    def test_relay_mode_detection(self):
        """Test relay mode detection from StatusPayload."""
        status = self.StatusPayload(
            relay_active=True,
            own_drone_sysid=1,
            packets_relayed=100,
            bytes_relayed=50000,
            mesh_to_uart_packets=50,
            uart_to_mesh_packets=50,
            mesh_to_uart_bytes=25000,
            uart_to_mesh_bytes=25000,
            bridge_gcs_to_mesh_packets=0,
            bridge_mesh_to_gcs_packets=0,
            bridge_gcs_to_mesh_bytes=0,
            bridge_mesh_to_gcs_bytes=0,
            rssi=-85.0,
            snr=8.5,
            last_activity_sec=0.2,
            active_peer_relays=1
        )
        
        with patch('builtins.print'):
            self.manager.check_relay_latency(status, system_id=1)
        
        relay_status = self.manager.get_relay_mode_status(system_id=1)
        self.assertTrue(relay_status[1])
    
    def test_no_alert_for_normal_latency(self):
        """Test that no alert is generated for normal latency."""
        status = self.StatusPayload(
            relay_active=True,
            own_drone_sysid=1,
            packets_relayed=100,
            bytes_relayed=50000,
            mesh_to_uart_packets=50,
            uart_to_mesh_packets=50,
            mesh_to_uart_bytes=25000,
            uart_to_mesh_bytes=25000,
            bridge_gcs_to_mesh_packets=0,
            bridge_mesh_to_gcs_packets=0,
            bridge_gcs_to_mesh_bytes=0,
            bridge_mesh_to_gcs_bytes=0,
            rssi=-85.0,
            snr=8.5,
            last_activity_sec=0.2,  # 200ms - below threshold
            active_peer_relays=1
        )
        
        with patch('builtins.print'):
            result = self.manager.check_relay_latency(status, system_id=1)
        
        self.assertFalse(result)
        self.assertEqual(self.manager.stats['relay_latency_alerts'], 0)
    
    def test_alert_for_high_latency(self):
        """Test that alert is generated for high latency."""
        status = self.StatusPayload(
            relay_active=True,
            own_drone_sysid=1,
            packets_relayed=100,
            bytes_relayed=50000,
            mesh_to_uart_packets=50,
            uart_to_mesh_packets=50,
            mesh_to_uart_bytes=25000,
            uart_to_mesh_bytes=25000,
            bridge_gcs_to_mesh_packets=0,
            bridge_mesh_to_gcs_packets=0,
            bridge_gcs_to_mesh_bytes=0,
            bridge_mesh_to_gcs_bytes=0,
            rssi=-85.0,
            snr=8.5,
            last_activity_sec=0.75,  # 750ms - exceeds threshold
            active_peer_relays=1
        )
        
        with patch('builtins.print'):
            result = self.manager.check_relay_latency(status, system_id=1)
        
        self.assertTrue(result)
        self.assertEqual(self.manager.stats['relay_latency_alerts'], 1)
        self.assertEqual(self.manager.stats['total_alerts'], 1)
    
    def test_no_alert_when_relay_inactive(self):
        """Test that no alert is generated when relay mode is inactive."""
        status = self.StatusPayload(
            relay_active=False,  # Relay inactive
            own_drone_sysid=1,
            packets_relayed=100,
            bytes_relayed=50000,
            mesh_to_uart_packets=50,
            uart_to_mesh_packets=50,
            mesh_to_uart_bytes=25000,
            uart_to_mesh_bytes=25000,
            bridge_gcs_to_mesh_packets=0,
            bridge_mesh_to_gcs_packets=0,
            bridge_gcs_to_mesh_bytes=0,
            bridge_mesh_to_gcs_bytes=0,
            rssi=-85.0,
            snr=8.5,
            last_activity_sec=0.75,  # High latency but relay inactive
            active_peer_relays=0
        )
        
        with patch('builtins.print'):
            result = self.manager.check_relay_latency(status, system_id=1)
        
        self.assertFalse(result)
        self.assertEqual(self.manager.stats['relay_latency_alerts'], 0)
    
    def test_relay_mode_transition_logging(self):
        """Test that relay mode transitions are logged."""
        # Start with relay active
        status_active = self.StatusPayload(
            relay_active=True,
            own_drone_sysid=1,
            packets_relayed=100,
            bytes_relayed=50000,
            mesh_to_uart_packets=50,
            uart_to_mesh_packets=50,
            mesh_to_uart_bytes=25000,
            uart_to_mesh_bytes=25000,
            bridge_gcs_to_mesh_packets=0,
            bridge_mesh_to_gcs_packets=0,
            bridge_gcs_to_mesh_bytes=0,
            bridge_mesh_to_gcs_bytes=0,
            rssi=-85.0,
            snr=8.5,
            last_activity_sec=0.2,
            active_peer_relays=1
        )
        
        with patch('builtins.print'):
            self.manager.check_relay_latency(status_active, system_id=1)
        
        # Transition to inactive
        status_inactive = self.StatusPayload(
            relay_active=False,
            own_drone_sysid=1,
            packets_relayed=100,
            bytes_relayed=50000,
            mesh_to_uart_packets=50,
            uart_to_mesh_packets=50,
            mesh_to_uart_bytes=25000,
            uart_to_mesh_bytes=25000,
            bridge_gcs_to_mesh_packets=0,
            bridge_mesh_to_gcs_packets=0,
            bridge_gcs_to_mesh_bytes=0,
            bridge_mesh_to_gcs_bytes=0,
            rssi=-85.0,
            snr=8.5,
            last_activity_sec=0.2,
            active_peer_relays=0
        )
        
        with patch('builtins.print'):
            self.manager.check_relay_latency(status_inactive, system_id=1)
        
        relay_status = self.manager.get_relay_mode_status(system_id=1)
        self.assertFalse(relay_status[1])
    
    def test_multiple_systems_relay_tracking(self):
        """Test relay mode tracking for multiple systems."""
        status1 = self.StatusPayload(
            relay_active=True,
            own_drone_sysid=1,
            packets_relayed=100,
            bytes_relayed=50000,
            mesh_to_uart_packets=50,
            uart_to_mesh_packets=50,
            mesh_to_uart_bytes=25000,
            uart_to_mesh_bytes=25000,
            bridge_gcs_to_mesh_packets=0,
            bridge_mesh_to_gcs_packets=0,
            bridge_gcs_to_mesh_bytes=0,
            bridge_mesh_to_gcs_bytes=0,
            rssi=-85.0,
            snr=8.5,
            last_activity_sec=0.2,
            active_peer_relays=1
        )
        
        status2 = self.StatusPayload(
            relay_active=False,
            own_drone_sysid=2,
            packets_relayed=50,
            bytes_relayed=25000,
            mesh_to_uart_packets=25,
            uart_to_mesh_packets=25,
            mesh_to_uart_bytes=12500,
            uart_to_mesh_bytes=12500,
            bridge_gcs_to_mesh_packets=0,
            bridge_mesh_to_gcs_packets=0,
            bridge_gcs_to_mesh_bytes=0,
            bridge_mesh_to_gcs_bytes=0,
            rssi=-88.0,
            snr=7.0,
            last_activity_sec=0.3,
            active_peer_relays=0
        )
        
        with patch('builtins.print'):
            self.manager.check_relay_latency(status1, system_id=1)
            self.manager.check_relay_latency(status2, system_id=2)
        
        relay_status = self.manager.get_relay_mode_status()
        self.assertTrue(relay_status[1])
        self.assertFalse(relay_status[2])
    
    def test_relay_latency_alert_dataclass(self):
        """Test RelayLatencyAlert dataclass properties."""
        from alert_manager import RelayLatencyAlert
        
        alert = RelayLatencyAlert(
            timestamp=time.time(),
            system_id=1,
            latency_ms=750.0,
            threshold_ms=500.0,
            relay_active=True,
            severity=Severity.WARNING
        )
        
        self.assertEqual(alert.rule_name, "Relay Mode Latency")
        self.assertEqual(alert.msg_type, "CMD_STATUS_REPORT")
        self.assertEqual(alert.field, "relay_latency")
        self.assertEqual(alert.actual_value, 750.0)
        self.assertEqual(alert.threshold, 500.0)
        self.assertIn("500.0ms", alert.description)


if __name__ == '__main__':
    unittest.main()
