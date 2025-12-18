"""
Report Generator Module

This module provides comprehensive report generation capabilities for telemetry
validation system, including summary reports, export functionality, and query tools.

Requirements: 5.2, 5.3, 10.1, 10.2, 10.3, 10.4, 10.5
"""

import csv
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import logging

# Handle both relative and absolute imports
try:
    from .validation_engine import ValidationEngine, Violation, Severity
    from .metrics_calculator import MetricsCalculator, TelemetryMetrics
    from .binary_protocol_parser import ParsedBinaryPacket, UartCommand
except ImportError:
    from validation_engine import ValidationEngine, Violation, Severity
    from metrics_calculator import MetricsCalculator, TelemetryMetrics
    from binary_protocol_parser import ParsedBinaryPacket, UartCommand

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Comprehensive report generator for telemetry validation system.
    
    This class generates summary reports with key metrics, validation results,
    and binary protocol health metrics. Reports can be formatted as text or HTML.
    
    Features:
    - Summary reports with key metrics
    - Validation results and violations
    - Binary protocol health metrics
    - Text and HTML formatting
    - Export to CSV, JSON, .tlog, and .binlog formats
    - Query tools for filtering by time range, message type, and system ID
    
    Requirements: 5.2, 5.3, 10.1, 10.2, 10.3, 10.4, 10.5
    """
    
    def __init__(self, 
                 validation_engine: Optional[ValidationEngine] = None,
                 metrics_calculator: Optional[MetricsCalculator] = None):
        """
        Initialize the report generator.
        
        Args:
            validation_engine: ValidationEngine instance for violation data
            metrics_calculator: MetricsCalculator instance for metrics data
        """
        self.validation_engine = validation_engine
        self.metrics_calculator = metrics_calculator
        
        logger.info("Report generator initialized")
    
    def generate_summary_report(self, 
                                format: str = 'text',
                                output_file: Optional[str] = None) -> str:
        """
        Generate a comprehensive summary report.
        
        Includes key metrics, validation results, violations, and binary
        protocol health metrics.
        
        Args:
            format: Output format ('text' or 'html')
            output_file: Optional file path to write report to
            
        Returns:
            Report content as string
            
        Requirements: 5.2
        """
        if format == 'html':
            report = self._generate_html_report()
        else:
            report = self._generate_text_report()
        
        # Write to file if specified
        if output_file:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(report)
                logger.info(f"Summary report written to {output_file}")
            except Exception as e:
                logger.error(f"Error writing report to file: {e}")
        
        return report
    
    def _generate_text_report(self) -> str:
        """
        Generate a text-formatted summary report.
        
        Returns:
            Report content as plain text string
            
        Requirements: 5.2
        """
        lines = []
        lines.append("=" * 80)
        lines.append("TELEMETRY VALIDATION SYSTEM - SUMMARY REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # Metrics section
        if self.metrics_calculator:
            lines.append("-" * 80)
            lines.append("TELEMETRY METRICS")
            lines.append("-" * 80)
            
            metrics = self.metrics_calculator.get_metrics()
            
            lines.append("\nPacket Rates:")
            lines.append(f"  Binary Protocol (1s/10s/60s): {metrics.binary_packet_rate_1s:.1f} / "
                        f"{metrics.binary_packet_rate_10s:.1f} / {metrics.binary_packet_rate_60s:.1f} pps")
            lines.append(f"  MAVLink Messages (1s/10s/60s): {metrics.mavlink_packet_rate_1s:.1f} / "
                        f"{metrics.mavlink_packet_rate_10s:.1f} / {metrics.mavlink_packet_rate_60s:.1f} pps")
            
            lines.append("\nLink Quality:")
            lines.append(f"  Average RSSI: {metrics.avg_rssi:.1f} dBm")
            lines.append(f"  Average SNR: {metrics.avg_snr:.1f} dB")
            lines.append(f"  Packet Loss Rate: {metrics.drop_rate:.2f}%")
            lines.append(f"  Packets Lost: {metrics.packets_lost}")
            lines.append(f"  Packets Received: {metrics.packets_received}")
            
            lines.append("\nCommand Latency:")
            if metrics.latency_samples > 0:
                lines.append(f"  Average: {metrics.latency_avg * 1000:.2f} ms")
                lines.append(f"  Min: {metrics.latency_min * 1000:.2f} ms")
                lines.append(f"  Max: {metrics.latency_max * 1000:.2f} ms")
                lines.append(f"  Samples: {metrics.latency_samples}")
            else:
                lines.append("  No latency data available")
            
            lines.append("\nBinary Protocol Health:")
            lines.append(f"  Checksum Error Rate: {metrics.checksum_error_rate:.2f} errors/min")
            lines.append(f"  Parse Error Rate: {metrics.parse_error_rate:.2f} errors/min")
            lines.append(f"  Protocol Success Rate: {metrics.protocol_success_rate:.2f}%")
            lines.append(f"  Buffer Overflows: {metrics.buffer_overflow_count}")
            lines.append(f"  Timeout Errors: {metrics.timeout_error_count}")
            
            lines.append("\nMAVLink Message Distribution:")
            if metrics.mavlink_msg_type_distribution:
                total_mavlink = sum(metrics.mavlink_msg_type_distribution.values())
                for msg_type, count in sorted(metrics.mavlink_msg_type_distribution.items(), 
                                             key=lambda x: x[1], reverse=True)[:10]:
                    percentage = (count / total_mavlink * 100) if total_mavlink > 0 else 0
                    lines.append(f"  {msg_type}: {count} ({percentage:.1f}%)")
            else:
                lines.append("  No MAVLink messages received")
            
            lines.append("\nBinary Protocol Command Distribution:")
            if metrics.binary_cmd_type_distribution:
                total_binary = sum(metrics.binary_cmd_type_distribution.values())
                for cmd_type, count in sorted(metrics.binary_cmd_type_distribution.items(), 
                                             key=lambda x: x[1], reverse=True):
                    percentage = (count / total_binary * 100) if total_binary > 0 else 0
                    lines.append(f"  {cmd_type}: {count} ({percentage:.1f}%)")
            else:
                lines.append("  No binary protocol packets received")
            
            lines.append("")
        
        # Validation section
        if self.validation_engine:
            lines.append("-" * 80)
            lines.append("VALIDATION RESULTS")
            lines.append("-" * 80)
            
            stats = self.validation_engine.get_stats()
            
            lines.append(f"\nTotal Checks: {stats['total_checks']}")
            lines.append(f"Total Violations: {stats['total_violations']}")
            
            lines.append("\nViolations by Severity:")
            lines.append(f"  INFO: {stats['violations_by_severity'][Severity.INFO]}")
            lines.append(f"  WARNING: {stats['violations_by_severity'][Severity.WARNING]}")
            lines.append(f"  CRITICAL: {stats['violations_by_severity'][Severity.CRITICAL]}")
            
            lines.append("\nViolations by Rule:")
            if stats['violations_by_rule']:
                for rule_name, count in sorted(stats['violations_by_rule'].items(), 
                                              key=lambda x: x[1], reverse=True):
                    if count > 0:
                        lines.append(f"  {rule_name}: {count}")
            else:
                lines.append("  No violations recorded")
            
            # Recent violations
            recent_violations = self.validation_engine.get_violations()[-10:]
            if recent_violations:
                lines.append("\nRecent Violations (last 10):")
                for v in recent_violations:
                    timestamp_str = datetime.fromtimestamp(v.timestamp).strftime('%H:%M:%S')
                    lines.append(f"  [{timestamp_str}] {v.severity.name}: {v.rule_name}")
                    lines.append(f"    {v.field} = {v.actual_value} (threshold: {v.threshold})")
                    if v.description:
                        lines.append(f"    {v.description}")
            
            lines.append("")
        
        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def _generate_html_report(self) -> str:
        """
        Generate an HTML-formatted summary report.
        
        Returns:
            Report content as HTML string
            
        Requirements: 5.2
        """
        html_parts = []
        
        # HTML header
        html_parts.append("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Telemetry Validation Report</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }
        h2 {
            color: #555;
            border-bottom: 2px solid #ddd;
            padding-bottom: 5px;
            margin-top: 30px;
        }
        h3 {
            color: #666;
            margin-top: 20px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }
        th, td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #4CAF50;
            color: white;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }
        .metric-card {
            background-color: #f9f9f9;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #4CAF50;
        }
        .metric-label {
            font-weight: bold;
            color: #666;
            font-size: 0.9em;
        }
        .metric-value {
            font-size: 1.5em;
            color: #333;
            margin-top: 5px;
        }
        .severity-info { color: #2196F3; }
        .severity-warning { color: #FF9800; }
        .severity-critical { color: #F44336; }
        .timestamp {
            color: #999;
            font-size: 0.9em;
        }
        .violation-item {
            background-color: #fff3cd;
            padding: 10px;
            margin: 10px 0;
            border-left: 4px solid #ffc107;
            border-radius: 3px;
        }
        .violation-critical {
            background-color: #f8d7da;
            border-left-color: #dc3545;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Telemetry Validation System - Summary Report</h1>
        <p class="timestamp">Generated: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
""")
        
        # Metrics section
        if self.metrics_calculator:
            metrics = self.metrics_calculator.get_metrics()
            
            html_parts.append("""
        <h2>Telemetry Metrics</h2>
        
        <h3>Packet Rates</h3>
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-label">Binary Protocol (1s)</div>
                <div class="metric-value">""" + f"{metrics.binary_packet_rate_1s:.1f}" + """ pps</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Binary Protocol (10s)</div>
                <div class="metric-value">""" + f"{metrics.binary_packet_rate_10s:.1f}" + """ pps</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">MAVLink (1s)</div>
                <div class="metric-value">""" + f"{metrics.mavlink_packet_rate_1s:.1f}" + """ pps</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">MAVLink (10s)</div>
                <div class="metric-value">""" + f"{metrics.mavlink_packet_rate_10s:.1f}" + """ pps</div>
            </div>
        </div>
        
        <h3>Link Quality</h3>
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-label">Average RSSI</div>
                <div class="metric-value">""" + f"{metrics.avg_rssi:.1f}" + """ dBm</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Average SNR</div>
                <div class="metric-value">""" + f"{metrics.avg_snr:.1f}" + """ dB</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Packet Loss Rate</div>
                <div class="metric-value">""" + f"{metrics.drop_rate:.2f}" + """%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Packets Lost</div>
                <div class="metric-value">""" + f"{metrics.packets_lost}" + """</div>
            </div>
        </div>
        
        <h3>Binary Protocol Health</h3>
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-label">Success Rate</div>
                <div class="metric-value">""" + f"{metrics.protocol_success_rate:.2f}" + """%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Checksum Errors</div>
                <div class="metric-value">""" + f"{metrics.checksum_error_rate:.2f}" + """/min</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Parse Errors</div>
                <div class="metric-value">""" + f"{metrics.parse_error_rate:.2f}" + """/min</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Buffer Overflows</div>
                <div class="metric-value">""" + f"{metrics.buffer_overflow_count}" + """</div>
            </div>
        </div>
""")
            
            # MAVLink message distribution table
            if metrics.mavlink_msg_type_distribution:
                html_parts.append("""
        <h3>MAVLink Message Distribution</h3>
        <table>
            <tr>
                <th>Message Type</th>
                <th>Count</th>
                <th>Percentage</th>
            </tr>
""")
                total_mavlink = sum(metrics.mavlink_msg_type_distribution.values())
                for msg_type, count in sorted(metrics.mavlink_msg_type_distribution.items(), 
                                             key=lambda x: x[1], reverse=True)[:15]:
                    percentage = (count / total_mavlink * 100) if total_mavlink > 0 else 0
                    html_parts.append(f"""
            <tr>
                <td>{msg_type}</td>
                <td>{count}</td>
                <td>{percentage:.1f}%</td>
            </tr>
""")
                html_parts.append("        </table>\n")
        
        # Validation section
        if self.validation_engine:
            stats = self.validation_engine.get_stats()
            
            html_parts.append("""
        <h2>Validation Results</h2>
        
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-label">Total Checks</div>
                <div class="metric-value">""" + f"{stats['total_checks']}" + """</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Total Violations</div>
                <div class="metric-value">""" + f"{stats['total_violations']}" + """</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">INFO Violations</div>
                <div class="metric-value severity-info">""" + f"{stats['violations_by_severity'][Severity.INFO]}" + """</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">WARNING Violations</div>
                <div class="metric-value severity-warning">""" + f"{stats['violations_by_severity'][Severity.WARNING]}" + """</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">CRITICAL Violations</div>
                <div class="metric-value severity-critical">""" + f"{stats['violations_by_severity'][Severity.CRITICAL]}" + """</div>
            </div>
        </div>
""")
            
            # Recent violations
            recent_violations = self.validation_engine.get_violations()[-10:]
            if recent_violations:
                html_parts.append("""
        <h3>Recent Violations</h3>
""")
                for v in recent_violations:
                    timestamp_str = datetime.fromtimestamp(v.timestamp).strftime('%H:%M:%S')
                    severity_class = "violation-critical" if v.severity == Severity.CRITICAL else "violation-item"
                    html_parts.append(f"""
        <div class="{severity_class}">
            <strong class="severity-{v.severity.name.lower()}">[{v.severity.name}]</strong> 
            <strong>{v.rule_name}</strong> at {timestamp_str}<br>
            {v.field} = {v.actual_value} (threshold: {v.threshold})<br>
            <em>{v.description}</em>
        </div>
""")
        
        # HTML footer
        html_parts.append("""
    </div>
</body>
</html>
""")
        
        return "".join(html_parts)

    
    def export_to_csv(self,
                     log_file: str,
                     output_file: str,
                     start_time: Optional[float] = None,
                     end_time: Optional[float] = None,
                     msg_type: Optional[str] = None,
                     system_id: Optional[int] = None) -> int:
        """
        Export telemetry data to CSV with optional filtering.
        
        Reads from a JSON log file and exports to CSV format with
        time range and message type filtering.
        
        Args:
            log_file: Path to JSON log file to read from
            output_file: Path to output CSV file
            start_time: Optional start timestamp (Unix time)
            end_time: Optional end timestamp (Unix time)
            msg_type: Optional MAVLink message type filter
            system_id: Optional system ID filter
            
        Returns:
            Number of records exported
            
        Requirements: 10.1, 10.2, 5.3
        """
        try:
            # Read JSON log file
            with open(log_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Filter data
            filtered_data = self._filter_data(data, start_time, end_time, msg_type, system_id)
            
            if not filtered_data:
                logger.warning("No data matches the filter criteria")
                return 0
            
            # Write to CSV
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write headers
                writer.writerow([
                    'timestamp',
                    'msg_type',
                    'msg_id',
                    'system_id',
                    'component_id',
                    'rssi',
                    'snr',
                    'fields'
                ])
                
                # Write data rows
                for record in filtered_data:
                    writer.writerow([
                        record.get('timestamp', ''),
                        record.get('msg_type', ''),
                        record.get('msg_id', ''),
                        record.get('system_id', ''),
                        record.get('component_id', ''),
                        record.get('rssi', ''),
                        record.get('snr', ''),
                        json.dumps(record.get('fields', {}))
                    ])
            
            logger.info(f"Exported {len(filtered_data)} records to {output_file}")
            return len(filtered_data)
        
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            return 0
    
    def export_to_json(self,
                      log_file: str,
                      output_file: str,
                      start_time: Optional[float] = None,
                      end_time: Optional[float] = None,
                      msg_type: Optional[str] = None,
                      system_id: Optional[int] = None) -> int:
        """
        Export telemetry data to JSON with optional filtering.
        
        Reads from a JSON log file and exports filtered data to a new
        JSON file with structured data.
        
        Args:
            log_file: Path to JSON log file to read from
            output_file: Path to output JSON file
            start_time: Optional start timestamp (Unix time)
            end_time: Optional end timestamp (Unix time)
            msg_type: Optional MAVLink message type filter
            system_id: Optional system ID filter
            
        Returns:
            Number of records exported
            
        Requirements: 10.3, 5.3
        """
        try:
            # Read JSON log file
            with open(log_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Filter data
            filtered_data = self._filter_data(data, start_time, end_time, msg_type, system_id)
            
            if not filtered_data:
                logger.warning("No data matches the filter criteria")
                return 0
            
            # Write to JSON with structured format
            output_data = {
                'metadata': {
                    'export_time': datetime.now().isoformat(),
                    'source_file': log_file,
                    'filters': {
                        'start_time': start_time,
                        'end_time': end_time,
                        'msg_type': msg_type,
                        'system_id': system_id
                    },
                    'record_count': len(filtered_data)
                },
                'messages': filtered_data
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2)
            
            logger.info(f"Exported {len(filtered_data)} records to {output_file}")
            return len(filtered_data)
        
        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
            return 0
    
    def export_to_tlog(self,
                      log_file: str,
                      output_file: str,
                      start_time: Optional[float] = None,
                      end_time: Optional[float] = None,
                      system_id: Optional[int] = None) -> int:
        """
        Export MAVLink data to .tlog format.
        
        Reads from a JSON log file and exports raw MAVLink bytes to .tlog
        format compatible with QGroundControl and MAVProxy.
        
        Note: This requires the raw_mavlink_bytes field to be present in
        the log data. Only MAVLink messages are exported (not binary protocol).
        
        Args:
            log_file: Path to JSON log file to read from
            output_file: Path to output .tlog file
            start_time: Optional start timestamp (Unix time)
            end_time: Optional end timestamp (Unix time)
            system_id: Optional system ID filter
            
        Returns:
            Number of messages exported
            
        Requirements: 10.4
        """
        try:
            # Read JSON log file
            with open(log_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Filter data
            filtered_data = self._filter_data(data, start_time, end_time, None, system_id)
            
            if not filtered_data:
                logger.warning("No data matches the filter criteria")
                return 0
            
            # Write to .tlog (binary format)
            count = 0
            with open(output_file, 'wb') as f:
                for record in filtered_data:
                    # Check if raw MAVLink bytes are available
                    # Note: This would need to be stored in the log format
                    # For now, we'll skip records without raw bytes
                    if 'raw_mavlink_bytes' in record and record['raw_mavlink_bytes']:
                        # Convert hex string back to bytes if needed
                        raw_bytes = record['raw_mavlink_bytes']
                        if isinstance(raw_bytes, str):
                            raw_bytes = bytes.fromhex(raw_bytes)
                        elif isinstance(raw_bytes, list):
                            raw_bytes = bytes(raw_bytes)
                        
                        f.write(raw_bytes)
                        count += 1
            
            logger.info(f"Exported {count} MAVLink messages to {output_file}")
            return count
        
        except Exception as e:
            logger.error(f"Error exporting to .tlog: {e}")
            return 0
    
    def export_to_binlog(self,
                        binary_log_file: str,
                        output_file: str,
                        start_time: Optional[float] = None,
                        end_time: Optional[float] = None,
                        command_type: Optional[UartCommand] = None) -> int:
        """
        Export binary protocol packets to .binlog format.
        
        Reads from a binary protocol log file and exports filtered packets
        to a new .binlog file for debugging and replay.
        
        Args:
            binary_log_file: Path to binary protocol log file to read from
            output_file: Path to output .binlog file
            start_time: Optional start timestamp (Unix time)
            end_time: Optional end timestamp (Unix time)
            command_type: Optional binary protocol command type filter
            
        Returns:
            Number of packets exported
            
        Requirements: 10.5
        """
        try:
            # Read binary log file
            # Note: This assumes a JSON format for binary protocol logs
            # In practice, this might be a custom binary format
            with open(binary_log_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Filter data
            filtered_data = []
            for record in data:
                # Apply time filter
                if start_time and record.get('timestamp', 0) < start_time:
                    continue
                if end_time and record.get('timestamp', float('inf')) > end_time:
                    continue
                
                # Apply command type filter
                if command_type and record.get('command') != command_type.name:
                    continue
                
                filtered_data.append(record)
            
            if not filtered_data:
                logger.warning("No data matches the filter criteria")
                return 0
            
            # Write to .binlog (binary format)
            count = 0
            with open(output_file, 'wb') as f:
                for record in filtered_data:
                    # Write raw packet bytes
                    if 'raw_bytes' in record and record['raw_bytes']:
                        raw_bytes = record['raw_bytes']
                        if isinstance(raw_bytes, str):
                            raw_bytes = bytes.fromhex(raw_bytes)
                        elif isinstance(raw_bytes, list):
                            raw_bytes = bytes(raw_bytes)
                        
                        f.write(raw_bytes)
                        count += 1
            
            logger.info(f"Exported {count} binary protocol packets to {output_file}")
            return count
        
        except Exception as e:
            logger.error(f"Error exporting to .binlog: {e}")
            return 0
    
    def query_logs(self,
                   log_file: str,
                   start_time: Optional[float] = None,
                   end_time: Optional[float] = None,
                   msg_type: Optional[str] = None,
                   system_id: Optional[int] = None,
                   command_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query telemetry logs with filtering.
        
        Reads from a JSON log file and returns filtered records based on
        time range, message type, system ID, or binary protocol command type.
        
        Args:
            log_file: Path to JSON log file to query
            start_time: Optional start timestamp (Unix time)
            end_time: Optional end timestamp (Unix time)
            msg_type: Optional MAVLink message type filter
            system_id: Optional system ID filter
            command_type: Optional binary protocol command type filter
            
        Returns:
            List of matching records
            
        Requirements: 5.3
        """
        try:
            # Read JSON log file
            with open(log_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both list and dict formats
            if isinstance(data, dict) and 'messages' in data:
                data = data['messages']
            
            # Filter data
            filtered_data = self._filter_data(data, start_time, end_time, msg_type, system_id, command_type)
            
            logger.info(f"Query returned {len(filtered_data)} records")
            return filtered_data
        
        except Exception as e:
            logger.error(f"Error querying logs: {e}")
            return []
    
    def _filter_data(self,
                    data: List[Dict[str, Any]],
                    start_time: Optional[float] = None,
                    end_time: Optional[float] = None,
                    msg_type: Optional[str] = None,
                    system_id: Optional[int] = None,
                    command_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Filter data based on criteria.
        
        Args:
            data: List of log records
            start_time: Optional start timestamp (Unix time)
            end_time: Optional end timestamp (Unix time)
            msg_type: Optional MAVLink message type filter
            system_id: Optional system ID filter
            command_type: Optional binary protocol command type filter
            
        Returns:
            Filtered list of records
            
        Requirements: 5.3
        """
        filtered = []
        
        for record in data:
            # Apply time filter
            if start_time and record.get('timestamp', 0) < start_time:
                continue
            if end_time and record.get('timestamp', float('inf')) > end_time:
                continue
            
            # Apply message type filter
            if msg_type and record.get('msg_type') != msg_type:
                continue
            
            # Apply system ID filter
            if system_id is not None and record.get('system_id') != system_id:
                continue
            
            # Apply command type filter (for binary protocol)
            if command_type and record.get('command') != command_type:
                continue
            
            filtered.append(record)
        
        return filtered
    
    def get_log_summary(self, log_file: str) -> Dict[str, Any]:
        """
        Get a summary of a log file.
        
        Provides statistics about the log file including time range,
        message counts, and system IDs present.
        
        Args:
            log_file: Path to JSON log file
            
        Returns:
            Dictionary with log file summary
            
        Requirements: 5.3
        """
        try:
            # Read JSON log file
            with open(log_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both list and dict formats
            if isinstance(data, dict) and 'messages' in data:
                data = data['messages']
            
            if not data:
                return {'error': 'No data in log file'}
            
            # Calculate summary statistics
            timestamps = [r.get('timestamp', 0) for r in data if 'timestamp' in r]
            msg_types = [r.get('msg_type') for r in data if 'msg_type' in r]
            system_ids = [r.get('system_id') for r in data if 'system_id' in r]
            
            summary = {
                'file': log_file,
                'total_records': len(data),
                'time_range': {
                    'start': min(timestamps) if timestamps else None,
                    'end': max(timestamps) if timestamps else None,
                    'duration_seconds': (max(timestamps) - min(timestamps)) if timestamps else 0
                },
                'message_types': {
                    'unique_count': len(set(msg_types)),
                    'distribution': {mt: msg_types.count(mt) for mt in set(msg_types)}
                },
                'system_ids': list(set(system_ids)),
                'system_id_count': len(set(system_ids))
            }
            
            return summary
        
        except Exception as e:
            logger.error(f"Error getting log summary: {e}")
            return {'error': str(e)}
    
    def compare_time_ranges(self,
                           log_file: str,
                           range1: Tuple[float, float],
                           range2: Tuple[float, float]) -> Dict[str, Any]:
        """
        Compare metrics between two time ranges.
        
        Useful for comparing performance before/after changes or between
        different flight modes.
        
        Args:
            log_file: Path to JSON log file
            range1: Tuple of (start_time, end_time) for first range
            range2: Tuple of (start_time, end_time) for second range
            
        Returns:
            Dictionary with comparison results
            
        Requirements: 5.3
        """
        try:
            # Query data for both ranges
            data1 = self.query_logs(log_file, start_time=range1[0], end_time=range1[1])
            data2 = self.query_logs(log_file, start_time=range2[0], end_time=range2[1])
            
            # Calculate metrics for each range
            metrics1 = self._calculate_range_metrics(data1, range1)
            metrics2 = self._calculate_range_metrics(data2, range2)
            
            # Calculate differences
            comparison = {
                'range1': {
                    'time_range': range1,
                    'metrics': metrics1
                },
                'range2': {
                    'time_range': range2,
                    'metrics': metrics2
                },
                'differences': {
                    'packet_rate_change': metrics2['packet_rate'] - metrics1['packet_rate'],
                    'packet_rate_change_pct': ((metrics2['packet_rate'] - metrics1['packet_rate']) / 
                                              metrics1['packet_rate'] * 100) if metrics1['packet_rate'] > 0 else 0,
                    'avg_rssi_change': metrics2['avg_rssi'] - metrics1['avg_rssi'],
                    'avg_snr_change': metrics2['avg_snr'] - metrics1['avg_snr']
                }
            }
            
            return comparison
        
        except Exception as e:
            logger.error(f"Error comparing time ranges: {e}")
            return {'error': str(e)}
    
    def _calculate_range_metrics(self, 
                                 data: List[Dict[str, Any]], 
                                 time_range: Tuple[float, float]) -> Dict[str, Any]:
        """
        Calculate metrics for a time range of data.
        
        Args:
            data: List of log records
            time_range: Tuple of (start_time, end_time)
            
        Returns:
            Dictionary with calculated metrics
        """
        if not data:
            return {
                'record_count': 0,
                'packet_rate': 0.0,
                'avg_rssi': 0.0,
                'avg_snr': 0.0,
                'message_types': {}
            }
        
        duration = time_range[1] - time_range[0]
        
        # Extract RSSI/SNR values
        rssi_values = [r.get('rssi') for r in data if r.get('rssi') is not None]
        snr_values = [r.get('snr') for r in data if r.get('snr') is not None]
        
        # Count message types
        msg_types = [r.get('msg_type') for r in data if 'msg_type' in r]
        msg_type_dist = {mt: msg_types.count(mt) for mt in set(msg_types)}
        
        return {
            'record_count': len(data),
            'packet_rate': len(data) / duration if duration > 0 else 0.0,
            'avg_rssi': sum(rssi_values) / len(rssi_values) if rssi_values else 0.0,
            'avg_snr': sum(snr_values) / len(snr_values) if snr_values else 0.0,
            'message_types': msg_type_dist
        }
