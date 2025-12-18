"""
Alert Manager Module

This module provides alert management capabilities with console output, email alerts,
filtering, and throttling to prevent alert spam.
"""

from enum import Enum
from typing import Dict, List, Optional, Set
import smtplib
from email.mime.text import MIMEText
import logging
import time
from collections import defaultdict
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AlertChannel(Enum):
    """Alert delivery channels."""
    CONSOLE = 1
    EMAIL = 2
    SMS = 3


# Import Severity from validation_engine to ensure consistency
try:
    from .validation_engine import Severity
except ImportError:
    # Fallback if import fails
    class Severity(Enum):
        """Severity levels for alerts."""
        INFO = 1
        WARNING = 2
        CRITICAL = 3


@dataclass
class RelayLatencyAlert:
    """
    Alert for relay mode latency issues.
    
    This is a specialized alert type for relay mode latency that doesn't
    come from the validation engine but is generated directly by the
    alert manager when monitoring relay mode status.
    
    Requirements: 9.5
    """
    timestamp: float
    system_id: int
    latency_ms: float
    threshold_ms: float
    relay_active: bool
    severity: Severity
    
    @property
    def rule_name(self) -> str:
        """Return a rule name for compatibility with alert history."""
        return "Relay Mode Latency"
    
    @property
    def msg_type(self) -> str:
        """Return message type for compatibility."""
        return "CMD_STATUS_REPORT"
    
    @property
    def field(self) -> str:
        """Return field name for compatibility."""
        return "relay_latency"
    
    @property
    def actual_value(self) -> float:
        """Return actual value for compatibility."""
        return self.latency_ms
    
    @property
    def threshold(self) -> float:
        """Return threshold for compatibility."""
        return self.threshold_ms
    
    @property
    def description(self) -> str:
        """Return description for compatibility."""
        return f"Relay mode latency exceeds {self.threshold_ms}ms threshold"


@dataclass
class BinaryProtocolErrorAlert:
    """
    Alert for binary protocol communication errors.
    
    This specialized alert type is generated when binary protocol errors
    exceed acceptable thresholds, indicating UART communication issues.
    
    Requirements: 3.2, 9.2
    """
    timestamp: float
    system_id: int
    error_type: str  # 'checksum', 'buffer_overflow', 'timeout'
    error_rate: float  # Errors per minute or count
    threshold: float
    severity: Severity
    
    @property
    def rule_name(self) -> str:
        """Return a rule name for compatibility with alert history."""
        return f"Binary Protocol {self.error_type.replace('_', ' ').title()} Error"
    
    @property
    def msg_type(self) -> str:
        """Return message type for compatibility."""
        return "BINARY_PROTOCOL"
    
    @property
    def field(self) -> str:
        """Return field name for compatibility."""
        return self.error_type
    
    @property
    def actual_value(self) -> float:
        """Return actual value for compatibility."""
        return self.error_rate
    
    @property
    def description(self) -> str:
        """Return description for compatibility."""
        if self.error_type == 'checksum':
            return f"Checksum error rate {self.error_rate:.1f}/min exceeds threshold {self.threshold}/min"
        elif self.error_type == 'buffer_overflow':
            return f"UART buffer overflow detected ({self.error_rate:.0f} events)"
        elif self.error_type == 'timeout':
            return f"Communication timeout detected ({self.error_rate:.0f} events)"
        else:
            return f"{self.error_type} error rate {self.error_rate:.1f} exceeds threshold {self.threshold}"


