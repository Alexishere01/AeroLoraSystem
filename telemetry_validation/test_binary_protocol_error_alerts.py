#!/usr/bin/env python3
"""
Test script for binary protocol error alerts.

This script validates that the AlertManager correctly generates alerts for:
1. High checksum error rate (>50/min)
2. UART buffer overflow
3. Communication timeout

Requirements: 3.2, 9.2
"""

import sys
import time
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from alert_manager import AlertManager, AlertChannel, Severity, BinaryProtocolErrorAlert
from metrics_calculator import MetricsCalculator, TelemetryMetrics


def test_checksum_error_alert():
    """Test alert generation for high checksum error rate."""
    print("\n" + "="*70)
    print("TEST 1: Checksum Error Rate Alert")
    print("="*70)
    
    # Create alert manager with low threshold for testing
    config = {
        'channels': [AlertChannel.CONSOLE],
        'checksum_error_threshold': 50.0  # 50 errors per minute
    }
    alert_manager = AlertManager(config)
    
    # Create metrics with high checksum error rate
    metrics = TelemetryMetrics(
        binary_packet_rate_1s=10.0,
        binary_packet_rate_10s=10.0,
        binary_packet_rate_60s=10.0,
        mavlink_packet_rate_1s=5.0,
        mavlink_packet_rate_10s=5.0,
        mavlink_packet_rate_60s=5.0,
        avg_rssi=-80.0,
        avg_snr=5.0,
        drop_rate=0.0,
        packets_lost=0,
        packets_received=100,
        latency_avg=0.05,
        latency_min=0.01,
        latency_max=0.1,
        latency_samples=10,
        mavlink_msg_type_distribution={},
        binary_cmd_type_distribution={},
        checksum_error_rate=75.0,  # 75 errors/min - exceeds threshold
        parse_error_rate=5.0,
        protocol_success_rate=90.0,
        buffer_overflow_count=0,
        timeout_error_count=0,
        timestamp=time.time()
    )
    
    # Check for binary protocol errors
    print("\nChecking binary protocol errors with checksum_error_rate=75.0/min...")
    alerts = alert_manager.check_binary_protocol_errors(metrics, system_id=1)
    
    # Verify checksum alert was generated
    if alerts[0]:
        print("✓ Checksum error alert generated successfully")
    else:
        print("✗ FAILED: Checksum error alert not generated")
        return False
    
    # Verify alert statistics
    stats = alert_manager.get_stats()
    if stats['binary_protocol_error_alerts'] == 1:
        print(f"✓ Alert statistics updated: {stats['binary_protocol_error_alerts']} binary protocol error alerts")
    else:
        print(f"✗ FAILED: Expected 1 alert, got {stats['binary_protocol_error_alerts']}")
        return False
    
    # Test throttling - should not generate another alert immediately
    print("\nTesting alert throttling (should not generate duplicate)...")
    alerts = alert_manager.check_binary_protocol_errors(metrics, system_id=1)
    if not alerts[0]:
        print("✓ Alert throttling working correctly")
    else:
        print("✗ FAILED: Duplicate alert generated (throttling not working)")
        return False
    
    print("\n✓ TEST 1 PASSED: Checksum error rate alerts working correctly")
    return True


def test_buffer_overflow_alert():
    """Test alert generation for buffer overflow."""
    print("\n" + "="*70)
    print("TEST 2: Buffer Overflow Alert")
    print("="*70)
    
    # Create alert manager
    config = {
        'channels': [AlertChannel.CONSOLE]
    }
    alert_manager = AlertManager(config)
    
    # Create metrics with buffer overflow
    metrics = TelemetryMetrics(
        binary_packet_rate_1s=10.0,
        binary_packet_rate_10s=10.0,
        binary_packet_rate_60s=10.0,
        mavlink_packet_rate_1s=5.0,
        mavlink_packet_rate_10s=5.0,
        mavlink_packet_rate_60s=5.0,
        avg_rssi=-80.0,
        avg_snr=5.0,
        drop_rate=0.0,
        packets_lost=0,
        packets_received=100,
        latency_avg=0.05,
        latency_min=0.01,
        latency_max=0.1,
        latency_samples=10,
        mavlink_msg_type_distribution={},
        binary_cmd_type_distribution={},
        checksum_error_rate=10.0,
        parse_error_rate=5.0,
        protocol_success_rate=95.0,
        buffer_overflow_count=3,  # Buffer overflow detected
        timeout_error_count=0,
        timestamp=time.time()
    )
    
    # Check for binary protocol errors
    print("\nChecking binary protocol errors with buffer_overflow_count=3...")
    alerts = alert_manager.check_binary_protocol_errors(metrics, system_id=1)
    
    # Verify buffer overflow alert was generated
    if alerts[1]:
        print("✓ Buffer overflow alert generated successfully")
    else:
        print("✗ FAILED: Buffer overflow alert not generated")
        return False
    
    # Verify alert statistics
    stats = alert_manager.get_stats()
    if stats['binary_protocol_error_alerts'] == 1:
        print(f"✓ Alert statistics updated: {stats['binary_protocol_error_alerts']} binary protocol error alerts")
    else:
        print(f"✗ FAILED: Expected 1 alert, got {stats['binary_protocol_error_alerts']}")
        return False
    
    # Verify severity is CRITICAL
    history = alert_manager.get_alert_history(limit=1)
    if history and history[0][2] == Severity.CRITICAL:
        print("✓ Buffer overflow alert has CRITICAL severity")
    else:
        print("✗ FAILED: Buffer overflow alert should have CRITICAL severity")
        return False
    
    print("\n✓ TEST 2 PASSED: Buffer overflow alerts working correctly")
    return True


