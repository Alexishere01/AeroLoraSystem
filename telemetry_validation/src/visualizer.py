"""
Real-time Telemetry Visualizer Module

This module provides real-time visualization of telemetry data with support
for multiple metrics, violation highlighting, historical data viewing, and
multi-drone support.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
"""

import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Deque, TYPE_CHECKING

if TYPE_CHECKING:
    from csv_utils import EnhancedLogEntry
import time
import logging
import numpy as np

# Handle both relative and absolute imports
try:
    from .metrics_calculator import TelemetryMetrics
    from .validation_engine import Violation, Severity
except ImportError:
    from metrics_calculator import TelemetryMetrics
    from validation_engine import Violation, Severity

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class VisualizerConfig:
    """
    Configuration for the visualizer.
    
    Attributes:
        update_rate_hz: Update rate in Hz (default 1 Hz per requirement 7.5)
        history_seconds: Number of seconds of history to display
        max_drones: Maximum number of drones to track
        show_violations: Whether to highlight violations on graphs
        window_title: Title for the visualization window
    """
    update_rate_hz: float = 1.0
    history_seconds: int = 60
    max_drones: int = 4
    show_violations: bool = True
    window_title: str = "Telemetry Validation - Real-time Monitor"


@dataclass
class MetricDataPoint:
    """
    Single data point for a metric.
    
    Attributes:
        timestamp: Unix timestamp
        value: Metric value
        system_id: System ID (for multi-drone support)
        has_violation: Whether this point has an associated violation
    """
    timestamp: float
    value: float
    system_id: int = 0
    has_violation: bool = False


