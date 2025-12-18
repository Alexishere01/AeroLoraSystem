#!/usr/bin/env python3
"""
Test script for relay mode latency alerts.

This script tests the relay latency alert functionality in the AlertManager.
"""

import sys
import time
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from alert_manager import AlertManager, AlertChannel, Severity, RelayLatencyAlert
from binary_protocol_parser import StatusPayload


def test_relay_latency_detection():
    """Test relay mode latency detection and alerting."""
    print("=" * 70)
    print("Testing Relay Mode Latency Alerts")
    print("=" * 70)
    
    # Create alert manager with relay latency threshold of 500ms
    config = {
        'channels': [AlertChannel.CONSOLE],
        'relay_latency_threshold_ms': 500.0,
        'throttle_window': 60,
        'duplicate_window': 300
    }
    
    alert_manager = AlertManager(config)
    print(f"\n✓ Alert manager initialized with {config['relay_latency_threshold_ms']}ms threshold")
    
    # Test 1: Normal relay mode (latency below threshold)
    print("\n" + "-" * 70)
    print("Test 1: Normal relay mode (latency below threshold)")
    print("-" * 70)
    
    status_payload_normal = StatusPayload(
        relay_active=True,
        own_drone_sysid=1,
        packets_relayed=100,
        bytes_relayed=50000,
        mesh_to_uart_packets=50,
        uart_to_mesh_packets=50,
        mesh_to_uart_bytes=25000,
        uart_to_mesh_bytes=25000,
        bridge_gcs_to_mesh_packets=0,
        bridge_mesh_to_gcs_packets=0,
        bridge_gcs_to_mesh_bytes=0,
        bridge_mesh_to_gcs_bytes=0,
        rssi=-85.0,
        snr=8.5,
        last_activity_sec=0.2,  # 200ms - below threshold
        active_peer_relays=1
    )
    
    alert_generated = alert_manager.check_relay_latency(status_payload_normal, system_id=1)
    print(f"Latency: {status_payload_normal.last_activity_sec * 1000:.1f}ms")
    print(f"Alert generated: {alert_generated}")
    assert not alert_generated, "Should not generate alert for normal latency"
    print("✓ No alert generated for normal latency")
    
    # Test 2: High relay mode latency (exceeds threshold)
    print("\n" + "-" * 70)
    print("Test 2: High relay mode latency (exceeds threshold)")
    print("-" * 70)
    
    status_payload_high = StatusPayload(
        relay_active=True,
        own_drone_sysid=1,
        packets_relayed=150,
        bytes_relayed=75000,
        mesh_to_uart_packets=75,
        uart_to_mesh_packets=75,
        mesh_to_uart_bytes=37500,
        uart_to_mesh_bytes=37500,
        bridge_gcs_to_mesh_packets=0,
        bridge_mesh_to_gcs_packets=0,
        bridge_gcs_to_mesh_bytes=0,
        bridge_mesh_to_gcs_bytes=0,
        rssi=-90.0,
        snr=6.0,
        last_activity_sec=0.75,  # 750ms - exceeds threshold
        active_peer_relays=1
    )
    
    time.sleep(0.1)  # Small delay to ensure different timestamp
    alert_generated = alert_manager.check_relay_latency(status_payload_high, system_id=1)
    print(f"Latency: {status_payload_high.last_activity_sec * 1000:.1f}ms")
    print(f"Alert generated: {alert_generated}")
    assert alert_generated, "Should generate alert for high latency"
    print("✓ Alert generated for high latency")
    
    # Test 3: Relay mode inactive (no alert)
    print("\n" + "-" * 70)
    print("Test 3: Relay mode inactive (no alert)")
    print("-" * 70)
    
    status_payload_inactive = StatusPayload(
        relay_active=False,  # Relay mode inactive
        own_drone_sysid=1,
        packets_relayed=150,
        bytes_relayed=75000,
        mesh_to_uart_packets=75,
        uart_to_mesh_packets=75,
        mesh_to_uart_bytes=37500,
        uart_to_mesh_bytes=37500,
        bridge_gcs_to_mesh_packets=0,
        bridge_mesh_to_gcs_packets=0,
        bridge_gcs_to_mesh_bytes=0,
        bridge_mesh_to_gcs_bytes=0,
        rssi=-85.0,
        snr=8.0,
        last_activity_sec=0.75,  # 750ms - but relay inactive
        active_peer_relays=0
    )
    
    time.sleep(0.1)
    alert_generated = alert_manager.check_relay_latency(status_payload_inactive, system_id=1)
    print(f"Relay active: {status_payload_inactive.relay_active}")
    print(f"Alert generated: {alert_generated}")
    assert not alert_generated, "Should not generate alert when relay is inactive"
    print("✓ No alert generated when relay mode is inactive")
    
    # Test 4: Multiple systems
    print("\n" + "-" * 70)
    print("Test 4: Multiple systems with different relay states")
    print("-" * 70)
    
    # System 2 with high latency
    status_payload_sys2 = StatusPayload(
        relay_active=True,
        own_drone_sysid=2,
        packets_relayed=200,
        bytes_relayed=100000,
        mesh_to_uart_packets=100,
        uart_to_mesh_packets=100,
        mesh_to_uart_bytes=50000,
        uart_to_mesh_bytes=50000,
        bridge_gcs_to_mesh_packets=0,
        bridge_mesh_to_gcs_packets=0,
        bridge_gcs_to_mesh_bytes=0,
        bridge_mesh_to_gcs_bytes=0,
        rssi=-88.0,
        snr=7.0,
        last_activity_sec=0.6,  # 600ms - exceeds threshold
        active_peer_relays=1
    )
    
    time.sleep(0.1)
    alert_generated = alert_manager.check_relay_latency(status_payload_sys2, system_id=2)
    print(f"System 2 latency: {status_payload_sys2.last_activity_sec * 1000:.1f}ms")
    print(f"Alert generated: {alert_generated}")
    assert alert_generated, "Should generate alert for system 2 high latency"
    print("✓ Alert generated for system 2")
    
    # Test 5: Check relay mode status
    print("\n" + "-" * 70)
    print("Test 5: Check relay mode status tracking")
    print("-" * 70)
    
    relay_status = alert_manager.get_relay_mode_status()
    print(f"Relay mode status: {relay_status}")
    assert relay_status[1] == False, "System 1 should be inactive"
    assert relay_status[2] == True, "System 2 should be active"
    print("✓ Relay mode status correctly tracked")
    
    # Test 6: Check statistics
    print("\n" + "-" * 70)
    print("Test 6: Check alert statistics")
    print("-" * 70)
    
    stats = alert_manager.get_stats()
    print(f"Total alerts: {stats['total_alerts']}")
    print(f"Relay latency alerts: {stats['relay_latency_alerts']}")
    print(f"Filtered duplicates: {stats['filtered_duplicates']}")
    print(f"Throttled alerts: {stats['throttled_alerts']}")
    
    assert stats['relay_latency_alerts'] == 2, "Should have 2 relay latency alerts"
    print("✓ Statistics correctly tracked")
    
    # Test 7: Alert throttling
    print("\n" + "-" * 70)
    print("Test 7: Alert throttling for repeated high latency")
    print("-" * 70)
    
    # Try to generate multiple alerts in quick succession
    alerts_generated = 0
    for i in range(5):
        time.sleep(0.05)
        if alert_manager.check_relay_latency(status_payload_high, system_id=1):
            alerts_generated += 1
    
    print(f"Alerts generated from 5 attempts: {alerts_generated}")
    print(f"Throttled alerts: {alert_manager.get_stats()['throttled_alerts']}")
    assert alerts_generated < 5, "Some alerts should be throttled"
    print("✓ Alert throttling working correctly")
    
    print("\n" + "=" * 70)
    print("All tests passed!")
    print("=" * 70)


