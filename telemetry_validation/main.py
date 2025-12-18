#!/usr/bin/env python3
"""
Telemetry Validation System - Main Application

This is the main entry point for the telemetry validation system. It provides
a command-line interface for monitoring, logging, validating, and visualizing
MAVLink telemetry data from the dual-controller LoRa relay system.

The system supports both binary protocol (custom UART protocol) and raw MAVLink
parsing modes, with comprehensive metrics tracking, validation, and alerting.

Requirements: 8.1, 8.2, 8.3, 8.5, All requirements
"""

import argparse
import sys
import signal
import time
import logging
from pathlib import Path
from typing import Optional
import json

# Import all components
from src.connection_manager import ConnectionManager, ConnectionType
from src.binary_protocol_parser import BinaryProtocolParser, MAVLinkExtractor
from src.mavlink_parser import MAVLinkParser
from src.telemetry_logger import TelemetryLogger
from src.validation_engine import ValidationEngine
from src.metrics_calculator import MetricsCalculator
from src.alert_manager import AlertManager, AlertChannel, Severity
from src.serial_monitor import SerialMonitor, MonitorConfig
from src.visualizer import TelemetryVisualizer, VisualizerConfig
from src.mode_tracker import ModeTracker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TelemetryValidationSystem:
    """
    Main telemetry validation system coordinator.
    
    This class integrates all components and manages the main processing loop,
    handling both binary protocol and raw MAVLink data streams.
    
    Requirements: All requirements
    """
    
    def __init__(self, args):
        """
        Initialize the telemetry validation system.
        
        Args:
            args: Parsed command-line arguments
        """
        self.args = args
        self.running = False
        self.config = {}
        
        # Components (initialized in setup())
        self.connection_manager: Optional[ConnectionManager] = None
        self.binary_parser: Optional[BinaryProtocolParser] = None
        self.mavlink_extractor: Optional[MAVLinkExtractor] = None
        self.mavlink_parser: Optional[MAVLinkParser] = None
        self.telemetry_logger: Optional[TelemetryLogger] = None
        self.validation_engine: Optional[ValidationEngine] = None
        self.metrics_calculator: Optional[MetricsCalculator] = None
        self.alert_manager: Optional[AlertManager] = None
        self.serial_monitor: Optional[SerialMonitor] = None
        self.visualizer: Optional[TelemetryVisualizer] = None
        self.mode_tracker: Optional[ModeTracker] = None
        
        # Statistics
        self.stats = {
            'binary_packets_processed': 0,
            'mavlink_messages_processed': 0,
            'violations_detected': 0,
            'alerts_sent': 0,
            'start_time': time.time()
        }
        
        logger.info("Telemetry Validation System initialized")
    
    def load_config(self):
        """
        Load configuration from file if specified.
        
        Requirements: 4.1, 4.3
        """
        if self.args.config:
            try:
                with open(self.args.config, 'r') as f:
                    self.config = json.load(f)
                logger.info(f"Loaded configuration from {self.args.config}")
            except Exception as e:
                logger.error(f"Failed to load configuration: {e}")
                logger.info("Using command-line arguments and defaults")
        
        # Override config with command-line arguments
        self._apply_cli_overrides()
    
    def _apply_cli_overrides(self):
        """Apply command-line argument overrides to configuration."""
        # Connection settings
        if not self.config.get('connection'):
            self.config['connection'] = {}
        
        if self.args.connection_type:
            self.config['connection']['type'] = self.args.connection_type
        
        if self.args.port:
            if self.args.connection_type == 'serial':
                if 'serial' not in self.config['connection']:
                    self.config['connection']['serial'] = {}
                self.config['connection']['serial']['port'] = self.args.port
            else:
                if 'udp' not in self.config['connection']:
                    self.config['connection']['udp'] = {}
                self.config['connection']['udp']['port'] = int(self.args.port)
        
        if self.args.baudrate:
            if 'serial' not in self.config['connection']:
                self.config['connection']['serial'] = {}
            self.config['connection']['serial']['baudrate'] = self.args.baudrate
        
        # Logging settings
        if not self.config.get('logging'):
            self.config['logging'] = {}
        
        if self.args.log_dir:
            self.config['logging']['log_dir'] = self.args.log_dir
        
        if self.args.no_logging:
            self.config['logging']['enabled'] = False
        else:
            self.config['logging']['enabled'] = True
        
        # Validation settings
        if not self.config.get('validation'):
            self.config['validation'] = {}
        
        if self.args.no_validation:
            self.config['validation']['enabled'] = False
        else:
            self.config['validation']['enabled'] = True
        
        if self.args.rules_file:
            self.config['validation']['rules_file'] = self.args.rules_file
        
        # Visualization settings
        if not self.config.get('visualization'):
            self.config['visualization'] = {}
        
        if self.args.no_visualization:
            self.config['visualization']['enabled'] = False
        elif self.args.visualization:
            self.config['visualization']['enabled'] = True
        
        # Protocol mode
        self.config['protocol_mode'] = self.args.protocol_mode
    
    def setup(self):
        """
        Set up all system components.
        
        Requirements: 8.1, 8.2, 8.3
        """
        logger.info("Setting up system components...")
        
        # Load configuration
        self.load_config()
        
        # Initialize connection manager
        self._setup_connection()
        
        # Initialize parsers based on protocol mode
        if self.config['protocol_mode'] == 'binary':
            logger.info("Using binary protocol mode")
            self.binary_parser = BinaryProtocolParser()
            self.mavlink_extractor = MAVLinkExtractor()
        else:
            logger.info("Using raw MAVLink mode")
            self.mavlink_parser = MAVLinkParser()
        
        # Initialize telemetry logger
        if self.config['logging'].get('enabled', True):
            log_dir = self.config['logging'].get('log_dir', './telemetry_logs')
            max_size = self.config['logging'].get('max_file_size_mb', 100)
            
            # Auto-generate prefix from connection source if not specified
            if hasattr(self.args, 'log_prefix') and self.args.log_prefix:
                log_prefix = self.args.log_prefix
            else:
                # Auto-detect: serial connections are "drone", UDP is "ground"
                if self.config['connection']['type'] == 'serial':
                    port = self.config['connection']['serial'].get('port', 'unknown')
                    # Extract just the device name (e.g., "usbserial-4" from "/dev/tty.usbserial-4")
                    if 'usbserial' in port:
                        device = port.split('.')[-1] if '.' in port else port.split('/')[-1]
                        log_prefix = f"drone_{device}"
                    else:
                        log_prefix = "drone_serial"
                else:
                    log_prefix = "ground_udp"
            
            self.telemetry_logger = TelemetryLogger(log_dir, max_size, log_prefix)
            logger.info(f"Telemetry logging enabled: {log_dir} (prefix: {log_prefix})")
        
        # Initialize validation engine
        if self.config['validation'].get('enabled', True):
            rules_file = self.config['validation'].get('rules_file', 'config/validation_rules.json')
            self.validation_engine = ValidationEngine(rules_file)
            logger.info("Validation engine enabled")
        
        # Initialize metrics calculator
        self.metrics_calculator = MetricsCalculator()
        logger.info("Metrics calculator initialized")
        
        # Initialize alert manager
        alert_config = self.config.get('alerts', {})
        # Convert channel strings to enums
        channels = []
        for channel_str in alert_config.get('channels', ['console']):
            if channel_str == 'console':
                channels.append(AlertChannel.CONSOLE)
            elif channel_str == 'email':
                channels.append(AlertChannel.EMAIL)
        alert_config['channels'] = channels
        
        self.alert_manager = AlertManager(alert_config)
        logger.info("Alert manager initialized")
        
        # Initialize serial monitor
        monitor_config = MonitorConfig(
            show_mavlink=True,
            show_binary=(self.config['protocol_mode'] == 'binary'),
            throttle_enabled=True,
            max_messages_per_second=10
        )
        self.serial_monitor = SerialMonitor(monitor_config, self.metrics_calculator)
        logger.info("Serial monitor initialized")
        
        # Initialize mode tracker
        self.mode_tracker = ModeTracker()
        logger.info("Mode tracker initialized")
        
        # Initialize visualizer if enabled
        if self.config['visualization'].get('enabled', False):
            viz_config = VisualizerConfig(
                update_rate_hz=self.config['visualization'].get('update_rate_hz', 1.0)
            )
            self.visualizer = TelemetryVisualizer(viz_config)
            logger.info("Visualizer initialized")
        
        logger.info("System setup complete")
    
    def _setup_connection(self):
        """Set up connection manager based on configuration."""
        conn_config = self.config.get('connection', {})
        conn_type_str = conn_config.get('type', 'serial')
        
        if conn_type_str == 'serial':
            conn_type = ConnectionType.SERIAL
            serial_config = conn_config.get('serial', {})
            kwargs = {
                'port': serial_config.get('port', '/dev/ttyUSB0'),
                'baudrate': serial_config.get('baudrate', 115200),
                'reconnect_interval': conn_config.get('reconnect_interval', 5)
            }
        else:
            conn_type = ConnectionType.UDP
            udp_config = conn_config.get('udp', {})
            kwargs = {
                'host': udp_config.get('host', '0.0.0.0'),
                'port': udp_config.get('port', 14550),
                'reconnect_interval': conn_config.get('reconnect_interval', 5)
            }
        
        self.connection_manager = ConnectionManager(conn_type, **kwargs)
        logger.info(f"Connection manager initialized: {conn_type.name}")
    
    def run(self):
        """
        Main processing loop.
        
        Connects to data source, parses packets, logs data, validates,
        calculates metrics, sends alerts, and updates visualization.
        
        Requirements: All requirements
        """
        logger.info("Starting telemetry validation system...")
        
        # Connect to data source
        if not self.connection_manager.connect():
            logger.error("Failed to establish initial connection")
            return 1
        
        self.running = True
        logger.info("System running - press Ctrl+C to stop")
        
        # Start visualizer in separate thread if enabled
        if self.visualizer:
            import threading
            viz_thread = threading.Thread(target=self.visualizer.start_realtime, daemon=True)
            viz_thread.start()
            logger.info("Visualizer started in background")
        
        # Main processing loop
        try:
            while self.running:
                # Check connection health and reconnect if needed
                if not self.connection_manager.is_healthy():
                    logger.warning("Connection unhealthy, attempting reconnect...")
                    self.connection_manager.auto_reconnect()
                    continue
                
                # Read data from connection
                data = self.connection_manager.read(1024)
                
                if not data:
                    time.sleep(0.01)  # Small delay to prevent busy-waiting
                    continue
                
                # Process data based on protocol mode
                if self.config['protocol_mode'] == 'binary':
                    self._process_binary_protocol(data)
                else:
                    self._process_raw_mavlink(data)
                
                # Periodic statistics display (every 10 seconds)
                if time.time() - self.stats.get('last_stats_display', 0) > 10:
                    self._display_statistics()
                    self.stats['last_stats_display'] = time.time()
        
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
        finally:
            self.shutdown()
        
        return 0
    
    def _process_binary_protocol(self, data: bytes):
        """
        Process binary protocol data stream.
        
        Parses binary packets, extracts MAVLink, logs, validates, and updates metrics.
        
        Args:
            data: Raw bytes from connection
            
        Requirements: 1.2, 2.1, 5.1
        """
        # Parse binary protocol packets
        packets = self.binary_parser.parse_stream(data)
        
        for packet in packets:
            self.stats['binary_packets_processed'] += 1
            
            # Log binary packet
            if self.telemetry_logger:
                self.telemetry_logger.log_binary_packet(packet)
            
            # Display binary packet
            if self.serial_monitor:
                self.serial_monitor.display_binary_packet(packet)
            
            # Update metrics with binary packet
            if self.metrics_calculator:
                self.metrics_calculator.update_binary_packet(packet)
            
            # Check for relay mode status and latency
            if self.alert_manager and hasattr(packet.payload, 'relay_active'):
                self.alert_manager.check_relay_latency(packet.payload, packet.payload.own_drone_sysid)
            
            # Track mode changes
            if self.mode_tracker and hasattr(packet.payload, 'relay_active'):
                self.mode_tracker.update_mode(packet.payload.relay_active, time.time())
            
            # Extract MAVLink from binary packet
            mavlink_msg = self.mavlink_extractor.extract_mavlink(packet)
            
            if mavlink_msg:
                self._process_mavlink_message(mavlink_msg)
    
    def _process_raw_mavlink(self, data: bytes):
        """
        Process raw MAVLink data stream.
        
        Parses MAVLink packets, logs, validates, and updates metrics.
        
        Args:
            data: Raw bytes from connection
            
        Requirements: 1.1, 2.1
        """
        # Parse MAVLink packets
        messages = self.mavlink_parser.parse_stream(data)
        
        for msg in messages:
            self._process_mavlink_message(msg)
    
    def _process_mavlink_message(self, msg):
        """
        Process a single MAVLink message.
        
        Logs, validates, updates metrics, sends alerts, and updates visualization.
        
        Args:
            msg: ParsedMessage or ParsedMAVLinkMessage object
            
        Requirements: 1.1, 3.1, 5.1, 9.1
        """
        self.stats['mavlink_messages_processed'] += 1
        
        # Log MAVLink message
        if self.telemetry_logger:
            self.telemetry_logger.log_message(msg)
        
        # Display MAVLink message
        if self.serial_monitor:
            self.serial_monitor.display_mavlink_message(msg)
        
        # Update metrics with MAVLink message
        if self.metrics_calculator:
            self.metrics_calculator.update_mavlink_message(msg)
        
        # Validate message
        if self.validation_engine:
            violations = self.validation_engine.validate_message(msg)
            
            if violations:
                self.stats['violations_detected'] += len(violations)
                
                # Send alerts for violations
                if self.alert_manager:
                    for violation in violations:
                        if self.alert_manager.send_alert(violation):
                            self.stats['alerts_sent'] += 1
                
                # Add violations to visualizer
                if self.visualizer:
                    for violation in violations:
                        self.visualizer.add_violation(violation)
        
        # Update visualizer with metrics
        if self.visualizer and self.metrics_calculator:
            metrics = self.metrics_calculator.get_metrics()
            
            # Extract battery voltage if available
            battery_voltage = None
            if msg.msg_type == 'SYS_STATUS' and 'voltage_battery' in msg.fields:
                battery_voltage = msg.fields['voltage_battery'] / 1000.0
            
            self.visualizer.update_data(metrics, msg.system_id, battery_voltage)
        
        # Check binary protocol errors periodically
        if self.alert_manager and self.metrics_calculator:
            if self.stats['mavlink_messages_processed'] % 100 == 0:
                metrics = self.metrics_calculator.get_metrics()
                self.alert_manager.check_binary_protocol_errors(metrics)
    
    def _display_statistics(self):
        """Display periodic statistics summary."""
        uptime = time.time() - self.stats['start_time']
        
        logger.info("=" * 70)
        logger.info(f"STATISTICS - Uptime: {uptime:.0f}s")
        logger.info(f"  Binary packets processed: {self.stats['binary_packets_processed']}")
        logger.info(f"  MAVLink messages processed: {self.stats['mavlink_messages_processed']}")
        logger.info(f"  Violations detected: {self.stats['violations_detected']}")
        logger.info(f"  Alerts sent: {self.stats['alerts_sent']}")
        
        if self.metrics_calculator:
            metrics = self.metrics_calculator.get_metrics()
            logger.info(f"  Packet rate (1s): {metrics.mavlink_packet_rate_1s:.1f} pkt/s")
            logger.info(f"  RSSI: {metrics.avg_rssi:.1f} dBm")
            logger.info(f"  SNR: {metrics.avg_snr:.1f} dB")
            logger.info(f"  Packet loss: {metrics.drop_rate:.2f}%")
        
        logger.info("=" * 70)
    
    def shutdown(self):
        """
        Graceful shutdown of all components.
        
        Requirements: 8.5
        """
        logger.info("Shutting down telemetry validation system...")
        
        self.running = False
        
        # Close connection
        if self.connection_manager:
            self.connection_manager.disconnect()
        
        # Close telemetry logger
        if self.telemetry_logger:
            self.telemetry_logger.close()
        
        # Stop visualizer
        if self.visualizer:
            self.visualizer.stop()
        
        # Display final statistics
        logger.info("Final Statistics:")
        logger.info(f"  Binary packets processed: {self.stats['binary_packets_processed']}")
        logger.info(f"  MAVLink messages processed: {self.stats['mavlink_messages_processed']}")
        logger.info(f"  Violations detected: {self.stats['violations_detected']}")
        logger.info(f"  Alerts sent: {self.stats['alerts_sent']}")
        logger.info(f"  Total runtime: {time.time() - self.stats['start_time']:.1f}s")
        
        logger.info("Shutdown complete")


