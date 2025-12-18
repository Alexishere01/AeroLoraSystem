"""
Metrics Calculator Module

This module provides comprehensive metrics calculation for telemetry data,
tracking both binary protocol packets and MAVLink messages with rolling
window statistics, packet loss detection, and command latency tracking.

Requirements: 2.4, 2.5, 5.1, 5.4, 5.5, 6.3, 9.4
"""

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, Optional, Any, Deque, List, Tuple
import time
import logging
import statistics

# Handle both relative and absolute imports
try:
    from .binary_protocol_parser import ParsedBinaryPacket, UartCommand, BridgePayload, StatusPayload
    from .mavlink_parser import ParsedMessage
    from .csv_utils import EnhancedLogEntry
except ImportError:
    from binary_protocol_parser import ParsedBinaryPacket, UartCommand, BridgePayload, StatusPayload
    from mavlink_parser import ParsedMessage
    from csv_utils import EnhancedLogEntry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TelemetryMetrics:
    """
    Comprehensive telemetry metrics snapshot.
    
    Contains calculated metrics for both binary protocol and MAVLink layers,
    including packet rates, link quality, and error rates.
    
    Requirements: 5.1, 5.5
    """
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
    buffer_overflow_count: int  # Total buffer overflow events
    timeout_error_count: int  # Total timeout events
    
    # Timestamp
    timestamp: float


@dataclass
class PerformanceMetrics:
    """
    Performance metrics calculated from enhanced CSV data.
    
    Contains metrics for throughput, latency, queue congestion, and error
    correlation analysis. Handles legacy format gracefully with None or 0 values.
    
    Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
    """
    # Throughput metrics
    avg_throughput_bps: float
    peak_throughput_bps: float
    min_throughput_bps: float
    
    # Latency metrics
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    max_latency_ms: float
    
    # Queue metrics
    avg_queue_depth: float
    max_queue_depth: int
    congestion_events: int
    congestion_duration_ms: int
    
    # Error metrics
    total_errors: int
    error_rate_per_minute: float
    errors_during_good_link: int  # RSSI > -85 dBm
    errors_during_poor_link: int  # RSSI <= -85 dBm


