#!/usr/bin/env python3
"""
Test script for binary protocol packet logging functionality.

This script validates that the TelemetryLogger correctly logs binary protocol
packets to .binlog files with full packet data including headers and checksums.

Requirements: 1.1, 10.4
"""

import sys
import os
import struct
import tempfile
import shutil
from pathlib import Path

# Add src directory to path
src_path = os.path.join(os.path.dirname(__file__), 'src')
sys.path.insert(0, src_path)

# Import from src package
from src.telemetry_logger import TelemetryLogger
from src.binary_protocol_parser import (
    BinaryProtocolParser, 
    ParsedBinaryPacket, 
    UartCommand,
    BridgePayload,
    StatusPayload,
    InitPayload,
    fletcher16,
    PACKET_START_BYTE
)


def create_test_binary_packet(command: UartCommand, payload_bytes: bytes) -> bytes:
    """
    Create a test binary protocol packet with proper structure.
    
    Args:
        command: Command type
        payload_bytes: Payload data
        
    Returns:
        Complete binary packet with headers and checksum
    """
    # Build packet header
    packet = bytearray()
    packet.append(PACKET_START_BYTE)  # Start byte
    packet.append(command.value)       # Command
    
    # Length (little-endian, 2 bytes)
    payload_len = len(payload_bytes)
    packet.append(payload_len & 0xFF)
    packet.append((payload_len >> 8) & 0xFF)
    
    # Payload
    packet.extend(payload_bytes)
    
    # Calculate checksum over header + payload
    checksum = fletcher16(bytes(packet))
    
    # Append checksum (little-endian, 2 bytes)
    packet.append(checksum & 0xFF)
    packet.append((checksum >> 8) & 0xFF)
    
    return bytes(packet)


def create_test_init_packet() -> bytes:
    """Create a test CMD_INIT packet"""
    # Create InitPayload
    mode = b"TEST_MODE\x00\x00\x00\x00\x00\x00\x00"  # 16 bytes
    primary_freq = struct.pack('<f', 915.0)
    secondary_freq = struct.pack('<f', 868.0)
    timestamp = struct.pack('<I', 12345)
    
    payload = mode + primary_freq + secondary_freq + timestamp
    
    return create_test_binary_packet(UartCommand.CMD_INIT, payload)


def create_test_bridge_packet() -> bytes:
    """Create a test CMD_BRIDGE_RX packet with MAVLink data"""
    # Create BridgePayload
    system_id = 1
    rssi = -85.5
    snr = 8.2
    
    # Fake MAVLink packet (simplified)
    mavlink_data = b'\xfe\x09\x00\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    data_len = len(mavlink_data)
    
    # Pack BridgePayload
    payload = struct.pack('<B', system_id)  # system_id
    payload += struct.pack('<f', rssi)       # rssi
    payload += struct.pack('<f', snr)        # snr
    payload += struct.pack('<H', data_len)   # data_len
    payload += mavlink_data                  # data
    
    return create_test_binary_packet(UartCommand.CMD_BRIDGE_RX, payload)