def parse_arguments():
    """
    Parse command-line arguments.
    
    Returns:
        Parsed arguments namespace
        
    Requirements: 8.1, 8.2, 8.3
    """
    parser = argparse.ArgumentParser(
        description='Telemetry Validation System for Dual-Controller LoRa Relay',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor serial port with binary protocol
  %(prog)s --connection-type serial --port /dev/ttyUSB0 --baudrate 115200
  
  # Monitor UDP with raw MAVLink
  %(prog)s --connection-type udp --port 14550 --protocol-mode mavlink
  
  # Use configuration file
  %(prog)s --config config.json
  
  # Disable logging and validation
  %(prog)s --no-logging --no-validation
  
  # Enable visualization
  %(prog)s --visualization
        """
    )
    
    # Connection arguments
    conn_group = parser.add_argument_group('Connection Options')
    conn_group.add_argument(
        '--connection-type', '-c',
        choices=['serial', 'udp'],
        default='serial',
        help='Connection type (default: serial)'
    )
    conn_group.add_argument(
        '--port', '-p',
        help='Serial port (e.g., /dev/ttyUSB0) or UDP port number (e.g., 14550)'
    )
    conn_group.add_argument(
        '--baudrate', '-b',
        type=int,
        default=115200,
        help='Serial baudrate (default: 115200)'
    )
    
    # Protocol mode
    protocol_group = parser.add_argument_group('Protocol Options')
    protocol_group.add_argument(
        '--protocol-mode', '-m',
        choices=['binary', 'mavlink'],
        default='binary',
        help='Protocol parsing mode: binary (custom UART protocol) or mavlink (raw MAVLink) (default: binary)'
    )
    
    # Logging arguments
    log_group = parser.add_argument_group('Logging Options')
    log_group.add_argument(
        '--log-dir', '-l',
        help='Directory for log files (default: ./telemetry_logs)'
    )
    log_group.add_argument(
        '--log-prefix',
        help='Prefix for log filenames (e.g., "ground" or "drone")'
    )
    log_group.add_argument(
        '--no-logging',
        action='store_true',
        help='Disable telemetry logging'
    )
    
    # Validation arguments
    val_group = parser.add_argument_group('Validation Options')
    val_group.add_argument(
        '--rules-file', '-r',
        help='Path to validation rules JSON file (default: config/validation_rules.json)'
    )
    val_group.add_argument(
        '--no-validation',
        action='store_true',
        help='Disable telemetry validation'
    )
    
    # Visualization arguments
    viz_group = parser.add_argument_group('Visualization Options')
    viz_group.add_argument(
        '--visualization', '-v',
        action='store_true',
        help='Enable real-time visualization'
    )
    viz_group.add_argument(
        '--no-visualization',
        action='store_true',
        help='Disable visualization (overrides config file)'
    )
    
    # Configuration file
    parser.add_argument(
        '--config',
        help='Path to configuration JSON file'
    )
    
    # Verbosity
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress non-error output'
    )
    
    return parser.parse_args()


def setup_signal_handlers(system: TelemetryValidationSystem):
    """
    Set up signal handlers for graceful shutdown.
    
    Args:
        system: TelemetryValidationSystem instance
        
    Requirements: 8.5
    """
    def signal_handler(signum, frame):
        """Handle interrupt signals."""
        logger.info(f"Received signal {signum}")
        system.running = False
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Signal handlers registered")


def main():
    """
    Main entry point.
    
    Requirements: 8.1, 8.2, 8.3, 8.5
    """
    # Parse command-line arguments
    args = parse_arguments()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger().setLevel(logging.ERROR)
    
    # Print banner
    print("=" * 70)
    print("Telemetry Validation System")
    print("Dual-Controller LoRa Relay - Binary Protocol Support")
    print("=" * 70)
    print()
    
    # Create system instance
    system = TelemetryValidationSystem(args)
    
    # Set up signal handlers for graceful shutdown
    setup_signal_handlers(system)
    
    try:
        # Set up system components
        system.setup()
        
        # Run main loop
        return system.run()
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
