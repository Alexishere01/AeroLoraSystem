"""
Validation Engine Module

This module provides telemetry validation capabilities with configurable rules,
violation tracking, GPS altitude jump detection, and packet loss detection.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, List, Dict
import json
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Severity(Enum):
    """Severity levels for validation violations."""
    INFO = 1
    WARNING = 2
    CRITICAL = 3


class Operator(Enum):
    """Comparison operators for validation rules."""
    LT = '<'
    GT = '>'
    EQ = '=='
    NE = '!='
    LTE = '<='
    GTE = '>='


@dataclass
class ValidationRule:
    """
    Validation rule definition.
    
    Attributes:
        name: Human-readable rule name
        msg_type: MAVLink message type to validate (e.g., 'HEARTBEAT', 'GPS_RAW_INT')
        field: Field name within the message to check
        operator: Comparison operator to apply
        threshold: Threshold value for comparison
        severity: Severity level if rule is violated
        description: Human-readable description of the rule
    """
    name: str
    msg_type: str
    field: str
    operator: Operator
    threshold: Any
    severity: Severity
    description: str = ""


@dataclass
class Violation:
    """
    Record of a validation rule violation.
    
    Attributes:
        timestamp: Unix timestamp when violation occurred
        rule_name: Name of the violated rule
        msg_type: MAVLink message type
        field: Field name that violated the rule
        actual_value: Actual value that caused the violation
        threshold: Expected threshold value
        severity: Severity level of the violation
        description: Human-readable description
        system_id: System ID of the source (optional)
    """
    timestamp: float
    rule_name: str
    msg_type: str
    field: str
    actual_value: Any
    threshold: Any
    severity: Severity
    description: str = ""
    system_id: Optional[int] = None


class ValidationEngine:
    """
    Telemetry validation engine with configurable rules.
    
    This engine validates MAVLink messages against configured rules,
    tracks violations, detects GPS altitude jumps, and monitors packet loss.
    """
    
    def __init__(self, config_file: str = 'config/validation_rules.json'):
        """
        Initialize the validation engine.
        
        Args:
            config_file: Path to JSON configuration file with validation rules
        """
        self.config_file = config_file
        self.rules: List[ValidationRule] = []
        self.violations: List[Violation] = []
        
        # Statistics tracking
        self.stats = {
            'total_checks': 0,
            'total_violations': 0,
            'violations_by_severity': {
                Severity.INFO: 0,
                Severity.WARNING: 0,
                Severity.CRITICAL: 0
            },
            'violations_by_rule': {}
        }
        
        # GPS altitude tracking for jump detection (per system_id)
        self.gps_altitude_history: Dict[int, List[tuple]] = {}  # system_id -> [(timestamp, altitude)]
        
        # Sequence number tracking for packet loss detection (per system_id)
        self.sequence_numbers: Dict[int, int] = {}  # system_id -> last_sequence
        
        # Load validation rules
        self.load_rules()
        
        logger.info(f"Validation engine initialized with {len(self.rules)} rules")
    
    def load_rules(self):
        """
        Load validation rules from JSON configuration file.
        
        Validates rule structure and converts string operators/severity to enums.
        Invalid rules are logged and skipped gracefully.
        """
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            self.rules = []
            rules_data = config.get('rules', [])
            
            for idx, rule_data in enumerate(rules_data):
                try:
                    # Validate required fields
                    required_fields = ['name', 'msg_type', 'field', 'operator', 'threshold', 'severity']
                    for req_field in required_fields:
                        if req_field not in rule_data:
                            raise ValueError(f"Missing required field: {req_field}")
                    
                    # Convert operator string to enum
                    operator_str = rule_data['operator']
                    operator = None
                    for op in Operator:
                        if op.value == operator_str:
                            operator = op
                            break
                    
                    if operator is None:
                        raise ValueError(f"Invalid operator: {operator_str}")
                    
                    # Convert severity string to enum
                    severity_str = rule_data['severity'].upper()
                    try:
                        severity = Severity[severity_str]
                    except KeyError:
                        raise ValueError(f"Invalid severity: {severity_str}")
                    
                    # Create validation rule
                    rule = ValidationRule(
                        name=rule_data['name'],
                        msg_type=rule_data['msg_type'],
                        field=rule_data['field'],
                        operator=operator,
                        threshold=rule_data['threshold'],
                        severity=severity,
                        description=rule_data.get('description', '')
                    )
                    
                    self.rules.append(rule)
                    
                    # Initialize violation counter for this rule
                    self.stats['violations_by_rule'][rule.name] = 0
                    
                    logger.debug(f"Loaded rule: {rule.name}")
                    
                except Exception as e:
                    logger.error(f"Error loading rule {idx}: {e}")
                    continue
            
            logger.info(f"Successfully loaded {len(self.rules)} validation rules")
            
        except FileNotFoundError:
            logger.warning(f"Configuration file not found: {self.config_file}")
            logger.info("Running with no validation rules")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
        except Exception as e:
            logger.error(f"Error loading validation rules: {e}")
    
    def reload_rules(self):
        """
        Reload validation rules from configuration file.
        
        Allows runtime configuration updates without restarting the system.
        """
        logger.info("Reloading validation rules...")
        old_count = len(self.rules)
        self.load_rules()
        new_count = len(self.rules)
        logger.info(f"Rules reloaded: {old_count} -> {new_count}")
    
    def validate_message(self, msg) -> List[Violation]:
        """
        Validate a message against all applicable rules.
        
        Args:
            msg: ParsedMessage object from MAVLink parser
            
        Returns:
            List of Violation objects for any rules that were violated
        """
        violations = []
        
        # Check standard validation rules
        for rule in self.rules:
            # Skip rules that don't apply to this message type
            if rule.msg_type != msg.msg_type:
                continue
            
            # Skip if field doesn't exist in message
            if rule.field not in msg.fields:
                continue
            
            self.stats['total_checks'] += 1
            
            # Get field value
            actual_value = msg.fields[rule.field]
            
            # Check if rule is violated
            violated = self._check_rule(actual_value, rule.operator, rule.threshold)
            
            if violated:
                violation = Violation(
                    timestamp=msg.timestamp,
                    rule_name=rule.name,
                    msg_type=msg.msg_type,
                    field=rule.field,
                    actual_value=actual_value,
                    threshold=rule.threshold,
                    severity=rule.severity,
                    description=rule.description,
                    system_id=msg.system_id
                )
                
                violations.append(violation)
                self.violations.append(violation)
                
                # Update statistics
                self.stats['total_violations'] += 1
                self.stats['violations_by_severity'][rule.severity] += 1
                self.stats['violations_by_rule'][rule.name] += 1
                
                logger.warning(
                    f"Violation: {rule.name} - {rule.field}={actual_value} "
                    f"(threshold: {rule.operator.value} {rule.threshold})"
                )
        
        # Check for GPS altitude jumps
        if msg.msg_type == 'GPS_RAW_INT':
            gps_violation = self._check_gps_altitude_jump(msg)
            if gps_violation:
                violations.append(gps_violation)
        
        # Check for packet loss
        if msg.msg_type == 'HEARTBEAT':
            loss_violation = self._check_packet_loss(msg)
            if loss_violation:
                violations.append(loss_violation)
        
        return violations
    
    def _check_rule(self, value: Any, operator: Operator, threshold: Any) -> bool:
        """
        Check if a value violates a rule based on operator and threshold.
        
        Args:
            value: Actual value from message
            operator: Comparison operator
            threshold: Threshold value to compare against
            
        Returns:
            True if rule is violated, False otherwise
        """
        try:
            if operator == Operator.LT:
                return value < threshold
            elif operator == Operator.GT:
                return value > threshold
            elif operator == Operator.EQ:
                return value == threshold
            elif operator == Operator.NE:
                return value != threshold
            elif operator == Operator.LTE:
                return value <= threshold
            elif operator == Operator.GTE:
                return value >= threshold
        except Exception as e:
            logger.debug(f"Error comparing {value} {operator.value} {threshold}: {e}")
            return False
        
        return False
    
    def _check_gps_altitude_jump(self, msg) -> Optional[Violation]:
        """
        Check for GPS altitude jumps (>50m in 1 second).
        
        Args:
            msg: ParsedMessage with GPS_RAW_INT data
            
        Returns:
            Violation object if altitude jump detected, None otherwise
        """
        system_id = msg.system_id
        
        # Get altitude from message (in millimeters, convert to meters)
        if 'alt' not in msg.fields:
            return None
        
        current_alt = msg.fields['alt'] / 1000.0  # Convert mm to meters
        current_time = msg.timestamp
        
        # Initialize history for this system if needed
        if system_id not in self.gps_altitude_history:
            self.gps_altitude_history[system_id] = []
        
        history = self.gps_altitude_history[system_id]
        
        # Check against previous altitude
        if history:
            prev_time, prev_alt = history[-1]
            time_diff = current_time - prev_time
            
            # Only check if time difference is reasonable (between 0.1s and 2s)
            if 0.1 <= time_diff <= 2.0:
                alt_change = abs(current_alt - prev_alt)
                rate = alt_change / time_diff
                
                # Flag if altitude changed >50m in 1 second
                if rate > 50.0:
                    violation = Violation(
                        timestamp=current_time,
                        rule_name="GPS Altitude Jump",
                        msg_type="GPS_RAW_INT",
                        field="alt",
                        actual_value=alt_change,
                        threshold=50.0,
                        severity=Severity.WARNING,
                        description=f"GPS altitude changed {alt_change:.1f}m in {time_diff:.2f}s (rate: {rate:.1f}m/s)",
                        system_id=system_id
                    )
                    
                    self.violations.append(violation)
                    self.stats['total_violations'] += 1
                    self.stats['violations_by_severity'][Severity.WARNING] += 1
                    
                    logger.warning(
                        f"GPS altitude jump detected for system {system_id}: "
                        f"{alt_change:.1f}m in {time_diff:.2f}s"
                    )
                    
                    # Update history and return violation
                    history.append((current_time, current_alt))
                    
                    # Keep only last 10 readings per system
                    if len(history) > 10:
                        history.pop(0)
                    
                    return violation
        
        # Add current reading to history
        history.append((current_time, current_alt))
        
        # Keep only last 10 readings per system
        if len(history) > 10:
            history.pop(0)
        
        return None
    
    def _check_packet_loss(self, msg) -> Optional[Violation]:
        """
        Check for packet loss by detecting gaps in MAVLink sequence numbers.
        
        This method tracks the MAVLink packet sequence number (from the packet header)
        for each system ID. Sequence numbers increment from 0-255 and wrap around.
        Any gap in the sequence indicates lost packets.
        
        Args:
            msg: ParsedMessage with sequence number from MAVLink packet header
            
        Returns:
            Violation object if packet loss detected, None otherwise
        """
        system_id = msg.system_id
        sequence = msg.sequence
        
        # Initialize tracking for this system
        if system_id not in self.sequence_numbers:
            self.sequence_numbers[system_id] = sequence
            return None
        
        # Check for sequence gap
        last_seq = self.sequence_numbers[system_id]
        expected_seq = (last_seq + 1) % 256  # MAVLink sequence wraps at 256
        
        # Calculate gap (handling wrap-around)
        if sequence >= expected_seq:
            gap = sequence - expected_seq
        else:
            # Wrap-around case
            gap = (256 - expected_seq) + sequence
        
        # If there's a gap, we lost packets
        if gap > 0 and gap < 200:  # Ignore large gaps (likely system restart)
            violation = Violation(
                timestamp=msg.timestamp,
                rule_name="Packet Loss",
                msg_type="HEARTBEAT",
                field="sequence",
                actual_value=sequence,
                threshold=expected_seq,
                severity=Severity.WARNING,
                description=f"Lost {gap} packet(s) - expected seq {expected_seq}, got {sequence}",
                system_id=system_id
            )
            
            self.violations.append(violation)
            self.stats['total_violations'] += 1
            self.stats['violations_by_severity'][Severity.WARNING] += 1
            
            logger.warning(
                f"Packet loss detected for system {system_id}: "
                f"lost {gap} packet(s) (seq {last_seq} -> {sequence})"
            )
            
            # Update sequence number
            self.sequence_numbers[system_id] = sequence
            
            return violation
        
        # Update sequence number
        self.sequence_numbers[system_id] = sequence
        
        return None
    
    def get_violations(self, severity: Optional[Severity] = None, 
                      system_id: Optional[int] = None,
                      since: Optional[float] = None) -> List[Violation]:
        """
        Get violations with optional filtering.
        
        Args:
            severity: Filter by severity level (optional)
            system_id: Filter by system ID (optional)
            since: Filter by timestamp - only violations after this time (optional)
            
        Returns:
            List of Violation objects matching the filters
        """
        filtered = self.violations
        
        if severity is not None:
            filtered = [v for v in filtered if v.severity == severity]
        
        if system_id is not None:
            filtered = [v for v in filtered if v.system_id == system_id]
        
        if since is not None:
            filtered = [v for v in filtered if v.timestamp >= since]
        
        return filtered
    
    def get_stats(self) -> dict:
        """
        Get validation statistics.
        
        Returns:
            Dictionary containing validation statistics
        """
        return self.stats.copy()
    
    def clear_violations(self):
        """Clear all recorded violations."""
        self.violations = []
        logger.info("Violations cleared")
    
    def reset_stats(self):
        """Reset all statistics counters."""
        self.stats = {
            'total_checks': 0,
            'total_violations': 0,
            'violations_by_severity': {
                Severity.INFO: 0,
                Severity.WARNING: 0,
                Severity.CRITICAL: 0
            },
            'violations_by_rule': {rule.name: 0 for rule in self.rules}
        }
        logger.info("Statistics reset")