def test_timeout_alert():
    """Test alert generation for communication timeout."""
    print("\n" + "="*70)
    print("TEST 3: Communication Timeout Alert")
    print("="*70)
    
    # Create alert manager
    config = {
        'channels': [AlertChannel.CONSOLE]
    }
    alert_manager = AlertManager(config)
    
    # Create metrics with timeout errors
    metrics = TelemetryMetrics(
        binary_packet_rate_1s=10.0,
        binary_packet_rate_10s=10.0,
        binary_packet_rate_60s=10.0,
        mavlink_packet_rate_1s=5.0,
        mavlink_packet_rate_10s=5.0,
        mavlink_packet_rate_60s=5.0,
        avg_rssi=-80.0,
        avg_snr=5.0,
        drop_rate=0.0,
        packets_lost=0,
        packets_received=100,
        latency_avg=0.05,
        latency_min=0.01,
        latency_max=0.1,
        latency_samples=10,
        mavlink_msg_type_distribution={},
        binary_cmd_type_distribution={},
        checksum_error_rate=10.0,
        parse_error_rate=5.0,
        protocol_success_rate=95.0,
        buffer_overflow_count=0,
        timeout_error_count=5,  # Timeout errors detected
        timestamp=time.time()
    )
    
    # Check for binary protocol errors
    print("\nChecking binary protocol errors with timeout_error_count=5...")
    alerts = alert_manager.check_binary_protocol_errors(metrics, system_id=1)
    
    # Verify timeout alert was generated
    if alerts[2]:
        print("✓ Communication timeout alert generated successfully")
    else:
        print("✗ FAILED: Communication timeout alert not generated")
        return False
    
    # Verify alert statistics
    stats = alert_manager.get_stats()
    if stats['binary_protocol_error_alerts'] == 1:
        print(f"✓ Alert statistics updated: {stats['binary_protocol_error_alerts']} binary protocol error alerts")
    else:
        print(f"✗ FAILED: Expected 1 alert, got {stats['binary_protocol_error_alerts']}")
        return False
    
    # Verify severity is WARNING
    history = alert_manager.get_alert_history(limit=1)
    if history and history[0][2] == Severity.WARNING:
        print("✓ Timeout alert has WARNING severity")
    else:
        print("✗ FAILED: Timeout alert should have WARNING severity")
        return False
    
    print("\n✓ TEST 3 PASSED: Communication timeout alerts working correctly")
    return True


