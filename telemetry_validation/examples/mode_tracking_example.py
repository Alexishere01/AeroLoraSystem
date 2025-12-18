"""
Mode Tracking Example

This example demonstrates how to use the mode tracking and comparison modules
to monitor operating mode changes and compare performance between direct and
relay modes.

Requirements: 6.1, 6.2, 6.3, 6.4
"""

import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mode_tracker import ModeTracker, OperatingMode
from src.mode_specific_metrics import ModeSpecificMetricsCalculator
from src.mode_comparison import ModeComparator
from src.binary_protocol_parser import (
    BinaryProtocolParser, ParsedBinaryPacket, UartCommand, 
    StatusPayload, BridgePayload
)
from src.mavlink_parser import ParsedMessage


def create_sample_status_packet(relay_active: bool, packets_relayed: int = 0) -> ParsedBinaryPacket:
    """Create a sample status report packet."""
    status = StatusPayload(
        relay_active=relay_active,
        own_drone_sysid=1,
        packets_relayed=packets_relayed,
        bytes_relayed=packets_relayed * 100,
        mesh_to_uart_packets=packets_relayed // 2,
        uart_to_mesh_packets=packets_relayed // 2,
        mesh_to_uart_bytes=packets_relayed * 50,
        uart_to_mesh_bytes=packets_relayed * 50,
        bridge_gcs_to_mesh_packets=10,
        bridge_mesh_to_gcs_packets=10,
        bridge_gcs_to_mesh_bytes=1000,
        bridge_mesh_to_gcs_bytes=1000,
        rssi=-80.0 if not relay_active else -85.0,
        snr=10.0 if not relay_active else 8.0,
        last_activity_sec=0,
        active_peer_relays=0 if not relay_active else 2
    )
    
    return ParsedBinaryPacket(
        timestamp=time.time(),
        command=UartCommand.CMD_STATUS_REPORT,
        payload=status,
        raw_bytes=b'',
        payload_bytes=b''
    )


def create_sample_mavlink_message(msg_type: str, system_id: int = 1) -> ParsedMessage:
    """Create a sample MAVLink message."""
    return ParsedMessage(
        timestamp=time.time(),
        msg_type=msg_type,
        msg_id=0,
        system_id=system_id,
        component_id=1,
        sequence=0,
        fields={'command': 400} if msg_type == 'COMMAND_LONG' else {},
        rssi=-80.0,
        snr=10.0,
        raw_bytes=b''
    )


