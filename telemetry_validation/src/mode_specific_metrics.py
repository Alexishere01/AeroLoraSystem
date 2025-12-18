"""
Mode-Specific Metrics Module

This module provides separate metrics tracking for direct and relay operating modes.
It maintains independent metric calculations for each mode to enable comparison
and analysis of performance differences.

Requirements: 6.2, 6.3, 6.4
"""

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, Optional, Any, Deque
import time
import logging

# Handle both relative and absolute imports
try:
    from .binary_protocol_parser import ParsedBinaryPacket, UartCommand, BridgePayload, StatusPayload
    from .mavlink_parser import ParsedMessage
    from .mode_tracker import OperatingMode
except ImportError:
    from binary_protocol_parser import ParsedBinaryPacket, UartCommand, BridgePayload, StatusPayload
    from mavlink_parser import ParsedMessage
    from mode_tracker import OperatingMode

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ModeMetrics:
    """
    Metrics for a specific operating mode.
    
    Contains all telemetry metrics calculated independently for either
    direct or relay mode.
    
    Requirements: 6.2
    """
    mode: OperatingMode
    
    # Packet rates (packets per second)
    binary_packet_rate_1s: float
    binary_packet_rate_10s: float
    binary_packet_rate_60s: float
    mavlink_packet_rate_1s: float
    mavlink_packet_rate_10s: float
    mavlink_packet_rate_60s: float
    
    # Link quality metrics
    avg_rssi: float
    avg_snr: float
    
    # Packet loss metrics
    drop_rate: float  # Percentage
    packets_lost: int
    packets_received: int
    
    # Command latency (seconds)
    latency_avg: float
    latency_min: float
    latency_max: float
    latency_samples: int
    
    # Message type distribution
    mavlink_msg_type_distribution: Dict[str, int]
    binary_cmd_type_distribution: Dict[str, int]
    
    # Binary protocol health
    checksum_error_rate: float  # Errors per minute
    parse_error_rate: float  # Errors per minute
    protocol_success_rate: float  # Percentage
    
    # Relay-specific metrics (only for RELAY mode)
    packets_relayed: int = 0
    bytes_relayed: int = 0
    active_peer_relays: int = 0
    mesh_to_uart_packets: int = 0
    uart_to_mesh_packets: int = 0
    mesh_to_uart_bytes: int = 0
    uart_to_mesh_bytes: int = 0
    
    # Relay latency metrics (only for RELAY mode)
    relay_latency_avg: float = 0.0
    relay_latency_min: float = 0.0
    relay_latency_max: float = 0.0
    relay_latency_samples: int = 0
    
    # Time spent in this mode
    time_in_mode_seconds: float = 0.0
    
    # Timestamp
    timestamp: float = 0.0


