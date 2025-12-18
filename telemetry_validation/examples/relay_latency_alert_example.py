#!/usr/bin/env python3
"""
Relay Latency Alert Example

This example demonstrates how to use the AlertManager to monitor relay mode
latency and generate alerts when latency exceeds configured thresholds.

The relay latency alert feature monitors CMD_STATUS_REPORT packets from the
binary protocol to detect when relay mode is active and track relay latency.
When latency exceeds the configured threshold (default 500ms), an alert is
generated.

Requirements: 9.5
"""

import sys
import time
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from alert_manager import AlertManager, AlertChannel, Severity
from binary_protocol_parser import StatusPayload


def main():
    """Demonstrate relay latency alert functionality."""
    
    print("=" * 70)
    print("Relay Latency Alert Example")
    print("=" * 70)
    
    # Configure alert manager with relay latency monitoring
    config = {
        'channels': [AlertChannel.CONSOLE],
        'relay_latency_threshold_ms': 500.0,  # Alert if latency > 500ms
        'throttle_window': 60,  # Throttle duplicate alerts within 60s
        'duplicate_window': 300  # Prevent duplicate alerts within 5 minutes
    }
    
    alert_manager = AlertManager(config)
    
    print(f"\nAlert Manager Configuration:")
    print(f"  Relay latency threshold: {config['relay_latency_threshold_ms']}ms")
    print(f"  Throttle window: {config['throttle_window']}s")
    print(f"  Duplicate window: {config['duplicate_window']}s")
    
    # Simulate receiving status reports from a relay node
    print("\n" + "=" * 70)
    print("Simulating Status Reports from Relay Node")
    print("=" * 70)
    
    # Status report 1: Normal operation (low latency)
    print("\n[1] Status Report - Normal Operation")
    print("-" * 70)
    
    status1 = StatusPayload(
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
        last_activity_sec=0.15,  # 150ms - normal latency
        active_peer_relays=1
    )
    
    print(f"Relay Active: {status1.relay_active}")
    print(f"Latency: {status1.last_activity_sec * 1000:.1f}ms")
    print(f"RSSI: {status1.rssi:.1f} dBm")
    print(f"SNR: {status1.snr:.1f} dB")
    print(f"Packets Relayed: {status1.packets_relayed}")
    
    alert_manager.check_relay_latency(status1, system_id=1)
    print("→ No alert (latency within threshold)")
    
    time.sleep(1)
    
    # Status report 2: Degraded performance (high latency)
    print("\n[2] Status Report - Degraded Performance")
    print("-" * 70)
    
    status2 = StatusPayload(
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
        rssi=-92.0,
        snr=5.0,
        last_activity_sec=0.75,  # 750ms - high latency!
        active_peer_relays=1
    )
    
    print(f"Relay Active: {status2.relay_active}")
    print(f"Latency: {status2.last_activity_sec * 1000:.1f}ms ⚠️")
    print(f"RSSI: {status2.rssi:.1f} dBm (degraded)")
    print(f"SNR: {status2.snr:.1f} dB (degraded)")
    print(f"Packets Relayed: {status2.packets_relayed}")
    
    alert_manager.check_relay_latency(status2, system_id=1)
    print("→ Alert generated (latency exceeds threshold)")
    
    time.sleep(1)
    
    # Status report 3: Relay mode deactivated
    print("\n[3] Status Report - Relay Mode Deactivated")
    print("-" * 70)
    
    status3 = StatusPayload(
        relay_active=False,  # Relay deactivated
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
        last_activity_sec=0.75,  # Still high, but relay inactive
        active_peer_relays=0
    )
    
    print(f"Relay Active: {status3.relay_active}")
    print(f"Latency: {status3.last_activity_sec * 1000:.1f}ms")
    print(f"RSSI: {status3.rssi:.1f} dBm")
    print(f"SNR: {status3.snr:.1f} dB")
    
    alert_manager.check_relay_latency(status3, system_id=1)
    print("→ No alert (relay mode inactive)")
    
    # Display statistics
    print("\n" + "=" * 70)
    print("Alert Statistics")
    print("=" * 70)
    
    stats = alert_manager.get_stats()
    print(f"\nTotal Alerts: {stats['total_alerts']}")
    print(f"Relay Latency Alerts: {stats['relay_latency_alerts']}")
    print(f"Filtered Duplicates: {stats['filtered_duplicates']}")
    print(f"Throttled Alerts: {stats['throttled_alerts']}")
    
    print(f"\nAlerts by Severity:")
    for severity, count in stats['alerts_by_severity'].items():
        print(f"  {severity.name}: {count}")
    
    # Display relay mode status
    print("\n" + "=" * 70)
    print("Relay Mode Status")
    print("=" * 70)
    
    relay_status = alert_manager.get_relay_mode_status()
    print(f"\nSystem 1: {'ACTIVE' if relay_status.get(1, False) else 'INACTIVE'}")
    
    # Display alert history
    print("\n" + "=" * 70)
    print("Alert History")
    print("=" * 70)
    
    history = alert_manager.get_alert_history(limit=10)
    print(f"\nRecent Alerts ({len(history)}):")
    for timestamp, message, severity, rule_name, system_id in history:
        time_str = time.strftime('%H:%M:%S', time.localtime(timestamp))
        print(f"  [{time_str}] {message}")
    
    print("\n" + "=" * 70)
    print("Example Complete")
    print("=" * 70)
    
    print("\nKey Features Demonstrated:")
    print("  ✓ Relay mode detection from CMD_STATUS_REPORT")
    print("  ✓ Latency threshold monitoring (500ms)")
    print("  ✓ Alert generation for excessive latency")
    print("  ✓ No alerts when relay mode is inactive")
    print("  ✓ Statistics tracking")
    print("  ✓ Alert history")
    
    print("\nIntegration Notes:")
    print("  • Call check_relay_latency() when receiving CMD_STATUS_REPORT")
    print("  • Configure relay_latency_threshold_ms in alert manager config")
    print("  • Alerts are automatically throttled to prevent spam")
    print("  • Use get_relay_mode_status() to query current relay state")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
