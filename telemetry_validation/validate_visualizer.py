#!/usr/bin/env python3
"""
Validation script for the Telemetry Visualizer.

This script validates that the visualizer is working correctly by:
1. Creating a visualizer instance
2. Simulating telemetry data
3. Adding violations
4. Verifying data structures
5. Testing all major features

Run this script to verify the visualizer implementation.
"""

import sys
import os
import time

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from visualizer import TelemetryVisualizer, VisualizerConfig, MetricDataPoint
from metrics_calculator import TelemetryMetrics
from validation_engine import Violation, Severity


def validate_initialization():
    """Validate visualizer initialization."""
    print("\n" + "="*60)
    print("TEST 1: Visualizer Initialization")
    print("="*60)
    
    try:
        # Test default config
        visualizer = TelemetryVisualizer()
        assert visualizer is not None
        assert visualizer.config.update_rate_hz == 1.0
        assert visualizer.config.history_seconds == 60
        print("✓ Default initialization successful")
        
        # Test custom config
        config = VisualizerConfig(
            update_rate_hz=2.0,
            history_seconds=120,
            max_drones=8
        )
        visualizer = TelemetryVisualizer(config)
        assert visualizer.config.update_rate_hz == 2.0
        assert visualizer.config.history_seconds == 120
        print("✓ Custom configuration successful")
        
        return True
    except Exception as e:
        print(f"✗ Initialization failed: {e}")
        return False


