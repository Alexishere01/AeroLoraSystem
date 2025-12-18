#!/usr/bin/env python3
"""
Test script for BinaryCommandHandler - Task 3.5

This script validates that the BinaryCommandHandler correctly:
- Parses CMD_STATUS_REPORT for system metrics
- Parses CMD_RELAY_RX for relay telemetry
- Parses CMD_INIT for initialization data
- Stores parsed payloads for metrics and logging

Requirements: 1.2, 5.1
"""

import sys
import struct
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from binary_protocol_parser import (
    BinaryCommandHandler,
    ParsedBinaryPacket,
    UartCommand,
    StatusPayload,
    InitPayload,
    RelayRxPayload,
    RelayRequestPayload,
    RelayActivatePayload
)


def test_status_report_handling():
    """Test CMD_STATUS_REPORT parsing and storage"""
    print("\n=== Test 1: CMD_STATUS_REPORT Handling ===")
    
    handler = BinaryCommandHandler()
    
    # Create a mock StatusPayload
    status_data = struct.pack('<BB10IffIB',
        1,      # relay_active (bool)
        42,     # own_drone_sysid
        100,    # packets_relayed
        50000,  # bytes_relayed
        75,     # mesh_to_uart_packets
        80,     # uart_to_mesh_packets
        40000,  # mesh_to_uart_bytes
        45000,  # uart_to_mesh_bytes
        60,     # bridge_gcs_to_mesh_packets
        65,     # bridge_mesh_to_gcs_packets
        35000,  # bridge_gcs_to_mesh_bytes
        38000,  # bridge_mesh_to_gcs_bytes
        -85.5,  # rssi
        12.3,   # snr
        120,    # last_activity_sec
        3       # active_peer_relays
    )
    
    status_payload = StatusPayload.from_bytes(status_data)
    
    # Create a parsed packet
    packet = ParsedBinaryPacket(
        timestamp=1234567890.0,
        command=UartCommand.CMD_STATUS_REPORT,
        payload=status_payload,
        raw_bytes=b'\xaa\x08\x2f\x00' + status_data + b'\x00\x00',
        payload_bytes=status_data
    )
    
    # Handle the packet
    handler.handle_packet(packet)
    
    # Verify storage
    latest_status = handler.get_latest_status()
    print(f"  Latest status: {latest_status}")
    assert latest_status is not None, "Status should be stored"
    
    is_active = handler.is_relay_active()
    print(f"  Is relay active: {is_active}")
    assert is_active == True, f"Relay should be active, got {is_active}"
    
    reports_count = handler.stats['status_reports_received']
    print(f"  Status reports received: {reports_count}")
    assert reports_count == 1, f"Should count status reports, got {reports_count}"
    
    # Verify system metrics
    metrics = handler.get_system_metrics()
    print(f"  Metrics: {metrics}")
    assert metrics['relay_active'] == True, f"relay_active should be True, got {metrics.get('relay_active')}"
    assert metrics['own_drone_sysid'] == 42, f"own_drone_sysid should be 42, got {metrics.get('own_drone_sysid')}"
    assert metrics['packets_relayed'] == 100, f"packets_relayed should be 100, got {metrics.get('packets_relayed')}"
    assert metrics['bytes_relayed'] == 50000, f"bytes_relayed should be 50000, got {metrics.get('bytes_relayed')}"
    assert abs(metrics['rssi'] - (-85.5)) < 0.1, f"rssi should be -85.5, got {metrics.get('rssi')}"
    assert abs(metrics['snr'] - 12.3) < 0.1, f"snr should be 12.3, got {metrics.get('snr')}"
    assert metrics['active_peer_relays'] == 3, f"active_peer_relays should be 3, got {metrics.get('active_peer_relays')}"
    
    print("✓ CMD_STATUS_REPORT parsed correctly")
    print(f"  - Relay active: {metrics['relay_active']}")
    print(f"  - System ID: {metrics['own_drone_sysid']}")
    print(f"  - Packets relayed: {metrics['packets_relayed']}")
    print(f"  - RSSI: {metrics['rssi']:.1f} dBm")
    print(f"  - SNR: {metrics['snr']:.1f} dB")
    print(f"  - Active peer relays: {metrics['active_peer_relays']}")


