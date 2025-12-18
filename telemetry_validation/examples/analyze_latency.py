#!/usr/bin/env python3
"""
Latency Analysis Example Script

This script demonstrates how to analyze end-to-end latency metrics from enhanced
CSV logs with tx_timestamp data. It calculates latency percentiles (p50, p95, p99),
generates latency distribution histograms, and identifies high-latency events.

Requirements: 6.2, 6.5

Usage:
    python analyze_latency.py <log_file1> [log_file2] [log_file3] ...
    
Example:
    python analyze_latency.py \
        telemetry_logs/drone2_primary_20251118.csv \
        telemetry_logs/drone2_secondary_20251118.csv
"""

import sys
import os
import logging
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np

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


def analyze_drone_latency(log_file: str, drone_name: str, high_latency_threshold_ms: float = 500.0):
    """
    Analyze latency metrics for a single drone log file.
    
    Args:
        log_file: Path to CSV log file
        drone_name: Name of the drone (for display purposes)
        high_latency_threshold_ms: Threshold in milliseconds for identifying high-latency events
        
    Returns:
        Dictionary with latency metrics and data
    """
    logger.info(f"Analyzing latency for {drone_name} from {log_file}")
    
    # Load log file
    try:
        entries, format_type = load_flight_log(log_file)
    except Exception as e:
        logger.error(f"Failed to load {log_file}: {e}")
        return None
    
    if format_type != 'enhanced':
        logger.warning(f"{drone_name}: Legacy format detected, latency analysis not available")
        return None
    
    if not entries:
        logger.warning(f"{drone_name}: No entries found in log file")
        return None
    
    # Calculate latency
    calculator = MetricsCalculator()
    latency_values_s = calculator.calculate_end_to_end_latency(entries)
    
    if not latency_values_s:
        logger.warning(f"{drone_name}: No latency data available (tx_timestamp = 0)")
        return None
    
    # Convert to milliseconds
    latency_values_ms = [l * 1000 for l in latency_values_s]
    
    # Calculate percentiles
    p50 = np.percentile(latency_values_ms, 50)
    p95 = np.percentile(latency_values_ms, 95)
    p99 = np.percentile(latency_values_ms, 99)
    avg_latency = np.mean(latency_values_ms)
    max_latency = np.max(latency_values_ms)
    min_latency = np.min(latency_values_ms)
    
    # Identify high-latency events
    high_latency_events = []
    for idx, entry in enumerate(entries):
        if entry.tx_timestamp > 0:
            latency_ms = entry.timestamp_ms - entry.tx_timestamp
            if 0 < latency_ms < 10000 and latency_ms > high_latency_threshold_ms:
                high_latency_events.append({
                    'timestamp_ms': entry.timestamp_ms,
                    'latency_ms': latency_ms,
                    'sequence_number': entry.sequence_number,
                    'rssi_dbm': entry.rssi_dbm,
                    'snr_db': entry.snr_db,
                    'queue_depth': entry.queue_depth
                })
    
    logger.info(f"{drone_name} Latency Statistics:")
    logger.info(f"  Samples:     {len(latency_values_ms)}")
    logger.info(f"  Average:     {avg_latency:.2f} ms")
    logger.info(f"  Median (p50): {p50:.2f} ms")
    logger.info(f"  p95:         {p95:.2f} ms")
    logger.info(f"  p99:         {p99:.2f} ms")
    logger.info(f"  Maximum:     {max_latency:.2f} ms")
    logger.info(f"  Minimum:     {min_latency:.2f} ms")
    logger.info(f"  High-latency events (>{high_latency_threshold_ms}ms): {len(high_latency_events)}")
    
    return {
        'drone_name': drone_name,
        'latency_values_ms': latency_values_ms,
        'avg_latency': avg_latency,
        'p50': p50,
        'p95': p95,
        'p99': p99,
        'max_latency': max_latency,
        'min_latency': min_latency,
        'sample_count': len(latency_values_ms),
        'high_latency_events': high_latency_events,
        'high_latency_threshold_ms': high_latency_threshold_ms
    }


