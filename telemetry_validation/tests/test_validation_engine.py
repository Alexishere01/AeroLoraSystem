"""
Unit tests for ValidationEngine module.

Tests validation rule loading, rule evaluation, GPS altitude jump detection,
and packet loss detection.
"""

import unittest
import json
import tempfile
import os
from pathlib import Path
import sys

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from validation_engine import (
    ValidationEngine, ValidationRule, Violation, Severity, Operator
)
from mavlink_parser import ParsedMessage


class TestValidationEngine(unittest.TestCase):
    """Test cases for ValidationEngine class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary config file
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, 'test_rules.json')
        
        # Create test validation rules
        test_rules = {
            "rules": [
                {
                    "name": "Low Battery",
                    "msg_type": "SYS_STATUS",
                    "field": "voltage_battery",
                    "operator": "<",
                    "threshold": 10500,
                    "severity": "WARNING",
                    "description": "Battery voltage below 10.5V"
                },
                {
                    "name": "High Temperature",
                    "msg_type": "SYS_STATUS",
                    "field": "temperature",
                    "operator": ">",
                    "threshold": 60,
                    "severity": "CRITICAL",
                    "description": "Temperature above 60C"
                }
            ]
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(test_rules, f)
        
        # Create validation engine
        self.engine = ValidationEngine(config_file=self.config_file)
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Remove temporary files
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
        os.rmdir(self.temp_dir)
    
    def test_load_rules(self):
        """Test loading validation rules from JSON config."""
        self.assertEqual(len(self.engine.rules), 2)
        self.assertEqual(self.engine.rules[0].name, "Low Battery")
        self.assertEqual(self.engine.rules[0].operator, Operator.LT)
        self.assertEqual(self.engine.rules[0].severity, Severity.WARNING)
    
    def test_validate_message_no_violation(self):
        """Test validation with no violations."""
        msg = ParsedMessage(
            timestamp=1234567890.0,
            msg_type="SYS_STATUS",
            msg_id=1,
            system_id=1,
            component_id=1,
            sequence=0,
            fields={"voltage_battery": 11000, "temperature": 45},
            rssi=-50.0,
            snr=10.0
        )
        
        violations = self.engine.validate_message(msg)
        self.assertEqual(len(violations), 0)
    
    def test_validate_message_with_violation(self):
        """Test validation with violations."""
        msg = ParsedMessage(
            timestamp=1234567890.0,
            msg_type="SYS_STATUS",
            msg_id=1,
            system_id=1,
            component_id=1,
            sequence=0,
            fields={"voltage_battery": 10000, "temperature": 70},
            rssi=-50.0,
            snr=10.0
        )
        
        violations = self.engine.validate_message(msg)
        self.assertEqual(len(violations), 2)
        
        # Check low battery violation
        battery_violation = next(v for v in violations if v.rule_name == "Low Battery")
        self.assertEqual(battery_violation.severity, Severity.WARNING)
        self.assertEqual(battery_violation.actual_value, 10000)
        
        # Check high temperature violation
        temp_violation = next(v for v in violations if v.rule_name == "High Temperature")
        self.assertEqual(temp_violation.severity, Severity.CRITICAL)
        self.assertEqual(temp_violation.actual_value, 70)
    
    def test_gps_altitude_jump_detection(self):
        """Test GPS altitude jump detection."""
        # First GPS message
        msg1 = ParsedMessage(
            timestamp=1000.0,
            msg_type="GPS_RAW_INT",
            msg_id=24,
            system_id=1,
            component_id=1,
            sequence=0,
            fields={"alt": 100000},  # 100m in mm
            rssi=-50.0,
            snr=10.0
        )
        
        violations1 = self.engine.validate_message(msg1)
        self.assertEqual(len(violations1), 0)  # No violation on first message
        
        # Second GPS message with large altitude jump
        msg2 = ParsedMessage(
            timestamp=1001.0,  # 1 second later
            msg_type="GPS_RAW_INT",
            msg_id=24,
            system_id=1,
            component_id=1,
            sequence=1,
            fields={"alt": 160000},  # 160m in mm (60m jump)
            rssi=-50.0,
            snr=10.0
        )
        
        violations2 = self.engine.validate_message(msg2)
        self.assertEqual(len(violations2), 1)
        self.assertEqual(violations2[0].rule_name, "GPS Altitude Jump")
        self.assertEqual(violations2[0].severity, Severity.WARNING)
    
    def test_packet_loss_detection(self):
        """Test packet loss detection."""
        # First HEARTBEAT
        msg1 = ParsedMessage(
            timestamp=1000.0,
            msg_type="HEARTBEAT",
            msg_id=0,
            system_id=1,
            component_id=1,
            sequence=10,
            fields={"type": 1, "autopilot": 3},
            rssi=-50.0,
            snr=10.0
        )
        
        violations1 = self.engine.validate_message(msg1)
        self.assertEqual(len(violations1), 0)  # No violation on first message
        
        # Second HEARTBEAT with gap in sequence
        msg2 = ParsedMessage(
            timestamp=1001.0,
            msg_type="HEARTBEAT",
            msg_id=0,
            system_id=1,
            component_id=1,
            sequence=15,  # Gap of 4 packets (11, 12, 13, 14 missing)
            fields={"type": 1, "autopilot": 3},
            rssi=-50.0,
            snr=10.0
        )
        
        violations2 = self.engine.validate_message(msg2)
        self.assertEqual(len(violations2), 1)
        self.assertEqual(violations2[0].rule_name, "Packet Loss")
        self.assertEqual(violations2[0].severity, Severity.WARNING)
        self.assertIn("Lost 4 packet(s)", violations2[0].description)
    
    def test_get_violations_filtering(self):
        """Test violation filtering."""
        # Create violations with different severities
        msg1 = ParsedMessage(
            timestamp=1000.0,
            msg_type="SYS_STATUS",
            msg_id=1,
            system_id=1,
            component_id=1,
            sequence=0,
            fields={"voltage_battery": 10000},  # WARNING
            rssi=-50.0,
            snr=10.0
        )
        
        msg2 = ParsedMessage(
            timestamp=1001.0,
            msg_type="SYS_STATUS",
            msg_id=1,
            system_id=2,
            component_id=1,
            sequence=0,
            fields={"temperature": 70},  # CRITICAL
            rssi=-50.0,
            snr=10.0
        )
        
        self.engine.validate_message(msg1)
        self.engine.validate_message(msg2)
        
        # Filter by severity
        warnings = self.engine.get_violations(severity=Severity.WARNING)
        self.assertEqual(len(warnings), 1)
        
        critical = self.engine.get_violations(severity=Severity.CRITICAL)
        self.assertEqual(len(critical), 1)
        
        # Filter by system_id
        system1_violations = self.engine.get_violations(system_id=1)
        self.assertEqual(len(system1_violations), 1)
        
        system2_violations = self.engine.get_violations(system_id=2)
        self.assertEqual(len(system2_violations), 1)


if __name__ == '__main__':
    unittest.main()
