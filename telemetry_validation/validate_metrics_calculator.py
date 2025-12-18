#!/usr/bin/env python3
"""
Validation script for MetricsCalculator module

This script validates that the MetricsCalculator implementation meets
all requirements and integrates correctly with other modules.
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from metrics_calculator import MetricsCalculator, TelemetryMetrics
from binary_protocol_parser import (
    BinaryProtocolParser,
    MAVLinkExtractor,
    UartCommand,
    BridgePayload,
    StatusPayload
)
from mavlink_parser import MAVLinkParser
import time


def validate_basic_functionality():
    """Validate basic metrics calculator functionality."""
    print("\n=== Validating Basic Functionality ===")
    
    calculator = MetricsCalculator()
    
    # Check initialization
    assert calculator is not None, "Calculator should initialize"
    assert len(calculator.binary_packets_1s) == 0, "Should start with empty buffers"
    
    print("✅ Initialization successful")
    
    # Check metrics retrieval
    metrics = calculator.get_metrics()
    assert isinstance(metrics, TelemetryMetrics), "Should return TelemetryMetrics"
    assert metrics.timestamp > 0, "Should have valid timestamp"
    
    print("✅ Metrics retrieval successful")
    
    return True


def validate_rolling_windows():
    """Validate rolling window packet rate calculation."""
    print("\n=== Validating Rolling Windows ===")
    
    calculator = MetricsCalculator()
    
    # Send packets at known rate
    from binary_protocol_parser import ParsedBinaryPacket
    
    for i in range(10):
        packet = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_BRIDGE_RX,
            payload=None,
            raw_bytes=b'\xaa' * 10,
            payload_bytes=b''
        )
        calculator.update_binary_packet(packet)
        time.sleep(0.05)  # 20 pkt/s
    
    metrics = calculator.get_metrics()
    
    # Should be approximately 20 pkt/s
    assert 15 < metrics.binary_packet_rate_1s < 25, \
        f"Rate should be ~20 pkt/s, got {metrics.binary_packet_rate_1s}"
    
    print(f"✅ Rolling window rate: {metrics.binary_packet_rate_1s:.2f} pkt/s (expected ~20)")
    
    return True


def validate_rssi_snr_extraction():
    """Validate RSSI/SNR extraction from binary protocol."""
    print("\n=== Validating RSSI/SNR Extraction ===")
    
    calculator = MetricsCalculator()
    
    from binary_protocol_parser import ParsedBinaryPacket
    
    # Test BridgePayload
    packet1 = ParsedBinaryPacket(
        timestamp=time.time(),
        command=UartCommand.CMD_BRIDGE_RX,
        payload=BridgePayload(
            system_id=1,
            rssi=-80.0,
            snr=12.0,
            data_len=10,
            data=b'\x00' * 10
        ),
        raw_bytes=b'\xaa' * 20,
        payload_bytes=b'\x00' * 10
    )
    
    calculator.update_binary_packet(packet1)
    
    # Test StatusPayload
    packet2 = ParsedBinaryPacket(
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
            rssi=-75.0,
            snr=15.0,
            last_activity_sec=1,
            active_peer_relays=2
        ),
        raw_bytes=b'\xaa' * 60,
        payload_bytes=b'\x00' * 55
    )
    
    calculator.update_binary_packet(packet2)
    
    metrics = calculator.get_metrics()
    
    # Average should be (-80 + -75) / 2 = -77.5
    assert abs(metrics.avg_rssi - (-77.5)) < 0.1, \
        f"RSSI should be -77.5, got {metrics.avg_rssi}"
    
    # Average should be (12 + 15) / 2 = 13.5
    assert abs(metrics.avg_snr - 13.5) < 0.1, \
        f"SNR should be 13.5, got {metrics.avg_snr}"
    
    print(f"✅ RSSI extraction: {metrics.avg_rssi:.2f} dBm (expected -77.5)")
    print(f"✅ SNR extraction: {metrics.avg_snr:.2f} dB (expected 13.5)")
    
    return True


def validate_packet_loss_detection():
    """Validate packet loss detection from sequence numbers."""
    print("\n=== Validating Packet Loss Detection ===")
    
    calculator = MetricsCalculator()
    
    from mavlink_parser import ParsedMessage
    
    # Send messages with gaps: 0, 1, 2, 5, 6 (missing 3, 4)
    sequences = [0, 1, 2, 5, 6]
    
    for seq in sequences:
        msg = ParsedMessage(
            timestamp=time.time(),
            msg_type='HEARTBEAT',
            msg_id=0,
            system_id=1,
            component_id=1,
            sequence=seq,
            fields={'type': 2},
            raw_bytes=b'\xfe' * 20
        )
        calculator.update_mavlink_message(msg)
    
    metrics = calculator.get_metrics()
    
    assert metrics.packets_lost == 2, \
        f"Should detect 2 lost packets, got {metrics.packets_lost}"
    assert metrics.packets_received == 5, \
        f"Should receive 5 packets, got {metrics.packets_received}"
    
    expected_drop_rate = (2 / 7) * 100  # 2 lost out of 7 total
    assert abs(metrics.drop_rate - expected_drop_rate) < 0.1, \
        f"Drop rate should be {expected_drop_rate:.2f}%, got {metrics.drop_rate:.2f}%"
    
    print(f"✅ Packet loss detection: {metrics.packets_lost} lost, {metrics.drop_rate:.2f}% drop rate")
    
    return True


def validate_command_latency():
    """Validate command latency tracking."""
    print("\n=== Validating Command Latency Tracking ===")
    
    calculator = MetricsCalculator()
    
    from mavlink_parser import ParsedMessage
    
    # Send COMMAND_LONG
    cmd_msg = ParsedMessage(
        timestamp=time.time(),
        msg_type='COMMAND_LONG',
        msg_id=76,
        system_id=1,
        component_id=1,
        sequence=0,
        fields={'command': 400, 'target_system': 1},
        raw_bytes=b'\xfe' * 30
    )
    
    calculator.update_mavlink_message(cmd_msg)
    
    # Simulate delay
    time.sleep(0.1)
    
    # Send COMMAND_ACK
    ack_msg = ParsedMessage(
        timestamp=time.time(),
        msg_type='COMMAND_ACK',
        msg_id=77,
        system_id=1,
        component_id=1,
        sequence=1,
        fields={'command': 400, 'result': 0},
        raw_bytes=b'\xfe' * 10
    )
    
    calculator.update_mavlink_message(ack_msg)
    
    metrics = calculator.get_metrics()
    
    assert metrics.latency_samples == 1, \
        f"Should have 1 latency sample, got {metrics.latency_samples}"
    assert 0.09 < metrics.latency_avg < 0.15, \
        f"Latency should be ~100ms, got {metrics.latency_avg*1000:.2f}ms"
    
    print(f"✅ Command latency: {metrics.latency_avg*1000:.2f} ms (expected ~100ms)")
    
    return True


def validate_protocol_health():
    """Validate binary protocol health metrics."""
    print("\n=== Validating Protocol Health Metrics ===")
    
    calculator = MetricsCalculator()
    
    from binary_protocol_parser import ParsedBinaryPacket
    
    # Add successful packets
    for i in range(10):
        packet = ParsedBinaryPacket(
            timestamp=time.time(),
            command=UartCommand.CMD_BRIDGE_RX,
            payload=None,
            raw_bytes=b'\xaa' * 10,
            payload_bytes=b''
        )
        calculator.update_binary_packet(packet)
    
    # Add errors
    calculator.record_checksum_error()
    calculator.record_checksum_error()
    calculator.record_parse_error()
    
    metrics = calculator.get_metrics()
    
    # Success rate should be 10 / 13 = 76.92%
    expected_success_rate = (10 / 13) * 100
    assert abs(metrics.protocol_success_rate - expected_success_rate) < 0.1, \
        f"Success rate should be {expected_success_rate:.2f}%, got {metrics.protocol_success_rate:.2f}%"
    
    print(f"✅ Protocol health: {metrics.protocol_success_rate:.2f}% success rate")
    print(f"✅ Checksum errors: {metrics.checksum_error_rate:.2f} errors/min")
    print(f"✅ Parse errors: {metrics.parse_error_rate:.2f} errors/min")
    
    return True


def validate_message_distribution():
    """Validate message type distribution tracking."""
    print("\n=== Validating Message Distribution ===")
    
    calculator = MetricsCalculator()
    
    from mavlink_parser import ParsedMessage
    
    # Send different message types
    msg_types = ['HEARTBEAT', 'GPS_RAW_INT', 'ATTITUDE', 'HEARTBEAT', 'HEARTBEAT']
    
    for msg_type in msg_types:
        msg = ParsedMessage(
            timestamp=time.time(),
            msg_type=msg_type,
            msg_id=0,
            system_id=1,
            component_id=1,
            sequence=0,
            fields={},
            raw_bytes=b'\xfe' * 20
        )
        calculator.update_mavlink_message(msg)
    
    metrics = calculator.get_metrics()
    
    assert metrics.mavlink_msg_type_distribution['HEARTBEAT'] == 3, \
        "Should have 3 HEARTBEAT messages"
    assert metrics.mavlink_msg_type_distribution['GPS_RAW_INT'] == 1, \
        "Should have 1 GPS_RAW_INT message"
    assert metrics.mavlink_msg_type_distribution['ATTITUDE'] == 1, \
        "Should have 1 ATTITUDE message"
    
    print(f"✅ Message distribution tracked correctly")
    print(f"   HEARTBEAT: {metrics.mavlink_msg_type_distribution['HEARTBEAT']}")
    print(f"   GPS_RAW_INT: {metrics.mavlink_msg_type_distribution['GPS_RAW_INT']}")
    print(f"   ATTITUDE: {metrics.mavlink_msg_type_distribution['ATTITUDE']}")
    
    return True


def main():
    """Run all validation tests."""
    print("\n" + "="*70)
    print("METRICS CALCULATOR VALIDATION")
    print("="*70)
    
    tests = [
        ("Basic Functionality", validate_basic_functionality),
        ("Rolling Windows", validate_rolling_windows),
        ("RSSI/SNR Extraction", validate_rssi_snr_extraction),
        ("Packet Loss Detection", validate_packet_loss_detection),
        ("Command Latency", validate_command_latency),
        ("Protocol Health", validate_protocol_health),
        ("Message Distribution", validate_message_distribution),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"\n❌ {test_name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*70)
    print(f"VALIDATION RESULTS: {passed} passed, {failed} failed")
    print("="*70 + "\n")
    
    if failed == 0:
        print("✅ All validations passed! MetricsCalculator is ready for use.\n")
        return 0
    else:
        print(f"❌ {failed} validation(s) failed. Please review the errors above.\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())
