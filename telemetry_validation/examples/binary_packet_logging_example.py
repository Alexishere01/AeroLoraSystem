#!/usr/bin/env python3
"""
Example: Binary Protocol Packet Logging

This example demonstrates how to log binary protocol packets to .binlog files
for debugging and replay purposes. The .binlog format stores complete packets
including headers, payloads, and checksums.

Requirements: 1.1, 10.4
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.telemetry_logger import TelemetryLogger
from src.binary_protocol_parser import BinaryProtocolParser
from src.connection_manager import ConnectionManager, ConnectionType


def main():
    """
    Example: Log binary protocol packets from serial connection.
    
    This example shows how to:
    1. Connect to a serial port
    2. Parse binary protocol packets
    3. Log packets to .binlog file
    4. Replay logged packets
    """
    
    print("=" * 70)
    print("Binary Protocol Packet Logging Example")
    print("=" * 70)
    
    # Initialize components
    print("\n1. Initializing components...")
    
    # Create connection manager (serial or UDP)
    conn = ConnectionManager(
        conn_type=ConnectionType.SERIAL,
        port='/dev/ttyUSB0',  # Adjust for your system
        baudrate=115200
    )
    
    # Create binary protocol parser
    parser = BinaryProtocolParser()
    
    # Create telemetry logger
    logger = TelemetryLogger(
        log_dir='./telemetry_logs',
        max_file_size_mb=100
    )
    
    print("✓ Components initialized")
    
    # Connect to data source
    print("\n2. Connecting to serial port...")
    if not conn.connect():
        print("✗ Failed to connect")
        return
    
    print("✓ Connected")
    
    # Main logging loop
    print("\n3. Logging binary protocol packets...")
    print("   Press Ctrl+C to stop\n")
    
    packet_count = 0
    
    try:
        while True:
            # Read data from connection
            data = conn.read(1024)
            
            if not data:
                continue
            
            # Parse binary protocol packets
            packets = parser.parse_stream(data)
            
            # Log each packet to .binlog file
            for packet in packets:
                logger.log_binary_packet(packet)
                packet_count += 1
                
                # Print packet info
                print(f"Logged packet #{packet_count}: {packet.command.name} "
                      f"({len(packet.raw_bytes)} bytes)")
                
                # Show parser statistics every 10 packets
                if packet_count % 10 == 0:
                    stats = parser.get_stats()
                    print(f"\nParser stats:")
                    print(f"  - Packets received: {stats['packets_received']}")
                    print(f"  - Success rate: {stats['success_rate']:.1f}%")
                    print(f"  - Checksum errors: {stats['checksum_errors']}")
                    print()
    
    except KeyboardInterrupt:
        print("\n\n4. Shutting down...")
    
    # Close connection and logger
    conn.disconnect()
    logger.close()
    
    # Show final statistics
    print("\n5. Final statistics:")
    logger_stats = logger.get_stats()
    print(f"   - Binary packets logged: {logger_stats['binary_packet_count']}")
    print(f"   - Binlog file: {logger_stats['binlog_file']}")
    
    parser_stats = parser.get_stats()
    print(f"   - Success rate: {parser_stats['success_rate']:.1f}%")
    print(f"   - Checksum errors: {parser_stats['checksum_errors']}")
    
    print("\n✓ Done!")
    
    # Demonstrate replay capability
    print("\n6. Replay demonstration:")
    print("   To replay logged packets, use:")
    print(f"   python replay_binlog.py {logger_stats['binlog_file']}")


def replay_binlog(binlog_file: str):
    """
    Replay packets from a .binlog file.
    
    This demonstrates how logged binary protocol packets can be replayed
    for debugging and analysis.
    
    Args:
        binlog_file: Path to .binlog file
    """
    print("=" * 70)
    print(f"Replaying: {binlog_file}")
    print("=" * 70)
    
    # Read binlog file
    with open(binlog_file, 'rb') as f:
        data = f.read()
    
    print(f"\n✓ Read {len(data)} bytes from binlog file")
    
    # Parse packets
    parser = BinaryProtocolParser()
    packets = parser.parse_stream(data)
    
    print(f"✓ Parsed {len(packets)} packets\n")
    
    # Display each packet
    for i, packet in enumerate(packets, 1):
        print(f"Packet {i}:")
        print(f"  - Command: {packet.command.name}")
        print(f"  - Size: {len(packet.raw_bytes)} bytes")
        print(f"  - Timestamp: {packet.timestamp:.3f}")
        
        if packet.payload:
            print(f"  - Payload type: {type(packet.payload).__name__}")
        
        print()
    
    print("✓ Replay complete!")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Replay mode
        replay_binlog(sys.argv[1])
    else:
        # Normal logging mode
        main()
