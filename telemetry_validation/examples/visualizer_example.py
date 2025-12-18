#!/usr/bin/env python3
"""
Telemetry Visualizer Example

This example demonstrates how to use the TelemetryVisualizer for real-time
and historical data visualization.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
"""

import sys
import os
import time
import random

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from visualizer import TelemetryVisualizer, VisualizerConfig, MetricDataPoint
from metrics_calculator import TelemetryMetrics
from validation_engine import Violation, Severity


def example_realtime_single_drone():
    """
    Example 1: Real-time visualization with a single drone.
    
    Simulates telemetry data for one drone with varying metrics.
    """
    print("=" * 60)
    print("Example 1: Real-time Visualization - Single Drone")
    print("=" * 60)
    
    # Create visualizer with default config
    config = VisualizerConfig(
        update_rate_hz=1.0,
        history_seconds=60,
        show_violations=True
    )
    visualizer = TelemetryVisualizer(config)
    
    # Initialize plots
    visualizer.initialize_plots()
    
    # Simulate data updates
    print("Simulating telemetry data...")
    print("Close the plot window to continue to next example")
    
    # Create a background thread to update data
    import threading
    
    def update_data():
        system_id = 1
        start_time = time.time()
        
        while time.time() - start_time < 60:  # Run for 60 seconds
            # Simulate metrics
            metrics = TelemetryMetrics(
                binary_packet_rate_1s=random.uniform(5, 15),
                binary_packet_rate_10s=random.uniform(5, 15),
                binary_packet_rate_60s=random.uniform(5, 15),
                mavlink_packet_rate_1s=random.uniform(3, 10),
                mavlink_packet_rate_10s=random.uniform(3, 10),
                mavlink_packet_rate_60s=random.uniform(3, 10),
                avg_rssi=random.uniform(-100, -60),
                avg_snr=random.uniform(5, 15),
                drop_rate=random.uniform(0, 5),
                packets_lost=random.randint(0, 10),
                packets_received=random.randint(100, 200),
                latency_avg=random.uniform(0.01, 0.1),
                latency_min=0.005,
                latency_max=0.2,
                latency_samples=10,
                mavlink_msg_type_distribution={'HEARTBEAT': 100, 'GPS_RAW_INT': 50},
                binary_cmd_type_distribution={'CMD_BRIDGE_TX': 80, 'CMD_BRIDGE_RX': 70},
                checksum_error_rate=random.uniform(0, 5),
                parse_error_rate=random.uniform(0, 2),
                protocol_success_rate=random.uniform(95, 100),
                buffer_overflow_count=0,
                timeout_error_count=0,
                timestamp=time.time()
            )
            
            # Simulate battery voltage
            battery_voltage = random.uniform(11.5, 12.6)
            
            # Update visualizer
            visualizer.update_data(metrics, system_id=system_id, battery_voltage=battery_voltage)
            
            # Simulate occasional violation
            if random.random() < 0.1:  # 10% chance
                violation = Violation(
                    timestamp=time.time(),
                    rule_name="Low RSSI",
                    msg_type="RADIO_STATUS",
                    field="rssi",
                    actual_value=metrics.avg_rssi,
                    threshold=-90,
                    severity=Severity.WARNING,
                    description="RSSI below threshold",
                    system_id=system_id
                )
                visualizer.add_violation(violation)
            
            time.sleep(1)
    
    # Start data update thread
    thread = threading.Thread(target=update_data, daemon=True)
    thread.start()
    
    # Start visualization (blocking)
    visualizer.start_realtime()


