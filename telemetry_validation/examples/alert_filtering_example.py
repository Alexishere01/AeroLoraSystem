#!/usr/bin/env python3
"""
Example demonstrating alert filtering and throttling capabilities.

This example shows how the AlertManager prevents duplicate alerts and
throttles high-frequency alerts to prevent spam.
"""

import sys
import os
import time

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from alert_manager import AlertManager, AlertChannel, Severity


class MockViolation:
    """Mock violation for demonstration."""
    def __init__(self, rule_name, system_id, severity, field="voltage", 
                 actual_value=10.5, threshold=11.0, msg_type="SYS_STATUS",
                 description="Battery voltage low", timestamp=None):
        self.rule_name = rule_name
        self.system_id = system_id
        self.severity = severity
        self.field = field
        self.actual_value = actual_value
        self.threshold = threshold
        self.msg_type = msg_type
        self.description = description
        self.timestamp = timestamp or time.time()


def main():
    """Demonstrate alert filtering and throttling."""
    
    print("=" * 70)
    print("Alert Filtering and Throttling Example")
    print("=" * 70)
    print()
    
    # Configure alert manager with aggressive settings for demonstration
    config = {
        'channels': [AlertChannel.CONSOLE],
        'throttle_window': 10,           # 10 seconds
        'duplicate_window': 30,          # 30 seconds
        'max_alerts_per_window': 3       # Max 3 alerts per 10 seconds
    }
    
    manager = AlertManager(config)
    
    print("Configuration:")
    print(f"  - Throttle window: {config['throttle_window']} seconds")
    print(f"  - Duplicate window: {config['duplicate_window']} seconds")
    print(f"  - Max alerts per window: {config['max_alerts_per_window']}")
    print()
    
    # Example 1: Duplicate filtering
    print("-" * 70)
    print("Example 1: Duplicate Alert Filtering")
    print("-" * 70)
    print()
    
    violation1 = MockViolation("Low Battery", 1, Severity.WARNING)
    violation2 = MockViolation("Low Battery", 1, Severity.WARNING)
    
    print("Sending first alert...")
    result1 = manager.send_alert(violation1)
    print(f"Result: {'Sent' if result1 else 'Filtered'}")
    print()
    
    print("Sending duplicate alert immediately...")
    result2 = manager.send_alert(violation2)
    print(f"Result: {'Sent' if result2 else 'Filtered (duplicate)'}")
    print()
    
    # Example 2: Different systems are not duplicates
    print("-" * 70)
    print("Example 2: Alerts from Different Systems")
    print("-" * 70)
    print()
    
    violation3 = MockViolation("Low Battery", 2, Severity.WARNING)
    
    print("Sending alert from different system (system_id=2)...")
    result3 = manager.send_alert(violation3)
    print(f"Result: {'Sent' if result3 else 'Filtered'}")
    print()
    
    # Example 3: Throttling
    print("-" * 70)
    print("Example 3: Alert Throttling")
    print("-" * 70)
    print()
    
    print(f"Sending {config['max_alerts_per_window']} alerts rapidly...")
    for i in range(config['max_alerts_per_window']):
        # Use different values to avoid duplicate detection
        violation = MockViolation(
            "GPS Glitch", 1, Severity.WARNING,
            field="altitude", actual_value=100 + i * 10
        )
        result = manager.send_alert(violation)
        print(f"  Alert {i+1}: {'Sent' if result else 'Filtered'}")
        time.sleep(0.1)
    
    print()
    print("Sending one more alert (should be throttled)...")
    violation = MockViolation(
        "GPS Glitch", 1, Severity.WARNING,
        field="altitude", actual_value=200
    )
    result = manager.send_alert(violation)
    print(f"Result: {'Sent' if result else 'Throttled (rate limit exceeded)'}")
    print()
    
    # Example 4: Different rules are throttled independently
    print("-" * 70)
    print("Example 4: Independent Throttling per Rule")
    print("-" * 70)
    print()
    
    print("Sending alert for different rule (should go through)...")
    violation = MockViolation("Signal Weak", 1, Severity.WARNING, field="rssi")
    result = manager.send_alert(violation)
    print(f"Result: {'Sent' if result else 'Filtered'}")
    print()
    
    # Show statistics
    print("-" * 70)
    print("Alert Statistics")
    print("-" * 70)
    print()
    
    stats = manager.get_stats()
    print(f"Total alerts sent: {stats['total_alerts']}")
    print(f"Filtered duplicates: {stats['filtered_duplicates']}")
    print(f"Throttled alerts: {stats['throttled_alerts']}")
    print()
    
    print("Alerts by severity:")
    for severity, count in stats['alerts_by_severity'].items():
        print(f"  {severity.name}: {count}")
    print()
    
    # Show alert history
    print("-" * 70)
    print("Alert History (most recent first)")
    print("-" * 70)
    print()
    
    history = manager.get_alert_history(limit=5)
    for i, (timestamp, message, severity, rule_name, system_id) in enumerate(history, 1):
        time_str = time.strftime('%H:%M:%S', time.localtime(timestamp))
        print(f"{i}. [{time_str}] {severity.name}: {rule_name} (System {system_id})")
    print()
    
    # Example 5: Throttle window expiry
    print("-" * 70)
    print("Example 5: Throttle Window Expiry")
    print("-" * 70)
    print()
    
    print(f"Waiting {config['throttle_window'] + 1} seconds for throttle window to expire...")
    time.sleep(config['throttle_window'] + 1)
    
    print("Sending alert after window expiry (should go through)...")
    violation = MockViolation(
        "GPS Glitch", 1, Severity.WARNING,
        field="altitude", actual_value=300
    )
    result = manager.send_alert(violation)
    print(f"Result: {'Sent' if result else 'Filtered'}")
    print()
    
    # Final statistics
    print("-" * 70)
    print("Final Statistics")
    print("-" * 70)
    print()
    
    stats = manager.get_stats()
    print(f"Total alerts sent: {stats['total_alerts']}")
    print(f"Filtered duplicates: {stats['filtered_duplicates']}")
    print(f"Throttled alerts: {stats['throttled_alerts']}")
    print()
    
    print("=" * 70)
    print("Example Complete")
    print("=" * 70)


if __name__ == '__main__':
    main()
