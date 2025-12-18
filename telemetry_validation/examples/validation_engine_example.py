#!/usr/bin/env python3
"""
ValidationEngine Usage Example

This example demonstrates how to use the ValidationEngine to validate
MAVLink telemetry data with configurable rules, GPS altitude jump detection,
and packet loss detection.
"""

import sys
from pathlib import Path
import time

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from validation_engine import ValidationEngine, Severity
from mavlink_parser import ParsedMessage


def example_basic_validation():
    """Example: Basic validation with rules."""
    print("=" * 60)
    print("Example 1: Basic Validation with Rules")
    print("=" * 60)
    
    # Initialize validation engine with config file
    engine = ValidationEngine(config_file='config/validation_rules.json')
    
    print(f"\nLoaded {len(engine.rules)} validation rules:")
    for rule in engine.rules:
        print(f"  - {rule.name} ({rule.severity.name})")
    
    # Create a test message with low battery
    msg = ParsedMessage(
        timestamp=time.time(),
        msg_type="SYS_STATUS",
        msg_id=1,
        system_id=1,
        component_id=1,
        sequence=0,
        fields={
            "voltage_battery": 10200,  # Below warning threshold
            "current_battery": -1000,
            "battery_remaining": 15
        },
        rssi=-75.0,
        snr=8.0
    )
    
    # Validate the message
    violations = engine.validate_message(msg)
    
    print(f"\nValidation Results:")
    if violations:
        print(f"  Found {len(violations)} violation(s):")
        for v in violations:
            print(f"    - {v.rule_name} ({v.severity.name})")
            print(f"      {v.description}")
            print(f"      Actual: {v.actual_value}, Threshold: {v.threshold}")
    else:
        print("  No violations detected")
    
    # Get statistics
    stats = engine.get_stats()
    print(f"\nStatistics:")
    print(f"  Total checks: {stats['total_checks']}")
    print(f"  Total violations: {stats['total_violations']}")
    print(f"  Violations by severity:")
    for severity, count in stats['violations_by_severity'].items():
        print(f"    {severity.name}: {count}")


def example_gps_altitude_jump():
    """Example: GPS altitude jump detection."""
    print("\n" + "=" * 60)
    print("Example 2: GPS Altitude Jump Detection")
    print("=" * 60)
    
    engine = ValidationEngine(config_file='config/validation_rules.json')
    
    # First GPS reading at 100m altitude
    msg1 = ParsedMessage(
        timestamp=1000.0,
        msg_type="GPS_RAW_INT",
        msg_id=24,
        system_id=1,
        component_id=1,
        sequence=10,
        fields={
            "lat": 473977420,  # 47.3977420 degrees
            "lon": 85234560,   # 8.5234560 degrees
            "alt": 100000,     # 100m in millimeters
            "fix_type": 3,
            "satellites_visible": 12
        },
        rssi=-70.0,
        snr=10.0
    )
    
    violations1 = engine.validate_message(msg1)
    print(f"\nFirst GPS reading: 100m altitude")
    print(f"  Violations: {len(violations1)}")
    
    # Second GPS reading 1 second later at 160m (60m jump)
    msg2 = ParsedMessage(
        timestamp=1001.0,
        msg_type="GPS_RAW_INT",
        msg_id=24,
        system_id=1,
        component_id=1,
        sequence=11,
        fields={
            "lat": 473977420,
            "lon": 85234560,
            "alt": 160000,     # 160m in millimeters (60m jump!)
            "fix_type": 3,
            "satellites_visible": 12
        },
        rssi=-70.0,
        snr=10.0
    )
    
    violations2 = engine.validate_message(msg2)
    print(f"\nSecond GPS reading: 160m altitude (1 second later)")
    print(f"  Violations: {len(violations2)}")
    
    if violations2:
        for v in violations2:
            print(f"  ⚠ {v.rule_name}: {v.description}")
    
    # Third GPS reading with normal change
    msg3 = ParsedMessage(
        timestamp=1002.0,
        msg_type="GPS_RAW_INT",
        msg_id=24,
        system_id=1,
        component_id=1,
        sequence=12,
        fields={
            "lat": 473977420,
            "lon": 85234560,
            "alt": 165000,     # 165m (5m change - normal)
            "fix_type": 3,
            "satellites_visible": 12
        },
        rssi=-70.0,
        snr=10.0
    )
    
    violations3 = engine.validate_message(msg3)
    print(f"\nThird GPS reading: 165m altitude (1 second later)")
    print(f"  Violations: {len(violations3)} (normal altitude change)")


