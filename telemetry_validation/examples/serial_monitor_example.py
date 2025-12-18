#!/usr/bin/env python3
"""
Serial Monitor Example

This example demonstrates how to use the SerialMonitor class to display
real-time telemetry data with color-coded output and statistics.

Requirements: 2.1, 2.2, 2.3, 2.4
"""

import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from connection_manager import ConnectionManager, ConnectionType
from binary_protocol_parser import BinaryProtocolParser, MAVLinkExtractor
from mavlink_parser import MAVLinkParser
from metrics_calculator import MetricsCalculator
from serial_monitor import SerialMonitor, MonitorConfig
from binary_protocol_parser import UartCommand


def main():
    """Main example function."""
    print("Serial Monitor Example")
    print("=" * 70)
    print()
    
    # Configuration
    use_serial = True  # Set to False to use UDP
    serial_port = '/dev/ttyUSB0'
    baudrate = 115200
    udp_port = 14550
    
    # Create custom monitor configuration
    config = MonitorConfig(
        show_mavlink=True,
        show_binary=True,
        show_timestamps=True,
        show_rssi_snr=True,
        highlight_critical=True,
        throttle_enabled=True,
        max_messages_per_second=10,
        critical_messages={
            'HEARTBEAT',
            'GPS_RAW_INT',
            'GLOBAL_POSITION_INT',
            'ATTITUDE',
            'SYS_STATUS',
            'BATTERY_STATUS',
            'COMMAND_ACK',
            'STATUSTEXT'
        },
        critical_commands={
            UartCommand.CMD_INIT,
            UartCommand.CMD_STATUS_REPORT,
            UartCommand.CMD_RELAY_ACTIVATE,
            UartCommand.CMD_BROADCAST_RELAY_REQ
        },
        color_enabled=True
    )
    
    # Create components
    print("Initializing components...")
    
    if use_serial:
        conn_mgr = ConnectionManager(
            ConnectionType.SERIAL,
            port=serial_port,
            baudrate=baudrate
        )
        print(f"Using serial connection: {serial_port} @ {baudrate} baud")
    else:
        conn_mgr = ConnectionManager(
            ConnectionType.UDP,
            port=udp_port
        )
        print(f"Using UDP connection: port {udp_port}")
    
    binary_parser = BinaryProtocolParser()
    mavlink_extractor = MAVLinkExtractor()
    mavlink_parser = MAVLinkParser()
    metrics_calc = MetricsCalculator()
    monitor = SerialMonitor(config=config, metrics_calculator=metrics_calc)
    
    print("Components initialized")
    print()
    
    # Connect
    print("Connecting...")
    if not conn_mgr.connect():
        print("Failed to connect!")
        return 1
    
    print("Connected successfully")
    print()
    print("Monitoring telemetry... (Press Ctrl+C to stop)")
    print("Statistics will be displayed every 30 seconds")
    print("=" * 70)
    print()
    
    # Main monitoring loop
    last_stats_time = time.time()
    stats_interval = 30.0  # Display statistics every 30 seconds
    
    try:
        while True:
            # Read data from connection
            data = conn_mgr.read(1024)
            
            if data:
                # Parse binary protocol packets
                binary_packets = binary_parser.parse_stream(data)
                
                for packet in binary_packets:
                    # Display binary packet
                    monitor.display_binary_packet(packet)
                    
                    # Update metrics
                    metrics_calc.update_binary_packet(packet)
                    
                    # Extract MAVLink message if present
                    mavlink_msg = mavlink_extractor.extract_mavlink(packet)
                    if mavlink_msg:
                        # Display MAVLink message
                        monitor.display_mavlink_message(mavlink_msg)
                        
                        # Update metrics
                        metrics_calc.update_mavlink_message(mavlink_msg)
                
                # Also try parsing as raw MAVLink (for direct MAVLink connections)
                mavlink_messages = mavlink_parser.parse_stream(data)
                for msg in mavlink_messages:
                    monitor.display_mavlink_message(msg)
                    metrics_calc.update_mavlink_message(msg)
            
            # Display statistics periodically
            current_time = time.time()
            if current_time - last_stats_time >= stats_interval:
                monitor.display_statistics()
                last_stats_time = current_time
            
            # Small sleep to prevent CPU spinning
            time.sleep(0.01)
    
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        
        # Display final statistics
        print("\nFinal Statistics:")
        monitor.display_statistics()
        
        # Display parser statistics
        print("\nBinary Protocol Parser Statistics:")
        binary_stats = binary_parser.get_stats()
        for key, value in binary_stats.items():
            print(f"  {key}: {value}")
        
        print("\nMAVLink Parser Statistics:")
        mavlink_stats = mavlink_parser.get_stats()
        for key, value in mavlink_stats.items():
            print(f"  {key}: {value}")
        
        print("\nMAVLink Extractor Statistics:")
        extractor_stats = mavlink_extractor.get_stats()
        for key, value in extractor_stats.items():
            print(f"  {key}: {value}")
    
    finally:
        # Cleanup
        conn_mgr.disconnect()
        print("\nDisconnected")
    
    return 0


