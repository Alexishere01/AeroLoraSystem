#!/usr/bin/env python3
"""
Example: Using BinaryCommandHandler to Process Non-MAVLink Commands

This example demonstrates how to use the BinaryCommandHandler class to
parse and extract metrics from binary protocol commands like CMD_STATUS_REPORT,
CMD_INIT, and CMD_RELAY_RX.

Requirements: 1.2, 5.1
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from binary_protocol_parser import (
    BinaryProtocolParser,
    BinaryCommandHandler,
    UartCommand
)


def main():
    """Demonstrate BinaryCommandHandler usage"""
    
    print("=" * 60)
    print("Binary Command Handler Example")
    print("=" * 60)
    
    # Initialize parser and handler
    parser = BinaryProtocolParser()
    handler = BinaryCommandHandler()
    
    print("\n1. Simulating binary protocol data stream...")
    print("   (In real usage, this would come from serial/UDP connection)")
    
    # Simulate receiving some binary protocol packets
    # In real usage, you would read from a serial port or UDP socket
    # For this example, we'll just show the processing flow
    
    # Example: Process a stream of data
    # data = serial_port.read(1024)  # or udp_socket.recv(1024)
    # packets = parser.parse_stream(data)
    
    print("\n2. Processing received packets...")
    
    # Simulate processing packets
    # for packet in packets:
    #     # Handle non-MAVLink commands
    #     handler.handle_packet(packet)
    #     
    #     # Check what type of command it was
    #     if packet.command == UartCommand.CMD_STATUS_REPORT:
    #         print(f"   Received status report")
    #     elif packet.command == UartCommand.CMD_INIT:
    #         print(f"   Received initialization")
    #     elif packet.command == UartCommand.CMD_RELAY_RX:
    #         print(f"   Received relay packet")
    
    print("\n3. Checking relay status...")
    
    # Check if relay mode is active
    if handler.is_relay_active():
        print("   ✓ Relay mode is ACTIVE")
    else:
        print("   ✗ Relay mode is INACTIVE")
    
    print("\n4. Extracting system metrics...")
    
    # Get system metrics from latest status report
    metrics = handler.get_system_metrics()
    
    if metrics:
        print(f"   System ID: {metrics.get('own_drone_sysid', 'N/A')}")
        print(f"   Relay active: {metrics.get('relay_active', False)}")
        print(f"   Packets relayed: {metrics.get('packets_relayed', 0)}")
        print(f"   Bytes relayed: {metrics.get('bytes_relayed', 0)}")
        print(f"   RSSI: {metrics.get('rssi', 0):.1f} dBm")
        print(f"   SNR: {metrics.get('snr', 0):.1f} dB")
        print(f"   Active peer relays: {metrics.get('active_peer_relays', 0)}")
        print(f"   Last activity: {metrics.get('last_activity_sec', 0)} seconds ago")
        
        # Bridge statistics
        print(f"\n   Bridge Statistics:")
        print(f"   - GCS → Mesh: {metrics.get('bridge_gcs_to_mesh_packets', 0)} packets, "
              f"{metrics.get('bridge_gcs_to_mesh_bytes', 0)} bytes")
        print(f"   - Mesh → GCS: {metrics.get('bridge_mesh_to_gcs_packets', 0)} packets, "
              f"{metrics.get('bridge_mesh_to_gcs_bytes', 0)} bytes")
        
        # Relay statistics
        print(f"\n   Relay Statistics:")
        print(f"   - Mesh → UART: {metrics.get('mesh_to_uart_packets', 0)} packets, "
              f"{metrics.get('mesh_to_uart_bytes', 0)} bytes")
        print(f"   - UART → Mesh: {metrics.get('uart_to_mesh_packets', 0)} packets, "
              f"{metrics.get('uart_to_mesh_bytes', 0)} bytes")
    else:
        print("   No status report received yet")
    
    print("\n5. Checking initialization data...")
    
    # Get initialization data
    init = handler.get_latest_init()
    
    if init:
        print(f"   Mode: {init.mode}")
        print(f"   Primary frequency: {init.primary_freq:.1f} MHz")
        print(f"   Secondary frequency: {init.secondary_freq:.1f} MHz")
        print(f"   Timestamp: {init.timestamp} ms")
    else:
        print("   No initialization data received yet")
    
    print("\n6. Viewing command statistics...")
    
    # Get handler statistics
    stats = handler.get_stats()
    
    print(f"   Status reports received: {stats['status_reports_received']}")
    print(f"   Init commands received: {stats['init_commands_received']}")
    print(f"   Relay requests received: {stats['relay_requests_received']}")
    print(f"   Relay activations received: {stats['relay_activations_received']}")
    print(f"   Relay RX packets received: {stats['relay_rx_packets_received']}")
    print(f"   Relay TX packets received: {stats['relay_tx_packets_received']}")
    print(f"   ACK received: {stats['ack_received']}")
    print(f"   Status requests received: {stats['status_requests_received']}")
    
    print("\n7. Monitoring relay requests...")
    
    # Check recent relay requests
    if handler.relay_requests:
        print(f"   Recent relay requests: {len(handler.relay_requests)}")
        for i, req in enumerate(handler.relay_requests[-3:], 1):  # Show last 3
            payload = req['payload']
            print(f"   Request {i}: RSSI={payload.rssi:.1f} dBm, "
                  f"SNR={payload.snr:.1f} dB, "
                  f"Loss={payload.packet_loss:.1f}%")
    else:
        print("   No relay requests received yet")
    
    print("\n8. Monitoring relay activations...")
    
    # Check recent relay activations
    if handler.relay_activations:
        print(f"   Recent relay activations: {len(handler.relay_activations)}")
        for i, activation in enumerate(handler.relay_activations[-3:], 1):  # Show last 3
            state = "ACTIVATE" if activation['activate'] else "DEACTIVATE"
            print(f"   Activation {i}: {state}")
    else:
        print("   No relay activations received yet")
    
    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    
    print("\nIntegration Tips:")
    print("  1. Create BinaryProtocolParser and BinaryCommandHandler instances")
    print("  2. Read data from serial port or UDP socket")
    print("  3. Parse data stream: packets = parser.parse_stream(data)")
    print("  4. Handle each packet: handler.handle_packet(packet)")
    print("  5. Extract metrics: metrics = handler.get_system_metrics()")
    print("  6. Check relay status: is_active = handler.is_relay_active()")
    print("  7. Get statistics: stats = handler.get_stats()")
    
    print("\nUse Cases:")
    print("  • Monitor relay mode activation/deactivation")
    print("  • Track system health (RSSI, SNR, packet counts)")
    print("  • Analyze bridge and relay traffic patterns")
    print("  • Detect relay requests and link quality issues")
    print("  • Log system configuration changes")


if __name__ == '__main__':
    main()
