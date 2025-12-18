"""
Serial Monitor Module

This module provides real-time telemetry monitoring with console output,
displaying decoded MAVLink messages and binary protocol commands with
highlighting for critical messages.

Requirements: 2.1, 2.2, 2.3, 2.4
"""

import time
from typing import Optional, Dict, Set, List
from collections import deque, defaultdict
from dataclasses import dataclass
import logging

# Handle both relative and absolute imports
try:
    from .binary_protocol_parser import (
        ParsedBinaryPacket, UartCommand, BridgePayload, StatusPayload,
        InitPayload, RelayActivatePayload, RelayRequestPayload, RelayRxPayload
    )
    from .mavlink_parser import ParsedMessage
    from .metrics_calculator import MetricsCalculator, TelemetryMetrics
except ImportError:
    from binary_protocol_parser import (
        ParsedBinaryPacket, UartCommand, BridgePayload, StatusPayload,
        InitPayload, RelayActivatePayload, RelayRequestPayload, RelayRxPayload
    )
    from mavlink_parser import ParsedMessage
    from metrics_calculator import MetricsCalculator, TelemetryMetrics

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ANSI color codes for console output
class Colors:
    """ANSI color codes for terminal output."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Foreground colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Bright foreground colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'
    
    # Background colors
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'


@dataclass
class MonitorConfig:
    """
    Configuration for the serial monitor.
    
    Attributes:
        show_mavlink: Display MAVLink messages
        show_binary: Display binary protocol commands
        show_timestamps: Include timestamps in output
        show_rssi_snr: Display RSSI/SNR values
        highlight_critical: Highlight critical messages
        throttle_enabled: Enable output throttling
        max_messages_per_second: Maximum messages to display per second
        critical_messages: Set of critical MAVLink message types to highlight
        critical_commands: Set of critical binary commands to highlight
        color_enabled: Enable color output
    """
    show_mavlink: bool = True
    show_binary: bool = True
    show_timestamps: bool = True
    show_rssi_snr: bool = True
    highlight_critical: bool = True
    throttle_enabled: bool = True
    max_messages_per_second: int = 10
    critical_messages: Set[str] = None
    critical_commands: Set[UartCommand] = None
    color_enabled: bool = True
    
    def __post_init__(self):
        """Initialize default critical message sets."""
        if self.critical_messages is None:
            self.critical_messages = {
                'HEARTBEAT',
                'GPS_RAW_INT',
                'GLOBAL_POSITION_INT',
                'ATTITUDE',
                'SYS_STATUS',
                'BATTERY_STATUS',
                'COMMAND_ACK',
                'STATUSTEXT'
            }
        
        if self.critical_commands is None:
            self.critical_commands = {
                UartCommand.CMD_INIT,
                UartCommand.CMD_STATUS_REPORT,
                UartCommand.CMD_RELAY_ACTIVATE,
                UartCommand.CMD_BROADCAST_RELAY_REQ
            }


class SerialMonitor:
    """
    Real-time telemetry monitor with console output.
    
    This class provides real-time display of telemetry data, including:
    - Decoded MAVLink messages with key fields
    - Binary protocol commands (INIT, STATUS_REPORT, RELAY_ACTIVATE)
    - Highlighted critical messages (HEARTBEAT, GPS, ATTITUDE)
    - RSSI/SNR from binary protocol
    - Output throttling to prevent buffer overflow
    - Statistics display on request
    
    Features:
    - Color-coded output for different message types
    - Throttling to limit output rate
    - Critical message highlighting
    - Statistics tracking and display
    - Binary protocol health monitoring
    
    Requirements: 2.1, 2.2, 2.3, 2.4
    """
    
    def __init__(self, config: Optional[MonitorConfig] = None, 
                 metrics_calculator: Optional[MetricsCalculator] = None):
        """
        Initialize the serial monitor.
        
        Args:
            config: Monitor configuration (uses defaults if None)
            metrics_calculator: Optional MetricsCalculator for statistics display
        """
        self.config = config or MonitorConfig()
        self.metrics_calculator = metrics_calculator
        
        # Throttling state
        self.message_timestamps: deque = deque(maxlen=1000)
        self.throttled_count = 0
        self.last_throttle_warning = 0.0
        
        # Statistics
        self.stats = {
            'mavlink_displayed': 0,
            'binary_displayed': 0,
            'throttled_messages': 0,
            'critical_messages': 0,
            'messages_by_type': defaultdict(int),
            'commands_by_type': defaultdict(int)
        }
        
        # Last displayed values for change detection
        self.last_rssi: Optional[float] = None
        self.last_snr: Optional[float] = None
        
        logger.info(
            f"Serial monitor initialized - "
            f"throttle={'enabled' if self.config.throttle_enabled else 'disabled'}, "
            f"max_rate={self.config.max_messages_per_second}/s, "
            f"color={'enabled' if self.config.color_enabled else 'disabled'}"
        )
    
    def display_mavlink_message(self, msg: ParsedMessage) -> bool:
        """
        Display a MAVLink message to the console.
        
        Args:
            msg: Parsed MAVLink message
            
        Returns:
            True if message was displayed, False if throttled
            
        Requirements: 2.1, 2.2, 2.3
        """
        if not self.config.show_mavlink:
            return False
        
        # Check throttling
        if self.config.throttle_enabled and not self._should_display(msg.msg_type):
            self.stats['throttled_messages'] += 1
            self.throttled_count += 1
            return False
        
        # Check if this is a critical message
        is_critical = msg.msg_type in self.config.critical_messages
        
        # Format and display the message
        output = self._format_mavlink_message(msg, is_critical)
        print(output)
        
        # Update statistics
        self.stats['mavlink_displayed'] += 1
        self.stats['messages_by_type'][msg.msg_type] += 1
        if is_critical:
            self.stats['critical_messages'] += 1
        
        # Update last RSSI/SNR
        if msg.rssi is not None:
            self.last_rssi = msg.rssi
        if msg.snr is not None:
            self.last_snr = msg.snr
        
        return True
    
    def display_binary_packet(self, packet: ParsedBinaryPacket) -> bool:
        """
        Display a binary protocol packet to the console.
        
        Args:
            packet: Parsed binary protocol packet
            
        Returns:
            True if packet was displayed, False if throttled
            
        Requirements: 2.1, 2.2, 2.3
        """
        if not self.config.show_binary:
            return False
        
        # Check throttling
        if self.config.throttle_enabled and not self._should_display(packet.command.name):
            self.stats['throttled_messages'] += 1
            self.throttled_count += 1
            return False
        
        # Check if this is a critical command
        is_critical = packet.command in self.config.critical_commands
        
        # Format and display the packet
        output = self._format_binary_packet(packet, is_critical)
        print(output)
        
        # Update statistics
        self.stats['binary_displayed'] += 1
        self.stats['commands_by_type'][packet.command.name] += 1
        if is_critical:
            self.stats['critical_messages'] += 1
        
        # Update last RSSI/SNR from payload if available
        if isinstance(packet.payload, (BridgePayload, StatusPayload)):
            if packet.payload.rssi is not None:
                self.last_rssi = packet.payload.rssi
            if packet.payload.snr is not None:
                self.last_snr = packet.payload.snr
        
        return True
    
    def _should_display(self, msg_type: str) -> bool:
        """
        Check if a message should be displayed based on throttling rules.
        
        Critical messages are always displayed. Non-critical messages are
        throttled based on the configured rate limit.
        
        Args:
            msg_type: Message type or command name
            
        Returns:
            True if message should be displayed, False if throttled
            
        Requirements: 2.3
        """
        now = time.time()
        
        # Always display critical messages
        if msg_type in self.config.critical_messages:
            return True
        
        # Check if we're within the rate limit
        self.message_timestamps.append(now)
        
        # Count messages in the last second
        recent_count = sum(1 for t in self.message_timestamps if now - t <= 1.0)
        
        # Allow if under the limit
        if recent_count <= self.config.max_messages_per_second:
            return True
        
        # Throttled - show warning periodically
        if now - self.last_throttle_warning > 5.0:
            self._display_throttle_warning()
            self.last_throttle_warning = now
        
        return False
    
    def _format_mavlink_message(self, msg: ParsedMessage, is_critical: bool) -> str:
        """
        Format a MAVLink message for console display.
        
        Args:
            msg: Parsed MAVLink message
            is_critical: Whether this is a critical message
            
        Returns:
            Formatted string for console output
            
        Requirements: 2.1, 2.2
        """
        parts = []
        
        # Timestamp
        if self.config.show_timestamps:
            timestamp_str = time.strftime('%H:%M:%S', time.localtime(msg.timestamp))
            parts.append(f"[{timestamp_str}]")
        
        # Message type with color
        if self.config.color_enabled:
            if is_critical:
                msg_type_str = f"{Colors.BOLD}{Colors.BRIGHT_YELLOW}MAV:{msg.msg_type}{Colors.RESET}"
            else:
                msg_type_str = f"{Colors.CYAN}MAV:{msg.msg_type}{Colors.RESET}"
        else:
            msg_type_str = f"MAV:{msg.msg_type}"
        
        parts.append(msg_type_str)
        
        # System ID
        parts.append(f"SYS:{msg.system_id}")
        
        # Key fields based on message type
        key_fields = self._extract_key_fields(msg)
        if key_fields:
            parts.append(key_fields)
        
        # RSSI/SNR
        if self.config.show_rssi_snr and (msg.rssi is not None or msg.snr is not None):
            rssi_str = f"{msg.rssi:.1f}" if msg.rssi is not None else "N/A"
            snr_str = f"{msg.snr:.1f}" if msg.snr is not None else "N/A"
            
            if self.config.color_enabled:
                # Color code RSSI (green=good, yellow=ok, red=poor)
                if msg.rssi is not None:
                    if msg.rssi > -80:
                        rssi_color = Colors.GREEN
                    elif msg.rssi > -100:
                        rssi_color = Colors.YELLOW
                    else:
                        rssi_color = Colors.RED
                    rssi_str = f"{rssi_color}{rssi_str}{Colors.RESET}"
                
                parts.append(f"RSSI:{rssi_str}dBm SNR:{snr_str}dB")
            else:
                parts.append(f"RSSI:{rssi_str}dBm SNR:{snr_str}dB")
        
        return " ".join(parts)
    
    def _format_binary_packet(self, packet: ParsedBinaryPacket, is_critical: bool) -> str:
        """
        Format a binary protocol packet for console display.
        
        Args:
            packet: Parsed binary protocol packet
            is_critical: Whether this is a critical command
            
        Returns:
            Formatted string for console output
            
        Requirements: 2.1, 2.2
        """
        parts = []
        
        # Timestamp
        if self.config.show_timestamps:
            timestamp_str = time.strftime('%H:%M:%S', time.localtime(packet.timestamp))
            parts.append(f"[{timestamp_str}]")
        
        # Command type with color
        if self.config.color_enabled:
            if is_critical:
                cmd_str = f"{Colors.BOLD}{Colors.BRIGHT_MAGENTA}BIN:{packet.command.name}{Colors.RESET}"
            else:
                cmd_str = f"{Colors.BLUE}BIN:{packet.command.name}{Colors.RESET}"
        else:
            cmd_str = f"BIN:{packet.command.name}"
        
        parts.append(cmd_str)
        
        # Payload details based on command type
        payload_str = self._format_payload(packet)
        if payload_str:
            parts.append(payload_str)
        
        # RSSI/SNR from payload
        if self.config.show_rssi_snr:
            rssi = None
            snr = None
            
            if isinstance(packet.payload, (BridgePayload, StatusPayload)):
                rssi = packet.payload.rssi
                snr = packet.payload.snr
            
            if rssi is not None or snr is not None:
                rssi_str = f"{rssi:.1f}" if rssi is not None else "N/A"
                snr_str = f"{snr:.1f}" if snr is not None else "N/A"
                
                if self.config.color_enabled and rssi is not None:
                    # Color code RSSI
                    if rssi > -80:
                        rssi_color = Colors.GREEN
                    elif rssi > -100:
                        rssi_color = Colors.YELLOW
                    else:
                        rssi_color = Colors.RED
                    rssi_str = f"{rssi_color}{rssi_str}{Colors.RESET}"
                
                parts.append(f"RSSI:{rssi_str}dBm SNR:{snr_str}dB")
        
        return " ".join(parts)
    
    def _extract_key_fields(self, msg: ParsedMessage) -> str:
        """
        Extract key fields from a MAVLink message for display.
        
        Args:
            msg: Parsed MAVLink message
            
        Returns:
            Formatted string with key fields
            
        Requirements: 2.1
        """
        fields = msg.fields
        key_info = []
        
        # Extract key fields based on message type
        if msg.msg_type == 'HEARTBEAT':
            mode = fields.get('custom_mode', 0)
            armed = fields.get('base_mode', 0) & 128  # MAV_MODE_FLAG_SAFETY_ARMED
            key_info.append(f"mode={mode} armed={'YES' if armed else 'NO'}")
        
        elif msg.msg_type == 'GPS_RAW_INT':
            lat = fields.get('lat', 0) / 1e7
            lon = fields.get('lon', 0) / 1e7
            alt = fields.get('alt', 0) / 1000.0
            fix = fields.get('fix_type', 0)
            sats = fields.get('satellites_visible', 0)
            key_info.append(f"lat={lat:.6f} lon={lon:.6f} alt={alt:.1f}m fix={fix} sats={sats}")
        
        elif msg.msg_type == 'GLOBAL_POSITION_INT':
            lat = fields.get('lat', 0) / 1e7
            lon = fields.get('lon', 0) / 1e7
            alt = fields.get('alt', 0) / 1000.0
            rel_alt = fields.get('relative_alt', 0) / 1000.0
            key_info.append(f"lat={lat:.6f} lon={lon:.6f} alt={alt:.1f}m rel={rel_alt:.1f}m")
        
        elif msg.msg_type == 'ATTITUDE':
            roll = fields.get('roll', 0)
            pitch = fields.get('pitch', 0)
            yaw = fields.get('yaw', 0)
            key_info.append(f"roll={roll:.2f} pitch={pitch:.2f} yaw={yaw:.2f}")
        
        elif msg.msg_type == 'SYS_STATUS':
            voltage = fields.get('voltage_battery', 0) / 1000.0
            current = fields.get('current_battery', 0) / 100.0
            remaining = fields.get('battery_remaining', -1)
            key_info.append(f"bat={voltage:.2f}V {current:.2f}A {remaining}%")
        
        elif msg.msg_type == 'BATTERY_STATUS':
            voltage = sum(fields.get('voltages', [0])) / 1000.0
            current = fields.get('current_battery', 0) / 100.0
            remaining = fields.get('battery_remaining', -1)
            key_info.append(f"bat={voltage:.2f}V {current:.2f}A {remaining}%")
        
        elif msg.msg_type == 'COMMAND_ACK':
            command = fields.get('command', 0)
            result = fields.get('result', 0)
            key_info.append(f"cmd={command} result={result}")
        
        elif msg.msg_type == 'STATUSTEXT':
            severity = fields.get('severity', 0)
            text = fields.get('text', '')
            key_info.append(f"[{severity}] {text}")
        
        return " ".join(key_info)
    
    def _format_payload(self, packet: ParsedBinaryPacket) -> str:
        """
        Format binary protocol payload for display.
        
        Args:
            packet: Parsed binary protocol packet
            
        Returns:
            Formatted string with payload details
            
        Requirements: 2.1
        """
        if packet.payload is None:
            return ""
        
        payload_info = []
        
        if isinstance(packet.payload, InitPayload):
            payload_info.append(f"mode={packet.payload.mode}")
            payload_info.append(f"freq1={packet.payload.primary_freq:.2f}MHz")
            payload_info.append(f"freq2={packet.payload.secondary_freq:.2f}MHz")
        
        elif isinstance(packet.payload, BridgePayload):
            payload_info.append(f"sysid={packet.payload.system_id}")
            payload_info.append(f"len={packet.payload.data_len}B")
        
        elif isinstance(packet.payload, StatusPayload):
            relay_status = "ACTIVE" if packet.payload.relay_active else "INACTIVE"
            payload_info.append(f"relay={relay_status}")
            payload_info.append(f"sysid={packet.payload.own_drone_sysid}")
            payload_info.append(f"relayed={packet.payload.packets_relayed}")
            payload_info.append(f"peers={packet.payload.active_peer_relays}")
        
        elif isinstance(packet.payload, RelayActivatePayload):
            status = "ACTIVATE" if packet.payload.activate else "DEACTIVATE"
            payload_info.append(status)
        
        elif isinstance(packet.payload, RelayRequestPayload):
            payload_info.append(f"loss={packet.payload.packet_loss:.1f}%")
        
        elif isinstance(packet.payload, RelayRxPayload):
            payload_info.append(f"len={len(packet.payload.data)}B")
        
        return " ".join(payload_info)
    
    def _display_throttle_warning(self):
        """
        Display a throttle warning message.
        
        Requirements: 2.3
        """
        if self.config.color_enabled:
            warning = (f"{Colors.YELLOW}⚠ Output throttled: "
                      f"{self.throttled_count} messages suppressed "
                      f"(limit: {self.config.max_messages_per_second}/s){Colors.RESET}")
        else:
            warning = (f"⚠ Output throttled: "
                      f"{self.throttled_count} messages suppressed "
                      f"(limit: {self.config.max_messages_per_second}/s)")
        
        print(warning)
        self.throttled_count = 0
    
    def display_statistics(self, metrics: Optional[TelemetryMetrics] = None):
        """
        Display comprehensive statistics to the console.
        
        Shows packet rates, message distribution, link quality, and binary
        protocol health metrics.
        
        Args:
            metrics: Optional TelemetryMetrics object (uses internal calculator if None)
            
        Requirements: 2.4
        """
        # Get metrics from calculator if not provided
        if metrics is None and self.metrics_calculator is not None:
            metrics = self.metrics_calculator.get_metrics()
        
        # Print header
        if self.config.color_enabled:
            print(f"\n{Colors.BOLD}{Colors.BRIGHT_CYAN}{'='*70}{Colors.RESET}")
            print(f"{Colors.BOLD}{Colors.BRIGHT_CYAN}TELEMETRY STATISTICS{Colors.RESET}")
            print(f"{Colors.BOLD}{Colors.BRIGHT_CYAN}{'='*70}{Colors.RESET}\n")
        else:
            print(f"\n{'='*70}")
            print("TELEMETRY STATISTICS")
            print(f"{'='*70}\n")
        
        # Display monitor statistics
        self._display_monitor_stats()
        
        # Display metrics if available
        if metrics is not None:
            self._display_packet_rates(metrics)
            self._display_link_quality(metrics)
            self._display_message_distribution(metrics)
            self._display_binary_protocol_health(metrics)
        
        # Print footer
        if self.config.color_enabled:
            print(f"{Colors.BOLD}{Colors.BRIGHT_CYAN}{'='*70}{Colors.RESET}\n")
        else:
            print(f"{'='*70}\n")
    
    def _display_monitor_stats(self):
        """Display serial monitor statistics."""
        if self.config.color_enabled:
            print(f"{Colors.BOLD}Monitor Statistics:{Colors.RESET}")
        else:
            print("Monitor Statistics:")
        
        print(f"  MAVLink messages displayed: {self.stats['mavlink_displayed']}")
        print(f"  Binary packets displayed: {self.stats['binary_displayed']}")
        print(f"  Critical messages: {self.stats['critical_messages']}")
        print(f"  Throttled messages: {self.stats['throttled_messages']}")
        print()
    
    def _display_packet_rates(self, metrics: TelemetryMetrics):
        """Display packet rate statistics."""
        if self.config.color_enabled:
            print(f"{Colors.BOLD}Packet Rates:{Colors.RESET}")
        else:
            print("Packet Rates:")
        
        print(f"  Binary Protocol:")
        print(f"    1s:  {metrics.binary_packet_rate_1s:.1f} pkt/s")
        print(f"    10s: {metrics.binary_packet_rate_10s:.1f} pkt/s")
        print(f"    60s: {metrics.binary_packet_rate_60s:.1f} pkt/s")
        
        print(f"  MAVLink:")
        print(f"    1s:  {metrics.mavlink_packet_rate_1s:.1f} pkt/s")
        print(f"    10s: {metrics.mavlink_packet_rate_10s:.1f} pkt/s")
        print(f"    60s: {metrics.mavlink_packet_rate_60s:.1f} pkt/s")
        print()
    
    def _display_link_quality(self, metrics: TelemetryMetrics):
        """Display link quality metrics."""
        if self.config.color_enabled:
            print(f"{Colors.BOLD}Link Quality:{Colors.RESET}")
        else:
            print("Link Quality:")
        
        # Color code RSSI
        rssi_str = f"{metrics.avg_rssi:.1f}"
        if self.config.color_enabled:
            if metrics.avg_rssi > -80:
                rssi_str = f"{Colors.GREEN}{rssi_str}{Colors.RESET}"
            elif metrics.avg_rssi > -100:
                rssi_str = f"{Colors.YELLOW}{rssi_str}{Colors.RESET}"
            else:
                rssi_str = f"{Colors.RED}{rssi_str}{Colors.RESET}"
        
        print(f"  Average RSSI: {rssi_str} dBm")
        print(f"  Average SNR:  {metrics.avg_snr:.1f} dB")
        
        # Color code packet loss
        loss_str = f"{metrics.drop_rate:.2f}"
        if self.config.color_enabled:
            if metrics.drop_rate < 1.0:
                loss_str = f"{Colors.GREEN}{loss_str}{Colors.RESET}"
            elif metrics.drop_rate < 5.0:
                loss_str = f"{Colors.YELLOW}{loss_str}{Colors.RESET}"
            else:
                loss_str = f"{Colors.RED}{loss_str}{Colors.RESET}"
        
        print(f"  Packet Loss:  {loss_str}% ({metrics.packets_lost}/{metrics.packets_received + metrics.packets_lost})")
        
        if metrics.latency_samples > 0:
            print(f"  Command Latency:")
            print(f"    Average: {metrics.latency_avg*1000:.1f} ms")
            print(f"    Min:     {metrics.latency_min*1000:.1f} ms")
            print(f"    Max:     {metrics.latency_max*1000:.1f} ms")
            print(f"    Samples: {metrics.latency_samples}")
        print()
    
    def _display_message_distribution(self, metrics: TelemetryMetrics):
        """Display message type distribution."""
        if self.config.color_enabled:
            print(f"{Colors.BOLD}Message Distribution:{Colors.RESET}")
        else:
            print("Message Distribution:")
        
        # MAVLink messages
        print(f"  MAVLink (top 10):")
        mavlink_sorted = sorted(
            metrics.mavlink_msg_type_distribution.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        for msg_type, count in mavlink_sorted:
            print(f"    {msg_type:25s}: {count:6d}")
        
        # Binary protocol commands
        print(f"  Binary Protocol:")
        binary_sorted = sorted(
            metrics.binary_cmd_type_distribution.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for cmd_type, count in binary_sorted:
            print(f"    {cmd_type:25s}: {count:6d}")
        print()
    
    def _display_binary_protocol_health(self, metrics: TelemetryMetrics):
        """Display binary protocol health metrics."""
        if self.config.color_enabled:
            print(f"{Colors.BOLD}Binary Protocol Health:{Colors.RESET}")
        else:
            print("Binary Protocol Health:")
        
        # Color code success rate
        success_str = f"{metrics.protocol_success_rate:.1f}"
        if self.config.color_enabled:
            if metrics.protocol_success_rate > 99.0:
                success_str = f"{Colors.GREEN}{success_str}{Colors.RESET}"
            elif metrics.protocol_success_rate > 95.0:
                success_str = f"{Colors.YELLOW}{success_str}{Colors.RESET}"
            else:
                success_str = f"{Colors.RED}{success_str}{Colors.RESET}"
        
        print(f"  Success Rate:     {success_str}%")
        print(f"  Checksum Errors:  {metrics.checksum_error_rate:.1f}/min")
        print(f"  Parse Errors:     {metrics.parse_error_rate:.1f}/min")
        print(f"  Buffer Overflows: {metrics.buffer_overflow_count}")
        print(f"  Timeouts:         {metrics.timeout_error_count}")
        print()
    
    def get_stats(self) -> Dict:
        """
        Get monitor statistics.
        
        Returns:
            Dictionary containing monitor statistics
        """
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset monitor statistics."""
        self.stats = {
            'mavlink_displayed': 0,
            'binary_displayed': 0,
            'throttled_messages': 0,
            'critical_messages': 0,
            'messages_by_type': defaultdict(int),
            'commands_by_type': defaultdict(int)
        }
        self.throttled_count = 0
        logger.info("Serial monitor statistics reset")