def example_realtime_multi_drone():
    """
    Example 2: Real-time visualization with multiple drones.
    
    Simulates telemetry data for 3 drones with different characteristics.
    """
    print("\n" + "=" * 60)
    print("Example 2: Real-time Visualization - Multiple Drones")
    print("=" * 60)
    
    # Create visualizer
    config = VisualizerConfig(
        update_rate_hz=1.0,
        history_seconds=60,
        max_drones=4,
        show_violations=True
    )
    visualizer = TelemetryVisualizer(config)
    
    # Initialize plots
    visualizer.initialize_plots()
    
    print("Simulating telemetry data for 3 drones...")
    print("Close the plot window to continue to next example")
    
    # Create a background thread to update data
    import threading
    
    def update_data():
        start_time = time.time()
        
        while time.time() - start_time < 60:  # Run for 60 seconds
            # Update data for each drone
            for system_id in [1, 2, 3]:
                # Simulate different characteristics per drone
                rssi_base = -70 - (system_id * 10)  # Drone 1: -80, Drone 2: -90, Drone 3: -100
                snr_base = 15 - (system_id * 2)     # Drone 1: 13, Drone 2: 11, Drone 3: 9
                
                metrics = TelemetryMetrics(
                    binary_packet_rate_1s=random.uniform(5, 15),
                    binary_packet_rate_10s=random.uniform(5, 15),
                    binary_packet_rate_60s=random.uniform(5, 15),
                    mavlink_packet_rate_1s=random.uniform(3, 10),
                    mavlink_packet_rate_10s=random.uniform(3, 10),
                    mavlink_packet_rate_60s=random.uniform(3, 10),
                    avg_rssi=rssi_base + random.uniform(-5, 5),
                    avg_snr=snr_base + random.uniform(-2, 2),
                    drop_rate=random.uniform(0, 5),
                    packets_lost=random.randint(0, 10),
                    packets_received=random.randint(100, 200),
                    latency_avg=random.uniform(0.01, 0.1),
                    latency_min=0.005,
                    latency_max=0.2,
                    latency_samples=10,
                    mavlink_msg_type_distribution={'HEARTBEAT': 100, 'GPS_RAW_INT': 50},
                    binary_cmd_type_distribution={'CMD_BRIDGE_TX': 80, 'CMD_BRIDGE_RX': 70},
                    checksum_error_rate=random.uniform(0, 5),
                    parse_error_rate=random.uniform(0, 2),
                    protocol_success_rate=random.uniform(95, 100),
                    buffer_overflow_count=0,
                    timeout_error_count=0,
                    timestamp=time.time()
                )
                
                battery_voltage = 12.6 - (system_id * 0.2) + random.uniform(-0.1, 0.1)
                
                visualizer.update_data(metrics, system_id=system_id, battery_voltage=battery_voltage)
            
            time.sleep(1)
    
    # Start data update thread
    thread = threading.Thread(target=update_data, daemon=True)
    thread.start()
    
    # Start visualization (blocking)
    visualizer.start_realtime()


def example_violation_highlighting():
    """
    Example 3: Violation highlighting on graphs.
    
    Demonstrates how violations are highlighted with red markers.
    """
    print("\n" + "=" * 60)
    print("Example 3: Violation Highlighting")
    print("=" * 60)
    
    # Create visualizer
    config = VisualizerConfig(
        update_rate_hz=1.0,
        history_seconds=30,
        show_violations=True
    )
    visualizer = TelemetryVisualizer(config)
    
    # Initialize plots
    visualizer.initialize_plots()
    
    print("Simulating telemetry with violations...")
    print("Watch for red 'X' markers on graphs")
    print("Close the plot window to continue to next example")
    
    # Create a background thread to update data
    import threading
    
    def update_data():
        system_id = 1
        start_time = time.time()
        violation_count = 0
        
        while time.time() - start_time < 30:  # Run for 30 seconds
            # Simulate metrics with occasional bad values
            rssi = random.uniform(-100, -60)
            snr = random.uniform(5, 15)
            battery_voltage = random.uniform(11.0, 12.6)
            
            # Trigger violations periodically
            if int(time.time() - start_time) % 5 == 0 and violation_count < 6:
                rssi = -105  # Bad RSSI
                battery_voltage = 10.2  # Low battery
                violation_count += 1
            
            metrics = TelemetryMetrics(
                binary_packet_rate_1s=random.uniform(5, 15),
                binary_packet_rate_10s=random.uniform(5, 15),
                binary_packet_rate_60s=random.uniform(5, 15),
                mavlink_packet_rate_1s=random.uniform(3, 10),
                mavlink_packet_rate_10s=random.uniform(3, 10),
                mavlink_packet_rate_60s=random.uniform(3, 10),
                avg_rssi=rssi,
                avg_snr=snr,
                drop_rate=random.uniform(0, 5),
                packets_lost=random.randint(0, 10),
                packets_received=random.randint(100, 200),
                latency_avg=random.uniform(0.01, 0.1),
                latency_min=0.005,
                latency_max=0.2,
                latency_samples=10,
                mavlink_msg_type_distribution={'HEARTBEAT': 100, 'GPS_RAW_INT': 50},
                binary_cmd_type_distribution={'CMD_BRIDGE_TX': 80, 'CMD_BRIDGE_RX': 70},
                checksum_error_rate=random.uniform(0, 5),
                parse_error_rate=random.uniform(0, 2),
                protocol_success_rate=random.uniform(95, 100),
                buffer_overflow_count=0,
                timeout_error_count=0,
                timestamp=time.time()
            )
            
            visualizer.update_data(metrics, system_id=system_id, battery_voltage=battery_voltage)
            
            # Add violations when thresholds exceeded
            if rssi < -100:
                violation = Violation(
                    timestamp=time.time(),
                    rule_name="Critical RSSI",
                    msg_type="RADIO_STATUS",
                    field="rssi",
                    actual_value=rssi,
                    threshold=-100,
                    severity=Severity.CRITICAL,
                    description="RSSI critically low",
                    system_id=system_id
                )
                visualizer.add_violation(violation)
                print(f"  [VIOLATION] RSSI: {rssi:.1f} dBm")
            
            if battery_voltage < 10.5:
                violation = Violation(
                    timestamp=time.time(),
                    rule_name="Low Battery",
                    msg_type="SYS_STATUS",
                    field="voltage_battery",
                    actual_value=battery_voltage,
                    threshold=10.5,
                    severity=Severity.WARNING,
                    description="Battery voltage low",
                    system_id=system_id
                )
                visualizer.add_violation(violation)
                print(f"  [VIOLATION] Battery: {battery_voltage:.2f} V")
            
            time.sleep(1)
    
    # Start data update thread
    thread = threading.Thread(target=update_data, daemon=True)
    thread.start()
    
    # Start visualization (blocking)
    visualizer.start_realtime()


