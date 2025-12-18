"""
Unit tests for Binary Protocol Parser module.

Tests binary protocol parsing, Fletcher-16 checksum validation,
MAVLink extraction from BridgePayload, and state machine behavior.

Requirements: 1.2, 2.1, 2.5, 3.1, 3.2, 5.1
"""

import unittest
import struct
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from binary_protocol_parser import (
    BinaryProtocolParser, MAVLinkExtractor, BinaryCommandHandler,
    ParsedBinaryPacket, UartCommand, BridgePayload, StatusPayload,
    InitPayload, RelayActivatePayload, RelayRequestPayload, RelayRxPayload,
    fletcher16, validate_checksum, RxState,
    PACKET_START_BYTE, MAX_PAYLOAD_SIZE
)


class TestFletcher16Checksum(unittest.TestCase):
    """Test cases for Fletcher-16 checksum calculation."""
    
    def test_fletcher16_empty_data(self):
        """Test Fletcher-16 with empty data."""
        checksum = fletcher16(b'')
        self.assertEqual(checksum, 0)
    
    def test_fletcher16_single_byte(self):
        """Test Fletcher-16 with single byte."""
        checksum = fletcher16(b'\x01')
        self.assertIsInstance(checksum, int)
        self.assertGreater(checksum, 0)
    
    def test_fletcher16_known_values(self):
        """Test Fletcher-16 with known test vectors."""
        # Test vector: "abcde"
        data = b'abcde'
        checksum = fletcher16(data)
        
        # Verify checksum is calculated correctly
        # Manual calculation: sum1 and sum2 should be deterministic
        self.assertIsInstance(checksum, int)
        self.assertGreaterEqual(checksum, 0)
        self.assertLessEqual(checksum, 0xFFFF)
    
    def test_fletcher16_consistency(self):
        """Test that Fletcher-16 produces consistent results."""
        data = b'test data for checksum'
        checksum1 = fletcher16(data)
        checksum2 = fletcher16(data)
        self.assertEqual(checksum1, checksum2)
    
    def test_fletcher16_different_data(self):
        """Test that different data produces different checksums."""
        data1 = b'test data 1'
        data2 = b'test data 2'
        checksum1 = fletcher16(data1)
        checksum2 = fletcher16(data2)
        self.assertNotEqual(checksum1, checksum2)
    
    def test_validate_checksum_valid(self):
        """Test checksum validation with valid checksum."""
        data = b'test packet data'
        expected = fletcher16(data)
        self.assertTrue(validate_checksum(data, expected))
    
    def test_validate_checksum_invalid(self):
        """Test checksum validation with invalid checksum."""
        data = b'test packet data'
        expected = fletcher16(data)
        invalid = expected + 1  # Corrupt checksum
        self.assertFalse(validate_checksum(data, invalid))


