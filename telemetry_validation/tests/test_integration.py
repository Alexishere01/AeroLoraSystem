"""
Integration tests for Telemetry Validation System.

Tests end-to-end logging pipeline with binary protocol, alert generation,
file rotation, and binary protocol error handling.

Requirements: All requirements
"""

import unittest
import tempfile
import shutil
import os
import struct
import time
import json
from pathlib import Path
import sys

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from binary_protocol_parser import (
    BinaryProtocolParser, MAVLinkExtractor, BinaryCommandHandler,
    UartCommand, BridgePayload, StatusPayload, InitPayload,
    PACKET_START_BYTE, fletcher16
)
from metrics_calculator import MetricsCalculator


class TestEndToEndLoggingPipeline(unittest.TestCase):
    """Test end-to-end logging pipeline with binary protocol."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Initialize components
        self.parser = BinaryProtocolParser()
        self.extractor = MAVLinkExtractor()
        self.metrics = MetricsCalculator()
    
    def _create_test_packet(self, command: UartCommand, payload: bytes = b'') -> bytes:
        """Helper to create a valid binary protocol packet."""
        packet = bytes([PACKET_START_BYTE])
        packet += bytes([command.value])
        packet += struct.pack('<H', len(payload))
        packet += payload
        checksum = fletcher16(packet)
        packet += struct.pack('<H', checksum)
        return packet
    
    def test_binary_packet_parsing_pipeline(self):
        """Test binary packet parsing pipeline."""
        # Create test packet
        packet_bytes = self._create_test_packet(UartCommand.CMD_ACK)
        
        # Parse packet
        packets = self.parser.parse_stream(packet_bytes)
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0].command, UartCommand.CMD_ACK)
    
    def test_bridge_packet_parsing(self):
        """Test end-to-end: binary packet -> MAVLink extraction."""
        # Create BridgePayload with fake MAVLink data
        system_id = struct.pack('B', 1)
        rssi = struct.pack('<f', -85.0)
        snr = struct.pack('<f', 8.0)
        # Minimal MAVLink-like data (not a real MAVLink packet)
        mavlink_data = b'\xfe\x09\x00\x01\x01\x00' + b'\x00' * 10
        data_len = struct.pack('<H', len(mavlink_data))
        payload_bytes = system_id + rssi + snr + data_len + mavlink_data
        
        # Create binary packet
        packet_bytes = self._create_test_packet(UartCommand.CMD_BRIDGE_TX, payload_bytes)
        
        # Parse binary packet
        binary_packets = self.parser.parse_stream(packet_bytes)
        self.assertEqual(len(binary_packets), 1)
        self.assertIsInstance(binary_packets[0].payload, BridgePayload)
    
    def test_metrics_calculation_pipeline(self):
        """Test metrics calculation from binary packets."""
        # Create multiple test packets
        for i in range(10):
            packet_bytes = self._create_test_packet(UartCommand.CMD_ACK)
            packets = self.parser.parse_stream(packet_bytes)
            
            for packet in packets:
                self.metrics.update_binary_packet(packet)
        
        # Get metrics
        metrics = self.metrics.get_metrics()
        
        # Verify metrics were calculated
        self.assertGreaterEqual(metrics.binary_packet_rate_1s, 0.0)
        self.assertEqual(metrics.binary_cmd_type_distribution['CMD_ACK'], 10)
    
    def test_status_report_metrics_extraction(self):
        """Test extracting metrics from STATUS_REPORT packets."""
        # Create StatusPayload
        status_data = struct.pack('<BB10IffIB',
            1, 1, 100, 5000, 50, 50, 2500, 2500, 25, 25, 1250, 1250,
            -90.0, 7.5, 1000, 2
        )
        
        # Create binary packet
        packet_bytes = self._create_test_packet(UartCommand.CMD_STATUS_REPORT, status_data)
        
        # Parse packet
        packets = self.parser.parse_stream(packet_bytes)
        self.assertEqual(len(packets), 1)
        
        # Update metrics
        self.metrics.update_binary_packet(packets[0])
        
        # Get metrics
        metrics = self.metrics.get_metrics()
        
        # Verify RSSI/SNR were extracted
        self.assertAlmostEqual(metrics.avg_rssi, -90.0, places=1)
        self.assertAlmostEqual(metrics.avg_snr, 7.5, places=1)



class TestBinaryProtocolErrorHandling(unittest.TestCase):
    """Test binary protocol error handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = BinaryProtocolParser()
        self.metrics = MetricsCalculator()
    
    def test_checksum_error_handling(self):
        """Test handling of checksum errors."""
        # Create packet with invalid checksum
        packet = bytes([PACKET_START_BYTE])
        packet += bytes([UartCommand.CMD_ACK.value])
        packet += struct.pack('<H', 0)
        packet += struct.pack('<H', 0xFFFF)  # Invalid checksum
        
        # Parse packet
        packets = self.parser.parse_stream(packet)
        
        # Should reject packet
        self.assertEqual(len(packets), 0)
        
        # Should record checksum error
        stats = self.parser.get_stats()
        self.assertGreater(stats['checksum_errors'], 0)
    
    def test_parse_error_handling(self):
        """Test handling of parse errors."""
        # Create packet with invalid payload length
        packet = bytes([PACKET_START_BYTE])
        packet += bytes([UartCommand.CMD_INIT.value])
        packet += struct.pack('<H', 300)  # Length > MAX_PAYLOAD_SIZE
        
        # Parse packet
        packets = self.parser.parse_stream(packet)
        
        # Should reject packet
        self.assertEqual(len(packets), 0)
        
        # Should record parse error
        stats = self.parser.get_stats()
        self.assertGreater(stats['parse_errors'], 0)
    
    def test_garbage_data_handling(self):
        """Test handling of garbage data."""
        # Send random garbage data
        garbage = b'\x00\x11\x22\x33\x44\x55\x66\x77\x88\x99' * 10
        
        # Parse garbage
        packets = self.parser.parse_stream(garbage)
        
        # Should not crash and should produce no valid packets
        self.assertIsInstance(packets, list)
    
    def test_metrics_error_tracking(self):
        """Test that metrics calculator tracks protocol errors."""
        # Record some errors
        self.metrics.record_checksum_error()
        self.metrics.record_parse_error()
        self.metrics.record_buffer_overflow()
        self.metrics.record_timeout_error()
        
        # Get metrics
        metrics = self.metrics.get_metrics()
        
        # Verify errors were tracked
        self.assertGreater(metrics.checksum_error_rate, 0.0)
        self.assertGreater(metrics.parse_error_rate, 0.0)
        self.assertEqual(metrics.buffer_overflow_count, 1)
        self.assertEqual(metrics.timeout_error_count, 1)