def example_historical_data():
    """
    Example 4: Historical data viewing.
    
    Demonstrates loading and displaying historical data from a CSV log file.
    Note: This example requires an existing log file.
    """
    print("\n" + "=" * 60)
    print("Example 4: Historical Data Viewing")
    print("=" * 60)
    
    # Check if log file exists
    log_file = 'telemetry_logs/telemetry_20241026_120000.csv'
    
    if not os.path.exists(log_file):
        print(f"Log file not found: {log_file}")
        print("Skipping historical data example")
        print("Run the telemetry logger first to generate log files")
        return
    
    # Create visualizer
    visualizer = TelemetryVisualizer()
    
    print(f"Loading historical data from {log_file}...")
    
    # Load historical data
    visualizer.load_historical_data(log_file)
    
    print("Displaying historical data")
    print("Close the plot window to exit")


def example_save_snapshot():
    """
    Example 5: Save visualization snapshot.
    
    Demonstrates saving the current visualization to a file.
    """
    print("\n" + "=" * 60)
    print("Example 5: Save Visualization Snapshot")
    print("=" * 60)
    
    # Create visualizer
    visualizer = TelemetryVisualizer()
    visualizer.initialize_plots()
    
    # Add some sample data
    system_id = 1
    for i in range(30):
        metrics = TelemetryMetrics(
            binary_packet_rate_1s=random.uniform(5, 15),
            binary_packet_rate_10s=random.uniform(5, 15),
            binary_packet_rate_60s=random.uniform(5, 15),
            mavlink_packet_rate_1s=random.uniform(3, 10),
            mavlink_packet_rate_10s=random.uniform(3, 10),
            mavlink_packet_rate_60s=random.uniform(3, 10),
            avg_rssi=random.uniform(-100, -60),
            avg_snr=random.uniform(5, 15),
            drop_rate=random.uniform(0, 5),
            packets_lost=random.randint(0, 10),
            packets_received=random.randint(100, 200),
            latency_avg=random.uniform(0.01, 0.1),
            latency_min=0.005,
            latency_max=0.2,
            latency_samples=10,
            mavlink_msg_type_distribution={'HEARTBEAT': 100, 'GPS_RAW_INT': 50},
            binary_cmd_type_distribution={'CMD_BRIDGE_TX': 80, 'CMD_BRIDGE_RX': 70},
            checksum_error_rate=random.uniform(0, 5),
            parse_error_rate=random.uniform(0, 2),
            protocol_success_rate=random.uniform(95, 100),
            buffer_overflow_count=0,
            timeout_error_count=0,
            timestamp=time.time()
        )
        
        battery_voltage = random.uniform(11.5, 12.6)
        visualizer.update_data(metrics, system_id=system_id, battery_voltage=battery_voltage)
        time.sleep(0.1)
    
    # Update plot
    visualizer.update_plot(0)
    
    # Save snapshot
    output_file = 'telemetry_snapshot.png'
    visualizer.save_snapshot(output_file)
    print(f"Snapshot saved to {output_file}")


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("Telemetry Visualizer Examples")
    print("=" * 60)
    print("\nThis script demonstrates various features of the visualizer:")
    print("1. Real-time visualization with single drone")
    print("2. Real-time visualization with multiple drones")
    print("3. Violation highlighting")
    print("4. Historical data viewing")
    print("5. Save visualization snapshot")
    print("\n" + "=" * 60)
    
    # Run examples
    try:
        example_realtime_single_drone()
        example_realtime_multi_drone()
        example_violation_highlighting()
        example_historical_data()
        example_save_snapshot()
        
        print("\n" + "=" * 60)
        print("All examples completed!")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\nExamples interrupted by user")
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