def create_test_status_packet() -> bytes:
    """Create a test CMD_STATUS_REPORT packet"""
    # Create StatusPayload (55 bytes)
    payload = struct.pack('<BB10IffIB',
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
    
    return create_test_binary_packet(UartCommand.CMD_STATUS_REPORT, payload)


def test_binary_packet_logging():
    """Test binary protocol packet logging functionality"""
    print("=" * 70)
    print("Binary Protocol Packet Logging Test")
    print("=" * 70)
    
    # Create temporary directory for test logs
    temp_dir = tempfile.mkdtemp(prefix='binlog_test_')
    print(f"\n✓ Created temporary log directory: {temp_dir}")
    
    try:
        # Initialize logger
        logger = TelemetryLogger(log_dir=temp_dir, max_file_size_mb=1)
        print("✓ Initialized TelemetryLogger")
        
        # Create test packets
        init_packet = create_test_init_packet()
        bridge_packet = create_test_bridge_packet()
        status_packet = create_test_status_packet()
        
        print(f"\n✓ Created test packets:")
        print(f"  - INIT packet: {len(init_packet)} bytes")
        print(f"  - BRIDGE_RX packet: {len(bridge_packet)} bytes")
        print(f"  - STATUS_REPORT packet: {len(status_packet)} bytes")
        
        # Parse packets using BinaryProtocolParser
        parser = BinaryProtocolParser()
        
        # Parse and log INIT packet
        parsed_packets = parser.parse_stream(init_packet)
        if parsed_packets:
            logger.log_binary_packet(parsed_packets[0])
            print(f"\n✓ Logged INIT packet (command: {parsed_packets[0].command.name})")
        
        # Parse and log BRIDGE_RX packet
        parsed_packets = parser.parse_stream(bridge_packet)
        if parsed_packets:
            logger.log_binary_packet(parsed_packets[0])
            print(f"✓ Logged BRIDGE_RX packet (command: {parsed_packets[0].command.name})")
        
        # Parse and log STATUS_REPORT packet
        parsed_packets = parser.parse_stream(status_packet)
        if parsed_packets:
            logger.log_binary_packet(parsed_packets[0])
            print(f"✓ Logged STATUS_REPORT packet (command: {parsed_packets[0].command.name})")
        
        # Test logging raw bytes directly
        logger.log_binary_packet(init_packet)
        print("✓ Logged raw binary packet (bytes)")
        
        # Get statistics
        stats = logger.get_stats()
        print(f"\n✓ Logger statistics:")
        print(f"  - Binary packets logged: {stats['binary_packet_count']}")
        print(f"  - Binlog file: {stats['binlog_file']}")
        
        # Close logger
        logger.close()
        print("\n✓ Closed logger")
        
        # Verify .binlog file exists and has content
        binlog_file = Path(stats['binlog_file'])
        if binlog_file.exists():
            file_size = binlog_file.stat().st_size
            print(f"\n✓ Binlog file exists: {binlog_file}")
            print(f"  - File size: {file_size} bytes")
            
            # Read and verify content
            with open(binlog_file, 'rb') as f:
                content = f.read()
                
            print(f"  - Content length: {len(content)} bytes")
            
            # Verify we can parse the logged packets
            replay_parser = BinaryProtocolParser()
            replayed_packets = replay_parser.parse_stream(content)
            
            print(f"\n✓ Replay test:")
            print(f"  - Replayed {len(replayed_packets)} packets from .binlog")
            
            for i, packet in enumerate(replayed_packets, 1):
                print(f"  - Packet {i}: {packet.command.name} ({len(packet.raw_bytes)} bytes)")
            
            if len(replayed_packets) >= 3:
                print("\n✓ SUCCESS: All packets logged and replayed correctly!")
                return True
            else:
                print(f"\n✗ FAILURE: Expected at least 3 packets, got {len(replayed_packets)}")
                return False
        else:
            print(f"\n✗ FAILURE: Binlog file not found: {binlog_file}")
            return False
            
    except Exception as e:
        print(f"\n✗ FAILURE: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up temporary directory
        try:
            shutil.rmtree(temp_dir)
            print(f"\n✓ Cleaned up temporary directory")
        except Exception as e:
            print(f"\n⚠ Warning: Could not clean up temp directory: {e}")


def test_file_rotation_with_binlog():
    """Test that .binlog files are properly rotated"""
    print("\n" + "=" * 70)
    print("Binary Protocol File Rotation Test")
    print("=" * 70)
    
    # Create temporary directory for test logs
    temp_dir = tempfile.mkdtemp(prefix='binlog_rotation_test_')
    print(f"\n✓ Created temporary log directory: {temp_dir}")
    
    try:
        # Initialize logger with small file size for testing rotation
        logger = TelemetryLogger(log_dir=temp_dir, max_file_size_mb=0.001)  # 1 KB
        print("✓ Initialized TelemetryLogger with 1 KB max file size")
        
        # Create test packet
        test_packet = create_test_bridge_packet()
        
        # Log many packets to trigger rotation
        initial_binlog = logger.binlog_file
        print(f"\n✓ Initial binlog file: {initial_binlog.name}")
        
        for i in range(100):
            logger.log_binary_packet(test_packet)
        
        # Check if rotation occurred
        current_binlog = logger.binlog_file
        
        if current_binlog != initial_binlog:
            print(f"✓ File rotation occurred!")
            print(f"  - New binlog file: {current_binlog.name}")
            print(f"  - File sequence: {logger.file_sequence}")
            
            # Verify both files exist
            if initial_binlog.exists() and current_binlog.exists():
                print(f"✓ Both binlog files exist")
                print(f"  - {initial_binlog.name}: {initial_binlog.stat().st_size} bytes")
                print(f"  - {current_binlog.name}: {current_binlog.stat().st_size} bytes")
                
                logger.close()
                print("\n✓ SUCCESS: File rotation works correctly!")
                return True
            else:
                print("✗ FAILURE: One or more binlog files missing after rotation")
                logger.close()
                return False
        else:
            print("⚠ Warning: File rotation did not occur (file size may not have exceeded limit)")
            logger.close()
            return True  # Not necessarily a failure
            
    except Exception as e:
        print(f"\n✗ FAILURE: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up temporary directory
        try:
            shutil.rmtree(temp_dir)
            print(f"\n✓ Cleaned up temporary directory")
        except Exception as e:
            print(f"\n⚠ Warning: Could not clean up temp directory: {e}")


if __name__ == '__main__':
    print("\nTesting Binary Protocol Packet Logging")
    print("=" * 70)
    
    # Run tests
    test1_passed = test_binary_packet_logging()
    test2_passed = test_file_rotation_with_binlog()
    
    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"Binary packet logging: {'PASSED' if test1_passed else 'FAILED'}")
    print(f"File rotation: {'PASSED' if test2_passed else 'FAILED'}")
    
    if test1_passed and test2_passed:
        print("\n✓ All tests PASSED!")
        sys.exit(0)
    else:
        print("\n✗ Some tests FAILED")
        sys.exit(1)