def test_init_handling():
    """Test CMD_INIT parsing and storage"""
    print("\n=== Test 2: CMD_INIT Handling ===")
    
    handler = BinaryCommandHandler()
    
    # Create a mock InitPayload
    mode = b'FREQUENCY_BRIDGE'
    mode_padded = mode + b'\x00' * (16 - len(mode))
    init_data = mode_padded + struct.pack('<ffI', 915.0, 868.0, 12345)
    
    init_payload = InitPayload.from_bytes(init_data)
    
    # Create a parsed packet
    packet = ParsedBinaryPacket(
        timestamp=1234567890.0,
        command=UartCommand.CMD_INIT,
        payload=init_payload,
        raw_bytes=b'\xaa\x01\x1c\x00' + init_data + b'\x00\x00',
        payload_bytes=init_data
    )
    
    # Handle the packet
    handler.handle_packet(packet)
    
    # Verify storage
    latest_init = handler.get_latest_init()
    print(f"  Latest init: {latest_init}")
    assert latest_init is not None, "Init should be stored"
    
    init_count = handler.stats['init_commands_received']
    print(f"  Init commands received: {init_count}")
    assert init_count == 1, f"Should count init commands, got {init_count}"
    
    init = handler.get_latest_init()
    print(f"  Init mode: '{init.mode}'")
    print(f"  Init primary_freq: {init.primary_freq}")
    print(f"  Init secondary_freq: {init.secondary_freq}")
    print(f"  Init timestamp: {init.timestamp}")
    assert init.mode == 'FREQUENCY_BRIDGE', f"mode should be 'FREQUENCY_BRIDGE', got '{init.mode}'"
    assert init.primary_freq == 915.0, f"primary_freq should be 915.0, got {init.primary_freq}"
    assert init.secondary_freq == 868.0, f"secondary_freq should be 868.0, got {init.secondary_freq}"
    assert init.timestamp == 12345, f"timestamp should be 12345, got {init.timestamp}"
    
    print("✓ CMD_INIT parsed correctly")
    print(f"  - Mode: {init.mode}")
    print(f"  - Primary frequency: {init.primary_freq} MHz")
    print(f"  - Secondary frequency: {init.secondary_freq} MHz")
    print(f"  - Timestamp: {init.timestamp} ms")


def test_relay_rx_handling():
    """Test CMD_RELAY_RX parsing and storage"""
    print("\n=== Test 3: CMD_RELAY_RX Handling ===")
    
    handler = BinaryCommandHandler()
    
    # Create a mock RelayRxPayload
    relay_data = b'\x01\x02\x03\x04\x05'  # Sample relay data
    relay_payload_data = struct.pack('<ff', -92.5, 8.7) + relay_data
    
    relay_payload = RelayRxPayload.from_bytes(relay_payload_data)
    
    # Create a parsed packet
    packet = ParsedBinaryPacket(
        timestamp=1234567890.0,
        command=UartCommand.CMD_RELAY_RX,
        payload=relay_payload,
        raw_bytes=b'\xaa\x05\x0d\x00' + relay_payload_data + b'\x00\x00',
        payload_bytes=relay_payload_data
    )
    
    # Handle the packet
    handler.handle_packet(packet)
    
    # Verify storage
    assert handler.stats['relay_rx_packets_received'] == 1, "Should count relay RX packets"
    
    print("✓ CMD_RELAY_RX parsed correctly")
    print(f"  - RSSI: {relay_payload.rssi:.1f} dBm")
    print(f"  - SNR: {relay_payload.snr:.1f} dB")
    print(f"  - Data length: {len(relay_payload.data)} bytes")
    print(f"  - Relay RX packets received: {handler.stats['relay_rx_packets_received']}")