def demo_with_simulated_data():
    """
    Demonstrate the serial monitor with simulated data.
    
    This is useful for testing without a real connection.
    """
    print("Serial Monitor Demo with Simulated Data")
    print("=" * 70)
    print()
    
    # Create components
    config = MonitorConfig(
        throttle_enabled=False,  # Disable throttling for demo
        color_enabled=True
    )
    
    metrics_calc = MetricsCalculator()
    monitor = SerialMonitor(config=config, metrics_calculator=metrics_calc)
    
    # Simulate some MAVLink messages
    from mavlink_parser import ParsedMessage
    
    print("Simulating MAVLink messages...")
    print()
    
    # HEARTBEAT
    heartbeat = ParsedMessage(
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
    monitor.display_mavlink_message(heartbeat)
    metrics_calc.update_mavlink_message(heartbeat)
    
    time.sleep(0.1)
    
    # GPS_RAW_INT
    gps = ParsedMessage(
        timestamp=time.time(),
        msg_type='GPS_RAW_INT',
        msg_id=24,
        system_id=1,
        component_id=1,
        sequence=1,
        fields={
            'lat': 371234560,  # 37.123456 degrees
            'lon': -1221234560,  # -122.123456 degrees
            'alt': 100500,  # 100.5 meters
            'fix_type': 3,  # 3D fix
            'satellites_visible': 12
        },
        rssi=-82.0,
        snr=9.2,
        raw_bytes=b''
    )
    monitor.display_mavlink_message(gps)
    metrics_calc.update_mavlink_message(gps)
    
    time.sleep(0.1)
    
    # ATTITUDE
    attitude = ParsedMessage(
        timestamp=time.time(),
        msg_type='ATTITUDE',
        msg_id=30,
        system_id=1,
        component_id=1,
        sequence=2,
        fields={
            'roll': 0.05,
            'pitch': -0.02,
            'yaw': 1.57
        },
        rssi=-85.0,
        snr=8.5,
        raw_bytes=b''
    )
    monitor.display_mavlink_message(attitude)
    metrics_calc.update_mavlink_message(attitude)
    
    time.sleep(0.1)
    
    # SYS_STATUS
    sys_status = ParsedMessage(
        timestamp=time.time(),
        msg_type='SYS_STATUS',
        msg_id=1,
        system_id=1,
        component_id=1,
        sequence=3,
        fields={
            'voltage_battery': 12600,  # 12.6V
            'current_battery': 1500,  # 15.0A
            'battery_remaining': 75  # 75%
        },
        rssi=-85.0,
        snr=8.5,
        raw_bytes=b''
    )
    monitor.display_mavlink_message(sys_status)
    metrics_calc.update_mavlink_message(sys_status)
    
    print()
    
    # Simulate binary protocol packets
    from binary_protocol_parser import (
        ParsedBinaryPacket, UartCommand, InitPayload, StatusPayload
    )
    
    print("Simulating binary protocol packets...")
    print()
    
    # CMD_INIT
    init_payload = InitPayload(
        mode="FREQUENCY_BRIDGE",
        primary_freq=915.0,
        secondary_freq=868.0,
        timestamp=12345
    )
    init_packet = ParsedBinaryPacket(
        timestamp=time.time(),
        command=UartCommand.CMD_INIT,
        payload=init_payload,
        raw_bytes=b'',
        payload_bytes=b''
    )
    monitor.display_binary_packet(init_packet)
    metrics_calc.update_binary_packet(init_packet)
    
    time.sleep(0.1)
    
    # CMD_STATUS_REPORT
    status_payload = StatusPayload(
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
    status_packet = ParsedBinaryPacket(
        timestamp=time.time(),
        command=UartCommand.CMD_STATUS_REPORT,
        payload=status_payload,
        raw_bytes=b'',
        payload_bytes=b''
    )
    monitor.display_binary_packet(status_packet)
    metrics_calc.update_binary_packet(status_packet)
    
    print()
    
    # Display statistics
    print("Displaying statistics...")
    print()
    monitor.display_statistics()
    
    print("\nDemo complete!")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Serial Monitor Example')
    parser.add_argument('--demo', action='store_true',
                       help='Run demo with simulated data instead of real connection')
    parser.add_argument('--serial', type=str, default='/dev/ttyUSB0',
                       help='Serial port (default: /dev/ttyUSB0)')
    parser.add_argument('--baudrate', type=int, default=115200,
                       help='Baud rate (default: 115200)')
    parser.add_argument('--udp', action='store_true',
                       help='Use UDP instead of serial')
    parser.add_argument('--port', type=int, default=14550,
                       help='UDP port (default: 14550)')
    
    args = parser.parse_args()
    
    if args.demo:
        demo_with_simulated_data()
    else:
        sys.exit(main())
