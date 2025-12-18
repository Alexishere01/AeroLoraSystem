"""
Mode Comparison Module

This module provides comparison and reporting functionality for direct vs relay
operating modes. It calculates percentage differences between modes and generates
comprehensive comparison summaries.

Requirements: 6.4
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
import logging

# Handle both relative and absolute imports
try:
    from .mode_specific_metrics import ModeMetrics
    from .mode_tracker import OperatingMode
except ImportError:
    from mode_specific_metrics import ModeMetrics
    from mode_tracker import OperatingMode

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MetricComparison:
    """
    Comparison of a single metric between direct and relay modes.
    
    Requirements: 6.4
    """
    metric_name: str
    direct_value: float
    relay_value: float
    difference: float           # relay - direct
    percent_difference: float   # ((relay - direct) / direct) * 100
    unit: str = ""
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        sign = "+" if self.difference >= 0 else ""
        return (f"{self.metric_name}: Direct={self.direct_value:.2f}{self.unit}, "
                f"Relay={self.relay_value:.2f}{self.unit}, "
                f"Diff={sign}{self.percent_difference:.1f}%")


@dataclass
class ModeComparisonReport:
    """
    Comprehensive comparison report between direct and relay modes.
    
    Contains all metric comparisons and summary statistics.
    
    Requirements: 6.4
    """
    # Packet rate comparisons
    binary_packet_rate_1s: MetricComparison
    mavlink_packet_rate_1s: MetricComparison
    
    # Link quality comparisons
    avg_rssi: MetricComparison
    avg_snr: MetricComparison
    
    # Packet loss comparison
    drop_rate: MetricComparison
    
    # Latency comparisons
    latency_avg: MetricComparison
    relay_additional_latency: Optional[MetricComparison] = None
    
    # Protocol health comparisons
    checksum_error_rate: MetricComparison = None
    protocol_success_rate: MetricComparison = None
    
    # Time spent in each mode
    direct_time_seconds: float = 0.0
    relay_time_seconds: float = 0.0
    direct_time_percentage: float = 0.0
    relay_time_percentage: float = 0.0
    
    # Relay-specific metrics (only available in relay mode)
    packets_relayed: int = 0
    bytes_relayed: int = 0
    active_peer_relays: int = 0
    
    # Summary
    overall_assessment: str = ""
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        return (f"ModeComparisonReport(\n"
                f"  Packet Rate: {self.mavlink_packet_rate_1s}\n"
                f"  RSSI: {self.avg_rssi}\n"
                f"  SNR: {self.avg_snr}\n"
                f"  Drop Rate: {self.drop_rate}\n"
                f"  Latency: {self.latency_avg}\n"
                f"  Assessment: {self.overall_assessment}\n"
                f")")


class ModeComparator:
    """
    Compares metrics between direct and relay operating modes.
    
    This class takes metrics from both modes and calculates percentage
    differences, generates comparison reports, and provides summary
    assessments of relative performance.
    
    Features:
    - Percentage difference calculation for all metrics
    - Comprehensive comparison reports
    - Overall performance assessment
    - Formatted text output for logging and display
    
    Requirements: 6.4
    """
    
    def __init__(self):
        """Initialize the mode comparator."""
        logger.info("Mode comparator initialized")
    
    def compare_modes(self, direct_metrics: Optional[ModeMetrics], 
                     relay_metrics: Optional[ModeMetrics]) -> Optional[ModeComparisonReport]:
        """
        Compare metrics between direct and relay modes.
        
        Calculates percentage differences for all metrics and generates
        a comprehensive comparison report.
        
        Args:
            direct_metrics: Metrics from direct mode
            relay_metrics: Metrics from relay mode
            
        Returns:
            ModeComparisonReport with all comparisons, or None if insufficient data
            
        Requirements: 6.4
        """
        # Validate inputs
        if not direct_metrics or not relay_metrics:
            logger.warning("Cannot compare modes: missing metrics data")
            return None
        
        if direct_metrics.mode != OperatingMode.DIRECT:
            logger.warning(f"Expected direct mode metrics, got {direct_metrics.mode.name}")
            return None
        
        if relay_metrics.mode != OperatingMode.RELAY:
            logger.warning(f"Expected relay mode metrics, got {relay_metrics.mode.name}")
            return None
        
        # Compare packet rates
        binary_rate_comp = self._compare_metric(
            "Binary Packet Rate (1s)",
            direct_metrics.binary_packet_rate_1s,
            relay_metrics.binary_packet_rate_1s,
            "pkt/s"
        )
        
        mavlink_rate_comp = self._compare_metric(
            "MAVLink Packet Rate (1s)",
            direct_metrics.mavlink_packet_rate_1s,
            relay_metrics.mavlink_packet_rate_1s,
            "pkt/s"
        )
        
        # Compare link quality
        rssi_comp = self._compare_metric(
            "Average RSSI",
            direct_metrics.avg_rssi,
            relay_metrics.avg_rssi,
            "dBm"
        )
        
        snr_comp = self._compare_metric(
            "Average SNR",
            direct_metrics.avg_snr,
            relay_metrics.avg_snr,
            "dB"
        )
        
        # Compare packet loss
        drop_rate_comp = self._compare_metric(
            "Packet Drop Rate",
            direct_metrics.drop_rate,
            relay_metrics.drop_rate,
            "%"
        )
        
        # Compare latency
        latency_comp = self._compare_metric(
            "Average Latency",
            direct_metrics.latency_avg * 1000,  # Convert to ms
            relay_metrics.latency_avg * 1000,
            "ms"
        )
        
        # Compare relay additional latency (if available)
        relay_latency_comp = None
        if relay_metrics.relay_latency_samples > 0:
            relay_latency_comp = MetricComparison(
                metric_name="Relay Additional Latency",
                direct_value=0.0,
                relay_value=relay_metrics.relay_latency_avg * 1000,  # Convert to ms
                difference=relay_metrics.relay_latency_avg * 1000,
                percent_difference=100.0,  # Always 100% increase from 0
                unit="ms"
            )
        
        # Compare protocol health
        checksum_comp = self._compare_metric(
            "Checksum Error Rate",
            direct_metrics.checksum_error_rate,
            relay_metrics.checksum_error_rate,
            "err/min"
        )
        
        success_comp = self._compare_metric(
            "Protocol Success Rate",
            direct_metrics.protocol_success_rate,
            relay_metrics.protocol_success_rate,
            "%"
        )
        
        # Calculate time percentages
        total_time = direct_metrics.time_in_mode_seconds + relay_metrics.time_in_mode_seconds
        direct_pct = (direct_metrics.time_in_mode_seconds / total_time * 100.0) if total_time > 0 else 0.0
        relay_pct = (relay_metrics.time_in_mode_seconds / total_time * 100.0) if total_time > 0 else 0.0
        
        # Generate overall assessment
        assessment = self._generate_assessment(
            mavlink_rate_comp, rssi_comp, snr_comp, drop_rate_comp, latency_comp
        )
        
        # Create comparison report
        report = ModeComparisonReport(
            binary_packet_rate_1s=binary_rate_comp,
            mavlink_packet_rate_1s=mavlink_rate_comp,
            avg_rssi=rssi_comp,
            avg_snr=snr_comp,
            drop_rate=drop_rate_comp,
            latency_avg=latency_comp,
            relay_additional_latency=relay_latency_comp,
            checksum_error_rate=checksum_comp,
            protocol_success_rate=success_comp,
            direct_time_seconds=direct_metrics.time_in_mode_seconds,
            relay_time_seconds=relay_metrics.time_in_mode_seconds,
            direct_time_percentage=direct_pct,
            relay_time_percentage=relay_pct,
            packets_relayed=relay_metrics.packets_relayed,
            bytes_relayed=relay_metrics.bytes_relayed,
            active_peer_relays=relay_metrics.active_peer_relays,
            overall_assessment=assessment
        )
        
        logger.info(f"Mode comparison completed: {assessment}")
        
        return report
    
    def _compare_metric(self, name: str, direct_value: float, relay_value: float, 
                       unit: str = "") -> MetricComparison:
        """
        Compare a single metric between modes.
        
        Args:
            name: Metric name
            direct_value: Value in direct mode
            relay_value: Value in relay mode
            unit: Unit of measurement
            
        Returns:
            MetricComparison object
            
        Requirements: 6.4
        """
        difference = relay_value - direct_value
        
        # Calculate percentage difference
        if direct_value != 0:
            percent_diff = (difference / abs(direct_value)) * 100.0
        else:
            # Handle division by zero
            if relay_value != 0:
                percent_diff = 100.0 if relay_value > 0 else -100.0
            else:
                percent_diff = 0.0
        
        return MetricComparison(
            metric_name=name,
            direct_value=direct_value,
            relay_value=relay_value,
            difference=difference,
            percent_difference=percent_diff,
            unit=unit
        )
    
    def _generate_assessment(self, packet_rate: MetricComparison, rssi: MetricComparison,
                           snr: MetricComparison, drop_rate: MetricComparison,
                           latency: MetricComparison) -> str:
        """
        Generate an overall assessment of relay mode performance.
        
        Args:
            packet_rate: Packet rate comparison
            rssi: RSSI comparison
            snr: SNR comparison
            drop_rate: Drop rate comparison
            latency: Latency comparison
            
        Returns:
            Assessment string
            
        Requirements: 6.4
        """
        issues = []
        improvements = []
        
        # Check packet rate
        if packet_rate.percent_difference < -10:
            issues.append(f"packet rate decreased by {abs(packet_rate.percent_difference):.1f}%")
        elif packet_rate.percent_difference > 10:
            improvements.append(f"packet rate increased by {packet_rate.percent_difference:.1f}%")
        
        # Check RSSI (higher is better, but values are negative)
        if rssi.percent_difference < -10:
            issues.append(f"RSSI degraded by {abs(rssi.percent_difference):.1f}%")
        elif rssi.percent_difference > 10:
            improvements.append(f"RSSI improved by {rssi.percent_difference:.1f}%")
        
        # Check SNR (higher is better)
        if snr.percent_difference < -10:
            issues.append(f"SNR degraded by {abs(snr.percent_difference):.1f}%")
        elif snr.percent_difference > 10:
            improvements.append(f"SNR improved by {snr.percent_difference:.1f}%")
        
        # Check drop rate (lower is better)
        if drop_rate.percent_difference > 10:
            issues.append(f"packet loss increased by {drop_rate.percent_difference:.1f}%")
        elif drop_rate.percent_difference < -10:
            improvements.append(f"packet loss decreased by {abs(drop_rate.percent_difference):.1f}%")
        
        # Check latency (lower is better)
        if latency.percent_difference > 10:
            issues.append(f"latency increased by {latency.percent_difference:.1f}%")
        elif latency.percent_difference < -10:
            improvements.append(f"latency decreased by {abs(latency.percent_difference):.1f}%")
        
        # Generate assessment
        if len(issues) > 2:
            return f"Relay mode shows degraded performance: {', '.join(issues)}"
        elif len(issues) > 0:
            return f"Relay mode has minor issues: {', '.join(issues)}"
        elif len(improvements) > 0:
            return f"Relay mode performing well: {', '.join(improvements)}"
        else:
            return "Relay mode performance comparable to direct mode"
    
    def format_comparison_report(self, report: ModeComparisonReport) -> str:
        """
        Format a comparison report as human-readable text.
        
        Args:
            report: Mode comparison report
            
        Returns:
            Formatted text report
            
        Requirements: 6.4
        """
        lines = []
        lines.append("=" * 80)
        lines.append("MODE COMPARISON REPORT: DIRECT vs RELAY")
        lines.append("=" * 80)
        lines.append("")
        
        # Time distribution
        lines.append("Time Distribution:")
        lines.append(f"  Direct Mode: {report.direct_time_seconds:.1f}s ({report.direct_time_percentage:.1f}%)")
        lines.append(f"  Relay Mode:  {report.relay_time_seconds:.1f}s ({report.relay_time_percentage:.1f}%)")
        lines.append("")
        
        # Packet rates
        lines.append("Packet Rates:")
        lines.append(f"  {self._format_comparison(report.binary_packet_rate_1s)}")
        lines.append(f"  {self._format_comparison(report.mavlink_packet_rate_1s)}")
        lines.append("")
        
        # Link quality
        lines.append("Link Quality:")
        lines.append(f"  {self._format_comparison(report.avg_rssi)}")
        lines.append(f"  {self._format_comparison(report.avg_snr)}")
        lines.append("")
        
        # Packet loss
        lines.append("Packet Loss:")
        lines.append(f"  {self._format_comparison(report.drop_rate)}")
        lines.append("")
        
        # Latency
        lines.append("Latency:")
        lines.append(f"  {self._format_comparison(report.latency_avg)}")
        if report.relay_additional_latency:
            lines.append(f"  {self._format_comparison(report.relay_additional_latency)}")
        lines.append("")
        
        # Protocol health
        lines.append("Protocol Health:")
        if report.checksum_error_rate:
            lines.append(f"  {self._format_comparison(report.checksum_error_rate)}")
        if report.protocol_success_rate:
            lines.append(f"  {self._format_comparison(report.protocol_success_rate)}")
        lines.append("")
        
        # Relay-specific metrics
        if report.packets_relayed > 0:
            lines.append("Relay-Specific Metrics:")
            lines.append(f"  Packets Relayed: {report.packets_relayed}")
            lines.append(f"  Bytes Relayed: {report.bytes_relayed}")
            lines.append(f"  Active Peer Relays: {report.active_peer_relays}")
            lines.append("")
        
        # Overall assessment
        lines.append("Overall Assessment:")
        lines.append(f"  {report.overall_assessment}")
        lines.append("")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def _format_comparison(self, comp: MetricComparison) -> str:
        """
        Format a single metric comparison.
        
        Args:
            comp: Metric comparison
            
        Returns:
            Formatted string
        """
        sign = "+" if comp.difference >= 0 else ""
        return (f"{comp.metric_name}: "
                f"Direct={comp.direct_value:.2f}{comp.unit}, "
                f"Relay={comp.relay_value:.2f}{comp.unit}, "
                f"Diff={sign}{comp.percent_difference:.1f}%")
    
    def get_comparison_summary(self, report: ModeComparisonReport) -> Dict[str, Any]:
        """
        Get a dictionary summary of the comparison report.
        
        Args:
            report: Mode comparison report
            
        Returns:
            Dictionary with comparison summary
            
        Requirements: 6.4
        """
        summary = {
            'time_distribution': {
                'direct_seconds': report.direct_time_seconds,
                'relay_seconds': report.relay_time_seconds,
                'direct_percentage': report.direct_time_percentage,
                'relay_percentage': report.relay_time_percentage
            },
            'packet_rates': {
                'binary_rate_diff_pct': report.binary_packet_rate_1s.percent_difference,
                'mavlink_rate_diff_pct': report.mavlink_packet_rate_1s.percent_difference
            },
            'link_quality': {
                'rssi_diff_pct': report.avg_rssi.percent_difference,
                'snr_diff_pct': report.avg_snr.percent_difference
            },
            'packet_loss': {
                'drop_rate_diff_pct': report.drop_rate.percent_difference
            },
            'latency': {
                'latency_diff_pct': report.latency_avg.percent_difference,
                'relay_additional_latency_ms': (report.relay_additional_latency.relay_value 
                                               if report.relay_additional_latency else 0.0)
            },
            'relay_metrics': {
                'packets_relayed': report.packets_relayed,
                'bytes_relayed': report.bytes_relayed,
                'active_peer_relays': report.active_peer_relays
            },
            'assessment': report.overall_assessment
        }
        
        return summary