def validate_data_update():
    """Validate data update functionality."""
    print("\n" + "="*60)
    print("TEST 2: Data Update")
    print("="*60)
    
    try:
        visualizer = TelemetryVisualizer()
        
        # Create sample metrics
        metrics = TelemetryMetrics(
            binary_packet_rate_1s=10.0,
            binary_packet_rate_10s=9.5,
            binary_packet_rate_60s=9.0,
            mavlink_packet_rate_1s=5.0,
            mavlink_packet_rate_10s=4.8,
            mavlink_packet_rate_60s=4.5,
            avg_rssi=-75.0,
            avg_snr=12.0,
            drop_rate=2.5,
            packets_lost=10,
            packets_received=400,
            latency_avg=0.05,
            latency_min=0.01,
            latency_max=0.1,
            latency_samples=50,
            mavlink_msg_type_distribution={'HEARTBEAT': 100},
            binary_cmd_type_distribution={'CMD_BRIDGE_TX': 80},
            checksum_error_rate=1.0,
            parse_error_rate=0.5,
            protocol_success_rate=98.5,
            buffer_overflow_count=0,
            timeout_error_count=0,
            timestamp=time.time()
        )
        
        # Update visualizer
        visualizer.update_data(metrics, system_id=1, battery_voltage=12.4)
        
        # Verify data was added
        assert 1 in visualizer.active_system_ids
        assert 1 in visualizer.rssi_data
        assert len(visualizer.rssi_data[1]) == 1
        assert visualizer.rssi_data[1][0].value == -75.0
        print("✓ Single system data update successful")
        
        # Update multiple times
        for i in range(10):
            visualizer.update_data(metrics, system_id=1, battery_voltage=12.4)
        
        assert len(visualizer.rssi_data[1]) == 11
        print("✓ Multiple data updates successful")
        
        return True
    except Exception as e:
        print(f"✗ Data update failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_multi_drone():
    """Validate multi-drone support."""
    print("\n" + "="*60)
    print("TEST 3: Multi-Drone Support")
    print("="*60)
    
    try:
        visualizer = TelemetryVisualizer()
        
        # Add data for multiple drones
        for system_id in [1, 2, 3]:
            metrics = TelemetryMetrics(
                binary_packet_rate_1s=10.0,
                binary_packet_rate_10s=9.5,
                binary_packet_rate_60s=9.0,
                mavlink_packet_rate_1s=5.0,
                mavlink_packet_rate_10s=4.8,
                mavlink_packet_rate_60s=4.5,
                avg_rssi=-70.0 - (system_id * 5),
                avg_snr=10.0 + system_id,
                drop_rate=2.5,
                packets_lost=10,
                packets_received=400,
                latency_avg=0.05,
                latency_min=0.01,
                latency_max=0.1,
                latency_samples=50,
                mavlink_msg_type_distribution={'HEARTBEAT': 100},
                binary_cmd_type_distribution={'CMD_BRIDGE_TX': 80},
                checksum_error_rate=1.0,
                parse_error_rate=0.5,
                protocol_success_rate=98.5,
                buffer_overflow_count=0,
                timeout_error_count=0,
                timestamp=time.time()
            )
            
            visualizer.update_data(metrics, system_id=system_id)
        
        # Verify all systems registered
        assert len(visualizer.active_system_ids) == 3
        assert 1 in visualizer.active_system_ids
        assert 2 in visualizer.active_system_ids
        assert 3 in visualizer.active_system_ids
        print("✓ Multiple systems registered")
        
        # Verify different colors assigned
        assert 1 in visualizer.system_colors
        assert 2 in visualizer.system_colors
        assert 3 in visualizer.system_colors
        assert visualizer.system_colors[1] != visualizer.system_colors[2]
        assert visualizer.system_colors[2] != visualizer.system_colors[3]
        print("✓ Different colors assigned to each system")
        
        # Verify data for each system
        for system_id in [1, 2, 3]:
            assert system_id in visualizer.rssi_data
            assert len(visualizer.rssi_data[system_id]) == 1
        print("✓ Data tracked separately for each system")
        
        return True
    except Exception as e:
        print(f"✗ Multi-drone support failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_violation_highlighting():
    """Validate violation highlighting."""
    print("\n" + "="*60)
    print("TEST 4: Violation Highlighting")
    print("="*60)
    
    try:
        visualizer = TelemetryVisualizer()
        
        # Add data
        metrics = TelemetryMetrics(
            binary_packet_rate_1s=10.0,
            binary_packet_rate_10s=9.5,
            binary_packet_rate_60s=9.0,
            mavlink_packet_rate_1s=5.0,
            mavlink_packet_rate_10s=4.8,
            mavlink_packet_rate_60s=4.5,
            avg_rssi=-105.0,  # Bad RSSI
            avg_snr=12.0,
            drop_rate=2.5,
            packets_lost=10,
            packets_received=400,
            latency_avg=0.05,
            latency_min=0.01,
            latency_max=0.1,
            latency_samples=50,
            mavlink_msg_type_distribution={'HEARTBEAT': 100},
            binary_cmd_type_distribution={'CMD_BRIDGE_TX': 80},
            checksum_error_rate=1.0,
            parse_error_rate=0.5,
            protocol_success_rate=98.5,
            buffer_overflow_count=0,
            timeout_error_count=0,
            timestamp=time.time()
        )
        
        visualizer.update_data(metrics, system_id=1)
        
        # Create violation
        violation = Violation(
            timestamp=time.time(),
            rule_name="Low RSSI",
            msg_type="RADIO_STATUS",
            field="rssi",
            actual_value=-105.0,
            threshold=-100.0,
            severity=Severity.WARNING,
            description="RSSI below threshold",
            system_id=1
        )
        
        # Add violation
        visualizer.add_violation(violation)
        
        # Verify violation was added
        assert len(visualizer.violations) == 1
        assert visualizer.violations[0].rule_name == "Low RSSI"
        print("✓ Violation added successfully")
        
        # Verify data point was marked
        assert visualizer.rssi_data[1][-1].has_violation == True
        print("✓ Data point marked with violation")
        
        return True
    except Exception as e:
        print(f"✗ Violation highlighting failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_data_structures():
    """Validate efficient data structures."""
    print("\n" + "="*60)
    print("TEST 5: Data Structure Efficiency")
    print("="*60)
    
    try:
        config = VisualizerConfig(history_seconds=10, update_rate_hz=1.0)
        visualizer = TelemetryVisualizer(config)
        
        history_size = visualizer.history_size
        print(f"  History size: {history_size} data points")
        
        # Add more data than history_size
        for i in range(history_size + 20):
            metrics = TelemetryMetrics(
                binary_packet_rate_1s=10.0,
                binary_packet_rate_10s=9.5,
                binary_packet_rate_60s=9.0,
                mavlink_packet_rate_1s=5.0,
                mavlink_packet_rate_10s=4.8,
                mavlink_packet_rate_60s=4.5,
                avg_rssi=-75.0,
                avg_snr=12.0,
                drop_rate=2.5,
                packets_lost=10,
                packets_received=400,
                latency_avg=0.05,
                latency_min=0.01,
                latency_max=0.1,
                latency_samples=50,
                mavlink_msg_type_distribution={'HEARTBEAT': 100},
                binary_cmd_type_distribution={'CMD_BRIDGE_TX': 80},
                checksum_error_rate=1.0,
                parse_error_rate=0.5,
                protocol_success_rate=98.5,
                buffer_overflow_count=0,
                timeout_error_count=0,
                timestamp=time.time()
            )
            
            visualizer.update_data(metrics, system_id=1)
        
        # Verify deque length doesn't exceed maxlen
        assert len(visualizer.rssi_data[1]) <= history_size
        assert len(visualizer.snr_data[1]) <= history_size
        assert len(visualizer.checksum_error_data) <= history_size
        print(f"✓ Deque maxlen enforced (actual: {len(visualizer.rssi_data[1])})")
        
        # Verify memory efficiency
        import sys
        rssi_size = sys.getsizeof(visualizer.rssi_data[1])
        print(f"✓ Memory efficient (RSSI deque: {rssi_size} bytes)")
        
        return True
    except Exception as e:
        print(f"✗ Data structure validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_configuration():
    """Validate configuration options."""
    print("\n" + "="*60)
    print("TEST 6: Configuration Options")
    print("="*60)
    
    try:
        # Test different update rates
        for rate in [0.5, 1.0, 2.0, 5.0]:
            config = VisualizerConfig(update_rate_hz=rate)
            visualizer = TelemetryVisualizer(config)
            assert visualizer.config.update_rate_hz == rate
        print("✓ Update rate configuration working")
        
        # Test different history sizes
        for history in [30, 60, 120, 300]:
            config = VisualizerConfig(history_seconds=history)
            visualizer = TelemetryVisualizer(config)
            assert visualizer.config.history_seconds == history
        print("✓ History size configuration working")
        
        # Test max drones
        for max_drones in [2, 4, 8]:
            config = VisualizerConfig(max_drones=max_drones)
            visualizer = TelemetryVisualizer(config)
            assert visualizer.config.max_drones == max_drones
        print("✓ Max drones configuration working")
        
        # Test violation display toggle
        for show_violations in [True, False]:
            config = VisualizerConfig(show_violations=show_violations)
            visualizer = TelemetryVisualizer(config)
            assert visualizer.config.show_violations == show_violations
        print("✓ Violation display toggle working")
        
        return True
    except Exception as e:
        print(f"✗ Configuration validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all validation tests."""
    print("\n" + "="*60)
    print("TELEMETRY VISUALIZER VALIDATION")
    print("="*60)
    print("\nValidating visualizer implementation...")
    
    results = []
    
    # Run validation tests
    results.append(("Initialization", validate_initialization()))
    results.append(("Data Update", validate_data_update()))
    results.append(("Multi-Drone Support", validate_multi_drone()))
    results.append(("Violation Highlighting", validate_violation_highlighting()))
    results.append(("Data Structures", validate_data_structures()))
    results.append(("Configuration", validate_configuration()))
    
    # Print summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "="*60)
    print(f"Results: {passed}/{total} tests passed")
    print("="*60)
    
    if passed == total:
        print("\n✓ All validation tests passed!")
        print("\nThe visualizer is ready for use.")
        print("\nNext steps:")
        print("1. Run examples: python examples/visualizer_example.py")
        print("2. Run unit tests: python tests/test_visualizer.py")
        print("3. Integrate with main application")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        print("\nPlease review the failures above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