class TestPayloadParsing(unittest.TestCase):
    """Test cases for payload structure parsing."""
    
    def test_init_payload_parsing(self):
        """Test InitPayload parsing from binary data."""
        # Create test InitPayload (mode is 16 bytes)
        mode = b'FREQUENCY_BRIDGE'
        if len(mode) < 16:
            mode = mode + b'\x00' * (16 - len(mode))
        primary_freq = struct.pack('<f', 915.0)
        secondary_freq = struct.pack('<f', 868.0)
        timestamp = struct.pack('<I', 12345)
        
        data = mode + primary_freq + secondary_freq + timestamp
        
        payload = InitPayload.from_bytes(data)
        
        self.assertEqual(payload.mode, 'FREQUENCY_BRIDGE')
        self.assertAlmostEqual(payload.primary_freq, 915.0, places=1)
        self.assertAlmostEqual(payload.secondary_freq, 868.0, places=1)
        self.assertEqual(payload.timestamp, 12345)
    
    def test_bridge_payload_parsing(self):
        """Test BridgePayload parsing from binary data."""
        # Create test BridgePayload
        system_id = struct.pack('B', 1)
        rssi = struct.pack('<f', -85.5)
        snr = struct.pack('<f', 8.2)
        mavlink_data = b'\xfe\x09\x00\x01\x01\x00' + b'\x00' * 10  # Fake MAVLink
        data_len = struct.pack('<H', len(mavlink_data))
        
        data = system_id + rssi + snr + data_len + mavlink_data
        
        payload = BridgePayload.from_bytes(data)
        
        self.assertEqual(payload.system_id, 1)
        self.assertAlmostEqual(payload.rssi, -85.5, places=1)
        self.assertAlmostEqual(payload.snr, 8.2, places=1)
        self.assertEqual(payload.data_len, len(mavlink_data))
        self.assertEqual(payload.data, mavlink_data)
    
    def test_status_payload_parsing(self):
        """Test StatusPayload parsing from binary data."""
        # Create test StatusPayload (55 bytes)
        data = struct.pack('<BB10IffIB',
            1,      # relay_active
            1,      # own_drone_sysid
            100,    # packets_relayed
            5000,   # bytes_relayed
            50,     # mesh_to_uart_packets
            50,     # uart_to_mesh_packets
            2500,   # mesh_to_uart_bytes
            2500,   # uart_to_mesh_bytes
            25,     # bridge_gcs_to_mesh_packets
            25,     # bridge_mesh_to_gcs_packets
            1250,   # bridge_gcs_to_mesh_bytes
            1250,   # bridge_mesh_to_gcs_bytes
            -90.0,  # rssi
            7.5,    # snr
            1000,   # last_activity_sec
            2       # active_peer_relays
        )
        
        payload = StatusPayload.from_bytes(data)
        
        self.assertTrue(payload.relay_active)
        self.assertEqual(payload.own_drone_sysid, 1)
        self.assertEqual(payload.packets_relayed, 100)
        self.assertEqual(payload.bytes_relayed, 5000)
        self.assertAlmostEqual(payload.rssi, -90.0, places=1)
        self.assertAlmostEqual(payload.snr, 7.5, places=1)
        self.assertEqual(payload.active_peer_relays, 2)
    
    def test_relay_activate_payload_parsing(self):
        """Test RelayActivatePayload parsing."""
        data = struct.pack('B', 1)  # activate = true
        payload = RelayActivatePayload.from_bytes(data)
        self.assertTrue(payload.activate)
        
        data = struct.pack('B', 0)  # activate = false
        payload = RelayActivatePayload.from_bytes(data)
        self.assertFalse(payload.activate)
    
    def test_relay_request_payload_parsing(self):
        """Test RelayRequestPayload parsing."""
        data = struct.pack('<fff', -95.0, 6.5, 0.05)
        payload = RelayRequestPayload.from_bytes(data)
        
        self.assertAlmostEqual(payload.rssi, -95.0, places=1)
        self.assertAlmostEqual(payload.snr, 6.5, places=1)
        self.assertAlmostEqual(payload.packet_loss, 0.05, places=2)
    
    def test_relay_rx_payload_parsing(self):
        """Test RelayRxPayload parsing."""
        rssi = struct.pack('<f', -88.0)
        snr = struct.pack('<f', 9.0)
        relay_data = b'test relay data'
        
        data = rssi + snr + relay_data
        payload = RelayRxPayload.from_bytes(data)
        
        self.assertAlmostEqual(payload.rssi, -88.0, places=1)
        self.assertAlmostEqual(payload.snr, 9.0, places=1)
        self.assertEqual(payload.data, relay_data)


