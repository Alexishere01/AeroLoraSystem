"""
Unit tests for MetricsCalculator module

Tests the metrics calculation functionality including packet rates,
packet loss detection, command latency tracking, and protocol health.
"""

import unittest
import time
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from metrics_calculator import MetricsCalculator, TelemetryMetrics
from binary_protocol_parser import (
    ParsedBinaryPacket,
    UartCommand,
    BridgePayload,
    StatusPayload
)
from mavlink_parser import ParsedMessage


class TestMetricsCalculator(unittest.TestCase):
    """Test cases for MetricsCalculator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.calculator = MetricsCalculator()
    
    def test_initialization(self):
        """Test that calculator initializes correctly."""
        self.assertIsNotNone(self.calculator)
        self.assertEqual(len(self.calculator.binary_packets_1s), 0)
        self.assertEqual(len(self.calculator.mavlink_packets_1s), 0)
        self.assertEqual(self.calculator.packets_lost, 0)
        self.assertEqual(self.calculator.packets_received, 0)
    
    def test_binary_packet_tracking(self):
        """Test tracking of binary protocol packets."""
        # Create test packet
        packet = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_BRIDGE_RX,
            payload=BridgePayload(
                system_id=1,
                rssi=-85.0,
                snr=10.0,
                data_len=50,
                data=b'\xfe' * 50
            ),
            raw_bytes=b'\xaa' * 100,
            payload_bytes=b'\x00' * 50
        )
        
        # Update calculator
        self.calculator.update_binary_packet(packet)
        
        # Verify tracking
        self.assertEqual(len(self.calculator.binary_packets_1s), 1)
        self.assertEqual(self.calculator.binary_cmd_type_counts['CMD_BRIDGE_RX'], 1)
        self.assertEqual(self.calculator.successful_binary_packets, 1)
    
    def test_rssi_snr_extraction_from_bridge_payload(self):
        """Test RSSI/SNR extraction from BridgePayload."""
        packet = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_BRIDGE_RX,
            payload=BridgePayload(
                system_id=1,
                rssi=-80.0,
                snr=12.5,
                data_len=10,
                data=b'\x00' * 10
            ),
            raw_bytes=b'\xaa' * 20,
            payload_bytes=b'\x00' * 10
        )
        
        self.calculator.update_binary_packet(packet)
        
        # Verify RSSI/SNR stored
        self.assertEqual(len(self.calculator.rssi_values), 1)
        self.assertEqual(len(self.calculator.snr_values), 1)
        self.assertEqual(self.calculator.rssi_values[0], -80.0)
        self.assertEqual(self.calculator.snr_values[0], 12.5)
    
    def test_rssi_snr_extraction_from_status_payload(self):
        """Test RSSI/SNR extraction from StatusPayload."""
        packet = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_STATUS_REPORT,
            payload=StatusPayload(
                relay_active=True,
                own_drone_sysid=1,
                packets_relayed=100,
                bytes_relayed=5000,
                mesh_to_uart_packets=50,
                uart_to_mesh_packets=50,
                mesh_to_uart_bytes=2500,
                uart_to_mesh_bytes=2500,
                bridge_gcs_to_mesh_packets=0,
                bridge_mesh_to_gcs_packets=0,
                bridge_gcs_to_mesh_bytes=0,
                bridge_mesh_to_gcs_bytes=0,
                rssi=-75.0,
                snr=15.0,
                last_activity_sec=1,
                active_peer_relays=2
            ),
            raw_bytes=b'\xaa' * 60,
            payload_bytes=b'\x00' * 55
        )
        
        self.calculator.update_binary_packet(packet)
        
        # Verify RSSI/SNR stored
        self.assertEqual(len(self.calculator.rssi_values), 1)
        self.assertEqual(len(self.calculator.snr_values), 1)
        self.assertEqual(self.calculator.rssi_values[0], -75.0)
        self.assertEqual(self.calculator.snr_values[0], 15.0)
    
    def test_mavlink_message_tracking(self):
        """Test tracking of MAVLink messages."""
        msg = ParsedMessage(
            timestamp=time.time(),
            msg_type='HEARTBEAT',
            msg_id=0,
            system_id=1,
            component_id=1,
            sequence=0,
            fields={'type': 2, 'autopilot': 3},
            raw_bytes=b'\xfe' * 20
        )
        
        self.calculator.update_mavlink_message(msg)
        
        # Verify tracking
        self.assertEqual(len(self.calculator.mavlink_packets_1s), 1)
        self.assertEqual(self.calculator.mavlink_msg_type_counts['HEARTBEAT'], 1)
        self.assertEqual(self.calculator.packets_received, 1)
    
    def test_packet_loss_detection(self):
        """Test packet loss detection from sequence numbers."""
        # Send messages with sequence: 0, 1, 2, 5 (missing 3, 4)
        sequences = [0, 1, 2, 5]
        
        for seq in sequences:
            msg = ParsedMessage(
                timestamp=time.time(),
                msg_type='HEARTBEAT',
                msg_id=0,
                system_id=1,
                component_id=1,
                sequence=seq,
                fields={'type': 2},
                raw_bytes=b'\xfe' * 20
            )
            self.calculator.update_mavlink_message(msg)
        
        # Should detect 2 lost packets (sequences 3 and 4)
        self.assertEqual(self.calculator.packets_lost, 2)
        self.assertEqual(self.calculator.packets_received, 4)
    
    def test_packet_loss_sequence_wraparound(self):
        """Test packet loss detection with sequence wraparound."""
        # Send messages with sequence: 254, 255, 0, 1 (no loss)
        sequences = [254, 255, 0, 1]
        
        for seq in sequences:
            msg = ParsedMessage(
                timestamp=time.time(),
                msg_type='HEARTBEAT',
                msg_id=0,
                system_id=1,
                component_id=1,
                sequence=seq,
                fields={'type': 2},
                raw_bytes=b'\xfe' * 20
            )
            self.calculator.update_mavlink_message(msg)
        
        # Should detect no packet loss
        self.assertEqual(self.calculator.packets_lost, 0)
        self.assertEqual(self.calculator.packets_received, 4)
    
    def test_command_latency_tracking(self):
        """Test command latency tracking."""
        # Send COMMAND_LONG
        cmd_msg = ParsedMessage(
            timestamp=time.time(),
            msg_type='COMMAND_LONG',
            msg_id=76,
            system_id=1,
            component_id=1,
            sequence=0,
            fields={'command': 400, 'target_system': 1},
            raw_bytes=b'\xfe' * 30
        )
        
        self.calculator.update_mavlink_message(cmd_msg)
        
        # Verify command tracked
        self.assertIn(400, self.calculator.command_times)
        
        # Simulate delay
        time.sleep(0.1)
        
        # Send COMMAND_ACK
        ack_msg = ParsedMessage(
            timestamp=time.time(),
            msg_type='COMMAND_ACK',
            msg_id=77,
            system_id=1,
            component_id=1,
            sequence=1,
            fields={'command': 400, 'result': 0},
            raw_bytes=b'\xfe' * 10
        )
        
        self.calculator.update_mavlink_message(ack_msg)
        
        # Verify latency recorded
        self.assertEqual(len(self.calculator.latencies), 1)
        self.assertGreater(self.calculator.latencies[0], 0.09)  # At least 90ms
        self.assertLess(self.calculator.latencies[0], 0.15)  # Less than 150ms
        
        # Verify command removed from tracking
        self.assertNotIn(400, self.calculator.command_times)
    
    def test_error_recording(self):
        """Test checksum and parse error recording."""
        # Record some errors
        self.calculator.record_checksum_error()
        self.calculator.record_checksum_error()
        self.calculator.record_parse_error()
        
        # Verify errors recorded
        self.assertEqual(len(self.calculator.checksum_errors), 2)
        self.assertEqual(len(self.calculator.parse_errors), 1)
        self.assertEqual(self.calculator.total_binary_packets, 3)
    
    def test_get_metrics(self):
        """Test getting comprehensive metrics."""
        # Add some data
        for i in range(5):
            packet = ParsedBinaryPacket(
                timestamp=time.time(),
                command=UartCommand.CMD_BRIDGE_RX,
                payload=BridgePayload(
                    system_id=1,
                    rssi=-80.0,
                    snr=10.0,
                    data_len=10,
                    data=b'\x00' * 10
                ),
                raw_bytes=b'\xaa' * 20,
                payload_bytes=b'\x00' * 10
            )
            self.calculator.update_binary_packet(packet)
            time.sleep(0.01)
        
        # Get metrics
        metrics = self.calculator.get_metrics()
        
        # Verify metrics structure
        self.assertIsInstance(metrics, TelemetryMetrics)
        self.assertGreater(metrics.binary_packet_rate_1s, 0)
        self.assertEqual(metrics.avg_rssi, -80.0)
        self.assertEqual(metrics.avg_snr, 10.0)
        self.assertGreater(metrics.timestamp, 0)
    
    def test_packet_rate_calculation(self):
        """Test packet rate calculation over rolling windows."""
        # Send 10 packets over 1 second
        for i in range(10):
            packet = ParsedBinaryPacket(
                timestamp=time.time(),
                command=UartCommand.CMD_BRIDGE_RX,
                payload=None,
                raw_bytes=b'\xaa' * 10,
                payload_bytes=b''
            )
            self.calculator.update_binary_packet(packet)
            time.sleep(0.1)
        
        # Get metrics
        metrics = self.calculator.get_metrics()
        
        # Should be approximately 10 packets per second
        self.assertGreater(metrics.binary_packet_rate_1s, 8.0)
        self.assertLess(metrics.binary_packet_rate_1s, 12.0)
    
    def test_message_type_distribution(self):
        """Test message type distribution tracking."""
        # Send different message types
        msg_types = ['HEARTBEAT', 'GPS_RAW_INT', 'ATTITUDE', 'HEARTBEAT', 'GPS_RAW_INT', 'HEARTBEAT']
        
        for msg_type in msg_types:
            msg = ParsedMessage(
                timestamp=time.time(),
                msg_type=msg_type,
                msg_id=0,
                system_id=1,
                component_id=1,
                sequence=0,
                fields={},
                raw_bytes=b'\xfe' * 20
            )
            self.calculator.update_mavlink_message(msg)
        
        # Get metrics
        metrics = self.calculator.get_metrics()
        
        # Verify distribution
        self.assertEqual(metrics.mavlink_msg_type_distribution['HEARTBEAT'], 3)
        self.assertEqual(metrics.mavlink_msg_type_distribution['GPS_RAW_INT'], 2)
        self.assertEqual(metrics.mavlink_msg_type_distribution['ATTITUDE'], 1)
    
    def test_protocol_health_metrics(self):
        """Test binary protocol health metrics."""
        # Add successful packets
        for i in range(10):
            packet = ParsedBinaryPacket(
                timestamp=time.time(),
                command=UartCommand.CMD_BRIDGE_RX,
                payload=None,
                raw_bytes=b'\xaa' * 10,
                payload_bytes=b''
            )
            self.calculator.update_binary_packet(packet)
        
        # Add some errors
        self.calculator.record_checksum_error()
        self.calculator.record_checksum_error()
        
        # Get metrics
        metrics = self.calculator.get_metrics()
        
        # Verify health metrics
        # Success rate should be 10 / 12 = 83.33%
        self.assertAlmostEqual(metrics.protocol_success_rate, 83.33, places=1)
        self.assertGreater(metrics.checksum_error_rate, 0)
    
    def test_reset_stats(self):
        """Test resetting statistics."""
        # Add some data
        packet = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_BRIDGE_RX,
            payload=None,
            raw_bytes=b'\xaa' * 10,
            payload_bytes=b''
        )
        self.calculator.update_binary_packet(packet)
        
        # Reset
        self.calculator.reset_stats()
        
        # Verify reset
        self.assertEqual(len(self.calculator.binary_packets_1s), 0)
        self.assertEqual(len(self.calculator.mavlink_packets_1s), 0)
        self.assertEqual(self.calculator.packets_lost, 0)
        self.assertEqual(self.calculator.packets_received, 0)
        self.assertEqual(len(self.calculator.binary_cmd_type_counts), 0)
        self.assertEqual(len(self.calculator.mavlink_msg_type_counts), 0)


def run_tests():
    """Run all tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestMetricsCalculator)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success status
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