def main():
    """Main example function."""
    print("=" * 80)
    print("MODE TRACKING AND COMPARISON EXAMPLE")
    print("=" * 80)
    print()
    
    # Initialize components
    mode_tracker = ModeTracker()
    metrics_calc = ModeSpecificMetricsCalculator()
    comparator = ModeComparator()
    
    print("1. Simulating Direct Mode Operation")
    print("-" * 80)
    
    # Simulate direct mode for 2 seconds
    direct_start = time.time()
    packet_count = 0
    
    while time.time() - direct_start < 2.0:
        # Send status packet
        status_packet = create_sample_status_packet(relay_active=False)
        mode_tracker.update(status_packet)
        
        current_mode = mode_tracker.get_current_mode()
        metrics_calc.set_mode(current_mode)
        metrics_calc.update_binary_packet(status_packet, current_mode)
        
        # Send some MAVLink messages
        for _ in range(5):
            msg = create_sample_mavlink_message('HEARTBEAT')
            metrics_calc.update_mavlink_message(msg, current_mode)
            packet_count += 1
        
        time.sleep(0.1)
    
    print(f"Current Mode: {mode_tracker.get_current_mode().name}")
    print(f"Packets processed: {packet_count}")
    print(f"Mode transitions: {len(mode_tracker.get_mode_transitions())}")
    print()
    
    # Get direct mode metrics
    direct_metrics = metrics_calc.get_mode_metrics(OperatingMode.DIRECT)
    if direct_metrics:
        print(f"Direct Mode Metrics:")
        print(f"  MAVLink Packet Rate: {direct_metrics.mavlink_packet_rate_1s:.2f} pkt/s")
        print(f"  Average RSSI: {direct_metrics.avg_rssi:.1f} dBm")
        print(f"  Average SNR: {direct_metrics.avg_snr:.1f} dB")
        print(f"  Average Latency: {direct_metrics.latency_avg * 1000:.2f} ms")
        print(f"  Time in mode: {direct_metrics.time_in_mode_seconds:.1f} s")
    print()
    
    print("2. Simulating Mode Transition to Relay")
    print("-" * 80)
    
    # Transition to relay mode
    relay_packet = create_sample_status_packet(relay_active=True, packets_relayed=10)
    mode_tracker.update(relay_packet)
    
    current_mode = mode_tracker.get_current_mode()
    metrics_calc.set_mode(current_mode)
    
    print(f"Current Mode: {current_mode.name}")
    print(f"Mode transitions: {len(mode_tracker.get_mode_transitions())}")
    
    if mode_tracker.get_mode_transitions():
        transition = mode_tracker.get_mode_transitions()[-1]
        print(f"Last Transition: {transition.from_mode.name} -> {transition.to_mode.name}")
        print(f"  Packets relayed at transition: {transition.packets_relayed}")
        print(f"  Active peer relays: {transition.active_peer_relays}")
    print()
    
    print("3. Simulating Relay Mode Operation")
    print("-" * 80)
    
    # Simulate relay mode for 2 seconds
    relay_start = time.time()
    relay_packet_count = 0
    
    while time.time() - relay_start < 2.0:
        # Send status packet
        status_packet = create_sample_status_packet(
            relay_active=True, 
            packets_relayed=10 + relay_packet_count
        )
        mode_tracker.update(status_packet)
        
        current_mode = mode_tracker.get_current_mode()
        metrics_calc.update_binary_packet(status_packet, current_mode)
        
        # Send some MAVLink messages (slightly fewer in relay mode)
        for _ in range(4):
            msg = create_sample_mavlink_message('HEARTBEAT')
            metrics_calc.update_mavlink_message(msg, current_mode)
            relay_packet_count += 1
        
        time.sleep(0.1)
    
    print(f"Current Mode: {mode_tracker.get_current_mode().name}")
    print(f"Packets processed: {relay_packet_count}")
    print()
    
    # Get relay mode metrics
    relay_metrics = metrics_calc.get_mode_metrics(OperatingMode.RELAY)
    if relay_metrics:
        print(f"Relay Mode Metrics:")
        print(f"  MAVLink Packet Rate: {relay_metrics.mavlink_packet_rate_1s:.2f} pkt/s")
        print(f"  Average RSSI: {relay_metrics.avg_rssi:.1f} dBm")
        print(f"  Average SNR: {relay_metrics.avg_snr:.1f} dB")
        print(f"  Average Latency: {relay_metrics.latency_avg * 1000:.2f} ms")
        print(f"  Packets Relayed: {relay_metrics.packets_relayed}")
        print(f"  Active Peer Relays: {relay_metrics.active_peer_relays}")
        print(f"  Time in mode: {relay_metrics.time_in_mode_seconds:.1f} s")
    print()
    
    print("4. Mode Comparison Report")
    print("-" * 80)
    
    # Generate comparison report
    if direct_metrics and relay_metrics:
        report = comparator.compare_modes(direct_metrics, relay_metrics)
        
        if report:
            # Print formatted report
            formatted_report = comparator.format_comparison_report(report)
            print(formatted_report)
            
            # Print summary dictionary
            print("\nComparison Summary (JSON):")
            summary = comparator.get_comparison_summary(report)
            import json
            print(json.dumps(summary, indent=2))
    else:
        print("Insufficient data for comparison")
    print()
    
    print("5. Mode Tracker Statistics")
    print("-" * 80)
    
    stats = mode_tracker.get_stats()
    print(f"Current Mode: {stats['current_mode']}")
    print(f"Total Transitions: {stats['total_transitions']}")
    print(f"Direct Mode Count: {stats['direct_mode_count']}")
    print(f"Relay Mode Count: {stats['relay_mode_count']}")
    print(f"Status Reports Processed: {stats['status_reports_processed']}")
    print(f"Direct Mode Time: {stats['direct_mode_time_seconds']:.1f}s ({stats['direct_mode_percentage']:.1f}%)")
    print(f"Relay Mode Time: {stats['relay_mode_time_seconds']:.1f}s ({stats['relay_mode_percentage']:.1f}%)")
    print(f"Uptime: {stats['uptime_seconds']:.1f}s")
    print()
    
    print("6. Mode Transition History")
    print("-" * 80)
    
    transitions = mode_tracker.get_mode_transitions()
    if transitions:
        for i, transition in enumerate(transitions, 1):
            print(f"Transition {i}:")
            print(f"  Time: {transition.timestamp:.3f}")
            print(f"  From: {transition.from_mode.name}")
            print(f"  To: {transition.to_mode.name}")
            print(f"  Relay Active: {transition.relay_active}")
            print(f"  Packets Relayed: {transition.packets_relayed}")
            print(f"  Active Peer Relays: {transition.active_peer_relays}")
            print()
    else:
        print("No mode transitions recorded")
    
    print("=" * 80)
    print("Example completed successfully!")
    print("=" * 80)


if __name__ == '__main__':
    main()