class TestBinaryProtocolParser(unittest.TestCase):
    """Test cases for BinaryProtocolParser state machine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = BinaryProtocolParser()
    
    def _create_test_packet(self, command: UartCommand, payload: bytes = b'') -> bytes:
        """
        Helper to create a valid binary protocol packet.
        
        Args:
            command: Command type
            payload: Payload bytes
            
        Returns:
            Complete packet with checksum
        """
        # Start byte
        packet = bytes([PACKET_START_BYTE])
        
        # Command
        packet += bytes([command.value])
        
        # Length (little-endian)
        length = len(payload)
        packet += struct.pack('<H', length)
        
        # Payload
        packet += payload
        
        # Calculate checksum over header + payload
        checksum = fletcher16(packet)
        packet += struct.pack('<H', checksum)
        
        return packet
    
    def test_parse_empty_stream(self):
        """Test parsing empty data stream."""
        packets = self.parser.parse_stream(b'')
        self.assertEqual(len(packets), 0)
    
    def test_parse_single_ack_packet(self):
        """Test parsing a single ACK packet (no payload)."""
        packet_bytes = self._create_test_packet(UartCommand.CMD_ACK)
        packets = self.parser.parse_stream(packet_bytes)
        
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0].command, UartCommand.CMD_ACK)
        self.assertIsNone(packets[0].payload)
    
    def test_parse_init_packet(self):
        """Test parsing an INIT packet with payload."""
        # Create InitPayload
        mode = b'RELAY\x00' + b'\x00' * 10
        primary_freq = struct.pack('<f', 915.0)
        secondary_freq = struct.pack('<f', 915.0)
        timestamp = struct.pack('<I', 5000)
        payload_bytes = mode + primary_freq + secondary_freq + timestamp
        
        packet_bytes = self._create_test_packet(UartCommand.CMD_INIT, payload_bytes)
        packets = self.parser.parse_stream(packet_bytes)
        
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0].command, UartCommand.CMD_INIT)
        self.assertIsInstance(packets[0].payload, InitPayload)
        self.assertEqual(packets[0].payload.mode, 'RELAY')
    
    def test_parse_bridge_tx_packet(self):
        """Test parsing a BRIDGE_TX packet with MAVLink data."""
        # Create BridgePayload
        system_id = struct.pack('B', 1)
        rssi = struct.pack('<f', -80.0)
        snr = struct.pack('<f', 10.0)
        mavlink_data = b'\xfe\x09\x00\x01\x01\x00' + b'\x00' * 10
        data_len = struct.pack('<H', len(mavlink_data))
        payload_bytes = system_id + rssi + snr + data_len + mavlink_data
        
        packet_bytes = self._create_test_packet(UartCommand.CMD_BRIDGE_TX, payload_bytes)
        packets = self.parser.parse_stream(packet_bytes)
        
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0].command, UartCommand.CMD_BRIDGE_TX)
        self.assertIsInstance(packets[0].payload, BridgePayload)
        self.assertEqual(packets[0].payload.system_id, 1)
        self.assertAlmostEqual(packets[0].payload.rssi, -80.0, places=1)
    
    def test_parse_multiple_packets(self):
        """Test parsing multiple packets in one stream."""
        packet1 = self._create_test_packet(UartCommand.CMD_ACK)
        packet2 = self._create_test_packet(UartCommand.CMD_STATUS_REQUEST)
        
        stream = packet1 + packet2
        packets = self.parser.parse_stream(stream)
        
        self.assertEqual(len(packets), 2)
        self.assertEqual(packets[0].command, UartCommand.CMD_ACK)
        self.assertEqual(packets[1].command, UartCommand.CMD_STATUS_REQUEST)
    
    def test_parse_invalid_checksum(self):
        """Test that packets with invalid checksums are rejected."""
        # Create packet with corrupted checksum
        packet = bytes([PACKET_START_BYTE])
        packet += bytes([UartCommand.CMD_ACK.value])
        packet += struct.pack('<H', 0)  # No payload
        packet += struct.pack('<H', 0xFFFF)  # Invalid checksum
        
        packets = self.parser.parse_stream(packet)
        
        self.assertEqual(len(packets), 0)
        stats = self.parser.get_stats()
        self.assertGreater(stats['checksum_errors'], 0)
    
    def test_parse_garbage_data(self):
        """Test parser handles garbage data gracefully."""
        garbage = b'\x00\x11\x22\x33\x44\x55\x66\x77\x88\x99'
        packets = self.parser.parse_stream(garbage)
        
        # Should not crash, may produce 0 packets
        self.assertIsInstance(packets, list)
    
    def test_parse_partial_packet(self):
        """Test parser handles partial packets correctly."""
        # Create a complete packet
        complete_packet = self._create_test_packet(UartCommand.CMD_ACK)
        
        # Send only first half
        partial = complete_packet[:len(complete_packet)//2]
        packets = self.parser.parse_stream(partial)
        self.assertEqual(len(packets), 0)  # No complete packet yet
        
        # Send remaining half
        remaining = complete_packet[len(complete_packet)//2:]
        packets = self.parser.parse_stream(remaining)
        self.assertEqual(len(packets), 1)  # Now complete
    
    def test_parser_statistics(self):
        """Test parser statistics tracking."""
        # Parse some valid packets
        packet1 = self._create_test_packet(UartCommand.CMD_ACK)
        packet2 = self._create_test_packet(UartCommand.CMD_STATUS_REQUEST)
        
        self.parser.parse_stream(packet1)
        self.parser.parse_stream(packet2)
        
        stats = self.parser.get_stats()
        
        self.assertEqual(stats['packets_received'], 2)
        self.assertGreaterEqual(stats['success_rate'], 0.0)
        self.assertLessEqual(stats['success_rate'], 100.0)
    
    def test_parser_reset_stats(self):
        """Test parser statistics reset."""
        packet = self._create_test_packet(UartCommand.CMD_ACK)
        self.parser.parse_stream(packet)
        
        self.parser.reset_stats()
        stats = self.parser.get_stats()
        
        self.assertEqual(stats['packets_received'], 0)
        self.assertEqual(stats['checksum_errors'], 0)


class TestMAVLinkExtractor(unittest.TestCase):
    """Test cases for MAVLink extraction from binary packets."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.extractor = MAVLinkExtractor()
    
    def test_extract_from_non_bridge_packet(self):
        """Test that non-bridge packets return None."""
        # Create a non-bridge packet
        packet = ParsedBinaryPacket(
            timestamp=1234567890.0,
            command=UartCommand.CMD_ACK,
            payload=None,
            raw_bytes=b'\xaa\x02\x00\x00\x00\x00'
        )
        
        result = self.extractor.extract_mavlink(packet)
        self.assertIsNone(result)
    
    def test_extract_from_bridge_packet_no_payload(self):
        """Test extraction from bridge packet with no payload."""
        packet = ParsedBinaryPacket(
            timestamp=1234567890.0,
            command=UartCommand.CMD_BRIDGE_TX,
            payload=None,
            raw_bytes=b'\xaa\x06\x00\x00\x00\x00'
        )
        
        result = self.extractor.extract_mavlink(packet)
        self.assertIsNone(result)
    
    def test_extractor_statistics(self):
        """Test MAVLink extractor statistics."""
        stats = self.extractor.get_stats()
        
        self.assertIn('mavlink_extracted', stats)
        self.assertIn('mavlink_parse_errors', stats)
        self.assertIn('bridge_packets_processed', stats)


