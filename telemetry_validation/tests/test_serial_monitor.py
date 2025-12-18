#!/usr/bin/env python3
"""
Unit tests for Serial Monitor module.

Tests the SerialMonitor class functionality including message display,
throttling, and statistics.
"""

import unittest
import sys
import time
from pathlib import Path
from io import StringIO

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from serial_monitor import SerialMonitor, MonitorConfig, Colors
from mavlink_parser import ParsedMessage
from binary_protocol_parser import (
    ParsedBinaryPacket, UartCommand, InitPayload, StatusPayload, BridgePayload
)
from metrics_calculator import MetricsCalculator


class TestSerialMonitor(unittest.TestCase):
    """Test cases for SerialMonitor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = MonitorConfig(
            throttle_enabled=False,  # Disable throttling for tests
            color_enabled=False  # Disable colors for easier testing
        )
        self.metrics_calc = MetricsCalculator()
        self.monitor = SerialMonitor(config=self.config, metrics_calculator=self.metrics_calc)
    
    def test_initialization(self):
        """Test monitor initialization."""
        self.assertIsNotNone(self.monitor)
        self.assertEqual(self.monitor.stats['mavlink_displayed'], 0)
        self.assertEqual(self.monitor.stats['binary_displayed'], 0)
    
    def test_display_mavlink_heartbeat(self):
        """Test displaying a HEARTBEAT message."""
        msg = ParsedMessage(
            timestamp=time.time(),
            msg_type='HEARTBEAT',
            msg_id=0,
            system_id=1,
            component_id=1,
            sequence=0,
            fields={
                'custom_mode': 0,
                'base_mode': 128  # Armed
            },
            rssi=-85.0,
            snr=8.5,
            raw_bytes=b''
        )
        
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        result = self.monitor.display_mavlink_message(msg)
        
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        
        self.assertTrue(result)
        self.assertIn('MAV:HEARTBEAT', output)
        self.assertIn('SYS:1', output)
        self.assertIn('armed=YES', output)
        self.assertEqual(self.monitor.stats['mavlink_displayed'], 1)
    
    def test_display_mavlink_gps(self):
        """Test displaying a GPS_RAW_INT message."""
        msg = ParsedMessage(
            timestamp=time.time(),
            msg_type='GPS_RAW_INT',
            msg_id=24,
            system_id=1,
            component_id=1,
            sequence=1,
            fields={
                'lat': 371234560,
                'lon': -1221234560,
                'alt': 100500,
                'fix_type': 3,
                'satellites_visible': 12
            },
            rssi=-82.0,
            snr=9.2,
            raw_bytes=b''
        )
        
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        result = self.monitor.display_mavlink_message(msg)
        
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        
        self.assertTrue(result)
        self.assertIn('MAV:GPS_RAW_INT', output)
        self.assertIn('lat=37.123456', output)
        self.assertIn('fix=3', output)
        self.assertIn('sats=12', output)
    
    def test_display_binary_init(self):
        """Test displaying a CMD_INIT packet."""
        payload = InitPayload(
            mode="FREQUENCY_BRIDGE",
            primary_freq=915.0,
            secondary_freq=868.0,
            timestamp=12345
        )
        
        packet = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_INIT,
            payload=payload,
            raw_bytes=b'',
            payload_bytes=b''
        )
        
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        result = self.monitor.display_binary_packet(packet)
        
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        
        self.assertTrue(result)
        self.assertIn('BIN:CMD_INIT', output)
        self.assertIn('mode=FREQUENCY_BRIDGE', output)
        self.assertIn('freq1=915.00MHz', output)
        self.assertEqual(self.monitor.stats['binary_displayed'], 1)
    
    def test_display_binary_status(self):
        """Test displaying a CMD_STATUS_REPORT packet."""
        payload = StatusPayload(
            relay_active=True,
            own_drone_sysid=1,
            packets_relayed=150,
            bytes_relayed=45000,
            mesh_to_uart_packets=75,
            uart_to_mesh_packets=75,
            mesh_to_uart_bytes=22500,
            uart_to_mesh_bytes=22500,
            bridge_gcs_to_mesh_packets=50,
            bridge_mesh_to_gcs_packets=50,
            bridge_gcs_to_mesh_bytes=15000,
            bridge_mesh_to_gcs_bytes=15000,
            rssi=-82.0,
            snr=9.2,
            last_activity_sec=2,
            active_peer_relays=2
        )
        
        packet = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_STATUS_REPORT,
            payload=payload,
            raw_bytes=b'',
            payload_bytes=b''
        )
        
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        result = self.monitor.display_binary_packet(packet)
        
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        
        self.assertTrue(result)
        self.assertIn('BIN:CMD_STATUS_REPORT', output)
        self.assertIn('relay=ACTIVE', output)
        self.assertIn('relayed=150', output)
    
    def test_throttling_enabled(self):
        """Test output throttling."""
        # Create monitor with throttling enabled
        config = MonitorConfig(
            throttle_enabled=True,
            max_messages_per_second=5,
            color_enabled=False
        )
        monitor = SerialMonitor(config=config)
        
        # Create non-critical message
        msg = ParsedMessage(
            timestamp=time.time(),
            msg_type='PARAM_VALUE',  # Non-critical
            msg_id=22,
            system_id=1,
            component_id=1,
            sequence=0,
            fields={},
            raw_bytes=b''
        )
        
        # Send more messages than the limit
        displayed_count = 0
        for i in range(10):
            if monitor.display_mavlink_message(msg):
                displayed_count += 1
        
        # Should have throttled some messages
        self.assertLess(displayed_count, 10)
        self.assertGreater(monitor.stats['throttled_messages'], 0)
    
    def test_critical_messages_bypass_throttling(self):
        """Test that critical messages bypass throttling."""
        # Create monitor with throttling enabled
        config = MonitorConfig(
            throttle_enabled=True,
            max_messages_per_second=2,
            color_enabled=False
        )
        monitor = SerialMonitor(config=config)
        
        # Create critical message
        msg = ParsedMessage(
            timestamp=time.time(),
            msg_type='HEARTBEAT',  # Critical
            msg_id=0,
            system_id=1,
            component_id=1,
            sequence=0,
            fields={'custom_mode': 0, 'base_mode': 0},
            raw_bytes=b''
        )
        
        # Send many critical messages
        displayed_count = 0
        for i in range(10):
            if monitor.display_mavlink_message(msg):
                displayed_count += 1
        
        # All critical messages should be displayed
        self.assertEqual(displayed_count, 10)
        self.assertEqual(monitor.stats['critical_messages'], 10)
    
    def test_rssi_snr_tracking(self):
        """Test RSSI/SNR tracking from messages."""
        msg = ParsedMessage(
            timestamp=time.time(),
            msg_type='HEARTBEAT',
            msg_id=0,
            system_id=1,
            component_id=1,
            sequence=0,
            fields={'custom_mode': 0, 'base_mode': 0},
            rssi=-85.0,
            snr=8.5,
            raw_bytes=b''
        )
        
        self.monitor.display_mavlink_message(msg)
        
        self.assertEqual(self.monitor.last_rssi, -85.0)
        self.assertEqual(self.monitor.last_snr, 8.5)
    
    def test_statistics_display(self):
        """Test statistics display."""
        # Add some messages
        msg = ParsedMessage(
            timestamp=time.time(),
            msg_type='HEARTBEAT',
            msg_id=0,
            system_id=1,
            component_id=1,
            sequence=0,
            fields={'custom_mode': 0, 'base_mode': 0},
            rssi=-85.0,
            snr=8.5,
            raw_bytes=b''
        )
        
        self.monitor.display_mavlink_message(msg)
        self.metrics_calc.update_mavlink_message(msg)
        
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        self.monitor.display_statistics()
        
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        
        self.assertIn('TELEMETRY STATISTICS', output)
        self.assertIn('Monitor Statistics', output)
        self.assertIn('Packet Rates', output)
        self.assertIn('Link Quality', output)
    
    def test_get_stats(self):
        """Test getting monitor statistics."""
        stats = self.monitor.get_stats()
        
        self.assertIn('mavlink_displayed', stats)
        self.assertIn('binary_displayed', stats)
        self.assertIn('throttled_messages', stats)
        self.assertIn('critical_messages', stats)
    
    def test_reset_stats(self):
        """Test resetting statistics."""
        # Add some messages
        msg = ParsedMessage(
            timestamp=time.time(),
            msg_type='HEARTBEAT',
            msg_id=0,
            system_id=1,
            component_id=1,
            sequence=0,
            fields={'custom_mode': 0, 'base_mode': 0},
            raw_bytes=b''
        )
        
        self.monitor.display_mavlink_message(msg)
        self.assertEqual(self.monitor.stats['mavlink_displayed'], 1)
        
        # Reset
        self.monitor.reset_stats()
        self.assertEqual(self.monitor.stats['mavlink_displayed'], 0)
    
    def test_color_output(self):
        """Test color-coded output."""
        # Create monitor with colors enabled
        config = MonitorConfig(color_enabled=True)
        monitor = SerialMonitor(config=config)
        
        msg = ParsedMessage(
            timestamp=time.time(),
            msg_type='HEARTBEAT',
            msg_id=0,
            system_id=1,
            component_id=1,
            sequence=0,
            fields={'custom_mode': 0, 'base_mode': 0},
            rssi=-85.0,
            snr=8.5,
            raw_bytes=b''
        )
        
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        monitor.display_mavlink_message(msg)
        
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        
        # Should contain ANSI color codes
        self.assertIn('\033[', output)
    
    def test_show_timestamps(self):
        """Test timestamp display."""
        config = MonitorConfig(show_timestamps=True, color_enabled=False)
        monitor = SerialMonitor(config=config)
        
        msg = ParsedMessage(
            timestamp=time.time(),
            msg_type='HEARTBEAT',
            msg_id=0,
            system_id=1,
            component_id=1,
            sequence=0,
            fields={'custom_mode': 0, 'base_mode': 0},
            raw_bytes=b''
        )
        
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        monitor.display_mavlink_message(msg)
        
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        
        # Should contain timestamp in [HH:MM:SS] format
        self.assertRegex(output, r'\[\d{2}:\d{2}:\d{2}\]')
    
    def test_hide_rssi_snr(self):
        """Test hiding RSSI/SNR display."""
        config = MonitorConfig(show_rssi_snr=False, color_enabled=False)
        monitor = SerialMonitor(config=config)
        
        msg = ParsedMessage(
            timestamp=time.time(),
            msg_type='HEARTBEAT',
            msg_id=0,
            system_id=1,
            component_id=1,
            sequence=0,
            fields={'custom_mode': 0, 'base_mode': 0},
            rssi=-85.0,
            snr=8.5,
            raw_bytes=b''
        )
        
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        monitor.display_mavlink_message(msg)
        
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        
        # Should not contain RSSI/SNR
        self.assertNotIn('RSSI:', output)
        self.assertNotIn('SNR:', output)


def run_tests():
    """Run all tests."""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == '__main__':
    run_tests()