class AlertManager:
    """
    Alert manager with filtering and throttling capabilities.
    
    Features:
    - Console alerts with color coding
    - Email alerts for critical issues
    - Duplicate alert prevention within time window
    - High-frequency alert throttling
    - Alert history tracking
    """
    
    def __init__(self, config: Optional[dict] = None):
        """
        Initialize the alert manager.
        
        Args:
            config: Configuration dictionary with alert settings
                - channels: List of AlertChannel enums to enable
                - email: Email configuration (server, port, username, password, from, to)
                - throttle_window: Time window in seconds for throttling (default: 60)
                - duplicate_window: Time window in seconds for duplicate prevention (default: 300)
                - max_alerts_per_window: Maximum alerts per throttle window (default: 10)
        """
        self.config = config or {}
        
        # Alert history: list of (timestamp, message, severity, rule_name, system_id)
        self.alert_history: List[tuple] = []
        
        # Throttling configuration
        self.throttle_window = self.config.get('throttle_window', 60)  # 60 seconds
        self.duplicate_window = self.config.get('duplicate_window', 300)  # 5 minutes
        self.max_alerts_per_window = self.config.get('max_alerts_per_window', 10)
        
        # Tracking for duplicate prevention
        # Key: (rule_name, system_id, severity), Value: last alert timestamp
        self.last_alert_time: Dict[tuple, float] = {}
        
        # Tracking for throttling
        # Key: (rule_name, system_id), Value: list of alert timestamps in current window
        self.alert_timestamps: Dict[tuple, List[float]] = defaultdict(list)
        
        # Statistics
        self.stats = {
            'total_alerts': 0,
            'alerts_by_severity': {
                Severity.INFO: 0,
                Severity.WARNING: 0,
                Severity.CRITICAL: 0
            },
            'alerts_by_channel': {
                AlertChannel.CONSOLE: 0,
                AlertChannel.EMAIL: 0,
                AlertChannel.SMS: 0
            },
            'filtered_duplicates': 0,
            'throttled_alerts': 0,
            'relay_latency_alerts': 0,
            'binary_protocol_error_alerts': 0
        }
        
        # Relay mode tracking
        self.relay_mode_active: Dict[int, bool] = {}  # system_id -> relay_active
        self.relay_latency_threshold_ms = self.config.get('relay_latency_threshold_ms', 500.0)
        self.last_relay_status_time: Dict[int, float] = {}  # system_id -> timestamp
        
        # Binary protocol error tracking
        self.checksum_error_threshold = self.config.get('checksum_error_threshold', 50.0)  # errors per minute
        self.last_checksum_alert_time: Dict[int, float] = {}  # system_id -> timestamp
        self.last_buffer_overflow_alert_time: Dict[int, float] = {}  # system_id -> timestamp
        self.last_timeout_alert_time: Dict[int, float] = {}  # system_id -> timestamp
        
        logger.info(
            f"Alert manager initialized - "
            f"throttle_window={self.throttle_window}s, "
            f"duplicate_window={self.duplicate_window}s, "
            f"max_alerts_per_window={self.max_alerts_per_window}, "
            f"relay_latency_threshold={self.relay_latency_threshold_ms}ms, "
            f"checksum_error_threshold={self.checksum_error_threshold}/min"
        )
    
    def send_alert(self, violation) -> bool:
        """
        Send alert for a violation with filtering and throttling.
        
        Args:
            violation: Violation object from ValidationEngine
            
        Returns:
            True if alert was sent, False if filtered/throttled
        """
        current_time = time.time()
        
        # Create throttle key (without severity for broader throttling)
        throttle_key = (violation.rule_name, violation.system_id)
        
        # Check if alert should be throttled FIRST (before duplicate check)
        # This allows throttling to work even with different violation instances
        if self._should_throttle(throttle_key, current_time):
            self.stats['throttled_alerts'] += 1
            logger.debug(
                f"Throttled alert: {violation.rule_name} "
                f"(system {violation.system_id}) - rate limit exceeded"
            )
            return False
        
        # Create alert key for duplicate detection
        # Include field and actual_value to make duplicate detection more specific
        alert_key = (violation.rule_name, violation.system_id, violation.severity, 
                     violation.field, violation.actual_value)
        
        # Check for duplicate alerts within time window
        if self._is_duplicate(alert_key, current_time):
            self.stats['filtered_duplicates'] += 1
            logger.debug(
                f"Filtered duplicate alert: {violation.rule_name} "
                f"(system {violation.system_id})"
            )
            return False
        
        # Alert passed filters - send it
        message = self._format_alert_message(violation)
        
        # Send to configured channels
        channels = self.config.get('channels', [AlertChannel.CONSOLE])
        
        if AlertChannel.CONSOLE in channels:
            self._console_alert(message, violation.severity)
            self.stats['alerts_by_channel'][AlertChannel.CONSOLE] += 1
        
        if AlertChannel.EMAIL in channels and violation.severity == Severity.CRITICAL:
            success = self._email_alert(message, violation)
            if success:
                self.stats['alerts_by_channel'][AlertChannel.EMAIL] += 1
        
        # Record alert in history
        self.alert_history.append((
            current_time,
            message,
            violation.severity,
            violation.rule_name,
            violation.system_id
        ))
        
        # Update tracking
        self.last_alert_time[alert_key] = current_time
        self.alert_timestamps[throttle_key].append(current_time)
        
        # Update statistics
        self.stats['total_alerts'] += 1
        self.stats['alerts_by_severity'][violation.severity] += 1
        
        return True
    
    def _is_duplicate(self, alert_key: tuple, current_time: float) -> bool:
        """
        Check if alert is a duplicate within the duplicate window.
        
        Args:
            alert_key: Tuple of (rule_name, system_id, severity)
            current_time: Current timestamp
            
        Returns:
            True if this is a duplicate alert, False otherwise
        """
        if alert_key not in self.last_alert_time:
            return False
        
        last_time = self.last_alert_time[alert_key]
        time_since_last = current_time - last_time
        
        return time_since_last < self.duplicate_window
    
    def _should_throttle(self, throttle_key: tuple, current_time: float) -> bool:
        """
        Check if alert should be throttled based on rate limiting.
        
        Args:
            throttle_key: Tuple of (rule_name, system_id)
            current_time: Current timestamp
            
        Returns:
            True if alert should be throttled, False otherwise
        """
        # Get alert timestamps for this key
        timestamps = self.alert_timestamps[throttle_key]
        
        # Remove timestamps outside the throttle window
        timestamps[:] = [t for t in timestamps if current_time - t < self.throttle_window]
        
        # Check if we've exceeded the rate limit
        return len(timestamps) >= self.max_alerts_per_window
    
    def _format_alert_message(self, violation) -> str:
        """
        Format a violation into an alert message.
        
        Args:
            violation: Violation object
            
        Returns:
            Formatted alert message string
        """
        system_str = f"[System {violation.system_id}] " if violation.system_id else ""
        
        message = (
            f"[{violation.severity.name}] {system_str}{violation.rule_name}: "
            f"{violation.field} = {violation.actual_value} "
            f"(threshold: {violation.threshold})"
        )
        
        if violation.description:
            message += f" - {violation.description}"
        
        return message
    
    def _console_alert(self, message: str, severity: Severity):
        """
        Print alert to console with color coding.
        
        Args:
            message: Alert message
            severity: Severity level for color selection
        """
        colors = {
            Severity.INFO: '\033[94m',      # Blue
            Severity.WARNING: '\033[93m',   # Yellow
            Severity.CRITICAL: '\033[91m'   # Red
        }
        reset = '\033[0m'
        
        color = colors.get(severity, reset)
        print(f"{color}⚠ ALERT: {message}{reset}")
    
    def _email_alert(self, message: str, violation) -> bool:
        """
        Send email alert.
        
        Args:
            message: Alert message
            violation: Violation object for additional context
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            smtp_config = self.config.get('email', {})
            
            # Validate email configuration
            required_fields = ['server', 'port', 'from', 'to']
            for field in required_fields:
                if field not in smtp_config:
                    logger.warning(f"Email configuration missing field: {field}")
                    return False
            
            # Create email message
            subject = f"[{violation.severity.name}] Telemetry Alert: {violation.rule_name}"
            
            body = f"""
