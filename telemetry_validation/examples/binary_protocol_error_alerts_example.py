#!/usr/bin/env python3
"""
Binary Protocol Error Alerts Example

This example demonstrates how to use the binary protocol error alert system
to monitor UART communication health and generate alerts for:
- High checksum error rate (>50/min)
- UART buffer overflow
- Communication timeout

Requirements: 3.2, 9.2
"""

import sys
import time
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from alert_manager import AlertManager, AlertChannel, Severity
from metrics_calculator import MetricsCalculator
from binary_protocol_parser import BinaryProtocolParser


def simulate_normal_operation():
    """Simulate normal operation with low error rates."""
    print("\n" + "="*70)
    print("SCENARIO 1: Normal Operation")
    print("="*70)
    print("\nSimulating normal UART communication with low error rates...")
    
    # Create components
    config = {
        'channels': [AlertChannel.CONSOLE],
        'checksum_error_threshold': 50.0
    }
    alert_manager = AlertManager(config)
    metrics_calc = MetricsCalculator()
    
    # Simulate some successful packets with occasional errors
    for i in range(100):
        metrics_calc.successful_binary_packets += 1
        metrics_calc.total_binary_packets += 1
        
        # Occasional checksum error (5% rate = 3 errors/min at 1 packet/sec)
        if i % 20 == 0:
            metrics_calc.record_checksum_error()
    
    # Get metrics
    metrics = metrics_calc.get_metrics()
    
    print(f"\nMetrics:")
    print(f"  - Checksum error rate: {metrics.checksum_error_rate:.1f}/min")
    print(f"  - Protocol success rate: {metrics.protocol_success_rate:.1f}%")
    print(f"  - Buffer overflows: {metrics.buffer_overflow_count}")
    print(f"  - Timeouts: {metrics.timeout_error_count}")
    
    # Check for errors
    print("\nChecking for binary protocol errors...")
    alerts = alert_manager.check_binary_protocol_errors(metrics, system_id=1)
    
    if not any(alerts):
        print("✓ No alerts generated - system operating normally")
    else:
        print(f"⚠ Generated {sum(alerts)} alerts")
    
    return alert_manager, metrics_calc


def simulate_high_checksum_errors():
    """Simulate high checksum error rate scenario."""
    print("\n" + "="*70)
    print("SCENARIO 2: High Checksum Error Rate")
    print("="*70)
    print("\nSimulating degraded UART communication with high checksum errors...")
    print("This could indicate electrical noise, baud rate mismatch, or cable issues.")
    
    # Create components
    config = {
        'channels': [AlertChannel.CONSOLE],
        'checksum_error_threshold': 50.0
    }
    alert_manager = AlertManager(config)
    metrics_calc = MetricsCalculator()
    
    # Simulate high error rate (60 errors in 1 minute = 60/min)
    for i in range(60):
        metrics_calc.record_checksum_error()
    
    # Also some successful packets
    for i in range(40):
        metrics_calc.successful_binary_packets += 1
        metrics_calc.total_binary_packets += 1
    
    # Get metrics
    metrics = metrics_calc.get_metrics()
    
    print(f"\nMetrics:")
    print(f"  - Checksum error rate: {metrics.checksum_error_rate:.1f}/min ⚠")
    print(f"  - Protocol success rate: {metrics.protocol_success_rate:.1f}%")
    
    # Check for errors
    print("\nChecking for binary protocol errors...")
    alerts = alert_manager.check_binary_protocol_errors(metrics, system_id=1)
    
    if alerts[0]:
        print("✓ Checksum error alert generated as expected")
    
    # Show statistics
    stats = alert_manager.get_stats()
    print(f"\nAlert Statistics:")
    print(f"  - Total alerts: {stats['total_alerts']}")
    print(f"  - Binary protocol error alerts: {stats['binary_protocol_error_alerts']}")
    
    return alert_manager, metrics_calc


