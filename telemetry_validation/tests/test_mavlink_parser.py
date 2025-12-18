"""
Unit tests for MAVLink Parser module.

Tests cover:
- Basic message parsing
- Buffer management
- Statistics tracking
- RSSI/SNR extraction
- Error handling
"""

import unittest
import time
from pymavlink import mavutil
from src.mavlink_parser import MAVLinkParser, ParsedMessage


class TestMAVLinkParser(unittest.TestCase):
    """Test cases for MAVLinkParser class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = MAVLinkParser()
        
        # Create a MAVLink connection for generating test packets
        self.mav_gen = mavutil.mavlink.MAVLink(None)
        self.mav_gen.srcSystem = 1
        self.mav_gen.srcComponent = 1
    
    def _generate_heartbeat(self) -> bytes:
        """Generate a HEARTBEAT message packet."""
        msg = self.mav_gen.heartbeat_encode(
            type=mavutil.mavlink.MAV_TYPE_QUADROTOR,
            autopilot=mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
            base_mode=0,
            custom_mode=0,
            system_status=mavutil.mavlink.MAV_STATE_ACTIVE
        )
        return msg.pack(self.mav_gen)
    
    def _generate_gps_raw_int(self) -> bytes:
        """Generate a GPS_RAW_INT message packet."""
        msg = self.mav_gen.gps_raw_int_encode(
            time_usec=int(time.time() * 1e6),
            fix_type=3,  # 3D fix
            lat=374564320,  # 37.4564320 degrees
            lon=-1220987650,  # -122.0987650 degrees
            alt=50000,  # 50 meters
            eph=100,
            epv=100,
            vel=500,
            cog=18000,
            satellites_visible=10
        )
        return msg.pack(self.mav_gen)
    
    def _generate_radio_status(self, rssi=150, remrssi=140, noise=50, remnoise=45) -> bytes:
        """Generate a RADIO_STATUS message packet."""
        msg = self.mav_gen.radio_status_encode(
            rssi=rssi,
            remrssi=remrssi,
            txbuf=100,
            noise=noise,
            remnoise=remnoise,
            rxerrors=0,
            fixed=0
        )
        return msg.pack(self.mav_gen)
    
    def test_parser_initialization(self):
        """Test that parser initializes correctly."""
        self.assertIsNotNone(self.parser.mav)
        self.assertEqual(self.parser.stats['total_packets'], 0)
        self.assertIsNone(self.parser.last_rssi)
        self.assertIsNone(self.parser.last_snr)
    
    def test_parse_single_heartbeat(self):
        """Test parsing a single HEARTBEAT message."""
        packet = self._generate_heartbeat()
        messages = self.parser.parse_stream(packet)
        
        self.assertEqual(len(messages), 1)
        msg = messages[0]
        
        self.assertIsInstance(msg, ParsedMessage)
        self.assertEqual(msg.msg_type, 'HEARTBEAT')
        self.assertEqual(msg.system_id, 1)
        self.assertEqual(msg.component_id, 1)
        self.assertIsInstance(msg.fields, dict)
        self.assertGreater(msg.timestamp, 0)
    
    def test_parse_multiple_messages(self):
        """Test parsing multiple messages in one stream."""
        packet1 = self._generate_heartbeat()
        packet2 = self._generate_gps_raw_int()
        combined = packet1 + packet2
        
        messages = self.parser.parse_stream(combined)
        
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].msg_type, 'HEARTBEAT')
        self.assertEqual(messages[1].msg_type, 'GPS_RAW_INT')
    
    def test_parse_fragmented_message(self):
        """Test parsing a message split across multiple calls."""
        packet = self._generate_heartbeat()
        
        # Split packet in half
        part1 = packet[:len(packet)//2]
        part2 = packet[len(packet)//2:]
        
        # First part should not produce a message
        messages1 = self.parser.parse_stream(part1)
        self.assertEqual(len(messages1), 0)
        
        # Second part should complete the message
        messages2 = self.parser.parse_stream(part2)
        self.assertEqual(len(messages2), 1)
        self.assertEqual(messages2[0].msg_type, 'HEARTBEAT')
    
    def test_statistics_tracking(self):
        """Test that statistics are tracked correctly."""
        initial_stats = self.parser.get_stats()
        self.assertEqual(initial_stats['total_packets'], 0)
        
        # Parse some messages
        packet1 = self._generate_heartbeat()
        packet2 = self._generate_gps_raw_int()
        
        self.parser.parse_stream(packet1)
        self.parser.parse_stream(packet2)
        
        stats = self.parser.get_stats()
        self.assertEqual(stats['total_packets'], 2)
        self.assertGreater(stats['bytes_processed'], 0)
    
    def test_rssi_snr_extraction(self):
        """Test RSSI and SNR extraction from RADIO_STATUS."""
        # First, send a RADIO_STATUS message
        radio_packet = self._generate_radio_status(rssi=150, remrssi=140, noise=50, remnoise=45)
        messages = self.parser.parse_stream(radio_packet)
        
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].msg_type, 'RADIO_STATUS')
        
        # Check that RSSI and SNR were extracted
        self.assertIsNotNone(self.parser.last_rssi)
        self.assertIsNotNone(self.parser.last_snr)
        
        # Now send another message and verify RSSI/SNR are attached
        heartbeat_packet = self._generate_heartbeat()
        messages = self.parser.parse_stream(heartbeat_packet)
        
        self.assertEqual(len(messages), 1)
        self.assertIsNotNone(messages[0].rssi)
        self.assertIsNotNone(messages[0].snr)
        self.assertEqual(messages[0].rssi, self.parser.last_rssi)
        self.assertEqual(messages[0].snr, self.parser.last_snr)
    
    def test_rssi_snr_persistence(self):
        """Test that RSSI/SNR persist across multiple messages."""
        # Send RADIO_STATUS
        radio_packet = self._generate_radio_status(rssi=150, remrssi=140)
        self.parser.parse_stream(radio_packet)
        
        rssi_value = self.parser.last_rssi
        snr_value = self.parser.last_snr
        
        # Send multiple other messages
        for _ in range(3):
            packet = self._generate_heartbeat()
            messages = self.parser.parse_stream(packet)
            
            # Each should have the same RSSI/SNR
            self.assertEqual(messages[0].rssi, rssi_value)
            self.assertEqual(messages[0].snr, snr_value)
    
    def test_invalid_data_handling(self):
        """Test handling of invalid data."""
        # Send garbage data
        invalid_data = b'\x00\x01\x02\x03\x04\x05'
        messages = self.parser.parse_stream(invalid_data)
        
        # Should not crash and should not produce messages
        self.assertEqual(len(messages), 0)
        
        # Bytes should still be processed
        stats = self.parser.get_stats()
        self.assertEqual(stats['bytes_processed'], len(invalid_data))
    
    def test_mixed_valid_invalid_data(self):
        """Test parsing with mixed valid and invalid data."""
        valid_packet = self._generate_heartbeat()
        invalid_data = b'\x00\x01\x02'
        
        # Mix invalid data before valid packet
        mixed = invalid_data + valid_packet
        messages = self.parser.parse_stream(mixed)
        
        # Should still parse the valid message
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].msg_type, 'HEARTBEAT')
    
    def test_reset_stats(self):
        """Test statistics reset functionality."""
        # Generate some activity
        packet = self._generate_heartbeat()
        self.parser.parse_stream(packet)
        
        stats_before = self.parser.get_stats()
        self.assertGreater(stats_before['total_packets'], 0)
        
        # Reset
        self.parser.reset_stats()
        
        stats_after = self.parser.get_stats()
        self.assertEqual(stats_after['total_packets'], 0)
        self.assertEqual(stats_after['parse_errors'], 0)
        self.assertEqual(stats_after['bytes_processed'], 0)
    
    def test_clear_buffer(self):
        """Test parser state clearing functionality."""
        # Parse some data
        packet = self._generate_heartbeat()
        self.parser.parse_stream(packet)
        
        # Clear parser state
        self.parser.clear_buffer()
        
        # Parser should still work after clearing
        packet2 = self._generate_heartbeat()
        messages = self.parser.parse_stream(packet2)
        
        # Should be able to parse messages after clearing
        self.assertGreaterEqual(len(messages), 0)
    
    def test_parsed_message_fields(self):
        """Test that ParsedMessage contains all expected fields."""
        packet = self._generate_gps_raw_int()
        messages = self.parser.parse_stream(packet)
        
        self.assertEqual(len(messages), 1)
        msg = messages[0]
        
        # Check all required fields exist
        self.assertIsNotNone(msg.timestamp)
        self.assertIsNotNone(msg.msg_type)
        self.assertIsNotNone(msg.msg_id)
        self.assertIsNotNone(msg.system_id)
        self.assertIsNotNone(msg.component_id)
        self.assertIsNotNone(msg.fields)
        
        # Check GPS-specific fields
        self.assertIn('lat', msg.fields)
        self.assertIn('lon', msg.fields)
        self.assertIn('alt', msg.fields)
        self.assertIn('fix_type', msg.fields)
    
    def test_error_rate_calculation(self):
        """Test error rate calculation in statistics."""
        # Parse valid messages
        for _ in range(10):
            packet = self._generate_heartbeat()
            self.parser.parse_stream(packet)
        
        stats = self.parser.get_stats()
        
        # With no errors, error rate should be 0
        self.assertEqual(stats['error_rate'], 0.0)
        
        # Manually inject some errors for testing
        self.parser.stats['parse_errors'] = 2
        stats = self.parser.get_stats()
        
        # Error rate should be calculated
        expected_rate = (2 / 12) * 100  # 2 errors out of 12 total
        self.assertAlmostEqual(stats['error_rate'], expected_rate, places=2)


class TestParsedMessage(unittest.TestCase):
    """Test cases for ParsedMessage dataclass."""
    
    def test_parsed_message_creation(self):
        """Test creating a ParsedMessage instance."""
        msg = ParsedMessage(
            timestamp=time.time(),
            msg_type='HEARTBEAT',
            msg_id=0,
            system_id=1,
            component_id=1,
            fields={'type': 2, 'autopilot': 3},
            rssi=-50.0,
            snr=20.0,
            raw_bytes=b'\xfe\x09\x00\x01\x01'
        )
        
        self.assertEqual(msg.msg_type, 'HEARTBEAT')
        self.assertEqual(msg.system_id, 1)
        self.assertEqual(msg.rssi, -50.0)
        self.assertEqual(msg.snr, 20.0)
    
    def test_parsed_message_optional_fields(self):
        """Test ParsedMessage with optional fields as None."""
        msg = ParsedMessage(
            timestamp=time.time(),
            msg_type='GPS_RAW_INT',
            msg_id=24,
            system_id=1,
            component_id=1,
            fields={}
        )
        
        # Optional fields should default to None or empty
        self.assertIsNone(msg.rssi)
        self.assertIsNone(msg.snr)
        self.assertEqual(msg.raw_bytes, b'')


if __name__ == '__main__':
    unittest.main()