def test_multiple_errors():
    """Test handling of multiple simultaneous errors."""
    print("\n" + "="*70)
    print("TEST 4: Multiple Simultaneous Errors")
    print("="*70)
    
    # Create alert manager
    config = {
        'channels': [AlertChannel.CONSOLE],
        'checksum_error_threshold': 50.0
    }
    alert_manager = AlertManager(config)
    
    # Create metrics with multiple errors
    metrics = TelemetryMetrics(
        binary_packet_rate_1s=10.0,
        binary_packet_rate_10s=10.0,
        binary_packet_rate_60s=10.0,
        mavlink_packet_rate_1s=5.0,
        mavlink_packet_rate_10s=5.0,
        mavlink_packet_rate_60s=5.0,
        avg_rssi=-80.0,
        avg_snr=5.0,
        drop_rate=0.0,
        packets_lost=0,
        packets_received=100,
        latency_avg=0.05,
        latency_min=0.01,
        latency_max=0.1,
        latency_samples=10,
        mavlink_msg_type_distribution={},
        binary_cmd_type_distribution={},
        checksum_error_rate=100.0,  # High checksum errors
        parse_error_rate=5.0,
        protocol_success_rate=80.0,
        buffer_overflow_count=2,  # Buffer overflow
        timeout_error_count=3,  # Timeout errors
        timestamp=time.time()
    )
    
    # Check for binary protocol errors
    print("\nChecking binary protocol errors with multiple error types...")
    alerts = alert_manager.check_binary_protocol_errors(metrics, system_id=1)
    
    # Count generated alerts
    alert_count = sum(alerts)
    print(f"\nGenerated {alert_count} alerts:")
    print(f"  - Checksum: {alerts[0]}")
    print(f"  - Buffer overflow: {alerts[1]}")
    print(f"  - Timeout: {alerts[2]}")
    
    if alert_count == 3:
        print("✓ All three alert types generated successfully")
    else:
        print(f"✗ FAILED: Expected 3 alerts, got {alert_count}")
        return False
    
    # Verify alert statistics
    stats = alert_manager.get_stats()
    if stats['binary_protocol_error_alerts'] == 3:
        print(f"✓ Alert statistics correct: {stats['binary_protocol_error_alerts']} binary protocol error alerts")
    else:
        print(f"✗ FAILED: Expected 3 alerts in stats, got {stats['binary_protocol_error_alerts']}")
        return False
    
    print("\n✓ TEST 4 PASSED: Multiple simultaneous errors handled correctly")
    return True


def test_metrics_calculator_integration():
    """Test integration with MetricsCalculator."""
    print("\n" + "="*70)
    print("TEST 5: MetricsCalculator Integration")
    print("="*70)
    
    # Create metrics calculator
    metrics_calc = MetricsCalculator()
    
    # Record some errors
    print("\nRecording binary protocol errors...")
    for i in range(60):
        metrics_calc.record_checksum_error()
    
    metrics_calc.record_buffer_overflow()
    metrics_calc.record_buffer_overflow()
    
    for i in range(5):
        metrics_calc.record_timeout_error()
    
    # Get metrics
    metrics = metrics_calc.get_metrics()
    
    print(f"\nMetrics calculated:")
    print(f"  - Checksum error rate: {metrics.checksum_error_rate:.1f}/min")
    print(f"  - Buffer overflow count: {metrics.buffer_overflow_count}")
    print(f"  - Timeout error count: {metrics.timeout_error_count}")
    
    # Verify metrics
    if metrics.checksum_error_rate > 0:
        print("✓ Checksum error rate calculated")
    else:
        print("✗ FAILED: Checksum error rate not calculated")
        return False
    
    if metrics.buffer_overflow_count == 2:
        print("✓ Buffer overflow count correct")
    else:
        print(f"✗ FAILED: Expected 2 buffer overflows, got {metrics.buffer_overflow_count}")
        return False
    
    if metrics.timeout_error_count == 5:
        print("✓ Timeout error count correct")
    else:
        print(f"✗ FAILED: Expected 5 timeouts, got {metrics.timeout_error_count}")
        return False
    
    # Test with alert manager
    config = {
        'channels': [AlertChannel.CONSOLE],
        'checksum_error_threshold': 50.0
    }
    alert_manager = AlertManager(config)
    
    print("\nTesting alert generation with calculated metrics...")
    alerts = alert_manager.check_binary_protocol_errors(metrics, system_id=1)
    
    alert_count = sum(alerts)
    if alert_count > 0:
        print(f"✓ Generated {alert_count} alerts from calculated metrics")
    else:
        print("✗ FAILED: No alerts generated from calculated metrics")
        return False
    
    print("\n✓ TEST 5 PASSED: MetricsCalculator integration working correctly")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("BINARY PROTOCOL ERROR ALERTS TEST SUITE")
    print("="*70)
    print("\nThis test suite validates binary protocol error alert functionality:")
    print("  1. High checksum error rate alerts (>50/min)")
    print("  2. UART buffer overflow alerts")
    print("  3. Communication timeout alerts")
    print("  4. Multiple simultaneous errors")
    print("  5. MetricsCalculator integration")
    
    tests = [
        ("Checksum Error Alert", test_checksum_error_alert),
        ("Buffer Overflow Alert", test_buffer_overflow_alert),
        ("Communication Timeout Alert", test_timeout_alert),
        ("Multiple Simultaneous Errors", test_multiple_errors),
        ("MetricsCalculator Integration", test_metrics_calculator_integration)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ TEST FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ ALL TESTS PASSED")
        return 0
    else:
        print(f"\n✗ {total - passed} TEST(S) FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(main())