def simulate_buffer_overflow():
    """Simulate buffer overflow scenario."""
    print("\n" + "="*70)
    print("SCENARIO 3: Buffer Overflow")
    print("="*70)
    print("\nSimulating UART buffer overflow...")
    print("This indicates data arriving faster than it can be processed.")
    
    # Create components
    config = {
        'channels': [AlertChannel.CONSOLE]
    }
    alert_manager = AlertManager(config)
    metrics_calc = MetricsCalculator()
    
    # Simulate buffer overflow events
    print("\nRecording buffer overflow events...")
    for i in range(3):
        metrics_calc.record_buffer_overflow()
        time.sleep(0.1)
    
    # Get metrics
    metrics = metrics_calc.get_metrics()
    
    print(f"\nMetrics:")
    print(f"  - Buffer overflows: {metrics.buffer_overflow_count} ⚠")
    
    # Check for errors
    print("\nChecking for binary protocol errors...")
    alerts = alert_manager.check_binary_protocol_errors(metrics, system_id=1)
    
    if alerts[1]:
        print("✓ Buffer overflow alert generated (CRITICAL severity)")
    
    # Show alert history
    history = alert_manager.get_alert_history(limit=1)
    if history:
        timestamp, message, severity, rule_name, system_id = history[0]
        print(f"\nLatest Alert:")
        print(f"  - Severity: {severity.name}")
        print(f"  - Rule: {rule_name}")
        print(f"  - System ID: {system_id}")
    
    return alert_manager, metrics_calc


def simulate_communication_timeout():
    """Simulate communication timeout scenario."""
    print("\n" + "="*70)
    print("SCENARIO 4: Communication Timeout")
    print("="*70)
    print("\nSimulating communication timeouts...")
    print("This indicates incomplete packet transmission or connection issues.")
    
    # Create components
    config = {
        'channels': [AlertChannel.CONSOLE]
    }
    alert_manager = AlertManager(config)
    metrics_calc = MetricsCalculator()
    
    # Simulate timeout events
    print("\nRecording timeout events...")
    for i in range(5):
        metrics_calc.record_timeout_error()
        time.sleep(0.1)
    
    # Get metrics
    metrics = metrics_calc.get_metrics()
    
    print(f"\nMetrics:")
    print(f"  - Timeout errors: {metrics.timeout_error_count} ⚠")
    
    # Check for errors
    print("\nChecking for binary protocol errors...")
    alerts = alert_manager.check_binary_protocol_errors(metrics, system_id=1)
    
    if alerts[2]:
        print("✓ Communication timeout alert generated")
    
    return alert_manager, metrics_calc


def simulate_multiple_errors():
    """Simulate multiple simultaneous errors."""
    print("\n" + "="*70)
    print("SCENARIO 5: Multiple Simultaneous Errors")
    print("="*70)
    print("\nSimulating severe UART communication degradation...")
    print("Multiple error types occurring simultaneously.")
    
    # Create components
    config = {
        'channels': [AlertChannel.CONSOLE],
        'checksum_error_threshold': 50.0
    }
    alert_manager = AlertManager(config)
    metrics_calc = MetricsCalculator()
    
    # Simulate multiple error types
    print("\nRecording multiple error types...")
    
    # High checksum errors
    for i in range(80):
        metrics_calc.record_checksum_error()
    
    # Buffer overflows
    for i in range(2):
        metrics_calc.record_buffer_overflow()
    
    # Timeouts
    for i in range(4):
        metrics_calc.record_timeout_error()
    
    # Get metrics
    metrics = metrics_calc.get_metrics()
    
    print(f"\nMetrics:")
    print(f"  - Checksum error rate: {metrics.checksum_error_rate:.1f}/min ⚠")
    print(f"  - Buffer overflows: {metrics.buffer_overflow_count} ⚠")
    print(f"  - Timeout errors: {metrics.timeout_error_count} ⚠")
    print(f"  - Protocol success rate: {metrics.protocol_success_rate:.1f}%")
    
    # Check for errors
    print("\nChecking for binary protocol errors...")
    alerts = alert_manager.check_binary_protocol_errors(metrics, system_id=1)
    
    alert_count = sum(alerts)
    print(f"\n✓ Generated {alert_count} alerts:")
    print(f"  - Checksum: {'Yes' if alerts[0] else 'No'}")
    print(f"  - Buffer overflow: {'Yes' if alerts[1] else 'No'}")
    print(f"  - Timeout: {'Yes' if alerts[2] else 'No'}")
    
    # Show statistics
    stats = alert_manager.get_stats()
    print(f"\nAlert Statistics:")
    print(f"  - Total alerts: {stats['total_alerts']}")
    print(f"  - Binary protocol error alerts: {stats['binary_protocol_error_alerts']}")
    print(f"  - Alerts by severity:")
    print(f"    - INFO: {stats['alerts_by_severity'][Severity.INFO]}")
    print(f"    - WARNING: {stats['alerts_by_severity'][Severity.WARNING]}")
    print(f"    - CRITICAL: {stats['alerts_by_severity'][Severity.CRITICAL]}")
    
    return alert_manager, metrics_calc


