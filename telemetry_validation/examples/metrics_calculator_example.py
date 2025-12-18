"""
Metrics Calculator Example

This example demonstrates how to use the MetricsCalculator class to track
and analyze telemetry metrics from both binary protocol packets and MAVLink
messages.

Usage:
    python examples/metrics_calculator_example.py
"""

import sys
import time
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from metrics_calculator import MetricsCalculator, TelemetryMetrics
from binary_protocol_parser import (
    BinaryProtocolParser, 
    ParsedBinaryPacket, 
    UartCommand,
    BridgePayload,
    StatusPayload
)
from mavlink_parser import MAVLinkParser, ParsedMessage


def print_metrics(metrics: TelemetryMetrics):
    """Print formatted metrics to console."""
    print("\n" + "="*70)
    print("TELEMETRY METRICS SNAPSHOT")
    print("="*70)
    
    print("\n📊 PACKET RATES")
    print(f"  Binary Protocol:")
    print(f"    1s:  {metrics.binary_packet_rate_1s:6.2f} pkt/s")
    print(f"    10s: {metrics.binary_packet_rate_10s:6.2f} pkt/s")
    print(f"    60s: {metrics.binary_packet_rate_60s:6.2f} pkt/s")
    print(f"  MAVLink Messages:")
    print(f"    1s:  {metrics.mavlink_packet_rate_1s:6.2f} msg/s")
    print(f"    10s: {metrics.mavlink_packet_rate_10s:6.2f} msg/s")
    print(f"    60s: {metrics.mavlink_packet_rate_60s:6.2f} msg/s")
    
    print("\n📡 LINK QUALITY")
    print(f"  RSSI: {metrics.avg_rssi:6.2f} dBm")
    print(f"  SNR:  {metrics.avg_snr:6.2f} dB")
    
    print("\n📉 PACKET LOSS")
    print(f"  Drop Rate:        {metrics.drop_rate:6.2f}%")
    print(f"  Packets Lost:     {metrics.packets_lost}")
    print(f"  Packets Received: {metrics.packets_received}")
    
    print("\n⏱️  COMMAND LATENCY")
    if metrics.latency_samples > 0:
        print(f"  Average: {metrics.latency_avg*1000:6.2f} ms")
        print(f"  Min:     {metrics.latency_min*1000:6.2f} ms")
        print(f"  Max:     {metrics.latency_max*1000:6.2f} ms")
        print(f"  Samples: {metrics.latency_samples}")
    else:
        print(f"  No latency data available")
    
    print("\n📋 MESSAGE TYPE DISTRIBUTION")
    print(f"  MAVLink Message Types ({len(metrics.mavlink_msg_type_distribution)}):")
    for msg_type, count in sorted(metrics.mavlink_msg_type_distribution.items(), 
                                   key=lambda x: x[1], reverse=True)[:5]:
        print(f"    {msg_type:20s}: {count:5d}")
    
    print(f"  Binary Command Types ({len(metrics.binary_cmd_type_distribution)}):")
    for cmd_type, count in sorted(metrics.binary_cmd_type_distribution.items(), 
                                   key=lambda x: x[1], reverse=True)[:5]:
        print(f"    {cmd_type:20s}: {count:5d}")
    
    print("\n🔧 BINARY PROTOCOL HEALTH")
    print(f"  Checksum Error Rate: {metrics.checksum_error_rate:6.2f} errors/min")
    print(f"  Parse Error Rate:    {metrics.parse_error_rate:6.2f} errors/min")
    print(f"  Success Rate:        {metrics.protocol_success_rate:6.2f}%")
    
    print("\n" + "="*70 + "\n")


