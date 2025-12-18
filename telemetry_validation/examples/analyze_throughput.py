#!/usr/bin/env python3
"""
Throughput Analysis Example Script

This script demonstrates how to analyze throughput metrics from enhanced CSV logs
captured from all three drone modules (Drone1, Drone2 Primary, Drone2 Secondary).

It calculates average, peak, and minimum throughput for each drone and generates
a comparison chart showing throughput over time.

Requirements: 6.1, 6.5

Usage:
    python analyze_throughput.py <drone1_log.csv> <drone2_primary_log.csv> <drone2_secondary_log.csv>
    
Example:
    python analyze_throughput.py \
        telemetry_logs/drone1_20251118.csv \
        telemetry_logs/drone2_primary_20251118.csv \
        telemetry_logs/drone2_secondary_20251118.csv
"""

import sys
import os
import logging
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.csv_utils import load_flight_log
from src.metrics_calculator import MetricsCalculator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def analyze_drone_throughput(log_file: str, drone_name: str):
    """
    Analyze throughput metrics for a single drone log file.
    
    Args:
        log_file: Path to CSV log file
        drone_name: Name of the drone (for display purposes)
        
    Returns:
        Dictionary with throughput metrics and data
    """
    logger.info(f"Analyzing throughput for {drone_name} from {log_file}")
    
    # Load log file
    try:
        entries, format_type = load_flight_log(log_file)
    except Exception as e:
        logger.error(f"Failed to load {log_file}: {e}")
        return None
    
    if format_type != 'enhanced':
        logger.warning(f"{drone_name}: Legacy format detected, throughput analysis not available")
        return None
    
    if not entries:
        logger.warning(f"{drone_name}: No entries found in log file")
        return None
    
    # Calculate throughput
    calculator = MetricsCalculator()
    throughput_values = calculator.calculate_throughput(entries, window_seconds=1.0)
    
    if not throughput_values:
        logger.warning(f"{drone_name}: No throughput data available (packet_size = 0)")
        return None
    
    # Calculate statistics
    avg_throughput = sum(throughput_values) / len(throughput_values)
    peak_throughput = max(throughput_values)
    min_throughput = min(throughput_values)
    
    # Calculate timestamps for plotting
    start_time_ms = entries[0].timestamp_ms
    timestamps = []
    current_window_start = start_time_ms
    
    for _ in throughput_values:
        timestamps.append(current_window_start / 1000.0)  # Convert to seconds
        current_window_start += 1000  # 1 second windows
    
    logger.info(f"{drone_name} Throughput Statistics:")
    logger.info(f"  Average: {avg_throughput:.2f} bytes/s ({avg_throughput * 8 / 1000:.2f} kbps)")
    logger.info(f"  Peak:    {peak_throughput:.2f} bytes/s ({peak_throughput * 8 / 1000:.2f} kbps)")
    logger.info(f"  Minimum: {min_throughput:.2f} bytes/s ({min_throughput * 8 / 1000:.2f} kbps)")
    
    return {
        'drone_name': drone_name,
        'avg_throughput': avg_throughput,
        'peak_throughput': peak_throughput,
        'min_throughput': min_throughput,
        'throughput_values': throughput_values,
        'timestamps': timestamps,
        'total_entries': len(entries),
        'duration_seconds': (entries[-1].timestamp_ms - entries[0].timestamp_ms) / 1000.0
    }