def generate_latency_charts(results: list, output_file: str):
    """
    Generate latency distribution histograms and comparison charts.
    
    Args:
        results: List of latency analysis results
        output_file: Path to save the chart
    """
    logger.info("Generating latency distribution charts...")
    
    # Filter out None results
    valid_results = [r for r in results if r is not None]
    
    if not valid_results:
        logger.error("No valid latency data to plot")
        return
    
    # Create figure with subplots
    num_drones = len(valid_results)
    fig = plt.figure(figsize=(14, 4 * num_drones + 4))
    fig.suptitle('End-to-End Latency Analysis', fontsize=16, fontweight='bold')
    
    # Create grid: one histogram per drone + one comparison chart
    gs = fig.add_gridspec(num_drones + 1, 1, hspace=0.3)
    
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    
    # Plot histogram for each drone
    for idx, result in enumerate(valid_results):
        ax = fig.add_subplot(gs[idx, 0])
        color = colors[idx % len(colors)]
        
        # Create histogram
        n, bins, patches = ax.hist(
            result['latency_values_ms'],
            bins=50,
            color=color,
            alpha=0.7,
            edgecolor='black',
            linewidth=0.5
        )
        
        # Add percentile lines
        ax.axvline(result['p50'], color='green', linestyle='--', linewidth=2, 
                  label=f"p50: {result['p50']:.2f}ms")
        ax.axvline(result['p95'], color='orange', linestyle='--', linewidth=2,
                  label=f"p95: {result['p95']:.2f}ms")
        ax.axvline(result['p99'], color='red', linestyle='--', linewidth=2,
                  label=f"p99: {result['p99']:.2f}ms")
        
        ax.set_xlabel('Latency (ms)', fontsize=11)
        ax.set_ylabel('Count', fontsize=11)
        ax.set_title(f'{result["drone_name"]} - Latency Distribution (n={result["sample_count"]})',
                    fontsize=12, fontweight='bold')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3, axis='y')
    
    # Comparison bar chart
    ax_comp = fig.add_subplot(gs[num_drones, 0])
    
    drone_names = [r['drone_name'] for r in valid_results]
    p50_values = [r['p50'] for r in valid_results]
    p95_values = [r['p95'] for r in valid_results]
    p99_values = [r['p99'] for r in valid_results]
    avg_values = [r['avg_latency'] for r in valid_results]
    
    x = np.arange(len(drone_names))
    width = 0.2
    
    ax_comp.bar(x - 1.5*width, avg_values, width, label='Average', color='#2ca02c', alpha=0.8)
    ax_comp.bar(x - 0.5*width, p50_values, width, label='p50', color='#1f77b4', alpha=0.8)
    ax_comp.bar(x + 0.5*width, p95_values, width, label='p95', color='#ff7f0e', alpha=0.8)
    ax_comp.bar(x + 1.5*width, p99_values, width, label='p99', color='#d62728', alpha=0.8)
    
    ax_comp.set_xlabel('Drone', fontsize=12)
    ax_comp.set_ylabel('Latency (ms)', fontsize=12)
    ax_comp.set_title('Latency Percentile Comparison', fontsize=14, fontweight='bold')
    ax_comp.set_xticks(x)
    ax_comp.set_xticklabels(drone_names)
    ax_comp.legend(loc='best')
    ax_comp.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for i, (avg, p50, p95, p99) in enumerate(zip(avg_values, p50_values, p95_values, p99_values)):
        ax_comp.text(i - 1.5*width, avg, f'{avg:.0f}', ha='center', va='bottom', fontsize=8)
        ax_comp.text(i - 0.5*width, p50, f'{p50:.0f}', ha='center', va='bottom', fontsize=8)
        ax_comp.text(i + 0.5*width, p95, f'{p95:.0f}', ha='center', va='bottom', fontsize=8)
        ax_comp.text(i + 1.5*width, p99, f'{p99:.0f}', ha='center', va='bottom', fontsize=8)
    
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    logger.info(f"Chart saved to {output_file}")
    plt.close()