def example_basic_usage():
    """Demonstrate basic metrics calculator usage."""
    print("\n=== EXAMPLE 1: Basic Usage ===\n")
    
    # Create metrics calculator
    calculator = MetricsCalculator()
    
    # Simulate receiving binary protocol packets
    print("Simulating binary protocol packets...")
    for i in range(10):
        # Create a mock binary packet
        packet = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_BRIDGE_RX,
            payload=BridgePayload(
                system_id=1,
                rssi=-85.0 + i,
                snr=10.0 + i * 0.5,
                data_len=50,
                data=b'\xfe' * 50
            ),
            raw_bytes=b'\xaa' * 100,
            payload_bytes=b'\x00' * 50
        )
        
        calculator.update_binary_packet(packet)
        time.sleep(0.1)
    
    # Simulate receiving MAVLink messages
    print("Simulating MAVLink messages...")
    for i in range(10):
        # Create a mock MAVLink message
        msg = ParsedMessage(
            timestamp=time.time(),
            msg_type='HEARTBEAT',
            msg_id=0,
            system_id=1,
            component_id=1,
            sequence=i,
            fields={'type': 2, 'autopilot': 3, 'base_mode': 81, 'custom_mode': 0, 'system_status': 4},
            rssi=-85.0,
            snr=10.0,
            raw_bytes=b'\xfe' * 20
        )
        
        calculator.update_mavlink_message(msg)
        time.sleep(0.1)
    
    # Get and display metrics
    metrics = calculator.get_metrics()
    print_metrics(metrics)


def example_packet_loss_detection():
    """Demonstrate packet loss detection."""
    print("\n=== EXAMPLE 2: Packet Loss Detection ===\n")
    
    calculator = MetricsCalculator()
    
    print("Sending sequence of HEARTBEAT messages with gaps...")
    
    # Send messages with sequence numbers: 0, 1, 2, 5, 6, 7 (missing 3, 4)
    sequences = [0, 1, 2, 5, 6, 7]
    
    for seq in sequences:
        msg = ParsedMessage(
            timestamp=time.time(),
            msg_type='HEARTBEAT',
            msg_id=0,
            system_id=1,
            component_id=1,
            sequence=seq,
            fields={'type': 2, 'autopilot': 3},
            raw_bytes=b'\xfe' * 20
        )
        
        calculator.update_mavlink_message(msg)
        print(f"  Sent HEARTBEAT with sequence {seq}")
        time.sleep(0.1)
    
    # Get metrics
    metrics = calculator.get_metrics()
    
    print(f"\n📉 Packet Loss Results:")
    print(f"  Packets Received: {metrics.packets_received}")
    print(f"  Packets Lost:     {metrics.packets_lost}")
    print(f"  Drop Rate:        {metrics.drop_rate:.2f}%")
    print(f"\n  Expected: 2 packets lost (sequences 3 and 4)")


def example_command_latency():
    """Demonstrate command latency tracking."""
    print("\n=== EXAMPLE 3: Command Latency Tracking ===\n")
    
    calculator = MetricsCalculator()
    
    print("Sending COMMAND_LONG and receiving COMMAND_ACK...")
    
    # Send COMMAND_LONG
    cmd_msg = ParsedMessage(
        timestamp=time.time(),
        msg_type='COMMAND_LONG',
        msg_id=76,
        system_id=1,
        component_id=1,
        sequence=0,
        fields={
            'command': 400,  # MAV_CMD_COMPONENT_ARM_DISARM
            'target_system': 1,
            'target_component': 1,
            'param1': 1.0
        },
        raw_bytes=b'\xfe' * 30
    )
    
    calculator.update_mavlink_message(cmd_msg)
    print("  Sent COMMAND_LONG (command 400)")
    
    # Simulate network delay
    time.sleep(0.15)  # 150ms delay
    
    # Receive COMMAND_ACK
    ack_msg = ParsedMessage(
        timestamp=time.time(),
        msg_type='COMMAND_ACK',
        msg_id=77,
        system_id=1,
        component_id=1,
        sequence=1,
        fields={
            'command': 400,
            'result': 0  # MAV_RESULT_ACCEPTED
        },
        raw_bytes=b'\xfe' * 10
    )
    
    calculator.update_mavlink_message(ack_msg)
    print("  Received COMMAND_ACK (command 400)")
    
    # Get metrics
    metrics = calculator.get_metrics()
    
    print(f"\n⏱️  Latency Results:")
    print(f"  Average Latency: {metrics.latency_avg*1000:.2f} ms")
    print(f"  Min Latency:     {metrics.latency_min*1000:.2f} ms")
    print(f"  Max Latency:     {metrics.latency_max*1000:.2f} ms")
    print(f"  Samples:         {metrics.latency_samples}")
    print(f"\n  Expected: ~150ms latency")