class TelemetryVisualizer:
    """
    Real-time telemetry visualization with matplotlib.
    
    This class provides real-time graphs of key telemetry metrics including
    RSSI, SNR, packet rate, battery voltage, and binary protocol health.
    Supports violation highlighting, historical data viewing, and multi-drone
    tracking.
    
    Features:
    - Real-time plotting with configurable update rate (1 Hz default)
    - Multiple subplots for different metrics
    - Violation highlighting with red indicators
    - Historical data viewing with time range selection
    - Multi-drone support with color-coded graphs
    - Binary protocol health monitoring
    - Efficient data structures for plotting
    
    Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
    """
    
    def __init__(self, config: Optional[VisualizerConfig] = None):
        """
        Initialize the telemetry visualizer.
        
        Args:
            config: Visualizer configuration (uses defaults if None)
            
        Requirements: 7.1, 7.5
        """
        self.config = config or VisualizerConfig()
        
        # Data storage (efficient deques for rolling windows)
        self.history_size = int(self.config.history_seconds * self.config.update_rate_hz)
        
        # Per-system-ID data storage
        self.rssi_data: Dict[int, Deque[MetricDataPoint]] = {}
        self.snr_data: Dict[int, Deque[MetricDataPoint]] = {}
        self.packet_rate_data: Dict[int, Deque[MetricDataPoint]] = {}
        self.battery_voltage_data: Dict[int, Deque[MetricDataPoint]] = {}
        
        # Binary protocol health data (system-wide)
        self.checksum_error_data: Deque[MetricDataPoint] = deque(maxlen=self.history_size)
        self.protocol_success_data: Deque[MetricDataPoint] = deque(maxlen=self.history_size)
        
        # Violation tracking
        self.violations: List[Violation] = []
        
        # System ID tracking for multi-drone support
        self.active_system_ids: set = set()
        self.system_colors: Dict[int, str] = {}
        self.color_palette = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', 
                             '#9467bd', '#8c564b', '#e377c2', '#7f7f7f']
        
        # Figure and axes
        self.fig: Optional[Figure] = None
        self.axes: Dict[str, Axes] = {}
        self.animation: Optional[animation.FuncAnimation] = None
        
        # Timing
        self.start_time = time.time()
        self.last_update_time = 0.0
        
        # Historical data viewing
        self.view_mode = 'realtime'  # 'realtime' or 'historical'
        self.historical_time_range: Optional[Tuple[float, float]] = None
        
        logger.info(f"Telemetry visualizer initialized with {self.config.update_rate_hz} Hz update rate")
    
    def initialize_plots(self):
        """
        Initialize matplotlib figure and subplots.
        
        Creates a 4x2 grid of subplots:
        - Row 1: RSSI, SNR
        - Row 2: Packet Rate, Battery Voltage
        - Row 3: Throughput, Latency Distribution
        - Row 4: Queue Depth, Error Rate
        
        Requirements: 7.1, 4.1, 4.2, 4.3, 4.4
        """
        # Create figure with subplots
        self.fig, axes_array = plt.subplots(4, 2, figsize=(14, 12))
        self.fig.suptitle(self.config.window_title, fontsize=14, fontweight='bold')
        
        # Flatten axes array for easier access
        axes_flat = axes_array.flatten()
        
        # Assign axes to metrics
        self.axes = {
            'rssi': axes_flat[0],
            'snr': axes_flat[1],
            'packet_rate': axes_flat[2],
            'battery_voltage': axes_flat[3],
            'throughput': axes_flat[4],
            'latency': axes_flat[5],
            'queue_depth': axes_flat[6],
            'error_rate': axes_flat[7]
        }
        
        # Configure each subplot
        self._configure_subplot(self.axes['rssi'], 'RSSI (dBm)', 'RSSI', 'dBm')
        self._configure_subplot(self.axes['snr'], 'SNR (dB)', 'SNR', 'dB')
        self._configure_subplot(self.axes['packet_rate'], 'Packet Rate', 'Rate', 'packets/s')
        self._configure_subplot(self.axes['battery_voltage'], 'Battery Voltage', 'Voltage', 'V')
        self._configure_subplot(self.axes['throughput'], 'Throughput', 'Throughput', 'bytes/s')
        self._configure_subplot(self.axes['latency'], 'End-to-End Latency', 'Latency', 's')
        self._configure_subplot(self.axes['queue_depth'], 'Queue Depth', 'Depth', 'packets')
        self._configure_subplot(self.axes['error_rate'], 'Error Rate', 'Errors', 'errors')
        
        # Adjust layout
        plt.tight_layout()
        
        logger.info("Plots initialized with 4x2 layout")
    
    def _configure_subplot(self, ax: Axes, title: str, ylabel: str, unit: str):
        """
        Configure a subplot with labels and grid.
        
        Args:
            ax: Matplotlib axes object
            title: Plot title
            ylabel: Y-axis label
            unit: Unit of measurement
        """
        ax.set_title(title, fontsize=10, fontweight='bold')
        ax.set_xlabel('Time (s)', fontsize=9)
        ax.set_ylabel(f'{ylabel} ({unit})', fontsize=9)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.tick_params(labelsize=8)
    
    def update_data(self, metrics: TelemetryMetrics, system_id: int = 0, 
                   battery_voltage: Optional[float] = None):
        """
        Update visualizer with new metrics data.
        
        Args:
            metrics: TelemetryMetrics object from MetricsCalculator
            system_id: System ID for multi-drone support
            battery_voltage: Battery voltage in volts (optional)
            
        Requirements: 7.1, 7.4, 7.5
        """
        now = time.time()
        
        # Track active system IDs
        if system_id not in self.active_system_ids:
            self._register_system_id(system_id)
        
        # Initialize data structures for this system if needed
        if system_id not in self.rssi_data:
            self.rssi_data[system_id] = deque(maxlen=self.history_size)
            self.snr_data[system_id] = deque(maxlen=self.history_size)
            self.packet_rate_data[system_id] = deque(maxlen=self.history_size)
            self.battery_voltage_data[system_id] = deque(maxlen=self.history_size)
        
        # Add data points
        self.rssi_data[system_id].append(MetricDataPoint(now, metrics.avg_rssi, system_id))
        self.snr_data[system_id].append(MetricDataPoint(now, metrics.avg_snr, system_id))
        self.packet_rate_data[system_id].append(MetricDataPoint(now, metrics.mavlink_packet_rate_1s, system_id))
        
        if battery_voltage is not None:
            self.battery_voltage_data[system_id].append(MetricDataPoint(now, battery_voltage, system_id))
        
        # Add binary protocol health data (system-wide)
        self.checksum_error_data.append(MetricDataPoint(now, metrics.checksum_error_rate, 0))
        self.protocol_success_data.append(MetricDataPoint(now, metrics.protocol_success_rate, 0))
    
    def _register_system_id(self, system_id: int):
        """
        Register a new system ID and assign it a color.
        
        Args:
            system_id: System ID to register
            
        Requirements: 7.4
        """
        if len(self.active_system_ids) >= self.config.max_drones:
            logger.warning(f"Maximum number of drones ({self.config.max_drones}) reached")
            return
        
        self.active_system_ids.add(system_id)
        
        # Assign color from palette
        color_index = len(self.active_system_ids) - 1
        if color_index < len(self.color_palette):
            self.system_colors[system_id] = self.color_palette[color_index]
        else:
            # Generate random color if palette exhausted
            import random
            self.system_colors[system_id] = f'#{random.randint(0, 0xFFFFFF):06x}'
        
        logger.info(f"Registered system ID {system_id} with color {self.system_colors[system_id]}")
    
    def add_violation(self, violation: Violation):
        """
        Add a violation for highlighting on graphs.
        
        Args:
            violation: Violation object from ValidationEngine
            
        Requirements: 7.2
        """
        self.violations.append(violation)
        
        # Mark data points with violations
        self._mark_violation_points(violation)
    
    def _mark_violation_points(self, violation: Violation):
        """
        Mark data points that correspond to a violation.
        
        Args:
            violation: Violation object
            
        Requirements: 7.2
        """
        # Determine which metric was violated and mark the corresponding data point
        system_id = violation.system_id or 0
        
        # Map violation fields to data structures
        field_to_data = {
            'rssi': self.rssi_data,
            'snr': self.snr_data,
            'voltage_battery': self.battery_voltage_data
        }
        
        # Find matching data structure
        for field_name, data_dict in field_to_data.items():
            if field_name in violation.field.lower():
                if system_id in data_dict:
                    # Mark the most recent data point
                    if data_dict[system_id]:
                        data_dict[system_id][-1].has_violation = True
                break
    
    def update_plot(self, frame):
        """
        Update plot callback for animation.
        
        This method is called by matplotlib's FuncAnimation at the configured
        update rate (1 Hz by default).
        
        Args:
            frame: Frame number (unused, required by FuncAnimation)
            
        Requirements: 7.1, 7.2, 7.5
        """
        # Clear all axes
        for ax in self.axes.values():
            ax.clear()
            
        # Reconfigure subplots
        self._configure_subplot(self.axes['rssi'], 'RSSI (dBm)', 'RSSI', 'dBm')
        self._configure_subplot(self.axes['snr'], 'SNR (dB)', 'SNR', 'dB')
        self._configure_subplot(self.axes['packet_rate'], 'Packet Rate', 'Rate', 'packets/s')
        self._configure_subplot(self.axes['battery_voltage'], 'Battery Voltage', 'Voltage', 'V')
        self._configure_subplot(self.axes['throughput'], 'Throughput', 'Throughput', 'bytes/s')
        self._configure_subplot(self.axes['latency'], 'End-to-End Latency', 'Latency', 's')
        self._configure_subplot(self.axes['queue_depth'], 'Queue Depth', 'Depth', 'packets')
        self._configure_subplot(self.axes['error_rate'], 'Error Rate', 'Errors', 'errors')
        
        # Plot data for each system ID
        for system_id in self.active_system_ids:
            color = self.system_colors.get(system_id, '#000000')
            label = f'System {system_id}' if system_id > 0 else 'System'
            
            # Plot RSSI
            self._plot_metric(self.axes['rssi'], self.rssi_data.get(system_id, deque()), 
                            color, label, show_violations=True)
            
            # Plot SNR
            self._plot_metric(self.axes['snr'], self.snr_data.get(system_id, deque()), 
                            color, label, show_violations=True)
            
            # Plot packet rate
            self._plot_metric(self.axes['packet_rate'], self.packet_rate_data.get(system_id, deque()), 
                            color, label, show_violations=False)
            
            # Plot battery voltage
            self._plot_metric(self.axes['battery_voltage'], self.battery_voltage_data.get(system_id, deque()), 
                            color, label, show_violations=True)
        
        # Note: Enhanced plots (throughput, latency, queue_depth, error_rate) 
        # are handled separately when loading historical CSV data
        
        # Add legends if multiple systems
        if len(self.active_system_ids) > 1:
            for ax in [self.axes['rssi'], self.axes['snr'], self.axes['packet_rate'], self.axes['battery_voltage']]:
                ax.legend(fontsize=8, loc='upper left')
        
        # Update timestamp in title
        elapsed = time.time() - self.start_time
        self.fig.suptitle(f'{self.config.window_title} - Elapsed: {elapsed:.0f}s', 
                         fontsize=14, fontweight='bold')
    
    def _plot_metric(self, ax: Axes, data: Deque[MetricDataPoint], color: str, 
                    label: str, show_violations: bool = True):
        """
        Plot a single metric on an axes.
        
        Args:
            ax: Matplotlib axes object
            data: Deque of MetricDataPoint objects
            color: Line color
            label: Line label
            show_violations: Whether to highlight violations
            
        Requirements: 7.1, 7.2
        """
        if not data:
            return
        
        # Extract timestamps and values
        timestamps = np.array([dp.timestamp - self.start_time for dp in data])
        values = np.array([dp.value for dp in data])
        
        # Plot main line
        ax.plot(timestamps, values, color=color, label=label, linewidth=1.5, alpha=0.8)
        
        # Highlight violations with red markers
        if show_violations and self.config.show_violations:
            violation_times = []
            violation_values = []
            
            for dp in data:
                if dp.has_violation:
                    violation_times.append(dp.timestamp - self.start_time)
                    violation_values.append(dp.value)
            
            if violation_times:
                ax.scatter(violation_times, violation_values, color='red', s=100, 
                          marker='x', linewidths=2, zorder=5, label='Violation')
    
    def update_throughput_plot(self, entries: List['EnhancedLogEntry']):
        """
        Update throughput subplot with bytes/second over time.
        
        Args:
            entries: List of EnhancedLogEntry objects from CSV
            
        Requirements: 4.1
        """
        ax = self.axes['throughput']
        ax.clear()
        self._configure_subplot(ax, 'Throughput', 'Throughput', 'bytes/s')
        
        # Import metrics calculator if needed
        try:
            from .metrics_calculator import MetricsCalculator
        except ImportError:
            from metrics_calculator import MetricsCalculator
        
        # Calculate throughput
        calc = MetricsCalculator()
        throughput = calc.calculate_throughput(entries)
        
        if throughput:
            timestamps = range(len(throughput))
            ax.plot(timestamps, throughput, color='#2ca02c', linewidth=1.5)
            ax.set_ylabel('Throughput (bytes/s)')
            ax.set_xlabel('Time (s)')
            ax.set_title('Throughput Over Time')
            ax.grid(True, alpha=0.3)
        else:
            ax.text(0.5, 0.5, 'No throughput data\n(legacy format)', 
                   ha='center', va='center', transform=ax.transAxes,
                   fontsize=10, color='gray')
    
    def update_latency_plot(self, entries: List['EnhancedLogEntry']):
        """
        Update latency distribution subplot with histogram.
        
        Args:
            entries: List of EnhancedLogEntry objects from CSV
            
        Requirements: 4.2
        """
        ax = self.axes['latency']
        ax.clear()
        self._configure_subplot(ax, 'End-to-End Latency', 'Latency', 's')
        
        # Import metrics calculator if needed
        try:
            from .metrics_calculator import MetricsCalculator
        except ImportError:
            from metrics_calculator import MetricsCalculator
        
        # Calculate latencies
        calc = MetricsCalculator()
        latencies = calc.calculate_end_to_end_latency(entries)
        
        if latencies:
            # Create histogram
            ax.hist(latencies, bins=50, color='#ff7f0e', alpha=0.7, edgecolor='black')
            ax.set_ylabel('Count')
            ax.set_xlabel('Latency (s)')
            ax.set_title('End-to-End Latency Distribution')
            ax.grid(True, alpha=0.3, axis='y')
            
            # Add percentile lines
            p50 = np.percentile(latencies, 50)
            p95 = np.percentile(latencies, 95)
            p99 = np.percentile(latencies, 99)
            
            ax.axvline(p50, color='green', linestyle='--', linewidth=2, label=f'p50: {p50:.3f}s')
            ax.axvline(p95, color='orange', linestyle='--', linewidth=2, label=f'p95: {p95:.3f}s')
            ax.axvline(p99, color='red', linestyle='--', linewidth=2, label=f'p99: {p99:.3f}s')
            ax.legend(fontsize=8)
        else:
            ax.text(0.5, 0.5, 'No latency data\n(legacy format or no tx_timestamp)', 
                   ha='center', va='center', transform=ax.transAxes,
                   fontsize=10, color='gray')
    
    def update_queue_depth_plot(self, entries: List['EnhancedLogEntry']):
        """
        Update queue depth subplot with congestion highlighting.
        
        Args:
            entries: List of EnhancedLogEntry objects from CSV
            
        Requirements: 4.3
        """
        ax = self.axes['queue_depth']
        ax.clear()
        self._configure_subplot(ax, 'Queue Depth', 'Depth', 'packets')
        
        # Extract queue depth data
        # Check if we have any queue depth data (non-zero values indicate enhanced format)
        has_queue_data = entries and any(e.queue_depth > 0 for e in entries)
        
        if has_queue_data:
            timestamps = [(e.timestamp_ms - entries[0].timestamp_ms) / 1000.0 for e in entries]
            queue_depths = [e.queue_depth for e in entries]
            
            # Plot queue depth
            ax.plot(timestamps, queue_depths, color='#1f77b4', linewidth=1.5, label='Queue Depth')
            
            # Highlight congestion events (queue_depth > 20)
            congestion_times = []
            congestion_depths = []
            for e in entries:
                if e.queue_depth > 20:
                    congestion_times.append((e.timestamp_ms - entries[0].timestamp_ms) / 1000.0)
                    congestion_depths.append(e.queue_depth)
            
            if congestion_times:
                ax.scatter(congestion_times, congestion_depths, color='red', s=50, 
                          marker='o', zorder=5, label='Congestion (>20)')
                ax.axhline(y=20, color='red', linestyle='--', linewidth=1, alpha=0.5)
            
            ax.set_ylabel('Queue Depth (packets)')
            ax.set_xlabel('Time (s)')
            ax.set_title('Queue Depth Over Time')
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=8)
        else:
            ax.text(0.5, 0.5, 'No queue data\n(legacy format or no queue_depth)', 
                   ha='center', va='center', transform=ax.transAxes,
                   fontsize=10, color='gray')
    
    def update_error_rate_plot(self, entries: List['EnhancedLogEntry']):
        """
        Update error rate subplot with RSSI correlation.
        
        Args:
            entries: List of EnhancedLogEntry objects from CSV
            
        Requirements: 4.4
        """
        ax = self.axes['error_rate']
        ax.clear()
        
        # Extract error and RSSI data
        # Check if we have error data (enhanced format has errors field)
        has_error_data = entries and len(entries) > 0
        
        if has_error_data:
            timestamps = [(e.timestamp_ms - entries[0].timestamp_ms) / 1000.0 for e in entries]
            
            # Calculate error deltas (errors per interval)
            error_deltas = [0]
            for i in range(1, len(entries)):
                delta = entries[i].errors - entries[i-1].errors
                error_deltas.append(max(0, delta))  # Ensure non-negative
            
            rssi_values = [e.rssi_dbm for e in entries]
            
            # Create dual y-axes
            ax1 = ax
            ax2 = ax1.twinx()
            
            # Plot error rate on left axis
            for i in range(len(timestamps)):
                color = 'green' if rssi_values[i] > -85 else 'red'
                ax1.scatter(timestamps[i], error_deltas[i], color=color, s=20, alpha=0.6)
            
            ax1.set_xlabel('Time (s)')
            ax1.set_ylabel('Error Rate (errors)', color='black')
            ax1.tick_params(axis='y', labelcolor='black')
            ax1.grid(True, alpha=0.3)
            
            # Plot RSSI on right axis
            ax2.plot(timestamps, rssi_values, color='blue', linewidth=1, alpha=0.5, label='RSSI')
            ax2.set_ylabel('RSSI (dBm)', color='blue')
            ax2.tick_params(axis='y', labelcolor='blue')
            ax2.axhline(y=-85, color='orange', linestyle='--', linewidth=1, alpha=0.5, label='Link Quality Threshold')
            
            ax1.set_title('Error Rate vs RSSI (Green=Good Link, Red=Poor Link)')
            
            # Add legend
            from matplotlib.patches import Patch
            legend_elements = [
                Patch(facecolor='green', alpha=0.6, label='Good Link (RSSI > -85)'),
                Patch(facecolor='red', alpha=0.6, label='Poor Link (RSSI ≤ -85)')
            ]
            ax1.legend(handles=legend_elements, fontsize=8, loc='upper left')
        else:
            ax.text(0.5, 0.5, 'No error data\n(legacy format or no errors field)', 
                   ha='center', va='center', transform=ax.transAxes,
                   fontsize=10, color='gray')
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('Errors')
            ax.set_title('Error Rate vs RSSI')
    
    def start_realtime(self):
        """
        Start real-time visualization.
        
        Initializes plots and starts the animation loop at the configured
        update rate (1 Hz by default).
        
        Requirements: 7.1, 7.5
        """
        if self.fig is None:
            self.initialize_plots()
        
        # Calculate interval in milliseconds
        interval_ms = int(1000 / self.config.update_rate_hz)
        
        # Create animation
        self.animation = animation.FuncAnimation(
            self.fig, 
            self.update_plot, 
            interval=interval_ms,
            blit=False,
            cache_frame_data=False
        )
        
        logger.info(f"Starting real-time visualization at {self.config.update_rate_hz} Hz")
        plt.show()
    
    def load_historical_data(self, log_file: str, time_range: Optional[Tuple[float, float]] = None):
        """
        Load and display historical data from log files.
        
        Supports both enhanced (12-field) and legacy (8-field) CSV formats.
        Enhanced format enables throughput, latency, queue depth, and error
        correlation visualizations.
        
        Args:
            log_file: Path to CSV log file (flight log format)
            time_range: Optional tuple of (start_time, end_time) for filtering
            
        Requirements: 7.3, 5.1, 5.2, 5.3, 5.4, 5.5
        """
        logger.info(f"Loading historical data from {log_file}")
        
        # Set view mode
        self.view_mode = 'historical'
        self.historical_time_range = time_range
        
        # Clear existing data
        self._clear_data()
        
        try:
            # Import CSV utilities
            try:
                from .csv_utils import load_flight_log, EnhancedLogEntry
            except ImportError:
                from csv_utils import load_flight_log, EnhancedLogEntry
            
            # Load CSV with automatic format detection
            entries, format_type = load_flight_log(log_file)
            
            logger.info(f"Detected format: {format_type}")
            
            if format_type == 'legacy':
                logger.warning("Legacy format detected - enhanced metrics not available")
                logger.warning("  - Throughput visualization disabled")
                logger.warning("  - Latency distribution disabled")
                logger.warning("  - Queue depth monitoring disabled")
                logger.warning("  - Error correlation disabled")
            
            # Apply time range filter if specified
            if time_range:
                entries = [e for e in entries 
                          if time_range[0] <= e.timestamp_ms / 1000.0 <= time_range[1]]
            
            if not entries:
                logger.warning("No entries found in specified time range")
                return
            
            # Process entries for basic metrics (RSSI, SNR, packet rate)
            for entry in entries:
                system_id = entry.system_id
                timestamp = entry.timestamp_ms / 1000.0  # Convert to seconds
                
                # Register system ID
                if system_id not in self.active_system_ids:
                    self._register_system_id(system_id)
                
                # Initialize data structures
                if system_id not in self.rssi_data:
                    self.rssi_data[system_id] = deque(maxlen=self.history_size * 10)
                    self.snr_data[system_id] = deque(maxlen=self.history_size * 10)
                    self.packet_rate_data[system_id] = deque(maxlen=self.history_size * 10)
                    self.battery_voltage_data[system_id] = deque(maxlen=self.history_size * 10)
                
                # Add data points
                self.rssi_data[system_id].append(MetricDataPoint(timestamp, entry.rssi_dbm, system_id))
                self.snr_data[system_id].append(MetricDataPoint(timestamp, entry.snr_db, system_id))
            
            logger.info(f"Loaded {len(entries)} entries for {len(self.active_system_ids)} system(s)")
            
            # Display static plot with enhanced metrics
            self._display_historical_plot(entries, format_type)
            
        except FileNotFoundError:
            logger.error(f"File not found: {log_file}")
        except Exception as e:
            logger.error(f"Error loading historical data: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    def _display_historical_plot(self, entries: List['EnhancedLogEntry'], format_type: str):
        """
        Display a static plot of historical data with enhanced metrics.
        
        Args:
            entries: List of EnhancedLogEntry objects
            format_type: 'enhanced' or 'legacy'
        
        Requirements: 7.3, 5.1, 5.2, 5.3, 5.4, 5.5
        """
        if self.fig is None:
            self.initialize_plots()
        
        # Update basic plots with historical data
        self.update_plot(0)
        
        # Update enhanced plots if format supports it
        if format_type == 'enhanced':
            logger.info("Rendering enhanced metric visualizations")
            self.update_throughput_plot(entries)
            self.update_latency_plot(entries)
            self.update_queue_depth_plot(entries)
            self.update_error_rate_plot(entries)
        else:
            # Display "not available" messages for legacy format
            logger.info("Rendering legacy format - enhanced metrics disabled")
            self.update_throughput_plot([])  # Empty list shows "no data" message
            self.update_latency_plot([])
            self.update_queue_depth_plot([])
            self.update_error_rate_plot([])
        
        # Show static plot
        plt.show()
    
    def _clear_data(self):
        """Clear all data structures."""
        self.rssi_data.clear()
        self.snr_data.clear()
        self.packet_rate_data.clear()
        self.battery_voltage_data.clear()
        self.checksum_error_data.clear()
        self.protocol_success_data.clear()
        self.violations.clear()
        self.active_system_ids.clear()
        self.system_colors.clear()
    
    def stop(self):
        """Stop the visualization."""
        if self.animation:
            self.animation.event_source.stop()
        plt.close(self.fig)
        logger.info("Visualization stopped")
    
    def save_snapshot(self, filename: str):
        """
        Save current visualization to file.
        
        Args:
            filename: Output filename (e.g., 'snapshot.png')
        """
        if self.fig:
            self.fig.savefig(filename, dpi=150, bbox_inches='tight')
            logger.info(f"Snapshot saved to {filename}")