def test_relay_latency_alert_dataclass():
    """Test RelayLatencyAlert dataclass."""
    print("\n" + "=" * 70)
    print("Testing RelayLatencyAlert Dataclass")
    print("=" * 70)
    
    alert = RelayLatencyAlert(
        timestamp=time.time(),
        system_id=1,
        latency_ms=750.0,
        threshold_ms=500.0,
        relay_active=True,
        severity=Severity.WARNING
    )
    
    print(f"\nAlert properties:")
    print(f"  Rule name: {alert.rule_name}")
    print(f"  Message type: {alert.msg_type}")
    print(f"  Field: {alert.field}")
    print(f"  Actual value: {alert.actual_value}")
    print(f"  Threshold: {alert.threshold}")
    print(f"  Description: {alert.description}")
    print(f"  Severity: {alert.severity.name}")
    
    assert alert.rule_name == "Relay Mode Latency"
    assert alert.msg_type == "CMD_STATUS_REPORT"
    assert alert.field == "relay_latency"
    assert alert.actual_value == 750.0
    assert alert.threshold == 500.0
    
    print("\n✓ RelayLatencyAlert dataclass working correctly")


if __name__ == '__main__':
    try:
        test_relay_latency_alert_dataclass()
        test_relay_latency_detection()
        
        print("\n" + "=" * 70)
        print("SUCCESS: All relay latency alert tests passed!")
        print("=" * 70)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