def example_packet_loss():
    """Example: Packet loss detection."""
    print("\n" + "=" * 60)
    print("Example 3: Packet Loss Detection")
    print("=" * 60)
    
    engine = ValidationEngine(config_file='config/validation_rules.json')
    
    # First HEARTBEAT with sequence 10
    msg1 = ParsedMessage(
        timestamp=1000.0,
        msg_type="HEARTBEAT",
        msg_id=0,
        system_id=1,
        component_id=1,
        sequence=10,
        fields={
            "type": 2,        # MAV_TYPE_QUADROTOR
            "autopilot": 3,   # MAV_AUTOPILOT_ARDUPILOTMEGA
            "base_mode": 81,
            "custom_mode": 0,
            "system_status": 4,
            "mavlink_version": 3
        },
        rssi=-65.0,
        snr=12.0
    )
    
    violations1 = engine.validate_message(msg1)
    print(f"\nFirst HEARTBEAT (seq=10)")
    print(f"  Violations: {len(violations1)}")
    
    # Second HEARTBEAT with sequence 11 (no loss)
    msg2 = ParsedMessage(
        timestamp=1001.0,
        msg_type="HEARTBEAT",
        msg_id=0,
        system_id=1,
        component_id=1,
        sequence=11,
        fields={
            "type": 2,
            "autopilot": 3,
            "base_mode": 81,
            "custom_mode": 0,
            "system_status": 4,
            "mavlink_version": 3
        },
        rssi=-65.0,
        snr=12.0
    )
    
    violations2 = engine.validate_message(msg2)
    print(f"\nSecond HEARTBEAT (seq=11)")
    print(f"  Violations: {len(violations2)} (no packet loss)")
    
    # Third HEARTBEAT with sequence 15 (lost 3 packets: 12, 13, 14)
    msg3 = ParsedMessage(
        timestamp=1002.0,
        msg_type="HEARTBEAT",
        msg_id=0,
        system_id=1,
        component_id=1,
        sequence=15,
        fields={
            "type": 2,
            "autopilot": 3,
            "base_mode": 81,
            "custom_mode": 0,
            "system_status": 4,
            "mavlink_version": 3
        },
        rssi=-65.0,
        snr=12.0
    )
    
    violations3 = engine.validate_message(msg3)
    print(f"\nThird HEARTBEAT (seq=15)")
    print(f"  Violations: {len(violations3)}")
    
    if violations3:
        for v in violations3:
            print(f"  ⚠ {v.rule_name}: {v.description}")


def example_violation_filtering():
    """Example: Filtering violations."""
    print("\n" + "=" * 60)
    print("Example 4: Violation Filtering")
    print("=" * 60)
    
    engine = ValidationEngine(config_file='config/validation_rules.json')
    
    # Create multiple violations with different severities and systems
    messages = [
        ParsedMessage(
            timestamp=1000.0,
            msg_type="SYS_STATUS",
            msg_id=1,
            system_id=1,
            component_id=1,
            sequence=0,
            fields={"voltage_battery": 10200},  # WARNING
            rssi=-70.0,
            snr=10.0
        ),
        ParsedMessage(
            timestamp=1001.0,
            msg_type="SYS_STATUS",
            msg_id=1,
            system_id=1,
            component_id=1,
            sequence=1,
            fields={"voltage_battery": 9800},   # CRITICAL
            rssi=-70.0,
            snr=10.0
        ),
        ParsedMessage(
            timestamp=1002.0,
            msg_type="SYS_STATUS",
            msg_id=1,
            system_id=2,
            component_id=1,
            sequence=0,
            fields={"voltage_battery": 10300},  # WARNING
            rssi=-75.0,
            snr=8.0
        ),
    ]
    
    # Validate all messages
    for msg in messages:
        engine.validate_message(msg)
    
    # Get all violations
    all_violations = engine.get_violations()
    print(f"\nTotal violations: {len(all_violations)}")
    
    # Filter by severity
    warnings = engine.get_violations(severity=Severity.WARNING)
    critical = engine.get_violations(severity=Severity.CRITICAL)
    print(f"\nBy severity:")
    print(f"  WARNING: {len(warnings)}")
    print(f"  CRITICAL: {len(critical)}")
    
    # Filter by system_id
    system1 = engine.get_violations(system_id=1)
    system2 = engine.get_violations(system_id=2)
    print(f"\nBy system:")
    print(f"  System 1: {len(system1)}")
    print(f"  System 2: {len(system2)}")
    
    # Filter by time
    recent = engine.get_violations(since=1001.0)
    print(f"\nSince timestamp 1001.0: {len(recent)}")


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("ValidationEngine Usage Examples")
    print("=" * 60)
    
    try:
        example_basic_validation()
        example_gps_altitude_jump()
        example_packet_loss()
        example_violation_filtering()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