def test_relay_request_handling():
    """Test CMD_BROADCAST_RELAY_REQ parsing and storage"""
    print("\n=== Test 4: CMD_BROADCAST_RELAY_REQ Handling ===")
    
    handler = BinaryCommandHandler()
    
    # Create a mock RelayRequestPayload
    relay_req_data = struct.pack('<fff', -88.0, 10.5, 5.2)
    
    relay_req_payload = RelayRequestPayload.from_bytes(relay_req_data)
    
    # Create a parsed packet
    packet = ParsedBinaryPacket(
        timestamp=1234567890.0,
        command=UartCommand.CMD_BROADCAST_RELAY_REQ,
        payload=relay_req_payload,
        raw_bytes=b'\xaa\x09\x0c\x00' + relay_req_data + b'\x00\x00',
        payload_bytes=relay_req_data
    )
    
    # Handle the packet
    handler.handle_packet(packet)
    
    # Verify storage
    req_count = handler.stats['relay_requests_received']
    print(f"  Relay requests received: {req_count}")
    assert req_count == 1, f"Should count relay requests, got {req_count}"
    
    req_list_len = len(handler.relay_requests)
    print(f"  Relay requests stored: {req_list_len}")
    assert req_list_len == 1, f"Should store relay request, got {req_list_len}"
    
    stored_req = handler.relay_requests[0]
    print(f"  Stored request: {stored_req}")
    assert abs(stored_req['payload'].rssi - (-88.0)) < 0.1, f"rssi should be -88.0, got {stored_req['payload'].rssi}"
    assert abs(stored_req['payload'].snr - 10.5) < 0.1, f"snr should be 10.5, got {stored_req['payload'].snr}"
    assert abs(stored_req['payload'].packet_loss - 5.2) < 0.1, f"packet_loss should be 5.2, got {stored_req['payload'].packet_loss}"
    
    print("✓ CMD_BROADCAST_RELAY_REQ parsed correctly")
    print(f"  - RSSI: {relay_req_payload.rssi:.1f} dBm")
    print(f"  - SNR: {relay_req_payload.snr:.1f} dB")
    print(f"  - Packet loss: {relay_req_payload.packet_loss:.1f}%")
    print(f"  - Relay requests received: {handler.stats['relay_requests_received']}")


def test_relay_activate_handling():
    """Test CMD_RELAY_ACTIVATE parsing and storage"""
    print("\n=== Test 5: CMD_RELAY_ACTIVATE Handling ===")
    
    handler = BinaryCommandHandler()
    
    # Create a mock RelayActivatePayload
    relay_activate_data = struct.pack('<B', 1)  # activate = true
    
    relay_activate_payload = RelayActivatePayload.from_bytes(relay_activate_data)
    
    # Create a parsed packet
    packet = ParsedBinaryPacket(
        timestamp=1234567890.0,
        command=UartCommand.CMD_RELAY_ACTIVATE,
        payload=relay_activate_payload,
        raw_bytes=b'\xaa\x03\x01\x00' + relay_activate_data + b'\x00\x00',
        payload_bytes=relay_activate_data
    )
    
    # Handle the packet
    handler.handle_packet(packet)
    
    # Verify storage
    assert handler.stats['relay_activations_received'] == 1, "Should count relay activations"
    assert len(handler.relay_activations) == 1, "Should store relay activation"
    
    stored_activation = handler.relay_activations[0]
    assert stored_activation['activate'] == True
    
    print("✓ CMD_RELAY_ACTIVATE parsed correctly")
    print(f"  - Activate: {relay_activate_payload.activate}")
    print(f"  - Relay activations received: {handler.stats['relay_activations_received']}")


