#!/usr/bin/env python3
"""
Error Correlation Analysis Example Script

This script demonstrates how to correlate error rates with RSSI degradation from
enhanced CSV logs with errors field. It calculates error rates during good vs poor
link conditions and generates error correlation reports.

Requirements: 6.4, 6.5

Usage:
    python analyze_error_correlation.py <log_file1> [log_file2] [log_file3] ...
    
Example:
    python analyze_error_correlation.py \
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


def analyze_drone_error_correlation(log_file: str, drone_name: str, rssi_threshold: float = -85.0):
    """
    Analyze error correlation with RSSI for a single drone log file.
    
    Args:
        log_file: Path to CSV log file
        drone_name: Name of the drone (for display purposes)
        rssi_threshold: RSSI threshold in dBm for good/poor link classification
        
    Returns:
        Dictionary with error correlation metrics and data
    """
    logger.info(f"Analyzing error correlation for {drone_name} from {log_file}")
    
    # Load log file
    try:
        entries, format_type = load_flight_log(log_file)
    except Exception as e:
        logger.error(f"Failed to load {log_file}: {e}")
        return None
    
    if format_type != 'enhanced':
        logger.warning(f"{drone_name}: Legacy format detected, error correlation not available")
        return None
    
    if not entries:
        logger.warning(f"{drone_name}: No entries found in log file")
        return None
    
    # Check if error data is available
    has_error_data = entries[-1].errors > 0 if entries else False
    if not has_error_data:
        logger.warning(f"{drone_name}: No error data available (errors = 0)")
        return None
    
    # Calculate error correlation
    calculator = MetricsCalculator()
    error_correlation = calculator.correlate_errors_with_rssi(entries)
    
    # Extract time series data
    timestamps = [entry.timestamp_ms / 1000.0 for entry in entries]  # Convert to seconds
    rssi_values = [entry.rssi_dbm for entry in entries]
    snr_values = [entry.snr_db for entry in entries]
    error_counts = [entry.errors for entry in entries]
    
    # Calculate error deltas (new errors per sample)
    error_deltas = [0]
    for i in range(1, len(error_counts)):
        error_deltas.append(error_counts[i] - error_counts[i-1])
    
    # Calculate statistics
    total_errors = entries[-1].errors
    errors_good_link = sum(delta for _, delta in error_correlation['good_link'])
    errors_poor_link = sum(delta for _, delta in error_correlation['poor_link'])
    
    # Calculate time spent in each link condition
    good_link_samples = sum(1 for entry in entries if entry.rssi_dbm > rssi_threshold)
    poor_link_samples = len(entries) - good_link_samples
    
    total_duration_s = (entries[-1].timestamp_ms - entries[0].timestamp_ms) / 1000.0
    good_link_duration_s = (good_link_samples / len(entries)) * total_duration_s
    poor_link_duration_s = (poor_link_samples / len(entries)) * total_duration_s
    
    # Calculate error rates (errors per minute)
    error_rate_good_link = (errors_good_link / good_link_duration_s * 60) if good_link_duration_s > 0 else 0
    error_rate_poor_link = (errors_poor_link / poor_link_duration_s * 60) if poor_link_duration_s > 0 else 0
    
    # Find RSSI ranges with highest error rates
    rssi_bins = np.arange(-120, -40, 5)  # 5 dBm bins from -120 to -40
    errors_by_rssi_bin = {bin_start: 0 for bin_start in rssi_bins}
    samples_by_rssi_bin = {bin_start: 0 for bin_start in rssi_bins}
    
    for entry in entries:
        # Find appropriate bin
        for bin_start in rssi_bins:
            if bin_start <= entry.rssi_dbm < bin_start + 5:
                samples_by_rssi_bin[bin_start] += 1
                break
    
    prev_errors = 0
    for entry in entries:
        error_delta = entry.errors - prev_errors
        prev_errors = entry.errors
        
        # Find appropriate bin
        for bin_start in rssi_bins:
            if bin_start <= entry.rssi_dbm < bin_start + 5:
                errors_by_rssi_bin[bin_start] += error_delta
                break
    
    logger.info(f"{drone_name} Error Correlation Statistics:")
    logger.info(f"  Total Errors:            {total_errors}")
    logger.info(f"  Errors (Good Link):      {errors_good_link} ({errors_good_link/total_errors*100:.1f}%)")
    logger.info(f"  Errors (Poor Link):      {errors_poor_link} ({errors_poor_link/total_errors*100:.1f}%)")
    logger.info(f"  Error Rate (Good Link):  {error_rate_good_link:.2f} errors/min")
    logger.info(f"  Error Rate (Poor Link):  {error_rate_poor_link:.2f} errors/min")
    logger.info(f"  Good Link Duration:      {good_link_duration_s:.2f}s ({good_link_duration_s/total_duration_s*100:.1f}%)")
    logger.info(f"  Poor Link Duration:      {poor_link_duration_s:.2f}s ({poor_link_duration_s/total_duration_s*100:.1f}%)")
    
    return {
        'drone_name': drone_name,
        'timestamps': timestamps,
        'rssi_values': rssi_values,
        'snr_values': snr_values,
        'error_counts': error_counts,
        'error_deltas': error_deltas,
        'total_errors': total_errors,
        'errors_good_link': errors_good_link,
        'errors_poor_link': errors_poor_link,
        'error_rate_good_link': error_rate_good_link,
        'error_rate_poor_link': error_rate_poor_link,
        'good_link_duration_s': good_link_duration_s,
        'poor_link_duration_s': poor_link_duration_s,
        'rssi_threshold': rssi_threshold,
        'error_correlation': error_correlation,
        'errors_by_rssi_bin': errors_by_rssi_bin,
        'samples_by_rssi_bin': samples_by_rssi_bin,
        'rssi_bins': rssi_bins
    }


def generate_correlation_charts(results: list, output_file: str):
    """
    Generate error correlation visualization charts.
    
    Args:
        results: List of error correlation analysis results
        output_file: Path to save the chart
    """
    logger.info("Generating error correlation charts...")
    
    # Filter out None results
    valid_results = [r for r in results if r is not None]
    
    if not valid_results:
        logger.error("No valid error correlation data to plot")
        return
    
    # Create figure with subplots
    num_drones = len(valid_results)
    fig = plt.figure(figsize=(14, 5 * num_drones + 4))
    fig.suptitle('Error Correlation with RSSI Analysis', fontsize=16, fontweight='bold')
    
    # Create grid: two plots per drone + one comparison chart
    gs = fig.add_gridspec(num_drones * 2 + 1, 1, hspace=0.4)
    
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    
    # Plot for each drone
    for idx, result in enumerate(valid_results):
        color = colors[idx % len(colors)]
        
        # Plot 1: Error rate and RSSI over time
        ax1 = fig.add_subplot(gs[idx * 2, 0])
        
        # Create twin axis for RSSI
        ax1_twin = ax1.twinx()
        
        # Plot error deltas as bars
        ax1.bar(result['timestamps'], result['error_deltas'], 
               width=1.0, color='red', alpha=0.6, label='New Errors')
        
        # Plot RSSI as line
        ax1_twin.plot(result['timestamps'], result['rssi_values'], 
                     color=color, linewidth=1.5, alpha=0.8, label='RSSI')
        
        # Add threshold line
        ax1_twin.axhline(y=result['rssi_threshold'], color='orange', 
                        linestyle='--', linewidth=2, alpha=0.7,
                        label=f'Threshold ({result["rssi_threshold"]} dBm)')
        
        ax1.set_xlabel('Time (seconds)', fontsize=11)
        ax1.set_ylabel('New Errors', fontsize=11, color='red')
        ax1_twin.set_ylabel('RSSI (dBm)', fontsize=11, color=color)
        ax1.set_title(f'{result["drone_name"]} - Error Rate vs RSSI Over Time',
                     fontsize=12, fontweight='bold')
        
        # Combine legends
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax1_twin.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        
        ax1.grid(True, alpha=0.3)
        ax1.tick_params(axis='y', labelcolor='red')
        ax1_twin.tick_params(axis='y', labelcolor=color)
        
        # Plot 2: Errors by RSSI bin
        ax2 = fig.add_subplot(gs[idx * 2 + 1, 0])
        
        # Calculate error rate per bin (errors per sample)
        bin_centers = []
        error_rates = []
        
        for bin_start in result['rssi_bins']:
            if result['samples_by_rssi_bin'][bin_start] > 0:
                bin_centers.append(bin_start + 2.5)  # Center of 5 dBm bin
                error_rate = result['errors_by_rssi_bin'][bin_start] / result['samples_by_rssi_bin'][bin_start]
                error_rates.append(error_rate)
        
        if bin_centers:
            ax2.bar(bin_centers, error_rates, width=4.5, color=color, alpha=0.7, edgecolor='black')
            ax2.axvline(x=result['rssi_threshold'], color='orange', linestyle='--', 
                       linewidth=2, alpha=0.7, label=f'Threshold ({result["rssi_threshold"]} dBm)')
        
        ax2.set_xlabel('RSSI (dBm)', fontsize=11)
        ax2.set_ylabel('Errors per Sample', fontsize=11)
        ax2.set_title(f'{result["drone_name"]} - Error Rate by RSSI Range',
                     fontsize=12, fontweight='bold')
        ax2.legend(loc='upper left')
        ax2.grid(True, alpha=0.3, axis='y')
    
    # Comparison bar chart
    ax_comp = fig.add_subplot(gs[num_drones * 2, 0])
    
    drone_names = [r['drone_name'] for r in valid_results]
    error_rate_good = [r['error_rate_good_link'] for r in valid_results]
    error_rate_poor = [r['error_rate_poor_link'] for r in valid_results]
    
    x = np.arange(len(drone_names))
    width = 0.35
    
    ax_comp.bar(x - width/2, error_rate_good, width, label='Good Link (RSSI > -85 dBm)', 
               color='#2ca02c', alpha=0.8)
    ax_comp.bar(x + width/2, error_rate_poor, width, label='Poor Link (RSSI ≤ -85 dBm)', 
               color='#d62728', alpha=0.8)
    
    ax_comp.set_xlabel('Drone', fontsize=12)
    ax_comp.set_ylabel('Error Rate (errors/min)', fontsize=12)
    ax_comp.set_title('Error Rate Comparison: Good vs Poor Link', fontsize=14, fontweight='bold')
    ax_comp.set_xticks(x)
    ax_comp.set_xticklabels(drone_names)
    ax_comp.legend(loc='best')
    ax_comp.grid(True, alpha=0.3, axis='y')
    
    # Add value labels
    for i, (good, poor) in enumerate(zip(error_rate_good, error_rate_poor)):
        ax_comp.text(i - width/2, good, f'{good:.2f}', ha='center', va='bottom', fontsize=9)
        ax_comp.text(i + width/2, poor, f'{poor:.2f}', ha='center', va='bottom', fontsize=9)
    
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    logger.info(f"Chart saved to {output_file}")
    plt.close()


def save_report(results: list, output_file: str):
    """
    Save error correlation analysis report to a text file.
    
    Args:
        results: List of error correlation analysis results
        output_file: Path to save the report
    """
    logger.info(f"Saving report to {output_file}")
    
    # Filter out None results
    valid_results = [r for r in results if r is not None]
    
    with open(output_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("ERROR CORRELATION WITH RSSI ANALYSIS REPORT\n")
        f.write("=" * 80 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Drones Analyzed: {len(valid_results)}\n")
        f.write("=" * 80 + "\n\n")
        
        for result in valid_results:
            f.write(f"Drone: {result['drone_name']}\n")
            f.write("-" * 80 + "\n")
            f.write(f"  RSSI Threshold:          {result['rssi_threshold']} dBm\n")
            f.write(f"  Total Errors:            {result['total_errors']}\n")
            f.write(f"  Errors (Good Link):      {result['errors_good_link']} "
                   f"({result['errors_good_link']/result['total_errors']*100:.1f}%)\n")
            f.write(f"  Errors (Poor Link):      {result['errors_poor_link']} "
                   f"({result['errors_poor_link']/result['total_errors']*100:.1f}%)\n")
            f.write(f"  Error Rate (Good Link):  {result['error_rate_good_link']:.2f} errors/min\n")
            f.write(f"  Error Rate (Poor Link):  {result['error_rate_poor_link']:.2f} errors/min\n")
            f.write(f"  Good Link Duration:      {result['good_link_duration_s']:.2f}s\n")
            f.write(f"  Poor Link Duration:      {result['poor_link_duration_s']:.2f}s\n")
            
            # Calculate correlation strength
            if result['error_rate_good_link'] > 0:
                rate_ratio = result['error_rate_poor_link'] / result['error_rate_good_link']
                f.write(f"  Error Rate Ratio:        {rate_ratio:.2f}x higher during poor link\n")
            
            # Show top RSSI ranges with most errors
            f.write(f"\n  Top RSSI Ranges with Most Errors:\n")
            f.write(f"  {'RSSI Range (dBm)':<20} {'Errors':<10} {'Samples':<10} {'Rate':<10}\n")
            f.write(f"  {'-'*20} {'-'*10} {'-'*10} {'-'*10}\n")
            
            # Sort bins by error count
            sorted_bins = sorted(result['rssi_bins'], 
                               key=lambda b: result['errors_by_rssi_bin'][b], reverse=True)
            
            for bin_start in sorted_bins[:10]:
                if result['errors_by_rssi_bin'][bin_start] > 0:
                    samples = result['samples_by_rssi_bin'][bin_start]
                    errors = result['errors_by_rssi_bin'][bin_start]
                    rate = errors / samples if samples > 0 else 0
                    f.write(f"  {bin_start} to {bin_start+5:<8} {errors:<10} {samples:<10} {rate:<10.4f}\n")
            
            f.write("\n")
        
        # Summary comparison
        if len(valid_results) > 1:
            f.write("=" * 80 + "\n")
            f.write("COMPARISON SUMMARY\n")
            f.write("=" * 80 + "\n")
            
            # Find best and worst performers
            lowest_error_rate_poor = min(valid_results, key=lambda r: r['error_rate_poor_link'])
            highest_error_rate_poor = max(valid_results, key=lambda r: r['error_rate_poor_link'])
            
            f.write(f"Lowest Error Rate (Poor Link):  {lowest_error_rate_poor['drone_name']} "
                   f"({lowest_error_rate_poor['error_rate_poor_link']:.2f} errors/min)\n")
            f.write(f"Highest Error Rate (Poor Link): {highest_error_rate_poor['drone_name']} "
                   f"({highest_error_rate_poor['error_rate_poor_link']:.2f} errors/min)\n")
            f.write("\n")
            
            # Overall correlation analysis
            f.write("Overall Findings:\n")
            avg_rate_good = np.mean([r['error_rate_good_link'] for r in valid_results])
            avg_rate_poor = np.mean([r['error_rate_poor_link'] for r in valid_results])
            
            if avg_rate_good > 0:
                overall_ratio = avg_rate_poor / avg_rate_good
                f.write(f"  Average error rate is {overall_ratio:.2f}x higher during poor link conditions\n")
            
            f.write(f"  Average error rate (good link): {avg_rate_good:.2f} errors/min\n")
            f.write(f"  Average error rate (poor link): {avg_rate_poor:.2f} errors/min\n")
        
        f.write("\n")
        f.write("=" * 80 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 80 + "\n")
    
    logger.info(f"Report saved to {output_file}")


def main():
    """Main entry point for error correlation analysis."""
    if len(sys.argv) < 2:
        print("Usage: python analyze_error_correlation.py <log_file1> [log_file2] [log_file3] ...")
        print("\nExample:")
        print("  python analyze_error_correlation.py \\")
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
        result = analyze_drone_error_correlation(log_file, drone_name, rssi_threshold=-85.0)
        results.append(result)
    
    # Check if we have any valid results
    valid_results = [r for r in results if r is not None]
    if not valid_results:
        logger.error("No valid error correlation data found in any log files")
        sys.exit(1)
    
    # Generate outputs
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path('telemetry_logs')
    output_dir.mkdir(exist_ok=True)
    
    chart_file = output_dir / f'error_correlation_analysis_{timestamp}.png'
    report_file = output_dir / f'error_correlation_report_{timestamp}.txt'
    
    generate_correlation_charts(results, str(chart_file))
    save_report(results, str(report_file))
    
    logger.info("Error correlation analysis complete!")
    logger.info(f"  Chart: {chart_file}")
    logger.info(f"  Report: {report_file}")


if __name__ == '__main__':
    main()