def demonstrate_throttling():
    """Demonstrate alert throttling behavior."""
    print("\n" + "="*70)
    print("SCENARIO 6: Alert Throttling")
    print("="*70)
    print("\nDemonstrating alert throttling to prevent spam...")
    
    # Create components
    config = {
        'channels': [AlertChannel.CONSOLE],
        'checksum_error_threshold': 50.0
    }
    alert_manager = AlertManager(config)
    metrics_calc = MetricsCalculator()
    
    # Record high checksum errors
    for i in range(80):
        metrics_calc.record_checksum_error()
    
    metrics = metrics_calc.get_metrics()
    
    # First check - should generate alert
    print("\nFirst check (should generate alert):")
    alerts = alert_manager.check_binary_protocol_errors(metrics, system_id=1)
    print(f"  Alert generated: {alerts[0]}")
    
    # Immediate second check - should be throttled
    print("\nImmediate second check (should be throttled):")
    alerts = alert_manager.check_binary_protocol_errors(metrics, system_id=1)
    print(f"  Alert generated: {alerts[0]}")
    
    # Show statistics
    stats = alert_manager.get_stats()
    print(f"\nThrottling Statistics:")
    print(f"  - Total alerts: {stats['total_alerts']}")
    print(f"  - Throttled alerts: {stats['throttled_alerts']}")
    
    print("\n✓ Throttling prevents duplicate alerts within time window")
    
    return alert_manager, metrics_calc


def main():
    """Run all example scenarios."""
    print("\n" + "="*70)
    print("BINARY PROTOCOL ERROR ALERTS - EXAMPLE SCENARIOS")
    print("="*70)
    print("\nThis example demonstrates the binary protocol error alert system")
    print("with various scenarios showing different types of UART communication issues.")
    
    # Run scenarios
    scenarios = [
        ("Normal Operation", simulate_normal_operation),
        ("High Checksum Errors", simulate_high_checksum_errors),
        ("Buffer Overflow", simulate_buffer_overflow),
        ("Communication Timeout", simulate_communication_timeout),
        ("Multiple Errors", simulate_multiple_errors),
        ("Alert Throttling", demonstrate_throttling)
    ]
    
    for name, scenario_func in scenarios:
        try:
            scenario_func()
            time.sleep(1)  # Brief pause between scenarios
        except Exception as e:
            print(f"\n✗ Scenario '{name}' failed: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print("\nThe binary protocol error alert system provides:")
    print("  ✓ Checksum error rate monitoring (>50/min threshold)")
    print("  ✓ Buffer overflow detection (CRITICAL alerts)")
    print("  ✓ Communication timeout detection")
    print("  ✓ Intelligent throttling to prevent alert spam")
    print("  ✓ Comprehensive statistics tracking")
    print("\nUse this system to proactively detect and diagnose UART")
    print("communication issues before they impact system reliability.")
    print("\n" + "="*70)


if __name__ == '__main__':
    main()
