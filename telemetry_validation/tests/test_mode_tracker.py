"""
Unit tests for Mode Tracker module.

Tests mode detection, transition logging, and statistics tracking.

Requirements: 6.1
"""

import unittest
import time
from src.mode_tracker import ModeTracker, OperatingMode, ModeTransition
from src.binary_protocol_parser import ParsedBinaryPacket, UartCommand, StatusPayload


class TestModeTracker(unittest.TestCase):
    """Test cases for ModeTracker class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tracker = ModeTracker()
    
    def test_initialization(self):
        """Test mode tracker initialization."""
        self.assertEqual(self.tracker.current_mode, OperatingMode.UNKNOWN)
        self.assertEqual(len(self.tracker.mode_transitions), 0)
        self.assertEqual(self.tracker.stats['total_transitions'], 0)
    
    def test_initial_mode_detection_direct(self):
        """Test initial mode detection for direct mode."""
        # Create status payload with relay_active = False
        status = StatusPayload(
            relay_active=False,
            own_drone_sysid=1,
            packets_relayed=0,
            bytes_relayed=0,
            mesh_to_uart_packets=0,
            uart_to_mesh_packets=0,
            mesh_to_uart_bytes=0,
            uart_to_mesh_bytes=0,
            bridge_gcs_to_mesh_packets=0,
            bridge_mesh_to_gcs_packets=0,
            bridge_gcs_to_mesh_bytes=0,
            bridge_mesh_to_gcs_bytes=0,
            rssi=-80.0,
            snr=10.0,
            last_activity_sec=0,
            active_peer_relays=0
        )
        
        packet = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_STATUS_REPORT,
            payload=status,
            raw_bytes=b'',
            payload_bytes=b''
        )
        
        self.tracker.update(packet)
        
        self.assertEqual(self.tracker.current_mode, OperatingMode.DIRECT)
        self.assertEqual(len(self.tracker.mode_transitions), 0)
        self.assertEqual(self.tracker.stats['status_reports_processed'], 1)
    
    def test_initial_mode_detection_relay(self):
        """Test initial mode detection for relay mode."""
        # Create status payload with relay_active = True
        status = StatusPayload(
            relay_active=True,
            own_drone_sysid=1,
            packets_relayed=10,
            bytes_relayed=1000,
            mesh_to_uart_packets=5,
            uart_to_mesh_packets=5,
            mesh_to_uart_bytes=500,
            uart_to_mesh_bytes=500,
            bridge_gcs_to_mesh_packets=0,
            bridge_mesh_to_gcs_packets=0,
            bridge_gcs_to_mesh_bytes=0,
            bridge_mesh_to_gcs_bytes=0,
            rssi=-85.0,
            snr=8.0,
            last_activity_sec=1,
            active_peer_relays=2
        )
        
        packet = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_STATUS_REPORT,
            payload=status,
            raw_bytes=b'',
            payload_bytes=b''
        )
        
        self.tracker.update(packet)
        
        self.assertEqual(self.tracker.current_mode, OperatingMode.RELAY)
        self.assertEqual(len(self.tracker.mode_transitions), 0)
    
    def test_mode_transition_direct_to_relay(self):
        """Test mode transition from direct to relay."""
        # Start in direct mode
        status_direct = StatusPayload(
            relay_active=False,
            own_drone_sysid=1,
            packets_relayed=0,
            bytes_relayed=0,
            mesh_to_uart_packets=0,
            uart_to_mesh_packets=0,
            mesh_to_uart_bytes=0,
            uart_to_mesh_bytes=0,
            bridge_gcs_to_mesh_packets=0,
            bridge_mesh_to_gcs_packets=0,
            bridge_gcs_to_mesh_bytes=0,
            bridge_mesh_to_gcs_bytes=0,
            rssi=-80.0,
            snr=10.0,
            last_activity_sec=0,
            active_peer_relays=0
        )
        
        packet_direct = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_STATUS_REPORT,
            payload=status_direct,
            raw_bytes=b'',
            payload_bytes=b''
        )
        
        self.tracker.update(packet_direct)
        self.assertEqual(self.tracker.current_mode, OperatingMode.DIRECT)
        
        # Transition to relay mode
        time.sleep(0.1)
        status_relay = StatusPayload(
            relay_active=True,
            own_drone_sysid=1,
            packets_relayed=5,
            bytes_relayed=500,
            mesh_to_uart_packets=3,
            uart_to_mesh_packets=2,
            mesh_to_uart_bytes=300,
            uart_to_mesh_bytes=200,
            bridge_gcs_to_mesh_packets=0,
            bridge_mesh_to_gcs_packets=0,
            bridge_gcs_to_mesh_bytes=0,
            bridge_mesh_to_gcs_bytes=0,
            rssi=-85.0,
            snr=8.0,
            last_activity_sec=1,
            active_peer_relays=1
        )
        
        packet_relay = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_STATUS_REPORT,
            payload=status_relay,
            raw_bytes=b'',
            payload_bytes=b''
        )
        
        self.tracker.update(packet_relay)
        
        self.assertEqual(self.tracker.current_mode, OperatingMode.RELAY)
        self.assertEqual(len(self.tracker.mode_transitions), 1)
        self.assertEqual(self.tracker.stats['total_transitions'], 1)
        self.assertEqual(self.tracker.stats['relay_mode_count'], 1)
        
        # Check transition details
        transition = self.tracker.mode_transitions[0]
        self.assertEqual(transition.from_mode, OperatingMode.DIRECT)
        self.assertEqual(transition.to_mode, OperatingMode.RELAY)
        self.assertTrue(transition.relay_active)
        self.assertEqual(transition.packets_relayed, 5)
        self.assertEqual(transition.active_peer_relays, 1)
    
    def test_mode_transition_relay_to_direct(self):
        """Test mode transition from relay to direct."""
        # Start in relay mode
        status_relay = StatusPayload(
            relay_active=True,
            own_drone_sysid=1,
            packets_relayed=10,
            bytes_relayed=1000,
            mesh_to_uart_packets=5,
            uart_to_mesh_packets=5,
            mesh_to_uart_bytes=500,
            uart_to_mesh_bytes=500,
            bridge_gcs_to_mesh_packets=0,
            bridge_mesh_to_gcs_packets=0,
            bridge_gcs_to_mesh_bytes=0,
            bridge_mesh_to_gcs_bytes=0,
            rssi=-85.0,
            snr=8.0,
            last_activity_sec=1,
            active_peer_relays=2
        )
        
        packet_relay = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_STATUS_REPORT,
            payload=status_relay,
            raw_bytes=b'',
            payload_bytes=b''
        )
        
        self.tracker.update(packet_relay)
        self.assertEqual(self.tracker.current_mode, OperatingMode.RELAY)
        
        # Transition to direct mode
        time.sleep(0.1)
        status_direct = StatusPayload(
            relay_active=False,
            own_drone_sysid=1,
            packets_relayed=10,
            bytes_relayed=1000,
            mesh_to_uart_packets=5,
            uart_to_mesh_packets=5,
            mesh_to_uart_bytes=500,
            uart_to_mesh_bytes=500,
            bridge_gcs_to_mesh_packets=0,
            bridge_mesh_to_gcs_packets=0,
            bridge_gcs_to_mesh_bytes=0,
            bridge_mesh_to_gcs_bytes=0,
            rssi=-80.0,
            snr=10.0,
            last_activity_sec=0,
            active_peer_relays=0
        )
        
        packet_direct = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_STATUS_REPORT,
            payload=status_direct,
            raw_bytes=b'',
            payload_bytes=b''
        )
        
        self.tracker.update(packet_direct)
        
        self.assertEqual(self.tracker.current_mode, OperatingMode.DIRECT)
        self.assertEqual(len(self.tracker.mode_transitions), 1)
        self.assertEqual(self.tracker.stats['total_transitions'], 1)
        self.assertEqual(self.tracker.stats['direct_mode_count'], 1)
        
        # Check transition details
        transition = self.tracker.mode_transitions[0]
        self.assertEqual(transition.from_mode, OperatingMode.RELAY)
        self.assertEqual(transition.to_mode, OperatingMode.DIRECT)
        self.assertFalse(transition.relay_active)
    
    def test_multiple_transitions(self):
        """Test multiple mode transitions."""
        # Direct -> Relay -> Direct -> Relay
        modes = [False, True, False, True]
        
        for i, relay_active in enumerate(modes):
            status = StatusPayload(
                relay_active=relay_active,
                own_drone_sysid=1,
                packets_relayed=i * 5,
                bytes_relayed=i * 500,
                mesh_to_uart_packets=i * 2,
                uart_to_mesh_packets=i * 2,
                mesh_to_uart_bytes=i * 200,
                uart_to_mesh_bytes=i * 200,
                bridge_gcs_to_mesh_packets=0,
                bridge_mesh_to_gcs_packets=0,
                bridge_gcs_to_mesh_bytes=0,
                bridge_mesh_to_gcs_bytes=0,
                rssi=-80.0 - i,
                snr=10.0 - i,
                last_activity_sec=i,
                active_peer_relays=1 if relay_active else 0
            )
            
            packet = ParsedBinaryPacket(
                timestamp=time.time(),
                command=UartCommand.CMD_STATUS_REPORT,
                payload=status,
                raw_bytes=b'',
                payload_bytes=b''
            )
            
            self.tracker.update(packet)
            time.sleep(0.05)
        
        # Should have 3 transitions (initial mode doesn't count as transition)
        # Sequence: Direct (initial) -> Relay (transition 1) -> Direct (transition 2) -> Relay (transition 3)
        self.assertEqual(len(self.tracker.mode_transitions), 3)
        self.assertEqual(self.tracker.stats['total_transitions'], 3)
        # direct_mode_count counts transitions TO direct mode (not initial detection)
        self.assertEqual(self.tracker.stats['direct_mode_count'], 1)
        # relay_mode_count counts transitions TO relay mode
        self.assertEqual(self.tracker.stats['relay_mode_count'], 2)
    
    def test_get_current_mode(self):
        """Test getting current mode."""
        self.assertEqual(self.tracker.get_current_mode(), OperatingMode.UNKNOWN)
        
        # Set to direct mode
        status = StatusPayload(
            relay_active=False,
            own_drone_sysid=1,
            packets_relayed=0,
            bytes_relayed=0,
            mesh_to_uart_packets=0,
            uart_to_mesh_packets=0,
            mesh_to_uart_bytes=0,
            uart_to_mesh_bytes=0,
            bridge_gcs_to_mesh_packets=0,
            bridge_mesh_to_gcs_packets=0,
            bridge_gcs_to_mesh_bytes=0,
            bridge_mesh_to_gcs_bytes=0,
            rssi=-80.0,
            snr=10.0,
            last_activity_sec=0,
            active_peer_relays=0
        )
        
        packet = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_STATUS_REPORT,
            payload=status,
            raw_bytes=b'',
            payload_bytes=b''
        )
        
        self.tracker.update(packet)
        self.assertEqual(self.tracker.get_current_mode(), OperatingMode.DIRECT)
    
    def test_get_mode_transitions(self):
        """Test getting mode transition history."""
        transitions = self.tracker.get_mode_transitions()
        self.assertEqual(len(transitions), 0)
        
        # Create a transition
        status_direct = StatusPayload(
            relay_active=False,
            own_drone_sysid=1,
            packets_relayed=0,
            bytes_relayed=0,
            mesh_to_uart_packets=0,
            uart_to_mesh_packets=0,
            mesh_to_uart_bytes=0,
            uart_to_mesh_bytes=0,
            bridge_gcs_to_mesh_packets=0,
            bridge_mesh_to_gcs_packets=0,
            bridge_gcs_to_mesh_bytes=0,
            bridge_mesh_to_gcs_bytes=0,
            rssi=-80.0,
            snr=10.0,
            last_activity_sec=0,
            active_peer_relays=0
        )
        
        packet_direct = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_STATUS_REPORT,
            payload=status_direct,
            raw_bytes=b'',
            payload_bytes=b''
        )
        
        self.tracker.update(packet_direct)
        
        status_relay = StatusPayload(
            relay_active=True,
            own_drone_sysid=1,
            packets_relayed=5,
            bytes_relayed=500,
            mesh_to_uart_packets=3,
            uart_to_mesh_packets=2,
            mesh_to_uart_bytes=300,
            uart_to_mesh_bytes=200,
            bridge_gcs_to_mesh_packets=0,
            bridge_mesh_to_gcs_packets=0,
            bridge_gcs_to_mesh_bytes=0,
            bridge_mesh_to_gcs_bytes=0,
            rssi=-85.0,
            snr=8.0,
            last_activity_sec=1,
            active_peer_relays=1
        )
        
        packet_relay = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_STATUS_REPORT,
            payload=status_relay,
            raw_bytes=b'',
            payload_bytes=b''
        )
        
        self.tracker.update(packet_relay)
        
        transitions = self.tracker.get_mode_transitions()
        self.assertEqual(len(transitions), 1)
        self.assertIsInstance(transitions[0], ModeTransition)
    
    def test_get_mode_duration(self):
        """Test getting time spent in each mode."""
        # Initially no time in any mode
        self.assertEqual(self.tracker.get_mode_duration(OperatingMode.DIRECT), 0.0)
        self.assertEqual(self.tracker.get_mode_duration(OperatingMode.RELAY), 0.0)
        
        # Set to direct mode
        status_direct = StatusPayload(
            relay_active=False,
            own_drone_sysid=1,
            packets_relayed=0,
            bytes_relayed=0,
            mesh_to_uart_packets=0,
            uart_to_mesh_packets=0,
            mesh_to_uart_bytes=0,
            uart_to_mesh_bytes=0,
            bridge_gcs_to_mesh_packets=0,
            bridge_mesh_to_gcs_packets=0,
            bridge_gcs_to_mesh_bytes=0,
            bridge_mesh_to_gcs_bytes=0,
            rssi=-80.0,
            snr=10.0,
            last_activity_sec=0,
            active_peer_relays=0
        )
        
        packet_direct = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_STATUS_REPORT,
            payload=status_direct,
            raw_bytes=b'',
            payload_bytes=b''
        )
        
        self.tracker.update(packet_direct)
        
        # Wait a bit
        time.sleep(0.1)
        
        # Should have some time in direct mode
        direct_time = self.tracker.get_mode_duration(OperatingMode.DIRECT)
        self.assertGreater(direct_time, 0.0)
        self.assertLess(direct_time, 1.0)  # Should be less than 1 second
    
    def test_get_stats(self):
        """Test getting statistics."""
        stats = self.tracker.get_stats()
        
        self.assertIn('current_mode', stats)
        self.assertIn('total_transitions', stats)
        self.assertIn('direct_mode_count', stats)
        self.assertIn('relay_mode_count', stats)
        self.assertIn('status_reports_processed', stats)
        self.assertIn('direct_mode_time_seconds', stats)
        self.assertIn('relay_mode_time_seconds', stats)
        self.assertIn('direct_mode_percentage', stats)
        self.assertIn('relay_mode_percentage', stats)
        self.assertIn('uptime_seconds', stats)
        
        self.assertEqual(stats['current_mode'], 'UNKNOWN')
        self.assertEqual(stats['total_transitions'], 0)
    
    def test_reset_stats(self):
        """Test resetting statistics."""
        # Create some activity
        status = StatusPayload(
            relay_active=False,
            own_drone_sysid=1,
            packets_relayed=0,
            bytes_relayed=0,
            mesh_to_uart_packets=0,
            uart_to_mesh_packets=0,
            mesh_to_uart_bytes=0,
            uart_to_mesh_bytes=0,
            bridge_gcs_to_mesh_packets=0,
            bridge_mesh_to_gcs_packets=0,
            bridge_gcs_to_mesh_bytes=0,
            bridge_mesh_to_gcs_bytes=0,
            rssi=-80.0,
            snr=10.0,
            last_activity_sec=0,
            active_peer_relays=0
        )
        
        packet = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_STATUS_REPORT,
            payload=status,
            raw_bytes=b'',
            payload_bytes=b''
        )
        
        self.tracker.update(packet)
        self.assertEqual(self.tracker.stats['status_reports_processed'], 1)
        
        # Reset
        self.tracker.reset_stats()
        
        self.assertEqual(self.tracker.current_mode, OperatingMode.UNKNOWN)
        self.assertEqual(len(self.tracker.mode_transitions), 0)
        self.assertEqual(self.tracker.stats['status_reports_processed'], 0)
        self.assertEqual(self.tracker.stats['total_transitions'], 0)
    
    def test_ignores_non_status_packets(self):
        """Test that non-status packets are ignored."""
        # Create a non-status packet
        packet = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_BRIDGE_TX,
            payload=None,
            raw_bytes=b'',
            payload_bytes=b''
        )
        
        self.tracker.update(packet)
        
        # Should still be unknown
        self.assertEqual(self.tracker.current_mode, OperatingMode.UNKNOWN)
        self.assertEqual(self.tracker.stats['status_reports_processed'], 0)


if __name__ == '__main__':
    unittest.main()