Telemetry Alert
===============

Severity: {violation.severity.name}
Rule: {violation.rule_name}
System ID: {violation.system_id}
Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(violation.timestamp))}

Message Type: {violation.msg_type}
Field: {violation.field}
Actual Value: {violation.actual_value}
Threshold: {violation.threshold}

Description: {violation.description}

---
This is an automated alert from the Telemetry Validation System.
"""
            
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = smtp_config['from']
            msg['To'] = smtp_config['to']
            
            # Send email
            with smtplib.SMTP(smtp_config['server'], smtp_config['port']) as server:
                # Use TLS if configured
                if smtp_config.get('use_tls', True):
                    server.starttls()
                
                # Login if credentials provided
                if 'username' in smtp_config and 'password' in smtp_config:
                    server.login(smtp_config['username'], smtp_config['password'])
                
                server.send_message(msg)
            
            logger.info(f"Email alert sent: {violation.rule_name}")
            return True
            
        except Exception as e:
            logger.error(f"Email alert failed: {e}")
            return False
    
    def get_alert_history(self, 
                         severity: Optional[Severity] = None,
                         system_id: Optional[int] = None,
                         since: Optional[float] = None,
                         limit: Optional[int] = None) -> List[tuple]:
        """
        Get alert history with optional filtering.
        
        Args:
            severity: Filter by severity level
            system_id: Filter by system ID
            since: Only return alerts after this timestamp
            limit: Maximum number of alerts to return (most recent)
            
        Returns:
            List of alert tuples (timestamp, message, severity, rule_name, system_id)
        """
        filtered = self.alert_history
        
        if severity is not None:
            filtered = [a for a in filtered if a[2] == severity]
        
        if system_id is not None:
            filtered = [a for a in filtered if a[4] == system_id]
        
        if since is not None:
            filtered = [a for a in filtered if a[0] >= since]
        
        # Sort by timestamp (most recent first)
        filtered = sorted(filtered, key=lambda x: x[0], reverse=True)
        
        if limit is not None:
            filtered = filtered[:limit]
        
        return filtered
    
    def get_stats(self) -> dict:
        """
        Get alert statistics.
        
        Returns:
            Dictionary containing alert statistics
        """
        return self.stats.copy()
    
    def clear_history(self):
        """Clear alert history."""
        self.alert_history = []
        logger.info("Alert history cleared")
    
    def reset_stats(self):
        """Reset alert statistics."""
        self.stats = {
            'total_alerts': 0,
            'alerts_by_severity': {
                Severity.INFO: 0,
                Severity.WARNING: 0,
                Severity.CRITICAL: 0
            },
            'alerts_by_channel': {
                AlertChannel.CONSOLE: 0,
                AlertChannel.EMAIL: 0,
                AlertChannel.SMS: 0
            },
            'filtered_duplicates': 0,
            'throttled_alerts': 0,
            'relay_latency_alerts': 0,
            'binary_protocol_error_alerts': 0
        }
        logger.info("Alert statistics reset")
    
    def check_relay_latency(self, status_payload, system_id: int, current_time: Optional[float] = None) -> bool:
        """
        Check relay mode status and generate alerts for excessive latency.
        
        This method monitors CMD_STATUS_REPORT packets to detect relay mode
        and calculate relay latency. If relay mode is active and latency
        exceeds the configured threshold, an alert is generated.
        
        Args:
            status_payload: StatusPayload from CMD_STATUS_REPORT
            system_id: System ID of the reporting node
            current_time: Current timestamp (defaults to time.time())
            
        Returns:
            True if alert was generated, False otherwise
            
        Requirements: 9.5
        """
        if current_time is None:
            current_time = time.time()
        
        # Extract relay mode status
        relay_active = status_payload.relay_active
        
        # Update relay mode tracking
        was_active = self.relay_mode_active.get(system_id, False)
        self.relay_mode_active[system_id] = relay_active
        
        # Log mode transitions
        if relay_active != was_active:
            mode_str = "ACTIVE" if relay_active else "INACTIVE"
            logger.info(f"System {system_id} relay mode changed to {mode_str}")
        
        # Only check latency if relay mode is active
        if not relay_active:
            self.last_relay_status_time[system_id] = current_time
            return False
        
        # Use last_activity_sec from status payload as relay latency metric
        # This represents time since last relay activity in seconds
        latency_ms = status_payload.last_activity_sec * 1000.0
        
        # Check if latency exceeds threshold
        if latency_ms > self.relay_latency_threshold_ms:
            # Create relay latency alert
            alert = RelayLatencyAlert(
                timestamp=current_time,
                system_id=system_id,
                latency_ms=latency_ms,
                threshold_ms=self.relay_latency_threshold_ms,
                relay_active=relay_active,
                severity=Severity.WARNING
            )
            
            # Send the alert (reuse existing alert infrastructure)
            success = self.send_alert(alert)
            
            if success:
                self.stats['relay_latency_alerts'] += 1
                logger.warning(
                    f"Relay latency alert for system {system_id}: "
                    f"{latency_ms:.1f}ms exceeds threshold {self.relay_latency_threshold_ms}ms"
                )
            
            self.last_relay_status_time[system_id] = current_time
            return success
        
        # Update last status time
        self.last_relay_status_time[system_id] = current_time
        return False
    
    def get_relay_mode_status(self, system_id: Optional[int] = None) -> Dict[int, bool]:
        """
        Get current relay mode status for all systems or a specific system.
        
        Args:
            system_id: Optional system ID to query (None returns all)
            
        Returns:
            Dictionary of system_id -> relay_active status
            
        Requirements: 9.5
        """
        if system_id is not None:
            return {system_id: self.relay_mode_active.get(system_id, False)}
        return self.relay_mode_active.copy()
    
    def check_binary_protocol_errors(self, metrics, system_id: int = 0, current_time: Optional[float] = None) -> List[bool]:
        """
        Check binary protocol error rates and generate alerts if thresholds exceeded.
        
        This method monitors checksum errors, buffer overflows, and communication
        timeouts from the binary protocol parser. Alerts are generated when error
        rates exceed configured thresholds.
        
        Args:
            metrics: TelemetryMetrics object with binary protocol health data
            system_id: System ID for tracking (default: 0 for system-wide)
            current_time: Current timestamp (defaults to time.time())
            
        Returns:
            List of booleans indicating which alerts were generated
            [checksum_alert, buffer_overflow_alert, timeout_alert]
            
        Requirements: 3.2, 9.2
        """
        if current_time is None:
            current_time = time.time()
        
        alerts_generated = []
        
        # Check checksum error rate (errors per minute)
        checksum_alert = self._check_checksum_error_rate(
            metrics.checksum_error_rate,
            system_id,
            current_time
        )
        alerts_generated.append(checksum_alert)
        
        # Check for buffer overflow (from parser stats if available)
        # Note: This would need to be passed in metrics or separately
        # For now, we'll check if it's available in the metrics object
        buffer_overflow_alert = False
        if hasattr(metrics, 'buffer_overflow_count'):
            buffer_overflow_alert = self._check_buffer_overflow(
                metrics.buffer_overflow_count,
                system_id,
                current_time
            )
        alerts_generated.append(buffer_overflow_alert)
        
        # Check for communication timeout
        timeout_alert = False
        if hasattr(metrics, 'timeout_error_count'):
            timeout_alert = self._check_communication_timeout(
                metrics.timeout_error_count,
                system_id,
                current_time
            )
        alerts_generated.append(timeout_alert)
        
        return alerts_generated
    
    def _check_checksum_error_rate(self, error_rate: float, system_id: int, current_time: float) -> bool:
        """
        Check if checksum error rate exceeds threshold and generate alert.
        
        Args:
            error_rate: Checksum errors per minute
            system_id: System ID
            current_time: Current timestamp
            
        Returns:
            True if alert was generated, False otherwise
            
        Requirements: 3.2, 9.2
        """
        # Check if error rate exceeds threshold
        if error_rate <= self.checksum_error_threshold:
            return False
        
        # Check if we recently alerted for this system
        if system_id in self.last_checksum_alert_time:
            time_since_last = current_time - self.last_checksum_alert_time[system_id]
            # Don't alert more than once per minute for checksum errors
            if time_since_last < 60.0:
                return False
        
        # Create alert
        alert = BinaryProtocolErrorAlert(
            timestamp=current_time,
            system_id=system_id,
            error_type='checksum',
            error_rate=error_rate,
            threshold=self.checksum_error_threshold,
            severity=Severity.WARNING
        )
        
        # Send the alert
        success = self.send_alert(alert)
        
        if success:
            self.stats['binary_protocol_error_alerts'] += 1
            self.last_checksum_alert_time[system_id] = current_time
            logger.warning(
                f"Checksum error rate alert for system {system_id}: "
                f"{error_rate:.1f}/min exceeds threshold {self.checksum_error_threshold}/min"
            )
        
        return success
    
    def _check_buffer_overflow(self, overflow_count: int, system_id: int, current_time: float) -> bool:
        """
        Check for UART buffer overflow and generate alert.
        
        Args:
            overflow_count: Number of buffer overflow events
            system_id: System ID
            current_time: Current timestamp
            
        Returns:
            True if alert was generated, False otherwise
            
        Requirements: 3.2, 9.2
        """
        # Only alert if there are overflow events
        if overflow_count == 0:
            return False
        
        # Check if we recently alerted for this system
        if system_id in self.last_buffer_overflow_alert_time:
            time_since_last = current_time - self.last_buffer_overflow_alert_time[system_id]
            # Don't alert more than once per 5 minutes for buffer overflow
            if time_since_last < 300.0:
                return False
        
        # Create alert
        alert = BinaryProtocolErrorAlert(
            timestamp=current_time,
            system_id=system_id,
            error_type='buffer_overflow',
            error_rate=float(overflow_count),
            threshold=0.0,  # Any overflow is a problem
            severity=Severity.CRITICAL
        )
        
        # Send the alert
        success = self.send_alert(alert)
        
        if success:
            self.stats['binary_protocol_error_alerts'] += 1
            self.last_buffer_overflow_alert_time[system_id] = current_time
            logger.error(
                f"UART buffer overflow alert for system {system_id}: "
                f"{overflow_count} overflow events detected"
            )
        
        return success
    
    def _check_communication_timeout(self, timeout_count: int, system_id: int, current_time: float) -> bool:
        """
        Check for communication timeout and generate alert.
        
        Args:
            timeout_count: Number of timeout events
            system_id: System ID
            current_time: Current timestamp
            
        Returns:
            True if alert was generated, False otherwise
            
        Requirements: 3.2, 9.2
        """
        # Only alert if there are timeout events
        if timeout_count == 0:
            return False
        
        # Check if we recently alerted for this system
        if system_id in self.last_timeout_alert_time:
            time_since_last = current_time - self.last_timeout_alert_time[system_id]
            # Don't alert more than once per 2 minutes for timeouts
            if time_since_last < 120.0:
                return False
        
        # Create alert
        alert = BinaryProtocolErrorAlert(
            timestamp=current_time,
            system_id=system_id,
            error_type='timeout',
            error_rate=float(timeout_count),
            threshold=0.0,  # Any timeout is concerning
            severity=Severity.WARNING
        )
        
        # Send the alert
        success = self.send_alert(alert)
        
        if success:
            self.stats['binary_protocol_error_alerts'] += 1
            self.last_timeout_alert_time[system_id] = current_time
            logger.warning(
                f"Communication timeout alert for system {system_id}: "
                f"{timeout_count} timeout events detected"
            )
        
        return success
    
    def cleanup_old_tracking(self, max_age: float = 3600):
        """
        Clean up old tracking data to prevent memory growth.
        
        Args:
            max_age: Maximum age in seconds for tracking data (default: 1 hour)
        """
        current_time = time.time()
        
        # Clean up last_alert_time
        keys_to_remove = [
            key for key, timestamp in self.last_alert_time.items()
            if current_time - timestamp > max_age
        ]
        for key in keys_to_remove:
            del self.last_alert_time[key]
        
        # Clean up alert_timestamps
        for key in list(self.alert_timestamps.keys()):
            timestamps = self.alert_timestamps[key]
            timestamps[:] = [t for t in timestamps if current_time - t < max_age]
            
            # Remove empty entries
            if not timestamps:
                del self.alert_timestamps[key]
        
        # Clean up relay status tracking
        relay_keys_to_remove = [
            system_id for system_id, timestamp in self.last_relay_status_time.items()
            if current_time - timestamp > max_age
        ]
        for system_id in relay_keys_to_remove:
            if system_id in self.relay_mode_active:
                del self.relay_mode_active[system_id]
            del self.last_relay_status_time[system_id]
        
        # Clean up binary protocol error tracking
        checksum_keys_to_remove = [
            system_id for system_id, timestamp in self.last_checksum_alert_time.items()
            if current_time - timestamp > max_age
        ]
        for system_id in checksum_keys_to_remove:
            del self.last_checksum_alert_time[system_id]
        
        overflow_keys_to_remove = [
            system_id for system_id, timestamp in self.last_buffer_overflow_alert_time.items()
            if current_time - timestamp > max_age
        ]
        for system_id in overflow_keys_to_remove:
            del self.last_buffer_overflow_alert_time[system_id]
        
        timeout_keys_to_remove = [
            system_id for system_id, timestamp in self.last_timeout_alert_time.items()
            if current_time - timestamp > max_age
        ]
        for system_id in timeout_keys_to_remove:
            del self.last_timeout_alert_time[system_id]
        
        total_removed = (len(keys_to_remove) + len(relay_keys_to_remove) + 
                        len(checksum_keys_to_remove) + len(overflow_keys_to_remove) + 
                        len(timeout_keys_to_remove))
        if total_removed > 0:
            logger.debug(f"Cleaned up {total_removed} old tracking entries")
