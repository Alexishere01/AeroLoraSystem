#!/usr/bin/env python3
"""
Queue Congestion Analysis Example Script

This script demonstrates how to analyze queue congestion from enhanced CSV logs
with queue_depth data. It detects queue saturation events (queue_depth > 20),
calculates congestion duration and frequency, and correlates congestion with
packet loss.

Requirements: 6.3, 6.5

Usage:
    python analyze_queue_congestion.py <log_file1> [log_file2] [log_file3] ...
    
Example:
    python analyze_queue_congestion.py \
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


def analyze_drone_queue_congestion(log_file: str, drone_name: str, threshold: int = 20):
    """
    Analyze queue congestion metrics for a single drone log file.
    
    Args:
        log_file: Path to CSV log file
        drone_name: Name of the drone (for display purposes)
        threshold: Queue depth threshold for congestion detection
        
    Returns:
        Dictionary with queue congestion metrics and data
    """
    logger.info(f"Analyzing queue congestion for {drone_name} from {log_file}")
    
    # Load log file
    try:
        entries, format_type = load_flight_log(log_file)
    except Exception as e:
        logger.error(f"Failed to load {log_file}: {e}")
        return None
    
    if format_type != 'enhanced':
        logger.warning(f"{drone_name}: Legacy format detected, queue analysis not available")
        return None
    
    if not entries:
        logger.warning(f"{drone_name}: No entries found in log file")
        return None
    
    # Check if queue_depth data is available
    has_queue_data = any(entry.queue_depth > 0 for entry in entries)
    if not has_queue_data:
        logger.warning(f"{drone_name}: No queue depth data available (queue_depth = 0)")
        return None
    
    # Calculate queue metrics
    calculator = MetricsCalculator()
    congestion_events = calculator.detect_queue_congestion(entries, threshold=threshold)
    
    # Extract queue depth over time
    timestamps = [entry.timestamp_ms / 1000.0 for entry in entries]  # Convert to seconds
    queue_depths = [entry.queue_depth for entry in entries]
    
    # Calculate statistics
    avg_queue_depth = np.mean([q for q in queue_depths if q > 0])
    max_queue_depth = max(queue_depths)
    
    # Calculate congestion duration and frequency
    congestion_periods = []
    if congestion_events:
        # Group consecutive congestion events into periods
        current_period_start = None
        current_period_end = None
        
        for timestamp_ms, queue_depth in congestion_events:
            if current_period_start is None:
                current_period_start = timestamp_ms
                current_period_end = timestamp_ms
            elif timestamp_ms - current_period_end < 1000:  # Within 1 second
                current_period_end = timestamp_ms
            else:
                # Save previous period and start new one
                congestion_periods.append({
                    'start_ms': current_period_start,
                    'end_ms': current_period_end,
                    'duration_ms': current_period_end - current_period_start
                })
                current_period_start = timestamp_ms
                current_period_end = timestamp_ms
        
        # Save last period
        if current_period_start is not None:
            congestion_periods.append({
                'start_ms': current_period_start,
                'end_ms': current_period_end,
                'duration_ms': current_period_end - current_period_start
            })
    
    total_congestion_duration_ms = sum(p['duration_ms'] for p in congestion_periods)
    total_duration_ms = entries[-1].timestamp_ms - entries[0].timestamp_ms
    congestion_percentage = (total_congestion_duration_ms / total_duration_ms * 100) if total_duration_ms > 0 else 0
    
    # Correlate with packet loss (using sequence numbers)
    packet_loss_during_congestion = 0
    packet_loss_normal = 0
    
    prev_seq = None
    for entry in entries:
        if prev_seq is not None:
            expected_seq = (prev_seq + 1) % 65536  # Assuming 16-bit sequence
            if entry.sequence_number != expected_seq:
                # Packet loss detected
                if entry.queue_depth > threshold:
                    packet_loss_during_congestion += 1
                else:
                    packet_loss_normal += 1
        prev_seq = entry.sequence_number
    
    logger.info(f"{drone_name} Queue Congestion Statistics:")
    logger.info(f"  Average Queue Depth:     {avg_queue_depth:.2f}")
    logger.info(f"  Maximum Queue Depth:     {max_queue_depth}")
    logger.info(f"  Congestion Events:       {len(congestion_events)}")
    logger.info(f"  Congestion Periods:      {len(congestion_periods)}")
    logger.info(f"  Total Congestion Time:   {total_congestion_duration_ms / 1000:.2f} seconds "
               f"({congestion_percentage:.1f}% of total)")
    logger.info(f"  Packet Loss (Congested): {packet_loss_during_congestion}")
    logger.info(f"  Packet Loss (Normal):    {packet_loss_normal}")
    
    return {
        'drone_name': drone_name,
        'timestamps': timestamps,
        'queue_depths': queue_depths,
        'avg_queue_depth': avg_queue_depth,
        'max_queue_depth': max_queue_depth,
        'congestion_events': congestion_events,
        'congestion_periods': congestion_periods,
        'total_congestion_duration_ms': total_congestion_duration_ms,
        'congestion_percentage': congestion_percentage,
        'packet_loss_during_congestion': packet_loss_during_congestion,
        'packet_loss_normal': packet_loss_normal,
        'threshold': threshold,
        'total_duration_ms': total_duration_ms
    }


def generate_congestion_charts(results: list, output_file: str):
    """
    Generate queue congestion visualization charts.
    
    Args:
        results: List of queue congestion analysis results
        output_file: Path to save the chart
    """
    logger.info("Generating queue congestion charts...")
    
    # Filter out None results
    valid_results = [r for r in results if r is not None]
    
    if not valid_results:
        logger.error("No valid queue congestion data to plot")
        return
    
    # Create figure with subplots
    num_drones = len(valid_results)
    fig = plt.figure(figsize=(14, 4 * num_drones + 4))
    fig.suptitle('Queue Congestion Analysis', fontsize=16, fontweight='bold')
    
    # Create grid: one time series per drone + one comparison chart
    gs = fig.add_gridspec(num_drones + 1, 1, hspace=0.3)
    
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    
    # Plot queue depth over time for each drone
    for idx, result in enumerate(valid_results):
        ax = fig.add_subplot(gs[idx, 0])
        color = colors[idx % len(colors)]
        
        # Plot queue depth
        ax.plot(result['timestamps'], result['queue_depths'], 
               color=color, linewidth=1.0, alpha=0.7, label='Queue Depth')
        
        # Highlight congestion threshold
        ax.axhline(y=result['threshold'], color='red', linestyle='--', 
                  linewidth=2, alpha=0.7, label=f'Threshold ({result["threshold"]})')
        
        # Highlight congestion periods
        for period in result['congestion_periods']:
            start_s = period['start_ms'] / 1000.0
            end_s = period['end_ms'] / 1000.0
            ax.axvspan(start_s, end_s, alpha=0.2, color='red')
        
        ax.set_xlabel('Time (seconds)', fontsize=11)
        ax.set_ylabel('Queue Depth', fontsize=11)
        ax.set_title(f'{result["drone_name"]} - Queue Depth Over Time '
                    f'({len(result["congestion_periods"])} congestion periods)',
                    fontsize=12, fontweight='bold')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)
    
    # Comparison bar chart
    ax_comp = fig.add_subplot(gs[num_drones, 0])
    
    drone_names = [r['drone_name'] for r in valid_results]
    avg_depths = [r['avg_queue_depth'] for r in valid_results]
    max_depths = [r['max_queue_depth'] for r in valid_results]
    congestion_pcts = [r['congestion_percentage'] for r in valid_results]
    
    x = np.arange(len(drone_names))
    width = 0.25
    
    # Create twin axis for percentage
    ax_comp2 = ax_comp.twinx()
    
    ax_comp.bar(x - width, avg_depths, width, label='Avg Queue Depth', 
               color='#2ca02c', alpha=0.8)
    ax_comp.bar(x, max_depths, width, label='Max Queue Depth', 
               color='#ff7f0e', alpha=0.8)
    ax_comp2.bar(x + width, congestion_pcts, width, label='Congestion %', 
                color='#d62728', alpha=0.8)
    
    ax_comp.set_xlabel('Drone', fontsize=12)
    ax_comp.set_ylabel('Queue Depth', fontsize=12)
    ax_comp2.set_ylabel('Congestion Time (%)', fontsize=12)
    ax_comp.set_title('Queue Congestion Comparison', fontsize=14, fontweight='bold')
    ax_comp.set_xticks(x)
    ax_comp.set_xticklabels(drone_names)
    
    # Combine legends
    lines1, labels1 = ax_comp.get_legend_handles_labels()
    lines2, labels2 = ax_comp2.get_legend_handles_labels()
    ax_comp.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    ax_comp.grid(True, alpha=0.3, axis='y')
    
    # Add value labels
    for i, (avg, max_val, pct) in enumerate(zip(avg_depths, max_depths, congestion_pcts)):
        ax_comp.text(i - width, avg, f'{avg:.1f}', ha='center', va='bottom', fontsize=8)
        ax_comp.text(i, max_val, f'{max_val}', ha='center', va='bottom', fontsize=8)
        ax_comp2.text(i + width, pct, f'{pct:.1f}%', ha='center', va='bottom', fontsize=8)
    
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    logger.info(f"Chart saved to {output_file}")
    plt.close()


def save_report(results: list, output_file: str):
    """
    Save queue congestion analysis report to a text file.
    
    Args:
        results: List of queue congestion analysis results
        output_file: Path to save the report
    """
    logger.info(f"Saving report to {output_file}")
    
    # Filter out None results
    valid_results = [r for r in results if r is not None]
    
    with open(output_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("QUEUE CONGESTION ANALYSIS REPORT\n")
        f.write("=" * 80 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Drones Analyzed: {len(valid_results)}\n")
        f.write("=" * 80 + "\n\n")
        
        for result in valid_results:
            f.write(f"Drone: {result['drone_name']}\n")
            f.write("-" * 80 + "\n")
            f.write(f"  Congestion Threshold:    {result['threshold']}\n")
            f.write(f"  Average Queue Depth:     {result['avg_queue_depth']:.2f}\n")
            f.write(f"  Maximum Queue Depth:     {result['max_queue_depth']}\n")
            f.write(f"  Congestion Events:       {len(result['congestion_events'])}\n")
            f.write(f"  Congestion Periods:      {len(result['congestion_periods'])}\n")
            f.write(f"  Total Duration:          {result['total_duration_ms'] / 1000:.2f} seconds\n")
            f.write(f"  Congestion Duration:     {result['total_congestion_duration_ms'] / 1000:.2f} seconds "
                   f"({result['congestion_percentage']:.1f}%)\n")
            f.write(f"  Packet Loss (Congested): {result['packet_loss_during_congestion']}\n")
            f.write(f"  Packet Loss (Normal):    {result['packet_loss_normal']}\n")
            
            # Calculate packet loss correlation
            total_loss = result['packet_loss_during_congestion'] + result['packet_loss_normal']
            if total_loss > 0:
                loss_during_congestion_pct = (result['packet_loss_during_congestion'] / total_loss * 100)
                f.write(f"  Loss During Congestion:  {loss_during_congestion_pct:.1f}% of total packet loss\n")
            
            # List longest congestion periods
            if result['congestion_periods']:
                f.write(f"\n  Longest Congestion Periods:\n")
                f.write(f"  {'Start (s)':<12} {'End (s)':<12} {'Duration (ms)':<15}\n")
                f.write(f"  {'-'*12} {'-'*12} {'-'*15}\n")
                
                sorted_periods = sorted(result['congestion_periods'], 
                                      key=lambda p: p['duration_ms'], reverse=True)
                for period in sorted_periods[:10]:
                    f.write(f"  {period['start_ms']/1000:<12.2f} {period['end_ms']/1000:<12.2f} "
                           f"{period['duration_ms']:<15.0f}\n")
                
                if len(sorted_periods) > 10:
                    f.write(f"  ... and {len(sorted_periods) - 10} more periods\n")
            
            f.write("\n")
        
        # Summary comparison
        if len(valid_results) > 1:
            f.write("=" * 80 + "\n")
            f.write("COMPARISON SUMMARY\n")
            f.write("=" * 80 + "\n")
            
            # Find best and worst performers
            best_congestion = min(valid_results, key=lambda r: r['congestion_percentage'])
            worst_congestion = max(valid_results, key=lambda r: r['congestion_percentage'])
            most_loss_during_congestion = max(valid_results, 
                                             key=lambda r: r['packet_loss_during_congestion'])
            
            f.write(f"Least Congestion:        {best_congestion['drone_name']} "
                   f"({best_congestion['congestion_percentage']:.1f}%)\n")
            f.write(f"Most Congestion:         {worst_congestion['drone_name']} "
                   f"({worst_congestion['congestion_percentage']:.1f}%)\n")
            f.write(f"Most Loss During Congestion: {most_loss_during_congestion['drone_name']} "
                   f"({most_loss_during_congestion['packet_loss_during_congestion']} packets)\n")
            f.write("\n")
        
        f.write("=" * 80 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 80 + "\n")
    
    logger.info(f"Report saved to {output_file}")


def main():
    """Main entry point for queue congestion analysis."""
    if len(sys.argv) < 2:
        print("Usage: python analyze_queue_congestion.py <log_file1> [log_file2] [log_file3] ...")
        print("\nExample:")
        print("  python analyze_queue_congestion.py \\")
        print("      telemetry_logs/drone2_primary_20251118.csv \\")
        print("      telemetry_logs/drone2_secondary_20251118.csv")
        print("\nNote: Only logs with queue_depth data (Drone2 Primary/Secondary) will show congestion metrics.")
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
        result = analyze_drone_queue_congestion(log_file, drone_name, threshold=20)
        results.append(result)
    
    # Check if we have any valid results
    valid_results = [r for r in results if r is not None]
    if not valid_results:
        logger.error("No valid queue congestion data found in any log files")
        sys.exit(1)
    
    # Generate outputs
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path('telemetry_logs')
    output_dir.mkdir(exist_ok=True)
    
    chart_file = output_dir / f'queue_congestion_analysis_{timestamp}.png'
    report_file = output_dir / f'queue_congestion_report_{timestamp}.txt'
    
    generate_congestion_charts(results, str(chart_file))
    save_report(results, str(report_file))
    
    logger.info("Queue congestion analysis complete!")
    logger.info(f"  Chart: {chart_file}")
    logger.info(f"  Report: {report_file}")


if __name__ == '__main__':
    main()