def generate_comparison_chart(results: list, output_file: str):
    """
    Generate a throughput comparison chart for all drones.
    
    Args:
        results: List of throughput analysis results
        output_file: Path to save the chart
    """
    logger.info("Generating throughput comparison chart...")
    
    # Filter out None results
    valid_results = [r for r in results if r is not None]
    
    if not valid_results:
        logger.error("No valid throughput data to plot")
        return
    
    # Create figure with subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    fig.suptitle('Drone Throughput Analysis', fontsize=16, fontweight='bold')
    
    # Plot 1: Throughput over time for each drone
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    
    for idx, result in enumerate(valid_results):
        color = colors[idx % len(colors)]
        ax1.plot(
            result['timestamps'],
            result['throughput_values'],
            label=result['drone_name'],
            color=color,
            linewidth=1.5,
            alpha=0.8
        )
    
    ax1.set_xlabel('Time (seconds)', fontsize=12)
    ax1.set_ylabel('Throughput (bytes/s)', fontsize=12)
    ax1.set_title('Throughput Over Time', fontsize=14)
    ax1.legend(loc='best')
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Bar chart comparing average, peak, and min throughput
    drone_names = [r['drone_name'] for r in valid_results]
    avg_values = [r['avg_throughput'] for r in valid_results]
    peak_values = [r['peak_throughput'] for r in valid_results]
    min_values = [r['min_throughput'] for r in valid_results]
    
    x = range(len(drone_names))
    width = 0.25
    
    ax2.bar([i - width for i in x], avg_values, width, label='Average', color='#2ca02c', alpha=0.8)
    ax2.bar(x, peak_values, width, label='Peak', color='#ff7f0e', alpha=0.8)
    ax2.bar([i + width for i in x], min_values, width, label='Minimum', color='#1f77b4', alpha=0.8)
    
    ax2.set_xlabel('Drone', fontsize=12)
    ax2.set_ylabel('Throughput (bytes/s)', fontsize=12)
    ax2.set_title('Throughput Comparison', fontsize=14)
    ax2.set_xticks(x)
    ax2.set_xticklabels(drone_names)
    ax2.legend(loc='best')
    ax2.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for i, (avg, peak, min_val) in enumerate(zip(avg_values, peak_values, min_values)):
        ax2.text(i - width, avg, f'{avg:.0f}', ha='center', va='bottom', fontsize=9)
        ax2.text(i, peak, f'{peak:.0f}', ha='center', va='bottom', fontsize=9)
        ax2.text(i + width, min_val, f'{min_val:.0f}', ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    logger.info(f"Chart saved to {output_file}")
    plt.close()


def save_report(results: list, output_file: str):
    """
    Save throughput analysis report to a text file.
    
    Args:
        results: List of throughput analysis results
        output_file: Path to save the report
    """
    logger.info(f"Saving report to {output_file}")
    
    # Filter out None results
    valid_results = [r for r in results if r is not None]
    
    with open(output_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("THROUGHPUT ANALYSIS REPORT\n")
        f.write("=" * 80 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Drones Analyzed: {len(valid_results)}\n")
        f.write("=" * 80 + "\n\n")
        
        for result in valid_results:
            f.write(f"Drone: {result['drone_name']}\n")
            f.write("-" * 80 + "\n")
            f.write(f"  Total Entries:     {result['total_entries']}\n")
            f.write(f"  Duration:          {result['duration_seconds']:.2f} seconds\n")
            f.write(f"  Average Throughput: {result['avg_throughput']:.2f} bytes/s "
                   f"({result['avg_throughput'] * 8 / 1000:.2f} kbps)\n")
            f.write(f"  Peak Throughput:    {result['peak_throughput']:.2f} bytes/s "
                   f"({result['peak_throughput'] * 8 / 1000:.2f} kbps)\n")
            f.write(f"  Minimum Throughput: {result['min_throughput']:.2f} bytes/s "
                   f"({result['min_throughput'] * 8 / 1000:.2f} kbps)\n")
            f.write("\n")
        
        # Summary comparison
        if len(valid_results) > 1:
            f.write("=" * 80 + "\n")
            f.write("COMPARISON SUMMARY\n")
            f.write("=" * 80 + "\n")
            
            # Find best performers
            best_avg = max(valid_results, key=lambda r: r['avg_throughput'])
            best_peak = max(valid_results, key=lambda r: r['peak_throughput'])
            
            f.write(f"Highest Average Throughput: {best_avg['drone_name']} "
                   f"({best_avg['avg_throughput']:.2f} bytes/s)\n")
            f.write(f"Highest Peak Throughput:    {best_peak['drone_name']} "
                   f"({best_peak['peak_throughput']:.2f} bytes/s)\n")
            f.write("\n")
        
        f.write("=" * 80 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 80 + "\n")
    
    logger.info(f"Report saved to {output_file}")


def main():
    """Main entry point for throughput analysis."""
    if len(sys.argv) < 2:
        print("Usage: python analyze_throughput.py <log_file1> [log_file2] [log_file3] ...")
        print("\nExample:")
        print("  python analyze_throughput.py \\")
        print("      telemetry_logs/drone1_20251118.csv \\")
        print("      telemetry_logs/drone2_primary_20251118.csv \\")
        print("      telemetry_logs/drone2_secondary_20251118.csv")
        sys.exit(1)
    
    log_files = sys.argv[1:]
    
    # Validate files exist
    for log_file in log_files:
        if not os.path.exists(log_file):
            logger.error(f"File not found: {log_file}")
            sys.exit(1)
    
    # Analyze each drone
    results = []
    drone_names = ['Drone1', 'Drone2 Primary', 'Drone2 Secondary']
    
    for idx, log_file in enumerate(log_files):
        drone_name = drone_names[idx] if idx < len(drone_names) else f'Drone{idx + 1}'
        result = analyze_drone_throughput(log_file, drone_name)
        results.append(result)
    
    # Generate outputs
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path('telemetry_logs')
    output_dir.mkdir(exist_ok=True)
    
    chart_file = output_dir / f'throughput_analysis_{timestamp}.png'
    report_file = output_dir / f'throughput_report_{timestamp}.txt'
    
    generate_comparison_chart(results, str(chart_file))
    save_report(results, str(report_file))
    
    logger.info("Throughput analysis complete!")
    logger.info(f"  Chart: {chart_file}")
    logger.info(f"  Report: {report_file}")


if __name__ == '__main__':
    main()