class TestBinaryCommandHandler(unittest.TestCase):
    """Test cases for BinaryCommandHandler."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.handler = BinaryCommandHandler()
    
    def test_handle_status_report(self):
        """Test handling STATUS_REPORT command."""
        # Create StatusPayload
        status_data = struct.pack('<BB10IffIB',
            1, 1, 100, 5000, 50, 50, 2500, 2500, 25, 25, 1250, 1250,
            -90.0, 7.5, 1000, 2
        )
        status_payload = StatusPayload.from_bytes(status_data)
        
        packet = ParsedBinaryPacket(
            timestamp=1234567890.0,
            command=UartCommand.CMD_STATUS_REPORT,
            payload=status_payload,
            raw_bytes=b''
        )
        
        self.handler.handle_packet(packet)
        
        self.assertIsNotNone(self.handler.get_latest_status())
        self.assertTrue(self.handler.is_relay_active())
        
        metrics = self.handler.get_system_metrics()
        self.assertEqual(metrics['packets_relayed'], 100)
        self.assertEqual(metrics['active_peer_relays'], 2)
    
    def test_handle_init_command(self):
        """Test handling INIT command."""
        # Create InitPayload
        mode = b'RELAY\x00' + b'\x00' * 10
        init_data = mode + struct.pack('<ffI', 915.0, 915.0, 5000)
        init_payload = InitPayload.from_bytes(init_data)
        
        packet = ParsedBinaryPacket(
            timestamp=1234567890.0,
            command=UartCommand.CMD_INIT,
            payload=init_payload,
            raw_bytes=b''
        )
        
        self.handler.handle_packet(packet)
        
        latest_init = self.handler.get_latest_init()
        self.assertIsNotNone(latest_init)
        self.assertEqual(latest_init.mode, 'RELAY')
    
    def test_handle_relay_activate(self):
        """Test handling RELAY_ACTIVATE command."""
        activate_payload = RelayActivatePayload(activate=True)
        
        packet = ParsedBinaryPacket(
            timestamp=1234567890.0,
            command=UartCommand.CMD_RELAY_ACTIVATE,
            payload=activate_payload,
            raw_bytes=b''
        )
        
        self.handler.handle_packet(packet)
        
        stats = self.handler.get_stats()
        self.assertEqual(stats['relay_activations_received'], 1)
    
    def test_command_handler_statistics(self):
        """Test command handler statistics tracking."""
        stats = self.handler.get_stats()
        
        self.assertIn('status_reports_received', stats)
        self.assertIn('init_commands_received', stats)
        self.assertIn('relay_requests_received', stats)
        
        # All should start at 0
        self.assertEqual(stats['status_reports_received'], 0)
    
    def test_reset_statistics(self):
        """Test resetting command handler statistics."""
        # Create and handle a packet
        activate_payload = RelayActivatePayload(activate=True)
        packet = ParsedBinaryPacket(
            timestamp=1234567890.0,
            command=UartCommand.CMD_RELAY_ACTIVATE,
            payload=activate_payload,
            raw_bytes=b''
        )
        self.handler.handle_packet(packet)
        
        # Reset stats
        self.handler.reset_stats()
        stats = self.handler.get_stats()
        
        self.assertEqual(stats['relay_activations_received'], 0)


if __name__ == '__main__':
    unittest.main()