class ModeSpecificMetricsCalculator:
    """
    Calculates metrics separately for direct and relay operating modes.
    
    This class maintains independent metric tracking for each operating mode,
    allowing comparison of performance between direct and relay communication.
    It tracks all standard telemetry metrics plus relay-specific metrics.
    
    Features:
    - Separate metric tracking for direct and relay modes
    - Rolling window packet rate calculation per mode
    - RSSI/SNR averaging per mode
    - Packet loss detection per mode
    - Command latency tracking per mode
    - Relay-specific metrics (packets_relayed, active_peer_relays, etc.)
    
    Requirements: 6.2, 6.3
    """
    
    def __init__(self):
        """Initialize the mode-specific metrics calculator."""
        # Metrics for each mode
        self.direct_metrics = self._create_empty_metrics_tracker()
        self.relay_metrics = self._create_empty_metrics_tracker()
        
        # Current mode tracking
        self.current_mode = OperatingMode.UNKNOWN
        
        # Mode start times for duration tracking
        self.direct_mode_start_time: Optional[float] = None
        self.relay_mode_start_time: Optional[float] = None
        self.total_direct_time = 0.0
        self.total_relay_time = 0.0
        
        # Initialization time
        self.start_time = time.time()
        
        logger.info("Mode-specific metrics calculator initialized")
    
    def _create_empty_metrics_tracker(self) -> Dict[str, Any]:
        """
        Create an empty metrics tracker structure.
        
        Returns:
            Dictionary with empty metric tracking structures
        """
        return {
            # Binary protocol packet timestamps
            'binary_packets_1s': deque(maxlen=10000),
            'binary_packets_10s': deque(maxlen=10000),
            'binary_packets_60s': deque(maxlen=60000),
            
            # MAVLink message timestamps
            'mavlink_packets_1s': deque(maxlen=10000),
            'mavlink_packets_10s': deque(maxlen=10000),
            'mavlink_packets_60s': deque(maxlen=60000),
            
            # RSSI/SNR tracking
            'rssi_values': deque(maxlen=100),
            'snr_values': deque(maxlen=100),
            
            # Message type distribution
            'mavlink_msg_type_counts': defaultdict(int),
            'binary_cmd_type_counts': defaultdict(int),
            
            # Packet loss tracking
            'sequence_numbers': {},  # system_id -> last_sequence
            'packets_lost': 0,
            'packets_received': 0,
            
            # Command latency tracking
            'command_times': {},  # command_id -> timestamp
            'latencies': deque(maxlen=100),
            
            # Binary protocol health
            'checksum_errors': deque(maxlen=1000),
            'parse_errors': deque(maxlen=1000),
            'total_binary_packets': 0,
            'successful_binary_packets': 0,
            
            # Relay-specific metrics
            'packets_relayed': 0,
            'bytes_relayed': 0,
            'active_peer_relays': 0,
            'mesh_to_uart_packets': 0,
            'uart_to_mesh_packets': 0,
            'mesh_to_uart_bytes': 0,
            'uart_to_mesh_bytes': 0,
            
            # Relay latency tracking
            'relay_latencies': deque(maxlen=100)  # Additional latency in relay mode
        }
    
    def set_mode(self, mode: OperatingMode):
        """
        Set the current operating mode.
        
        Updates mode timing when mode changes.
        
        Args:
            mode: New operating mode
            
        Requirements: 6.2
        """
        now = time.time()
        
        # Update timing for previous mode
        if self.current_mode == OperatingMode.DIRECT and self.direct_mode_start_time:
            self.total_direct_time += (now - self.direct_mode_start_time)
            self.direct_mode_start_time = None
        elif self.current_mode == OperatingMode.RELAY and self.relay_mode_start_time:
            self.total_relay_time += (now - self.relay_mode_start_time)
            self.relay_mode_start_time = None
        
        # Start timing for new mode
        if mode == OperatingMode.DIRECT:
            self.direct_mode_start_time = now
        elif mode == OperatingMode.RELAY:
            self.relay_mode_start_time = now
        
        self.current_mode = mode
        logger.debug(f"Mode set to {mode.name}")
    
    def update_binary_packet(self, packet: ParsedBinaryPacket, mode: OperatingMode):
        """
        Update metrics with a binary protocol packet for a specific mode.
        
        Args:
            packet: Parsed binary protocol packet
            mode: Operating mode when packet was received
            
        Requirements: 6.2
        """
        if mode == OperatingMode.UNKNOWN:
            return
        
        # Select metrics tracker for this mode
        metrics = self.direct_metrics if mode == OperatingMode.DIRECT else self.relay_metrics
        
        now = time.time()
        
        # Track packet timestamps for rate calculation
        metrics['binary_packets_1s'].append(now)
        metrics['binary_packets_10s'].append(now)
        metrics['binary_packets_60s'].append(now)
        
        # Track command type distribution
        metrics['binary_cmd_type_counts'][packet.command.name] += 1
        
        # Track successful packets
        metrics['successful_binary_packets'] += 1
        metrics['total_binary_packets'] += 1
        
        # Extract RSSI/SNR from BridgePayload
        if isinstance(packet.payload, BridgePayload):
            if packet.payload.rssi is not None and packet.payload.rssi != 0:
                metrics['rssi_values'].append(packet.payload.rssi)
            if packet.payload.snr is not None and packet.payload.snr != 0:
                metrics['snr_values'].append(packet.payload.snr)
        
        # Extract RSSI/SNR and relay metrics from StatusPayload
        elif isinstance(packet.payload, StatusPayload):
            if packet.payload.rssi is not None and packet.payload.rssi != 0:
                metrics['rssi_values'].append(packet.payload.rssi)
            if packet.payload.snr is not None and packet.payload.snr != 0:
                metrics['snr_values'].append(packet.payload.snr)
            
            # Update relay-specific metrics
            metrics['packets_relayed'] = packet.payload.packets_relayed
            metrics['bytes_relayed'] = packet.payload.bytes_relayed
            metrics['active_peer_relays'] = packet.payload.active_peer_relays
            metrics['mesh_to_uart_packets'] = packet.payload.mesh_to_uart_packets
            metrics['uart_to_mesh_packets'] = packet.payload.uart_to_mesh_packets
            metrics['mesh_to_uart_bytes'] = packet.payload.mesh_to_uart_bytes
            metrics['uart_to_mesh_bytes'] = packet.payload.uart_to_mesh_bytes
    
    def update_mavlink_message(self, msg: ParsedMessage, mode: OperatingMode):
        """
        Update metrics with a MAVLink message for a specific mode.
        
        Args:
            msg: Parsed MAVLink message
            mode: Operating mode when message was received
            
        Requirements: 6.2, 6.3
        """
        if mode == OperatingMode.UNKNOWN:
            return
        
        # Select metrics tracker for this mode
        metrics = self.direct_metrics if mode == OperatingMode.DIRECT else self.relay_metrics
        
        now = time.time()
        
        # Track packet timestamps for rate calculation
        metrics['mavlink_packets_1s'].append(now)
        metrics['mavlink_packets_10s'].append(now)
        metrics['mavlink_packets_60s'].append(now)
        
        # Track message type distribution
        metrics['mavlink_msg_type_counts'][msg.msg_type] += 1
        
        # Track packet reception
        metrics['packets_received'] += 1
        
        # Track sequence numbers for packet loss detection
        if msg.msg_type == 'HEARTBEAT':
            self._track_sequence_number(msg, metrics)
        
        # Track command latency
        if msg.msg_type == 'COMMAND_LONG':
            self._track_command_sent(msg, metrics)
        elif msg.msg_type == 'COMMAND_ACK':
            self._track_command_ack(msg, metrics)
    
    def _track_sequence_number(self, msg: ParsedMessage, metrics: Dict[str, Any]):
        """
        Track MAVLink sequence numbers to detect packet loss.
        
        Args:
            msg: Parsed MAVLink message with sequence number
            metrics: Metrics tracker for current mode
            
        Requirements: 6.2
        """
        system_id = msg.system_id
        current_seq = msg.sequence
        
        if system_id in metrics['sequence_numbers']:
            last_seq = metrics['sequence_numbers'][system_id]
            
            # Calculate expected sequence (wraps at 256)
            expected_seq = (last_seq + 1) % 256
            
            # Detect gaps in sequence
            if current_seq != expected_seq:
                # Calculate number of lost packets
                if current_seq > expected_seq:
                    lost = current_seq - expected_seq
                else:
                    # Sequence wrapped around
                    lost = (256 - expected_seq) + current_seq
                
                # Only count reasonable gaps (< 100) to avoid false positives
                if lost < 100:
                    metrics['packets_lost'] += lost
                    logger.debug(f"Packet loss detected for system {system_id}: "
                               f"expected seq {expected_seq}, got {current_seq}, "
                               f"lost {lost} packets")
        
        # Update last sequence number
        metrics['sequence_numbers'][system_id] = current_seq
    
    def _track_command_sent(self, msg: ParsedMessage, metrics: Dict[str, Any]):
        """
        Track when a COMMAND_LONG is sent.
        
        Args:
            msg: COMMAND_LONG message
            metrics: Metrics tracker for current mode
            
        Requirements: 6.3
        """
        try:
            command_id = msg.fields.get('command', 0)
            if command_id:
                metrics['command_times'][command_id] = time.time()
        except Exception as e:
            logger.warning(f"Error tracking command sent: {e}")
    
    def _track_command_ack(self, msg: ParsedMessage, metrics: Dict[str, Any]):
        """
        Track when a COMMAND_ACK is received and calculate latency.
        
        For relay mode, this also calculates the additional latency introduced
        by the relay hop by comparing with direct mode latency.
        
        Args:
            msg: COMMAND_ACK message
            metrics: Metrics tracker for current mode
            
        Requirements: 6.3
        """
        try:
            command_id = msg.fields.get('command', 0)
            
            if command_id in metrics['command_times']:
                # Calculate latency
                sent_time = metrics['command_times'][command_id]
                latency = time.time() - sent_time
                
                # Store latency
                metrics['latencies'].append(latency)
                
                # If in relay mode, calculate additional relay latency
                if self.current_mode == OperatingMode.RELAY:
                    # Calculate relay latency as difference from direct mode average
                    direct_avg = self._get_direct_mode_avg_latency()
                    if direct_avg > 0:
                        relay_additional_latency = latency - direct_avg
                        if relay_additional_latency > 0:
                            metrics['relay_latencies'].append(relay_additional_latency)
                            logger.debug(f"Relay additional latency: {relay_additional_latency*1000:.2f} ms")
                
                # Remove from tracking
                del metrics['command_times'][command_id]
                
                logger.debug(f"Command {command_id} latency: {latency*1000:.2f} ms")
        
        except Exception as e:
            logger.warning(f"Error tracking command ACK: {e}")
    
    def _get_direct_mode_avg_latency(self) -> float:
        """
        Get average latency from direct mode for comparison.
        
        Returns:
            Average direct mode latency in seconds, or 0 if no data
            
        Requirements: 6.3
        """
        latencies = self.direct_metrics['latencies']
        if latencies:
            return sum(latencies) / len(latencies)
        return 0.0
    
    def record_checksum_error(self, mode: OperatingMode):
        """
        Record a checksum error for a specific mode.
        
        Args:
            mode: Operating mode when error occurred
            
        Requirements: 6.2
        """
        if mode == OperatingMode.UNKNOWN:
            return
        
        metrics = self.direct_metrics if mode == OperatingMode.DIRECT else self.relay_metrics
        metrics['checksum_errors'].append(time.time())
        metrics['total_binary_packets'] += 1
    
    def record_parse_error(self, mode: OperatingMode):
        """
        Record a parse error for a specific mode.
        
        Args:
            mode: Operating mode when error occurred
            
        Requirements: 6.2
        """
        if mode == OperatingMode.UNKNOWN:
            return
        
        metrics = self.direct_metrics if mode == OperatingMode.DIRECT else self.relay_metrics
        metrics['parse_errors'].append(time.time())
        metrics['total_binary_packets'] += 1
    
    def get_mode_metrics(self, mode: OperatingMode) -> Optional[ModeMetrics]:
        """
        Calculate and return metrics for a specific mode.
        
        Args:
            mode: Operating mode to get metrics for
            
        Returns:
            ModeMetrics object with calculated metrics or None if mode is UNKNOWN
            
        Requirements: 6.2
        """
        if mode == OperatingMode.UNKNOWN:
            return None
        
        metrics = self.direct_metrics if mode == OperatingMode.DIRECT else self.relay_metrics
        now = time.time()
        
        # Calculate packet rates
        binary_rate_1s = self._calculate_rate(metrics['binary_packets_1s'], 1.0, now)
        binary_rate_10s = self._calculate_rate(metrics['binary_packets_10s'], 10.0, now)
        binary_rate_60s = self._calculate_rate(metrics['binary_packets_60s'], 60.0, now)
        
        mavlink_rate_1s = self._calculate_rate(metrics['mavlink_packets_1s'], 1.0, now)
        mavlink_rate_10s = self._calculate_rate(metrics['mavlink_packets_10s'], 10.0, now)
        mavlink_rate_60s = self._calculate_rate(metrics['mavlink_packets_60s'], 60.0, now)
        
        # Calculate RSSI/SNR averages
        avg_rssi = sum(metrics['rssi_values']) / len(metrics['rssi_values']) if metrics['rssi_values'] else 0.0
        avg_snr = sum(metrics['snr_values']) / len(metrics['snr_values']) if metrics['snr_values'] else 0.0
        
        # Calculate packet loss rate
        total_packets = metrics['packets_received'] + metrics['packets_lost']
        drop_rate = (metrics['packets_lost'] / total_packets * 100.0) if total_packets > 0 else 0.0
        
        # Calculate command latency statistics
        latency_avg = sum(metrics['latencies']) / len(metrics['latencies']) if metrics['latencies'] else 0.0
        latency_min = min(metrics['latencies']) if metrics['latencies'] else 0.0
        latency_max = max(metrics['latencies']) if metrics['latencies'] else 0.0
        latency_samples = len(metrics['latencies'])
        
        # Calculate relay latency statistics (only for relay mode)
        relay_latency_avg = 0.0
        relay_latency_min = 0.0
        relay_latency_max = 0.0
        relay_latency_samples = 0
        
        if mode == OperatingMode.RELAY and metrics['relay_latencies']:
            relay_latency_avg = sum(metrics['relay_latencies']) / len(metrics['relay_latencies'])
            relay_latency_min = min(metrics['relay_latencies'])
            relay_latency_max = max(metrics['relay_latencies'])
            relay_latency_samples = len(metrics['relay_latencies'])
        
        # Calculate message type distributions
        mavlink_distribution = dict(metrics['mavlink_msg_type_counts'])
        binary_distribution = dict(metrics['binary_cmd_type_counts'])
        
        # Calculate binary protocol health metrics
        checksum_error_rate = self._calculate_error_rate(metrics['checksum_errors'], 60.0, now)
        parse_error_rate = self._calculate_error_rate(metrics['parse_errors'], 60.0, now)
        
        if metrics['total_binary_packets'] > 0:
            protocol_success_rate = (metrics['successful_binary_packets'] / metrics['total_binary_packets']) * 100.0
        else:
            protocol_success_rate = 100.0
        
        # Calculate time in mode
        time_in_mode = self._get_mode_duration(mode)
        
        return ModeMetrics(
            mode=mode,
            binary_packet_rate_1s=binary_rate_1s,
            binary_packet_rate_10s=binary_rate_10s,
            binary_packet_rate_60s=binary_rate_60s,
            mavlink_packet_rate_1s=mavlink_rate_1s,
            mavlink_packet_rate_10s=mavlink_rate_10s,
            mavlink_packet_rate_60s=mavlink_rate_60s,
            avg_rssi=avg_rssi,
            avg_snr=avg_snr,
            drop_rate=drop_rate,
            packets_lost=metrics['packets_lost'],
            packets_received=metrics['packets_received'],
            latency_avg=latency_avg,
            latency_min=latency_min,
            latency_max=latency_max,
            latency_samples=latency_samples,
            mavlink_msg_type_distribution=mavlink_distribution,
            binary_cmd_type_distribution=binary_distribution,
            checksum_error_rate=checksum_error_rate,
            parse_error_rate=parse_error_rate,
            protocol_success_rate=protocol_success_rate,
            packets_relayed=metrics['packets_relayed'],
            bytes_relayed=metrics['bytes_relayed'],
            active_peer_relays=metrics['active_peer_relays'],
            mesh_to_uart_packets=metrics['mesh_to_uart_packets'],
            uart_to_mesh_packets=metrics['uart_to_mesh_packets'],
            mesh_to_uart_bytes=metrics['mesh_to_uart_bytes'],
            uart_to_mesh_bytes=metrics['uart_to_mesh_bytes'],
            relay_latency_avg=relay_latency_avg,
            relay_latency_min=relay_latency_min,
            relay_latency_max=relay_latency_max,
            relay_latency_samples=relay_latency_samples,
            time_in_mode_seconds=time_in_mode,
            timestamp=now
        )
    
    def _calculate_rate(self, timestamps: Deque[float], window_seconds: float, now: float) -> float:
        """Calculate packet rate over a time window."""
        count = sum(1 for t in timestamps if now - t <= window_seconds)
        return count / window_seconds if window_seconds > 0 else 0.0
    
    def _calculate_error_rate(self, error_timestamps: Deque[float], window_seconds: float, now: float) -> float:
        """Calculate error rate (errors per minute) over a time window."""
        count = sum(1 for t in error_timestamps if now - t <= window_seconds)
        return (count / window_seconds) * 60.0 if window_seconds > 0 else 0.0
    
    def _get_mode_duration(self, mode: OperatingMode) -> float:
        """Get total time spent in a specific mode."""
        now = time.time()
        
        if mode == OperatingMode.DIRECT:
            total = self.total_direct_time
            if self.current_mode == OperatingMode.DIRECT and self.direct_mode_start_time:
                total += (now - self.direct_mode_start_time)
            return total
        
        elif mode == OperatingMode.RELAY:
            total = self.total_relay_time
            if self.current_mode == OperatingMode.RELAY and self.relay_mode_start_time:
                total += (now - self.relay_mode_start_time)
            return total
        
        return 0.0
    
    def reset_stats(self):
        """Reset all statistics for both modes."""
        self.direct_metrics = self._create_empty_metrics_tracker()
        self.relay_metrics = self._create_empty_metrics_tracker()
        self.current_mode = OperatingMode.UNKNOWN
        self.direct_mode_start_time = None
        self.relay_mode_start_time = None
        self.total_direct_time = 0.0
        self.total_relay_time = 0.0
        self.start_time = time.time()
        
        logger.info("Mode-specific metrics calculator statistics reset")