class MetricsCalculator:
    """
    Comprehensive metrics calculator for telemetry validation system.
    
    This class tracks metrics for both binary protocol packets and MAVLink
    messages, maintaining rolling windows for rate calculations and tracking
    packet loss, latency, and link quality.
    
    Features:
    - Rolling window packet rate calculation (1s, 10s, 60s)
    - RSSI/SNR averaging from binary protocol
    - Packet loss detection from MAVLink sequence numbers
    - Command latency tracking (COMMAND_LONG -> COMMAND_ACK)
    - Message type distribution tracking
    - Binary protocol health metrics
    
    Requirements: 2.4, 2.5, 5.1, 5.4, 5.5, 6.3, 9.2, 9.4
    """
    
    def __init__(self):
        """Initialize the metrics calculator with rolling windows."""
        # Binary protocol packet timestamps (for rate calculation)
        self.binary_packets_1s: Deque[float] = deque(maxlen=10000)
        self.binary_packets_10s: Deque[float] = deque(maxlen=10000)
        self.binary_packets_60s: Deque[float] = deque(maxlen=60000)
        
        # MAVLink message timestamps (for rate calculation)
        self.mavlink_packets_1s: Deque[float] = deque(maxlen=10000)
        self.mavlink_packets_10s: Deque[float] = deque(maxlen=10000)
        self.mavlink_packets_60s: Deque[float] = deque(maxlen=60000)
        
        # RSSI/SNR tracking from binary protocol
        self.rssi_values: Deque[float] = deque(maxlen=100)
        self.snr_values: Deque[float] = deque(maxlen=100)
        
        # Message type distribution
        self.mavlink_msg_type_counts: Dict[str, int] = defaultdict(int)
        self.binary_cmd_type_counts: Dict[str, int] = defaultdict(int)
        
        # Packet loss tracking (per system ID)
        self.sequence_numbers: Dict[int, int] = {}  # system_id -> last_sequence
        self.packets_lost: int = 0
        self.packets_received: int = 0
        
        # Command latency tracking
        self.command_times: Dict[int, float] = {}  # command_id -> timestamp
        self.latencies: Deque[float] = deque(maxlen=100)
        
        # Binary protocol health tracking
        self.checksum_errors: Deque[float] = deque(maxlen=1000)  # timestamps
        self.parse_errors: Deque[float] = deque(maxlen=1000)  # timestamps
        self.buffer_overflows: int = 0  # Total buffer overflow events
        self.timeout_errors: int = 0  # Total timeout events
        self.total_binary_packets: int = 0
        self.successful_binary_packets: int = 0
        
        # Initialization time
        self.start_time = time.time()
        
        logger.info("Metrics calculator initialized")
    
    def update_binary_packet(self, packet: ParsedBinaryPacket):
        """
        Update metrics with a binary protocol packet.
        
        Tracks packet rates, command distribution, and extracts RSSI/SNR
        from BridgePayload and StatusPayload.
        
        Args:
            packet: Parsed binary protocol packet
            
        Requirements: 5.1, 5.5
        """
        now = time.time()
        
        # Track packet timestamps for rate calculation
        self.binary_packets_1s.append(now)
        self.binary_packets_10s.append(now)
        self.binary_packets_60s.append(now)
        
        # Track command type distribution
        self.binary_cmd_type_counts[packet.command.name] += 1
        
        # Track successful packets
        self.successful_binary_packets += 1
        self.total_binary_packets += 1
        
        # Extract RSSI/SNR from BridgePayload
        if isinstance(packet.payload, BridgePayload):
            if packet.payload.rssi is not None and packet.payload.rssi != 0:
                self.rssi_values.append(packet.payload.rssi)
            if packet.payload.snr is not None and packet.payload.snr != 0:
                self.snr_values.append(packet.payload.snr)
        
        # Extract RSSI/SNR from StatusPayload
        elif isinstance(packet.payload, StatusPayload):
            if packet.payload.rssi is not None and packet.payload.rssi != 0:
                self.rssi_values.append(packet.payload.rssi)
            if packet.payload.snr is not None and packet.payload.snr != 0:
                self.snr_values.append(packet.payload.snr)
    
    def update_mavlink_message(self, msg: ParsedMessage):
        """
        Update metrics with a MAVLink message.
        
        Tracks packet rates, message type distribution, sequence numbers
        for packet loss detection, and command latency.
        
        Args:
            msg: Parsed MAVLink message
            
        Requirements: 2.5, 5.4, 6.3, 9.4
        """
        now = time.time()
        
        # Track packet timestamps for rate calculation
        self.mavlink_packets_1s.append(now)
        self.mavlink_packets_10s.append(now)
        self.mavlink_packets_60s.append(now)
        
        # Track message type distribution
        self.mavlink_msg_type_counts[msg.msg_type] += 1
        
        # Track packet reception
        self.packets_received += 1
        
        # Track sequence numbers for packet loss detection (HEARTBEAT messages)
        if msg.msg_type == 'HEARTBEAT':
            self._track_sequence_number(msg)
        
        # Track command latency
        if msg.msg_type == 'COMMAND_LONG':
            self._track_command_sent(msg)
        elif msg.msg_type == 'COMMAND_ACK':
            self._track_command_ack(msg)
    
    def _track_sequence_number(self, msg: ParsedMessage):
        """
        Track MAVLink sequence numbers to detect packet loss.
        
        MAVLink packets have a sequence number (0-255) that increments
        with each packet. Gaps in the sequence indicate lost packets.
        
        Args:
            msg: Parsed MAVLink message with sequence number
            
        Requirements: 5.4, 9.4
        """
        system_id = msg.system_id
        current_seq = msg.sequence
        
        if system_id in self.sequence_numbers:
            last_seq = self.sequence_numbers[system_id]
            
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
                    self.packets_lost += lost
                    logger.debug(f"Packet loss detected for system {system_id}: "
                               f"expected seq {expected_seq}, got {current_seq}, "
                               f"lost {lost} packets")
        
        # Update last sequence number
        self.sequence_numbers[system_id] = current_seq
    
    def _track_command_sent(self, msg: ParsedMessage):
        """
        Track when a COMMAND_LONG is sent.
        
        Stores the timestamp for latency calculation when the corresponding
        COMMAND_ACK is received.
        
        Args:
            msg: COMMAND_LONG message
            
        Requirements: 2.5, 6.3
        """
        try:
            command_id = msg.fields.get('command', 0)
            if command_id:
                self.command_times[command_id] = time.time()
                logger.debug(f"Tracking command {command_id}")
        except Exception as e:
            logger.warning(f"Error tracking command sent: {e}")
    
    def _track_command_ack(self, msg: ParsedMessage):
        """
        Track when a COMMAND_ACK is received and calculate latency.
        
        Matches the ACK with the corresponding COMMAND_LONG to calculate
        round-trip latency.
        
        Args:
            msg: COMMAND_ACK message
            
        Requirements: 2.5, 6.3
        """
        try:
            command_id = msg.fields.get('command', 0)
            
            if command_id in self.command_times:
                # Calculate latency
                sent_time = self.command_times[command_id]
                latency = time.time() - sent_time
                
                # Store latency
                self.latencies.append(latency)
                
                # Remove from tracking
                del self.command_times[command_id]
                
                logger.debug(f"Command {command_id} latency: {latency*1000:.2f} ms")
        
        except Exception as e:
            logger.warning(f"Error tracking command ACK: {e}")
    
    def record_checksum_error(self):
        """
        Record a checksum error from binary protocol parser.
        
        Requirements: 3.2, 9.2
        """
        self.checksum_errors.append(time.time())
        self.total_binary_packets += 1
    
    def record_parse_error(self):
        """
        Record a parse error from binary protocol parser.
        
        Requirements: 3.2, 9.2
        """
        self.parse_errors.append(time.time())
        self.total_binary_packets += 1
    
    def record_buffer_overflow(self):
        """
        Record a buffer overflow event from binary protocol parser.
        
        Requirements: 3.2, 9.2
        """
        self.buffer_overflows += 1
        logger.warning("UART buffer overflow detected")
    
    def record_timeout_error(self):
        """
        Record a timeout error from binary protocol parser.
        
        Requirements: 3.2, 9.2
        """
        self.timeout_errors += 1
        logger.warning("Communication timeout detected")
    
    def get_metrics(self) -> TelemetryMetrics:
        """
        Calculate and return current telemetry metrics.
        
        Computes all metrics including packet rates, averages, error rates,
        and distributions based on the tracked data.
        
        Returns:
            TelemetryMetrics object with all calculated metrics
            
        Requirements: 2.4, 5.1, 5.5
        """
        now = time.time()
        
        # Calculate binary protocol packet rates
        binary_rate_1s = self._calculate_rate(self.binary_packets_1s, 1.0, now)
        binary_rate_10s = self._calculate_rate(self.binary_packets_10s, 10.0, now)
        binary_rate_60s = self._calculate_rate(self.binary_packets_60s, 60.0, now)
        
        # Calculate MAVLink packet rates
        mavlink_rate_1s = self._calculate_rate(self.mavlink_packets_1s, 1.0, now)
        mavlink_rate_10s = self._calculate_rate(self.mavlink_packets_10s, 10.0, now)
        mavlink_rate_60s = self._calculate_rate(self.mavlink_packets_60s, 60.0, now)
        
        # Calculate RSSI/SNR averages
        avg_rssi = sum(self.rssi_values) / len(self.rssi_values) if self.rssi_values else 0.0
        avg_snr = sum(self.snr_values) / len(self.snr_values) if self.snr_values else 0.0
        
        # Calculate packet loss rate
        total_packets = self.packets_received + self.packets_lost
        drop_rate = (self.packets_lost / total_packets * 100.0) if total_packets > 0 else 0.0
        
        # Calculate command latency statistics
        latency_avg = sum(self.latencies) / len(self.latencies) if self.latencies else 0.0
        latency_min = min(self.latencies) if self.latencies else 0.0
        latency_max = max(self.latencies) if self.latencies else 0.0
        latency_samples = len(self.latencies)
        
        # Calculate message type distributions with percentages
        mavlink_total = sum(self.mavlink_msg_type_counts.values())
        mavlink_distribution = {
            msg_type: count
            for msg_type, count in self.mavlink_msg_type_counts.items()
        }
        
        binary_total = sum(self.binary_cmd_type_counts.values())
        binary_distribution = {
            cmd_type: count
            for cmd_type, count in self.binary_cmd_type_counts.items()
        }
        
        # Calculate binary protocol health metrics
        checksum_error_rate = self._calculate_error_rate(self.checksum_errors, 60.0, now)
        parse_error_rate = self._calculate_error_rate(self.parse_errors, 60.0, now)
        
        # Calculate protocol success rate
        if self.total_binary_packets > 0:
            protocol_success_rate = (self.successful_binary_packets / self.total_binary_packets) * 100.0
        else:
            protocol_success_rate = 100.0
        
        return TelemetryMetrics(
            binary_packet_rate_1s=binary_rate_1s,
            binary_packet_rate_10s=binary_rate_10s,
            binary_packet_rate_60s=binary_rate_60s,
            mavlink_packet_rate_1s=mavlink_rate_1s,
            mavlink_packet_rate_10s=mavlink_rate_10s,
            mavlink_packet_rate_60s=mavlink_rate_60s,
            avg_rssi=avg_rssi,
            avg_snr=avg_snr,
            drop_rate=drop_rate,
            packets_lost=self.packets_lost,
            packets_received=self.packets_received,
            latency_avg=latency_avg,
            latency_min=latency_min,
            latency_max=latency_max,
            latency_samples=latency_samples,
            mavlink_msg_type_distribution=mavlink_distribution,
            binary_cmd_type_distribution=binary_distribution,
            checksum_error_rate=checksum_error_rate,
            parse_error_rate=parse_error_rate,
            protocol_success_rate=protocol_success_rate,
            buffer_overflow_count=self.buffer_overflows,
            timeout_error_count=self.timeout_errors,
            timestamp=now
        )
    
    def _calculate_rate(self, timestamps: Deque[float], window_seconds: float, now: float) -> float:
        """
        Calculate packet rate over a time window.
        
        Args:
            timestamps: Deque of packet timestamps
            window_seconds: Time window in seconds
            now: Current timestamp
            
        Returns:
            Packets per second over the window
        """
        # Count packets within the window
        count = sum(1 for t in timestamps if now - t <= window_seconds)
        
        # Calculate rate
        return count / window_seconds if window_seconds > 0 else 0.0
    
    def _calculate_error_rate(self, error_timestamps: Deque[float], window_seconds: float, now: float) -> float:
        """
        Calculate error rate (errors per minute) over a time window.
        
        Args:
            error_timestamps: Deque of error timestamps
            window_seconds: Time window in seconds
            now: Current timestamp
            
        Returns:
            Errors per minute over the window
        """
        # Count errors within the window
        count = sum(1 for t in error_timestamps if now - t <= window_seconds)
        
        # Convert to errors per minute
        return (count / window_seconds) * 60.0 if window_seconds > 0 else 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics summary.
        
        Returns:
            Dictionary with all tracked statistics
        """
        metrics = self.get_metrics()
        
        return {
            'binary_packet_rate_1s': metrics.binary_packet_rate_1s,
            'binary_packet_rate_10s': metrics.binary_packet_rate_10s,
            'binary_packet_rate_60s': metrics.binary_packet_rate_60s,
            'mavlink_packet_rate_1s': metrics.mavlink_packet_rate_1s,
            'mavlink_packet_rate_10s': metrics.mavlink_packet_rate_10s,
            'mavlink_packet_rate_60s': metrics.mavlink_packet_rate_60s,
            'avg_rssi': metrics.avg_rssi,
            'avg_snr': metrics.avg_snr,
            'drop_rate': metrics.drop_rate,
            'packets_lost': metrics.packets_lost,
            'packets_received': metrics.packets_received,
            'latency_avg_ms': metrics.latency_avg * 1000,
            'latency_min_ms': metrics.latency_min * 1000,
            'latency_max_ms': metrics.latency_max * 1000,
            'latency_samples': metrics.latency_samples,
            'mavlink_msg_types': len(metrics.mavlink_msg_type_distribution),
            'binary_cmd_types': len(metrics.binary_cmd_type_distribution),
            'checksum_error_rate': metrics.checksum_error_rate,
            'parse_error_rate': metrics.parse_error_rate,
            'protocol_success_rate': metrics.protocol_success_rate,
            'uptime_seconds': time.time() - self.start_time
        }
    
    def reset_stats(self):
        """Reset all statistics counters and buffers."""
        self.binary_packets_1s.clear()
        self.binary_packets_10s.clear()
        self.binary_packets_60s.clear()
        self.mavlink_packets_1s.clear()
        self.mavlink_packets_10s.clear()
        self.mavlink_packets_60s.clear()
        self.rssi_values.clear()
        self.snr_values.clear()
        self.mavlink_msg_type_counts.clear()
        self.binary_cmd_type_counts.clear()
        self.sequence_numbers.clear()
        self.packets_lost = 0
        self.packets_received = 0
        self.command_times.clear()
        self.latencies.clear()
        self.checksum_errors.clear()
        self.parse_errors.clear()
        self.buffer_overflows = 0
        self.timeout_errors = 0
        self.total_binary_packets = 0
        self.successful_binary_packets = 0
        self.start_time = time.time()
        
        logger.info("Metrics calculator statistics reset")
    
    def calculate_throughput(self, entries: List[EnhancedLogEntry], 
                            window_seconds: float = 1.0) -> List[float]:
        """
        Calculate throughput in bytes/second over time windows.
        
        Uses packet_size field from enhanced format. Returns empty list
        for legacy format (packet_size=0).
        
        Args:
            entries: List of EnhancedLogEntry objects
            window_seconds: Time window in seconds for throughput calculation
            
        Returns:
            List of throughput values in bytes/second for each window.
            Empty list if legacy format or no data.
            
        Requirements: 3.2
        """
        # Return empty list if no entries or legacy format
        if not entries or entries[0].packet_size == 0:
            return []
        
        throughput = []
        window_start_ms = entries[0].timestamp_ms
        window_bytes = 0
        window_ms = window_seconds * 1000
        
        for entry in entries:
            # Check if we've moved to a new window
            if entry.timestamp_ms - window_start_ms >= window_ms:
                # Calculate throughput for completed window
                actual_duration_s = (entry.timestamp_ms - window_start_ms) / 1000.0
                if actual_duration_s > 0:
                    throughput.append(window_bytes / actual_duration_s)
                
                # Start new window
                window_start_ms = entry.timestamp_ms
                window_bytes = 0
            
            # Accumulate bytes in current window
            window_bytes += entry.packet_size
        
        # Add final window if it has data
        if window_bytes > 0 and entries:
            final_duration_s = (entries[-1].timestamp_ms - window_start_ms) / 1000.0
            if final_duration_s > 0:
                throughput.append(window_bytes / final_duration_s)
        
        return throughput
    
    def calculate_end_to_end_latency(self, entries: List[EnhancedLogEntry]) -> List[float]:
        """
        Calculate end-to-end latency from tx_timestamp to reception.
        
        Uses tx_timestamp field from enhanced format. Returns empty list
        for legacy format or entries without tx_timestamp.
        
        Filters out invalid latencies (negative or > 10 seconds).
        
        Args:
            entries: List of EnhancedLogEntry objects
            
        Returns:
            List of latency values in seconds.
            Empty list if legacy format or no valid tx_timestamp data.
            
        Requirements: 3.3
        """
        latencies = []
        
        for entry in entries:
            # Skip entries without tx_timestamp (legacy format or unavailable)
            if entry.tx_timestamp > 0:
                # Calculate latency in milliseconds
                latency_ms = entry.timestamp_ms - entry.tx_timestamp
                
                # Filter out invalid latencies
                # Valid range: 0 to 10000 ms (0 to 10 seconds)
                if 0 < latency_ms < 10000:
                    # Convert to seconds
                    latencies.append(latency_ms / 1000.0)
        
        return latencies
    
    def detect_queue_congestion(self, entries: List[EnhancedLogEntry], 
                               threshold: int = 20) -> List[Tuple[int, int]]:
        """
        Detect queue congestion events.
        
        Uses queue_depth field from enhanced format. Identifies events
        where queue_depth exceeds the specified threshold.
        
        Args:
            entries: List of EnhancedLogEntry objects
            threshold: Queue depth threshold for congestion detection (default 20)
            
        Returns:
            List of (timestamp_ms, queue_depth) tuples where queue_depth > threshold.
            Empty list if legacy format or no congestion events.
            
        Requirements: 3.4
        """
        congestion_events = []
        
        for entry in entries:
            # Check if queue depth exceeds threshold
            if entry.queue_depth > threshold:
                congestion_events.append((entry.timestamp_ms, entry.queue_depth))
        
        return congestion_events
    
    def correlate_errors_with_rssi(self, entries: List[EnhancedLogEntry]) -> Dict[str, List[Tuple[float, int]]]:
        """
        Correlate error rates with RSSI values.
        
        Uses errors field from enhanced format. Categorizes errors by
        link quality (good: RSSI > -85 dBm, poor: RSSI <= -85 dBm).
        
        Calculates error deltas between consecutive entries to determine
        new errors that occurred.
        
        Args:
            entries: List of EnhancedLogEntry objects
            
        Returns:
            Dictionary with 'good_link' and 'poor_link' keys, each containing
            a list of (rssi_dbm, error_delta) tuples.
            Empty lists if legacy format or no error data.
            
        Requirements: 3.5
        """
        good_link = []  # RSSI > -85 dBm
        poor_link = []  # RSSI <= -85 dBm
        
        prev_errors = 0
        
        for entry in entries:
            # Calculate error delta (new errors since last entry)
            error_delta = entry.errors - prev_errors
            prev_errors = entry.errors
            
            # Categorize by link quality
            if entry.rssi_dbm > -85:
                good_link.append((entry.rssi_dbm, error_delta))
            else:
                poor_link.append((entry.rssi_dbm, error_delta))
        
        return {
            'good_link': good_link,
            'poor_link': poor_link
        }
    
    def get_performance_metrics(self, entries: List[EnhancedLogEntry]) -> PerformanceMetrics:
        """
        Calculate all enhanced performance metrics from CSV log entries.
        
        Computes throughput, latency, queue congestion, and error correlation
        metrics. Handles legacy format gracefully with None or 0 values.
        
        Args:
            entries: List of EnhancedLogEntry objects
            
        Returns:
            PerformanceMetrics object with all calculated metrics
            
        Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
        """
        # Calculate throughput metrics
        throughput_values = self.calculate_throughput(entries)
        if throughput_values:
            avg_throughput_bps = statistics.mean(throughput_values)
            peak_throughput_bps = max(throughput_values)
            min_throughput_bps = min(throughput_values)
        else:
            avg_throughput_bps = 0.0
            peak_throughput_bps = 0.0
            min_throughput_bps = 0.0
        
        # Calculate latency metrics
        latency_values = self.calculate_end_to_end_latency(entries)
        if latency_values:
            # Convert to milliseconds for metrics
            latency_ms = [l * 1000 for l in latency_values]
            avg_latency_ms = statistics.mean(latency_ms)
            p50_latency_ms = statistics.median(latency_ms)
            
            # Calculate percentiles
            sorted_latencies = sorted(latency_ms)
            n = len(sorted_latencies)
            p95_idx = int(n * 0.95)
            p99_idx = int(n * 0.99)
            p95_latency_ms = sorted_latencies[p95_idx] if p95_idx < n else sorted_latencies[-1]
            p99_latency_ms = sorted_latencies[p99_idx] if p99_idx < n else sorted_latencies[-1]
            max_latency_ms = max(latency_ms)
        else:
            avg_latency_ms = 0.0
            p50_latency_ms = 0.0
            p95_latency_ms = 0.0
            p99_latency_ms = 0.0
            max_latency_ms = 0.0
        
        # Calculate queue metrics
        queue_depths = [entry.queue_depth for entry in entries if entry.queue_depth > 0]
        if queue_depths:
            avg_queue_depth = statistics.mean(queue_depths)
            max_queue_depth = max(queue_depths)
        else:
            avg_queue_depth = 0.0
            max_queue_depth = 0
        
        congestion_events_list = self.detect_queue_congestion(entries)
        congestion_events = len(congestion_events_list)
        
        # Calculate congestion duration
        if congestion_events_list:
            # Group consecutive congestion events
            congestion_duration_ms = 0
            prev_timestamp = None
            for timestamp_ms, _ in congestion_events_list:
                if prev_timestamp is not None:
                    # If events are close together (< 1 second), count as continuous
                    if timestamp_ms - prev_timestamp < 1000:
                        congestion_duration_ms += (timestamp_ms - prev_timestamp)
                prev_timestamp = timestamp_ms
        else:
            congestion_duration_ms = 0
        
        # Calculate error metrics
        total_errors = entries[-1].errors if entries else 0
        
        # Calculate error rate per minute
        if entries and len(entries) > 1:
            duration_minutes = (entries[-1].timestamp_ms - entries[0].timestamp_ms) / 60000.0
            error_rate_per_minute = total_errors / duration_minutes if duration_minutes > 0 else 0.0
        else:
            error_rate_per_minute = 0.0
        
        # Calculate errors by link quality
        error_correlation = self.correlate_errors_with_rssi(entries)
        errors_during_good_link = sum(delta for _, delta in error_correlation['good_link'])
        errors_during_poor_link = sum(delta for _, delta in error_correlation['poor_link'])
        
        return PerformanceMetrics(
            avg_throughput_bps=avg_throughput_bps,
            peak_throughput_bps=peak_throughput_bps,
            min_throughput_bps=min_throughput_bps,
            avg_latency_ms=avg_latency_ms,
            p50_latency_ms=p50_latency_ms,
            p95_latency_ms=p95_latency_ms,
            p99_latency_ms=p99_latency_ms,
            max_latency_ms=max_latency_ms,
            avg_queue_depth=avg_queue_depth,
            max_queue_depth=max_queue_depth,
            congestion_events=congestion_events,
            congestion_duration_ms=congestion_duration_ms,
            total_errors=total_errors,
            error_rate_per_minute=error_rate_per_minute,
            errors_during_good_link=errors_during_good_link,
            errors_during_poor_link=errors_during_poor_link
        )