def test_multiple_status_reports():
    """Test that latest status is updated correctly"""
    print("\n=== Test 6: Multiple Status Reports ===")
    
    handler = BinaryCommandHandler()
    
    # Send first status report
    status_data_1 = struct.pack('<BB10IffIB',
        0, 42, 100, 50000, 75, 80, 40000, 45000, 60, 65, 35000, 38000,
        -85.5, 12.3, 120, 3
    )
    status_payload_1 = StatusPayload.from_bytes(status_data_1)
    packet_1 = ParsedBinaryPacket(
        timestamp=1234567890.0,
        command=UartCommand.CMD_STATUS_REPORT,
        payload=status_payload_1,
        raw_bytes=b'',
        payload_bytes=status_data_1
    )
    handler.handle_packet(packet_1)
    
    # Send second status report with different values
    status_data_2 = struct.pack('<BB10IffIB',
        1, 42, 200, 100000, 150, 160, 80000, 90000, 120, 130, 70000, 76000,
        -80.0, 15.0, 240, 5
    )
    status_payload_2 = StatusPayload.from_bytes(status_data_2)
    packet_2 = ParsedBinaryPacket(
        timestamp=1234567900.0,
        command=UartCommand.CMD_STATUS_REPORT,
        payload=status_payload_2,
        raw_bytes=b'',
        payload_bytes=status_data_2
    )
    handler.handle_packet(packet_2)
    
    # Verify latest status is the second one
    assert handler.stats['status_reports_received'] == 2
    assert handler.is_relay_active() == True
    
    metrics = handler.get_system_metrics()
    assert metrics['packets_relayed'] == 200  # From second report
    assert metrics['rssi'] == -80.0  # From second report
    
    print("✓ Multiple status reports handled correctly")
    print(f"  - Total status reports: {handler.stats['status_reports_received']}")
    print(f"  - Latest packets relayed: {metrics['packets_relayed']}")
    print(f"  - Latest RSSI: {metrics['rssi']:.1f} dBm")


def test_statistics():
    """Test statistics tracking"""
    print("\n=== Test 7: Statistics Tracking ===")
    
    handler = BinaryCommandHandler()
    
    # Create various packets
    status_data = struct.pack('<BB10IffIB',
        1, 42, 100, 50000, 75, 80, 40000, 45000, 60, 65, 35000, 38000,
        -85.5, 12.3, 120, 3
    )
    status_payload = StatusPayload.from_bytes(status_data)
    
    init_data = b'RELAY\x00' + b'\x00' * 10 + struct.pack('<ffI', 915.0, 868.0, 12345)
    init_payload = InitPayload.from_bytes(init_data)
    
    relay_rx_data = struct.pack('<ff', -92.5, 8.7) + b'\x01\x02\x03'
    relay_rx_payload = RelayRxPayload.from_bytes(relay_rx_data)
    
    # Send multiple packets
    for i in range(5):
        handler.handle_packet(ParsedBinaryPacket(
            timestamp=1234567890.0 + i,
            command=UartCommand.CMD_STATUS_REPORT,
            payload=status_payload,
            raw_bytes=b'',
            payload_bytes=status_data
        ))
    
    for i in range(3):
        handler.handle_packet(ParsedBinaryPacket(
            timestamp=1234567890.0 + i,
            command=UartCommand.CMD_INIT,
            payload=init_payload,
            raw_bytes=b'',
            payload_bytes=init_data
        ))
    
    for i in range(7):
        handler.handle_packet(ParsedBinaryPacket(
            timestamp=1234567890.0 + i,
            command=UartCommand.CMD_RELAY_RX,
            payload=relay_rx_payload,
            raw_bytes=b'',
            payload_bytes=relay_rx_data
        ))
    
    # Verify statistics
    stats = handler.get_stats()
    assert stats['status_reports_received'] == 5
    assert stats['init_commands_received'] == 3
    assert stats['relay_rx_packets_received'] == 7
    
    print("✓ Statistics tracked correctly")
    print(f"  - Status reports: {stats['status_reports_received']}")
    print(f"  - Init commands: {stats['init_commands_received']}")
    print(f"  - Relay RX packets: {stats['relay_rx_packets_received']}")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Binary Command Handler Test Suite - Task 3.5")
    print("=" * 60)
    
    try:
        test_status_report_handling()
        test_init_handling()
        test_relay_rx_handling()
        test_relay_request_handling()
        test_relay_activate_handling()
        test_multiple_status_reports()
        test_statistics()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        print("\nTask 3.5 Implementation Verified:")
        print("  ✓ CMD_STATUS_REPORT parsing and storage")
        print("  ✓ CMD_RELAY_RX parsing and storage")
        print("  ✓ CMD_INIT parsing and storage")
        print("  ✓ CMD_BROADCAST_RELAY_REQ parsing and storage")
        print("  ✓ CMD_RELAY_ACTIVATE parsing and storage")
        print("  ✓ System metrics extraction")
        print("  ✓ Statistics tracking")
        print("\nRequirements satisfied: 1.2, 5.1")
        
        return 0
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