def example_binary_protocol_health():
    """Demonstrate binary protocol health tracking."""
    print("\n=== EXAMPLE 4: Binary Protocol Health ===\n")
    
    calculator = MetricsCalculator()
    
    print("Simulating successful packets and errors...")
    
    # Simulate successful packets
    for i in range(50):
        packet = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_STATUS_REPORT,
            payload=StatusPayload(
                relay_active=True,
                own_drone_sysid=1,
                packets_relayed=100,
                bytes_relayed=5000,
                mesh_to_uart_packets=50,
                uart_to_mesh_packets=50,
                mesh_to_uart_bytes=2500,
                uart_to_mesh_bytes=2500,
                bridge_gcs_to_mesh_packets=0,
                bridge_mesh_to_gcs_packets=0,
                bridge_gcs_to_mesh_bytes=0,
                bridge_mesh_to_gcs_bytes=0,
                rssi=-80.0,
                snr=12.0,
                last_activity_sec=1,
                active_peer_relays=2
            ),
            raw_bytes=b'\xaa' * 60,
            payload_bytes=b'\x00' * 55
        )
        
        calculator.update_binary_packet(packet)
    
    print(f"  Sent 50 successful packets")
    
    # Simulate some errors
    for i in range(5):
        calculator.record_checksum_error()
    
    print(f"  Recorded 5 checksum errors")
    
    for i in range(3):
        calculator.record_parse_error()
    
    print(f"  Recorded 3 parse errors")
    
    # Get metrics
    metrics = calculator.get_metrics()
    
    print(f"\n🔧 Protocol Health Results:")
    print(f"  Success Rate:        {metrics.protocol_success_rate:.2f}%")
    print(f"  Checksum Error Rate: {metrics.checksum_error_rate:.2f} errors/min")
    print(f"  Parse Error Rate:    {metrics.parse_error_rate:.2f} errors/min")
    print(f"\n  Expected: ~86% success rate (50 success / 58 total)")


def example_rolling_windows():
    """Demonstrate rolling window packet rate calculation."""
    print("\n=== EXAMPLE 5: Rolling Window Packet Rates ===\n")
    
    calculator = MetricsCalculator()
    
    print("Sending packets at varying rates...")
    
    # Send 10 packets quickly
    print("\n  Phase 1: Sending 10 packets rapidly...")
    for i in range(10):
        packet = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_BRIDGE_RX,
            payload=None,
            raw_bytes=b'\xaa' * 10,
            payload_bytes=b''
        )
        calculator.update_binary_packet(packet)
        time.sleep(0.05)  # 50ms between packets = 20 pkt/s
    
    # Get metrics after rapid sending
    metrics1 = calculator.get_metrics()
    print(f"  1s rate:  {metrics1.binary_packet_rate_1s:.2f} pkt/s")
    print(f"  10s rate: {metrics1.binary_packet_rate_10s:.2f} pkt/s")
    
    # Wait a bit
    print("\n  Phase 2: Waiting 2 seconds...")
    time.sleep(2)
    
    # Send 5 more packets slowly
    print("  Phase 3: Sending 5 packets slowly...")
    for i in range(5):
        packet = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_BRIDGE_RX,
            payload=None,
            raw_bytes=b'\xaa' * 10,
            payload_bytes=b''
        )
        calculator.update_binary_packet(packet)
        time.sleep(0.2)  # 200ms between packets = 5 pkt/s
    
    # Get metrics after slow sending
    metrics2 = calculator.get_metrics()
    print(f"\n  Final rates:")
    print(f"  1s rate:  {metrics2.binary_packet_rate_1s:.2f} pkt/s")
    print(f"  10s rate: {metrics2.binary_packet_rate_10s:.2f} pkt/s")
    print(f"\n  Note: 1s rate reflects recent slow rate, 10s rate is average of both phases")


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("METRICS CALCULATOR EXAMPLES")
    print("="*70)
    
    try:
        example_basic_usage()
        example_packet_loss_detection()
        example_command_latency()
        example_binary_protocol_health()
        example_rolling_windows()
        
        print("\n✅ All examples completed successfully!\n")
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}\n")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