def save_report(results: list, output_file: str):
    """
    Save latency analysis report to a text file.
    
    Args:
        results: List of latency analysis results
        output_file: Path to save the report
    """
    logger.info(f"Saving report to {output_file}")
    
    # Filter out None results
    valid_results = [r for r in results if r is not None]
    
    with open(output_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("END-TO-END LATENCY ANALYSIS REPORT\n")
        f.write("=" * 80 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Drones Analyzed: {len(valid_results)}\n")
        f.write("=" * 80 + "\n\n")
        
        for result in valid_results:
            f.write(f"Drone: {result['drone_name']}\n")
            f.write("-" * 80 + "\n")
            f.write(f"  Sample Count:       {result['sample_count']}\n")
            f.write(f"  Average Latency:    {result['avg_latency']:.2f} ms\n")
            f.write(f"  Median (p50):       {result['p50']:.2f} ms\n")
            f.write(f"  95th Percentile:    {result['p95']:.2f} ms\n")
            f.write(f"  99th Percentile:    {result['p99']:.2f} ms\n")
            f.write(f"  Maximum Latency:    {result['max_latency']:.2f} ms\n")
            f.write(f"  Minimum Latency:    {result['min_latency']:.2f} ms\n")
            f.write(f"  High-Latency Events (>{result['high_latency_threshold_ms']}ms): "
                   f"{len(result['high_latency_events'])}\n")
            
            # List high-latency events
            if result['high_latency_events']:
                f.write(f"\n  High-Latency Events:\n")
                f.write(f"  {'Timestamp (ms)':<15} {'Latency (ms)':<15} {'RSSI (dBm)':<12} "
                       f"{'SNR (dB)':<10} {'Queue Depth':<12}\n")
                f.write(f"  {'-'*15} {'-'*15} {'-'*12} {'-'*10} {'-'*12}\n")
                
                # Show up to 10 worst events
                sorted_events = sorted(result['high_latency_events'], 
                                     key=lambda e: e['latency_ms'], reverse=True)
                for event in sorted_events[:10]:
                    f.write(f"  {event['timestamp_ms']:<15} {event['latency_ms']:<15.2f} "
                           f"{event['rssi_dbm']:<12.2f} {event['snr_db']:<10.2f} "
                           f"{event['queue_depth']:<12}\n")
                
                if len(sorted_events) > 10:
                    f.write(f"  ... and {len(sorted_events) - 10} more events\n")
            
            f.write("\n")
        
        # Summary comparison
        if len(valid_results) > 1:
            f.write("=" * 80 + "\n")
            f.write("COMPARISON SUMMARY\n")
            f.write("=" * 80 + "\n")
            
            # Find best and worst performers
            best_avg = min(valid_results, key=lambda r: r['avg_latency'])
            worst_avg = max(valid_results, key=lambda r: r['avg_latency'])
            best_p99 = min(valid_results, key=lambda r: r['p99'])
            worst_p99 = max(valid_results, key=lambda r: r['p99'])
            
            f.write(f"Lowest Average Latency:  {best_avg['drone_name']} "
                   f"({best_avg['avg_latency']:.2f} ms)\n")
            f.write(f"Highest Average Latency: {worst_avg['drone_name']} "
                   f"({worst_avg['avg_latency']:.2f} ms)\n")
            f.write(f"Best p99 Latency:        {best_p99['drone_name']} "
                   f"({best_p99['p99']:.2f} ms)\n")
            f.write(f"Worst p99 Latency:       {worst_p99['drone_name']} "
                   f"({worst_p99['p99']:.2f} ms)\n")
            f.write("\n")
        
        f.write("=" * 80 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 80 + "\n")
    
    logger.info(f"Report saved to {output_file}")


def main():
    """Main entry point for latency analysis."""
    if len(sys.argv) < 2:
        print("Usage: python analyze_latency.py <log_file1> [log_file2] [log_file3] ...")
        print("\nExample:")
        print("  python analyze_latency.py \\")
        print("      telemetry_logs/drone2_primary_20251118.csv \\")
        print("      telemetry_logs/drone2_secondary_20251118.csv")
        print("\nNote: Only logs with tx_timestamp data (Drone2 Primary/Secondary) will show latency metrics.")
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
        result = analyze_drone_latency(log_file, drone_name, high_latency_threshold_ms=500.0)
        results.append(result)
    
    # Check if we have any valid results
    valid_results = [r for r in results if r is not None]
    if not valid_results:
        logger.error("No valid latency data found in any log files")
        sys.exit(1)
    
    # Generate outputs
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path('telemetry_logs')
    output_dir.mkdir(exist_ok=True)
    
    chart_file = output_dir / f'latency_analysis_{timestamp}.png'
    report_file = output_dir / f'latency_report_{timestamp}.txt'
    
    generate_latency_charts(results, str(chart_file))
    save_report(results, str(report_file))
    
    logger.info("Latency analysis complete!")
    logger.info(f"  Chart: {chart_file}")
    logger.info(f"  Report: {report_file}")


if __name__ == '__main__':
    main()
