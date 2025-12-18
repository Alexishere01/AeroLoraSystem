# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with the Telemetry Validation System.

## Table of Contents

- [Connection Issues](#connection-issues)
- [No Data Received](#no-data-received)
- [Binary Protocol Issues](#binary-protocol-issues)
- [Validation Issues](#validation-issues)
- [Performance Issues](#performance-issues)
- [Visualization Issues](#visualization-issues)
- [Alert Issues](#alert-issues)
- [Logging Issues](#logging-issues)

## Connection Issues

### Serial Port Not Found

**Symptoms**:
```
Error: Serial port /dev/ttyUSB0 not found
Connection failed: [Errno 2] No such file or directory: '/dev/ttyUSB0'
```

**Solutions**:

1. **List available serial ports**:
   ```bash
   # Linux/macOS
   ls /dev/tty*
   
   # Or use Python
   python -m serial.tools.list_ports
   ```

2. **Check USB connection**:
   - Verify USB cable is connected
   - Try different USB port
   - Check if device appears in system (dmesg on Linux)

3. **Check permissions** (Linux):
   ```bash
   # Add user to dialout group
   sudo usermod -a -G dialout $USER
   
   # Or change port permissions
   sudo chmod 666 /dev/ttyUSB0
   ```

4. **Specify correct port**:
   ```bash
   # Common ports:
   # Linux: /dev/ttyUSB0, /dev/ttyACM0
   # macOS: /dev/cu.usbserial-*, /dev/cu.usbmodem*
   # Windows: COM3, COM4, etc.
   
   python main.py --port /dev/ttyACM0
   ```

### Serial Port Permission Denied

**Symptoms**:
```
Error: Permission denied: '/dev/ttyUSB0'
```

**Solutions**:

1. **Add user to dialout group** (Linux):
   ```bash
   sudo usermod -a -G dialout $USER
   # Log out and log back in
   ```

2. **Temporary permission fix**:
   ```bash
   sudo chmod 666 /dev/ttyUSB0
   ```

3. **Run with sudo** (not recommended):
   ```bash
   sudo python main.py --port /dev/ttyUSB0
   ```

### UDP Port Already in Use

**Symptoms**:
```
Error: [Errno 48] Address already in use
```

**Solutions**:

1. **Find process using port**:
   ```bash
   # Linux/macOS
   lsof -i :14550
   
   # Kill process
   kill -9 <PID>
   ```

2. **Use different port**:
   ```bash
   python main.py --connection-type udp --port 14551
   ```

3. **Wait for port release**:
   - Wait 30-60 seconds for OS to release port
   - Restart system if persistent

### Connection Timeout

**Symptoms**:
```
Connection timeout after 5 seconds
Attempting to reconnect...
```

**Solutions**:

1. **Check device is transmitting**:
   - Verify Ground Station is powered on
   - Check LoRa link is established
   - Verify UART connection between controllers

2. **Check baud rate**:
   ```bash
   # Try common baud rates
   python main.py --baudrate 115200
   python main.py --baudrate 57600
   python main.py --baudrate 9600
   ```

3. **Check protocol mode**:
   ```bash
   # If device sends raw MAVLink (not binary protocol)
   python main.py --protocol-mode mavlink
   ```

4. **Enable debug logging**:
   ```bash
   python main.py --log-level DEBUG
   ```

## No Data Received

### Connected But No Packets

**Symptoms**:
- Connection successful
- No packets received
- Packet rate shows 0

**Solutions**:

1. **Verify data is being transmitted**:
   - Check Ground Station is receiving telemetry
   - Verify LoRa link is active
   - Check LED indicators on controllers

2. **Check protocol mode**:
   ```bash
   # If using binary protocol (default)
   python main.py --protocol-mode binary
   
   # If using raw MAVLink
   python main.py --protocol-mode mavlink
   ```

3. **Monitor raw serial data**:
   ```bash
   # Linux/macOS
   cat /dev/ttyUSB0
   
   # Or use screen
   screen /dev/ttyUSB0 115200
   ```

4. **Check for data with hex dump**:
   ```bash
   # Linux/macOS
   hexdump -C /dev/ttyUSB0
   ```

5. **Verify UART configuration**:
   - Check baud rate matches controller settings
   - Verify 8N1 configuration (8 data bits, no parity, 1 stop bit)

### Intermittent Data Reception

**Symptoms**:
- Packets received sporadically
- High packet loss rate
- Frequent connection drops

**Solutions**:

1. **Check signal quality**:
   - Monitor RSSI/SNR values
   - Move closer to reduce distance
   - Check for interference sources

2. **Check USB cable quality**:
   - Try different USB cable
   - Avoid USB hubs if possible
   - Use shorter cable

3. **Reduce baud rate**:
   ```bash
   python main.py --baudrate 57600
   ```

4. **Check system load**:
   - Close unnecessary applications
   - Monitor CPU usage
   - Check available memory

## Binary Protocol Issues

### High Checksum Error Rate

**Symptoms**:
```
⚠ ALERT: High checksum error rate: 15.2%
Checksum errors: 152 / 1000 packets
```

**Solutions**:

1. **Check UART connection quality**:
   - Verify wiring between controllers
   - Check for loose connections
   - Ensure proper grounding

2. **Reduce baud rate**:
   ```bash
   # Lower baud rate for more reliable communication
   python main.py --baudrate 57600
   ```

3. **Check for electrical interference**:
   - Move away from power supplies
   - Separate UART wires from power wires
   - Add ferrite beads to cables

4. **Verify protocol version**:
   - Ensure controllers use same protocol version
   - Check for firmware mismatches

5. **Enable debug logging**:
   ```python
   parser = BinaryProtocolParser(debug=True)
   ```

### Parse Errors

**Symptoms**:
```
Parse error: Invalid packet length
Parse error: Buffer overflow
Unknown command: 0xFF
```

**Solutions**:

1. **Check protocol synchronization**:
   - Parser may have lost sync with byte stream
   - Restart application to resynchronize
   - Check for corrupted data

2. **Verify protocol implementation**:
   - Ensure controllers use correct protocol format
   - Check start byte is 0xAA
   - Verify length field is little-endian

3. **Check buffer size**:
   - Increase buffer size in configuration
   - Reduce data rate if buffer overflows

4. **Enable packet logging**:
   ```bash
   python main.py --log-binary-packets
   ```

### Cannot Extract MAVLink

**Symptoms**:
```
Warning: Failed to extract MAVLink from packet
MAVLink parse error: Invalid packet
```

**Solutions**:

1. **Verify command type**:
   - MAVLink only in CMD_BRIDGE_TX and CMD_BRIDGE_RX
   - Check packet command type

2. **Check MAVLink packet integrity**:
   - Verify MAVLink start byte (0xFE or 0xFD)
   - Check MAVLink packet length
   - Verify MAVLink checksum

3. **Check data_len field**:
   - Ensure data_len matches actual MAVLink packet size
   - Verify data_len is within valid range (1-245)

4. **Enable MAVLink debug**:
   ```python
   parser = MAVLinkParser(debug=True)
   ```

### Protocol Version Mismatch

**Symptoms**:
```
Warning: Protocol version mismatch: expected 1, got 2
```

**Solutions**:

1. **Update firmware**:
   - Ensure all controllers have same firmware version
   - Update to latest version

2. **Check protocol version**:
   - Verify INIT packet protocol_version field
   - Update parser if protocol changed

3. **Use compatible version**:
   - Downgrade firmware if necessary
   - Update parser to support new version

## Validation Issues

### False Positive Alerts

**Symptoms**:
- Too many alerts for normal conditions
- Alerts for expected behavior
- Alert spam

**Solutions**:

1. **Adjust thresholds**:
   ```json
   {
     "name": "Low Battery Warning",
     "threshold": 10500,  // Adjust this value
     "severity": "WARNING"
   }
   ```

2. **Change severity level**:
   ```json
   {
     "severity": "INFO"  // Change from WARNING to INFO
   }
   ```

3. **Disable rule temporarily**:
   - Comment out rule in validation_rules.json
   - Or remove rule entirely

4. **Add hysteresis**:
   - Create separate rules for different thresholds
   - Use INFO for minor deviations, WARNING for significant

5. **Review with real data**:
   - Analyze historical logs
   - Determine appropriate thresholds
   - Test with actual flight data

### Rules Not Triggering

**Symptoms**:
- Expected alerts not generated
- Violations not logged
- Rules seem inactive

**Solutions**:

1. **Verify rule syntax**:
   ```bash
   # Validate JSON
   python -m json.tool config/validation_rules.json
   ```

2. **Check message type**:
   - Ensure msg_type matches exactly (case-sensitive)
   - Verify message type is being received
   - Check message type distribution in metrics

3. **Check field name**:
   - Verify field name matches MAVLink specification
   - Check for typos
   - Enable debug logging to see available fields

4. **Verify operator and threshold**:
   - Check operator is correct (<, >, ==, etc.)
   - Verify threshold value is correct type
   - Test with known values

5. **Check rule loading**:
   ```
   Loaded 6 validation rules  # Should see this on startup
   ```

6. **Enable validation debug**:
   ```python
   engine = ValidationEngine(debug=True)
   ```

### GPS Altitude Jump False Positives

**Symptoms**:
- Frequent GPS altitude jump alerts
- Alerts during normal flight
- Altitude changes seem normal

**Solutions**:

1. **Adjust threshold**:
   - Default is 50m in 1 second
   - Increase threshold for faster climbs
   - Modify in validation_engine.py

2. **Check GPS quality**:
   - Low satellite count can cause jumps
   - Check GPS HDOP/VDOP values
   - Verify GPS fix type is 3D

3. **Disable if not needed**:
   - Comment out GPS jump detection
   - Or adjust severity to INFO

## Performance Issues

### High CPU Usage

**Symptoms**:
- CPU usage > 80%
- System slowdown
- Dropped packets

**Solutions**:

1. **Reduce visualization update rate**:
   ```json
   {
     "visualization": {
       "update_rate_hz": 0.5  // Reduce from 1 Hz
     }
   }
   ```

2. **Disable visualization**:
   ```bash
   python main.py --no-visualization
   ```

3. **Reduce logging formats**:
   ```json
   {
     "logging": {
       "csv": true,
       "json": false,  // Disable JSON
       "tlog": false,  // Disable .tlog
       "binlog": false  // Disable .binlog
     }
   }
   ```

4. **Limit validation rules**:
   - Remove unnecessary rules
   - Disable low-priority rules

5. **Increase buffer flush interval**:
   ```json
   {
     "logging": {
       "buffer_flush_interval_s": 10  // Increase from 5
     }
   }
   ```

### High Memory Usage

**Symptoms**:
- Memory usage growing over time
- System swapping
- Out of memory errors

**Solutions**:

1. **Enable file rotation**:
   ```json
   {
     "logging": {
       "max_file_size_mb": 100,
       "rotate_files": true
     }
   }
   ```

2. **Reduce rolling window sizes**:
   ```json
   {
     "metrics": {
       "window_1s_size": 100,  // Reduce from 1000
       "window_10s_size": 1000,  // Reduce from 10000
       "window_60s_size": 6000  // Reduce from 60000
     }
   }
   ```

3. **Limit violation history**:
   - Clear old violations periodically
   - Reduce violation retention time

4. **Disable JSON buffering**:
   ```json
   {
     "logging": {
       "json": false
     }
   }
   ```

### Packet Loss in Logger

**Symptoms**:
- Packets received but not logged
- Missing data in log files
- Gaps in telemetry

**Solutions**:

1. **Increase buffer size**:
   ```json
   {
     "logging": {
       "buffer_size": 10000  // Increase from 1000
     }
   }
   ```

2. **Reduce flush interval**:
   ```json
   {
     "logging": {
       "buffer_flush_interval_s": 1  // Reduce from 5
     }
   }
   ```

3. **Check disk space**:
   ```bash
   df -h
   ```

4. **Check disk I/O**:
   ```bash
   iostat -x 1
   ```

5. **Use faster storage**:
   - Log to SSD instead of HDD
   - Use RAM disk for temporary logs

## Visualization Issues

### Graphs Not Updating

**Symptoms**:
- Visualization window frozen
- No data on graphs
- Graphs not refreshing

**Solutions**:

1. **Check data is being received**:
   - Verify packet rate > 0
   - Check console output for packets

2. **Verify visualization enabled**:
   ```bash
   python main.py --enable-visualization
   ```

3. **Check matplotlib backend**:
   ```python
   import matplotlib
   print(matplotlib.get_backend())
   ```

4. **Try different backend**:
   ```python
   import matplotlib
   matplotlib.use('TkAgg')  # Or 'Qt5Agg'
   ```

5. **Restart visualization**:
   - Close and reopen window
   - Restart application

### Slow Visualization

**Symptoms**:
- Graphs update slowly
- Laggy interface
- High CPU usage

**Solutions**:

1. **Reduce update rate**:
   ```json
   {
     "visualization": {
       "update_rate_hz": 0.5
     }
   }
   ```

2. **Reduce data points**:
   ```json
   {
     "visualization": {
       "max_points_per_graph": 100  // Reduce from 1000
     }
   }
   ```

3. **Disable some graphs**:
   ```json
   {
     "visualization": {
       "graphs": ["rssi", "snr"]  // Only show essential graphs
     }
   }
   ```

4. **Use simpler plot style**:
   - Disable markers
   - Use thinner lines
   - Reduce colors

### Multi-Drone Graphs Overlapping

**Symptoms**:
- Cannot distinguish between drones
- Colors too similar
- Graphs cluttered

**Solutions**:

1. **Adjust colors**:
   ```json
   {
     "visualization": {
       "drone_colors": ["red", "blue", "green", "orange"]
     }
   }
   ```

2. **Use separate subplots**:
   - Modify visualizer.py to create separate plots per drone

3. **Filter by system ID**:
   ```bash
   python main.py --filter-system-id 1
   ```

## Alert Issues

### No Alerts Generated

**Symptoms**:
- Violations logged but no alerts
- Expected alerts not appearing
- Alert system seems inactive

**Solutions**:

1. **Check alert channels enabled**:
   ```json
   {
     "alerts": {
       "channels": ["console", "email"]
     }
   }
   ```

2. **Verify severity level**:
   - Check rule severity matches alert threshold
   - INFO alerts may not be displayed

3. **Check alert throttling**:
   ```json
   {
     "alerts": {
       "throttle_seconds": 60,  // May be suppressing alerts
       "max_alerts_per_minute": 10
     }
   }
   ```

4. **Enable debug logging**:
   ```bash
   python main.py --log-level DEBUG
   ```

### Email Alerts Not Sending

**Symptoms**:
```
Email alert failed: [Errno 61] Connection refused
Email alert failed: Authentication failed
```

**Solutions**:

1. **Check SMTP configuration**:
   ```json
   {
     "alerts": {
       "email": {
         "server": "smtp.gmail.com",
         "port": 587,
         "username": "your-email@gmail.com",
         "password": "your-app-password",
         "from": "your-email@gmail.com",
         "to": "recipient@example.com"
       }
     }
   }
   ```

2. **Use app-specific password** (Gmail):
   - Enable 2-factor authentication
   - Generate app-specific password
   - Use app password instead of account password

3. **Check firewall**:
   - Ensure port 587 (or 465) is not blocked
   - Check network allows SMTP

4. **Test SMTP connection**:
   ```python
   import smtplib
   server = smtplib.SMTP('smtp.gmail.com', 587)
   server.starttls()
   server.login('user', 'pass')
   ```

### Alert Spam

**Symptoms**:
- Too many alerts
- Console flooded with alerts
- Alert fatigue

**Solutions**:

1. **Enable throttling**:
   ```json
   {
     "alerts": {
       "throttle_seconds": 60,
       "max_alerts_per_minute": 10
     }
   }
   ```

2. **Adjust severity levels**:
   - Change WARNING to INFO
   - Reserve CRITICAL for serious issues

3. **Adjust thresholds**:
   - Make rules less sensitive
   - Increase threshold values

4. **Disable noisy rules**:
   - Comment out or remove rules causing spam

## Logging Issues

### Log Files Not Created

**Symptoms**:
- No log files in output directory
- Logging seems inactive
- Cannot find logs

**Solutions**:

1. **Check log directory**:
   ```bash
   ls -la telemetry_logs/
   ```

2. **Verify logging enabled**:
   ```json
   {
     "logging": {
       "enabled": true,
       "csv": true
     }
   }
   ```

3. **Check permissions**:
   ```bash
   # Ensure write permission
   chmod 755 telemetry_logs/
   ```

4. **Specify log directory**:
   ```bash
   python main.py --log-dir ./my_logs
   ```

### Log Files Too Large

**Symptoms**:
- Log files growing rapidly
- Disk space filling up
- Performance degradation

**Solutions**:

1. **Enable file rotation**:
   ```json
   {
     "logging": {
       "max_file_size_mb": 100,
       "rotate_files": true
     }
   }
   ```

2. **Reduce logging formats**:
   ```json
   {
     "logging": {
       "csv": true,
       "json": false,
       "tlog": false,
       "binlog": false
     }
   }
   ```

3. **Filter logged messages**:
   - Log only specific message types
   - Reduce logging frequency

4. **Compress old logs**:
   ```bash
   gzip telemetry_logs/*.csv
   ```

### Cannot Read .tlog Files

**Symptoms**:
- QGC cannot open .tlog files
- MAVProxy fails to read logs
- Corrupted .tlog files

**Solutions**:

1. **Verify .tlog format**:
   - Should contain raw MAVLink bytes only
   - No headers or metadata

2. **Check file size**:
   ```bash
   ls -lh telemetry_logs/*.tlog
   ```

3. **Verify MAVLink packets**:
   ```bash
   # Use MAVProxy to validate
   mavlogdump.py telemetry.tlog
   ```

4. **Check for truncation**:
   - Ensure file was closed properly
   - Check for disk full errors

## Getting Help

If you cannot resolve an issue:

1. **Enable debug logging**:
   ```bash
   python main.py --log-level DEBUG > debug.log 2>&1
   ```

2. **Collect information**:
   - Python version: `python --version`
   - OS version: `uname -a` (Linux/macOS) or `ver` (Windows)
   - Package versions: `pip list`
   - Configuration files
   - Error messages and stack traces

3. **Check documentation**:
   - [README.md](README.md)
   - [USAGE.md](USAGE.md)
   - [BINARY_PROTOCOL.md](BINARY_PROTOCOL.md)
   - Component README files in src/

4. **Run validation scripts**:
   ```bash
   python validate_connection_manager.py
   python validate_binary_protocol_parser.py
   python validate_validation_engine.py
   ```

5. **Check examples**:
   - Review example scripts in examples/
   - Test individual components

6. **Report issue**:
   - Include debug log
   - Describe expected vs actual behavior
   - Provide configuration files
   - Include sample data if possible
