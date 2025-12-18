#!/usr/bin/env python3
"""
Comprehensive Performance Analysis Workflow Script

This script provides a complete workflow for analyzing flight logs from all three
drone modules (Drone1, Drone2 Primary, Drone2 Secondary). It runs all analysis
functions (throughput, latency, queue congestion, error correlation) and generates
a comprehensive performance report with multi-page PDF visualizations.

Requirements: 6.5

Usage:
    python comprehensive_analysis.py <drone1_log> <drone2_primary_log> <drone2_secondary_log>
    
Example:
    python comprehensive_analysis.py \
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
from matplotlib.backends.backend_pdf import PdfPages
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


def analyze_all_metrics(log_file: str, drone_name: str):
    """
    Analyze all performance metrics for a single drone log file.
    
    Args:
        log_file: Path to CSV log file
        drone_name: Name of the drone
        
    Returns:
        Dictionary with all performance metrics
    """
    logger.info(f"Analyzing all metrics for {drone_name} from {log_file}")
    
    # Load log file
    try:
        entries, format_type = load_flight_log(log_file)
    except Exception as e:
        logger.error(f"Failed to load {log_file}: {e}")
        return None
    
    if not entries:
        logger.warning(f"{drone_name}: No entries found in log file")
        return None
    
    # Get comprehensive performance metrics
    calculator = MetricsCalculator()
    perf_metrics = calculator.get_performance_metrics(entries)
    
    # Calculate additional time series data
    timestamps = [entry.timestamp_ms / 1000.0 for entry in entries]
    rssi_values = [entry.rssi_dbm for entry in entries]
    snr_values = [entry.snr_db for entry in entries]
    queue_depths = [entry.queue_depth for entry in entries]
    error_counts = [entry.errors for entry in entries]
    
    # Calculate throughput time series
    throughput_values = calculator.calculate_throughput(entries, window_seconds=1.0)
    
    # Calculate latency values
    latency_values_ms = [l * 1000 for l in calculator.calculate_end_to_end_latency(entries)]
    
    # Detect congestion events
    congestion_events = calculator.detect_queue_congestion(entries, threshold=20)
    
    logger.info(f"{drone_name} - Comprehensive Metrics Summary:")
    logger.info(f"  Format: {format_type}")
    logger.info(f"  Total Entries: {len(entries)}")
    logger.info(f"  Duration: {(entries[-1].timestamp_ms - entries[0].timestamp_ms) / 1000:.2f}s")
    logger.info(f"  Avg Throughput: {perf_metrics.avg_throughput_bps:.2f} bytes/s")
    logger.info(f"  Avg Latency: {perf_metrics.avg_latency_ms:.2f} ms")
    logger.info(f"  Congestion Events: {perf_metrics.congestion_events}")
    logger.info(f"  Total Errors: {perf_metrics.total_errors}")
    
    return {
        'drone_name': drone_name,
        'format_type': format_type,
        'entries': entries,
        'perf_metrics': perf_metrics,
        'timestamps': timestamps,
        'rssi_values': rssi_values,
        'snr_values': snr_values,
        'queue_depths': queue_depths,
        'error_counts': error_counts,
        'throughput_values': throughput_values,
        'latency_values_ms': latency_values_ms,
        'congestion_events': congestion_events
    }


def create_comprehensive_pdf(results: list, output_file: str):
    """
    Create a multi-page PDF with all visualizations.
    
    Args:
        results: List of analysis results for all drones
        output_file: Path to save the PDF
    """
    logger.info(f"Creating comprehensive PDF report: {output_file}")
    
    # Filter out None results
    valid_results = [r for r in results if r is not None]
    
    if not valid_results:
        logger.error("No valid results to generate PDF")
        return
    
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    
    with PdfPages(output_file) as pdf:
        # Page 1: Overview and Summary
        fig = plt.figure(figsize=(11, 8.5))
        fig.suptitle('Comprehensive Flight Log Analysis Report', fontsize=18, fontweight='bold')
        
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        # Title and metadata
        report_text = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report_text += f"Drones Analyzed: {len(valid_results)}\n\n"
        report_text += "=" * 80 + "\n"
        report_text += "SUMMARY\n"
        report_text += "=" * 80 + "\n\n"
        
        for result in valid_results:
            pm = result['perf_metrics']
            report_text += f"{result['drone_name']}:\n"
            report_text += f"  Format: {result['format_type']}\n"
            report_text += f"  Entries: {len(result['entries'])}\n"
            report_text += f"  Duration: {(result['entries'][-1].timestamp_ms - result['entries'][0].timestamp_ms) / 1000:.2f}s\n"
            report_text += f"  Avg Throughput: {pm.avg_throughput_bps:.2f} bytes/s ({pm.avg_throughput_bps * 8 / 1000:.2f} kbps)\n"
            report_text += f"  Peak Throughput: {pm.peak_throughput_bps:.2f} bytes/s ({pm.peak_throughput_bps * 8 / 1000:.2f} kbps)\n"
            report_text += f"  Avg Latency: {pm.avg_latency_ms:.2f} ms\n"
            report_text += f"  p95 Latency: {pm.p95_latency_ms:.2f} ms\n"
            report_text += f"  p99 Latency: {pm.p99_latency_ms:.2f} ms\n"
            report_text += f"  Congestion Events: {pm.congestion_events}\n"
            report_text += f"  Max Queue Depth: {pm.max_queue_depth}\n"
            report_text += f"  Total Errors: {pm.total_errors}\n"
            report_text += f"  Error Rate: {pm.error_rate_per_minute:.2f} errors/min\n"
            report_text += "\n"
        
        ax.text(0.05, 0.95, report_text, transform=ax.transAxes, 
               fontsize=10, verticalalignment='top', fontfamily='monospace')
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # Page 2: Throughput Analysis
        fig, axes = plt.subplots(2, 1, figsize=(11, 8.5))
        fig.suptitle('Throughput Analysis', fontsize=16, fontweight='bold')
        
        # Plot 1: Throughput over time
        for idx, result in enumerate(valid_results):
            if result['throughput_values']:
                color = colors[idx % len(colors)]
                timestamps = np.arange(len(result['throughput_values']))
                axes[0].plot(timestamps, result['throughput_values'], 
                           label=result['drone_name'], color=color, linewidth=1.5, alpha=0.8)
        
        axes[0].set_xlabel('Time (seconds)')
        axes[0].set_ylabel('Throughput (bytes/s)')
        axes[0].set_title('Throughput Over Time')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        
        # Plot 2: Throughput comparison
        drone_names = [r['drone_name'] for r in valid_results]
        avg_values = [r['perf_metrics'].avg_throughput_bps for r in valid_results]
        peak_values = [r['perf_metrics'].peak_throughput_bps for r in valid_results]
        
        x = np.arange(len(drone_names))
        width = 0.35
        
        axes[1].bar(x - width/2, avg_values, width, label='Average', color='#2ca02c', alpha=0.8)
        axes[1].bar(x + width/2, peak_values, width, label='Peak', color='#ff7f0e', alpha=0.8)
        
        axes[1].set_xlabel('Drone')
        axes[1].set_ylabel('Throughput (bytes/s)')
        axes[1].set_title('Throughput Comparison')
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(drone_names)
        axes[1].legend()
        axes[1].grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # Page 3: Latency Analysis
        fig, axes = plt.subplots(2, 1, figsize=(11, 8.5))
        fig.suptitle('Latency Analysis', fontsize=16, fontweight='bold')
        
        # Plot 1: Latency histograms
        for idx, result in enumerate(valid_results):
            if result['latency_values_ms']:
                color = colors[idx % len(colors)]
                axes[0].hist(result['latency_values_ms'], bins=30, 
                           label=result['drone_name'], color=color, alpha=0.5, edgecolor='black')
        
        axes[0].set_xlabel('Latency (ms)')
        axes[0].set_ylabel('Count')
        axes[0].set_title('Latency Distribution')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3, axis='y')
        
        # Plot 2: Latency percentile comparison
        p50_values = [r['perf_metrics'].p50_latency_ms for r in valid_results]
        p95_values = [r['perf_metrics'].p95_latency_ms for r in valid_results]
        p99_values = [r['perf_metrics'].p99_latency_ms for r in valid_results]
        
        x = np.arange(len(drone_names))
        width = 0.25
        
        axes[1].bar(x - width, p50_values, width, label='p50', color='#1f77b4', alpha=0.8)
        axes[1].bar(x, p95_values, width, label='p95', color='#ff7f0e', alpha=0.8)
        axes[1].bar(x + width, p99_values, width, label='p99', color='#d62728', alpha=0.8)
        
        axes[1].set_xlabel('Drone')
        axes[1].set_ylabel('Latency (ms)')
        axes[1].set_title('Latency Percentile Comparison')
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(drone_names)
        axes[1].legend()
        axes[1].grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # Page 4: Queue Congestion Analysis
        fig, axes = plt.subplots(2, 1, figsize=(11, 8.5))
        fig.suptitle('Queue Congestion Analysis', fontsize=16, fontweight='bold')
        
        # Plot 1: Queue depth over time
        for idx, result in enumerate(valid_results):
            if any(q > 0 for q in result['queue_depths']):
                color = colors[idx % len(colors)]
                axes[0].plot(result['timestamps'], result['queue_depths'], 
                           label=result['drone_name'], color=color, linewidth=1.0, alpha=0.7)
        
        axes[0].axhline(y=20, color='red', linestyle='--', linewidth=2, alpha=0.7, label='Threshold')
        axes[0].set_xlabel('Time (seconds)')
        axes[0].set_ylabel('Queue Depth')
        axes[0].set_title('Queue Depth Over Time')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        
        # Plot 2: Congestion metrics comparison
        congestion_events = [r['perf_metrics'].congestion_events for r in valid_results]
        max_queue_depths = [r['perf_metrics'].max_queue_depth for r in valid_results]
        
        x = np.arange(len(drone_names))
        width = 0.35
        
        axes[1].bar(x - width/2, congestion_events, width, label='Congestion Events', 
                   color='#d62728', alpha=0.8)
        axes[1].bar(x + width/2, max_queue_depths, width, label='Max Queue Depth', 
                   color='#ff7f0e', alpha=0.8)
        
        axes[1].set_xlabel('Drone')
        axes[1].set_ylabel('Count')
        axes[1].set_title('Queue Congestion Metrics')
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(drone_names)
        axes[1].legend()
        axes[1].grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # Page 5: Error Analysis
        fig, axes = plt.subplots(2, 1, figsize=(11, 8.5))
        fig.suptitle('Error Analysis', fontsize=16, fontweight='bold')
        
        # Plot 1: Cumulative errors over time
        for idx, result in enumerate(valid_results):
            color = colors[idx % len(colors)]
            axes[0].plot(result['timestamps'], result['error_counts'], 
                       label=result['drone_name'], color=color, linewidth=1.5, alpha=0.8)
        
        axes[0].set_xlabel('Time (seconds)')
        axes[0].set_ylabel('Cumulative Errors')
        axes[0].set_title('Error Accumulation Over Time')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        
        # Plot 2: Error rate comparison
        total_errors = [r['perf_metrics'].total_errors for r in valid_results]
        error_rates = [r['perf_metrics'].error_rate_per_minute for r in valid_results]
        errors_good_link = [r['perf_metrics'].errors_during_good_link for r in valid_results]
        errors_poor_link = [r['perf_metrics'].errors_during_poor_link for r in valid_results]
        
        x = np.arange(len(drone_names))
        width = 0.2
        
        axes[1].bar(x - 1.5*width, total_errors, width, label='Total Errors', 
                   color='#1f77b4', alpha=0.8)
        axes[1].bar(x - 0.5*width, errors_good_link, width, label='Errors (Good Link)', 
                   color='#2ca02c', alpha=0.8)
        axes[1].bar(x + 0.5*width, errors_poor_link, width, label='Errors (Poor Link)', 
                   color='#d62728', alpha=0.8)
        
        # Add error rate on secondary axis
        ax2 = axes[1].twinx()
        ax2.bar(x + 1.5*width, error_rates, width, label='Error Rate (errors/min)', 
               color='#ff7f0e', alpha=0.8)
        
        axes[1].set_xlabel('Drone')
        axes[1].set_ylabel('Error Count')
        ax2.set_ylabel('Error Rate (errors/min)')
        axes[1].set_title('Error Metrics Comparison')
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(drone_names)
        
        # Combine legends
        lines1, labels1 = axes[1].get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        axes[1].legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        
        axes[1].grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # Page 6: Link Quality Analysis
        fig, axes = plt.subplots(2, 1, figsize=(11, 8.5))
        fig.suptitle('Link Quality Analysis', fontsize=16, fontweight='bold')
        
        # Plot 1: RSSI over time
        for idx, result in enumerate(valid_results):
            color = colors[idx % len(colors)]
            axes[0].plot(result['timestamps'], result['rssi_values'], 
                       label=result['drone_name'], color=color, linewidth=1.0, alpha=0.7)
        
        axes[0].axhline(y=-85, color='orange', linestyle='--', linewidth=2, alpha=0.7, 
                       label='Good/Poor Threshold')
        axes[0].set_xlabel('Time (seconds)')
        axes[0].set_ylabel('RSSI (dBm)')
        axes[0].set_title('RSSI Over Time')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        
        # Plot 2: SNR over time
        for idx, result in enumerate(valid_results):
            color = colors[idx % len(colors)]
            axes[1].plot(result['timestamps'], result['snr_values'], 
                       label=result['drone_name'], color=color, linewidth=1.0, alpha=0.7)
        
        axes[1].set_xlabel('Time (seconds)')
        axes[1].set_ylabel('SNR (dB)')
        axes[1].set_title('SNR Over Time')
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        logger.info(f"PDF report saved: {output_file}")


def save_text_report(results: list, output_file: str):
    """
    Save comprehensive text report.
    
    Args:
        results: List of analysis results
        output_file: Path to save the report
    """
    logger.info(f"Saving text report: {output_file}")
    
    valid_results = [r for r in results if r is not None]
    
    with open(output_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("COMPREHENSIVE FLIGHT LOG ANALYSIS REPORT\n")
        f.write("=" * 80 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Drones Analyzed: {len(valid_results)}\n")
        f.write("=" * 80 + "\n\n")
        
        for result in valid_results:
            pm = result['perf_metrics']
            entries = result['entries']
            
            f.write(f"Drone: {result['drone_name']}\n")
            f.write("-" * 80 + "\n")
            f.write(f"Format: {result['format_type']}\n")
            f.write(f"Total Entries: {len(entries)}\n")
            f.write(f"Duration: {(entries[-1].timestamp_ms - entries[0].timestamp_ms) / 1000:.2f} seconds\n\n")
            
            f.write("THROUGHPUT METRICS:\n")
            f.write(f"  Average: {pm.avg_throughput_bps:.2f} bytes/s ({pm.avg_throughput_bps * 8 / 1000:.2f} kbps)\n")
            f.write(f"  Peak:    {pm.peak_throughput_bps:.2f} bytes/s ({pm.peak_throughput_bps * 8 / 1000:.2f} kbps)\n")
            f.write(f"  Minimum: {pm.min_throughput_bps:.2f} bytes/s ({pm.min_throughput_bps * 8 / 1000:.2f} kbps)\n\n")
            
            f.write("LATENCY METRICS:\n")
            f.write(f"  Average: {pm.avg_latency_ms:.2f} ms\n")
            f.write(f"  p50:     {pm.p50_latency_ms:.2f} ms\n")
            f.write(f"  p95:     {pm.p95_latency_ms:.2f} ms\n")
            f.write(f"  p99:     {pm.p99_latency_ms:.2f} ms\n")
            f.write(f"  Maximum: {pm.max_latency_ms:.2f} ms\n\n")
            
            f.write("QUEUE CONGESTION METRICS:\n")
            f.write(f"  Average Queue Depth:     {pm.avg_queue_depth:.2f}\n")
            f.write(f"  Maximum Queue Depth:     {pm.max_queue_depth}\n")
            f.write(f"  Congestion Events:       {pm.congestion_events}\n")
            f.write(f"  Congestion Duration:     {pm.congestion_duration_ms / 1000:.2f} seconds\n\n")
            
            f.write("ERROR METRICS:\n")
            f.write(f"  Total Errors:            {pm.total_errors}\n")
            f.write(f"  Error Rate:              {pm.error_rate_per_minute:.2f} errors/min\n")
            f.write(f"  Errors (Good Link):      {pm.errors_during_good_link}\n")
            f.write(f"  Errors (Poor Link):      {pm.errors_during_poor_link}\n\n")
            
            f.write("\n")
        
        f.write("=" * 80 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 80 + "\n")
    
    logger.info(f"Text report saved: {output_file}")


def main():
    """Main entry point for comprehensive analysis."""
    if len(sys.argv) != 4:
        print("Usage: python comprehensive_analysis.py <drone1_log> <drone2_primary_log> <drone2_secondary_log>")
        print("\nExample:")
        print("  python comprehensive_analysis.py \\")
        print("      telemetry_logs/drone1_20251118.csv \\")
        print("      telemetry_logs/drone2_primary_20251118.csv \\")
        print("      telemetry_logs/drone2_secondary_20251118.csv")
        sys.exit(1)
    
    drone1_log = sys.argv[1]
    drone2_primary_log = sys.argv[2]
    drone2_secondary_log = sys.argv[3]
    
    # Validate files exist
    for log_file in [drone1_log, drone2_primary_log, drone2_secondary_log]:
        if not os.path.exists(log_file):
            logger.error(f"File not found: {log_file}")
            sys.exit(1)
    
    # Analyze all drones
    logger.info("Starting comprehensive analysis...")
    
    results = [
        analyze_all_metrics(drone1_log, 'Drone1'),
        analyze_all_metrics(drone2_primary_log, 'Drone2 Primary'),
        analyze_all_metrics(drone2_secondary_log, 'Drone2 Secondary')
    ]
    
    # Check if we have any valid results
    valid_results = [r for r in results if r is not None]
    if not valid_results:
        logger.error("No valid data found in any log files")
        sys.exit(1)
    
    # Generate outputs
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path('telemetry_logs')
    output_dir.mkdir(exist_ok=True)
    
    pdf_file = output_dir / f'comprehensive_analysis_{timestamp}.pdf'
    report_file = output_dir / f'comprehensive_report_{timestamp}.txt'
    
    create_comprehensive_pdf(results, str(pdf_file))
    save_text_report(results, str(report_file))
    
    logger.info("=" * 80)
    logger.info("Comprehensive analysis complete!")
    logger.info(f"  PDF Report: {pdf_file}")
    logger.info(f"  Text Report: {report_file}")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()