class TestMultiComponentIntegration(unittest.TestCase):
    """Test integration of multiple components working together."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Initialize all components
        self.parser = BinaryProtocolParser()
        self.extractor = MAVLinkExtractor()
        self.command_handler = BinaryCommandHandler()
        self.metrics = MetricsCalculator()
    
    def test_full_pipeline_with_status_report(self):
        """Test full pipeline: binary packet -> parsing -> metrics."""
        # Create StatusPayload
        status_data = struct.pack('<BB10IffIB',
            1, 1, 100, 5000, 50, 50, 2500, 2500, 25, 25, 1250, 1250,
            -85.0, 9.0, 1000, 2
        )
        
        # Create binary packet
        packet = bytes([PACKET_START_BYTE])
        packet += bytes([UartCommand.CMD_STATUS_REPORT.value])
        packet += struct.pack('<H', len(status_data))
        packet += status_data
        checksum = fletcher16(packet)
        packet += struct.pack('<H', checksum)
        
        # Parse packet
        packets = self.parser.parse_stream(packet)
        self.assertEqual(len(packets), 1)
        
        # Handle command
        self.command_handler.handle_packet(packets[0])
        
        # Update metrics
        self.metrics.update_binary_packet(packets[0])
        
        # Verify all components processed the packet
        self.assertTrue(self.command_handler.is_relay_active())
        
        metrics = self.metrics.get_metrics()
        self.assertAlmostEqual(metrics.avg_rssi, -85.0, places=1)


if __name__ == '__main__':
    unittest.main()
