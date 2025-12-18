# Field Testing Guide - Telemetry Validation System

This guide provides comprehensive instructions for field testing the Telemetry Validation System alongside actual flight operations.

## Overview

The Telemetry Validation System is designed to run on a separate computer connected to the Ground Control Station (GCS) to monitor, validate, and analyze telemetry data in real-time without impacting drone operations.

## Prerequisites

### Hardware Requirements
- Laptop or computer with USB ports
- USB cable to connect to Ground Control Station (Heltec V3)
- Sufficient storage space for telemetry logs (recommend 10GB minimum)

### Software Requirements
- Python 3.8 or higher
- All dependencies installed (see requirements.txt)
- QGroundControl (for comparison validation)

### Installation
```bash
cd telemetry_validation
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Test Scenarios

### Scenario 1: Serial Connection Testing

**Objective**: Verify binary protocol parsing and logging via serial connection

**Setup**:
1. Connect laptop to GCS via USB
2. Identify serial port:
   - Linux: `/dev/ttyUSB0` or `/dev/ttyACM0`
   - macOS: `/dev/cu.usbserial-*` or `/dev/cu.usbmodem-*`
   - Windows: `COM3`, `COM4`, etc.

**Execution**:
```bash
python main.py \
  --connection serial \
  --port /dev/ttyUSB0 \
  --baudrate 115200 \
  --log-dir ./field_test_logs \
  --enable-validation \
  --enable-visualization
```

**Expected Results**:
- Binary protocol packets are parsed successfully
- MAVLink messages are extracted from BridgePayload
- RSSI/SNR values are displayed
- No checksum errors (or < 1% error rate)
- Packet rate matches expected telemetry rate

**Validation**:
- Compare packet counts with QGC's MAVLink Inspector
- Verify RSSI/SNR values match QGC's link quality indicators
- Check that all message types are captured

### Scenario 2: UDP Connection Testing

**Objective**: Verify system works with UDP MAVLink streams

**Setup**:
1. Configure QGC to forward MAVLink to UDP port 14550
2. Ensure firewall allows UDP traffic on port 14550

**Execution**:
```bash
python main.py \
  --connection udp \
  --port 14550 \
  --log-dir ./field_test_logs \
  --enable-validation
```

**Expected Results**:
- UDP packets are received and parsed
- No packet loss due to UDP buffer overflow
- Latency is minimal (< 10ms)

### Scenario 3: Direct Mode vs Relay Mode Comparison

**Objective**: Quantify the impact of relay operations on telemetry

**Setup**:
1. Start telemetry validation system
2. Fly drone in direct mode (no relay) for 5 minutes
3. Activate relay mode and fly for 5 minutes
4. Return to direct mode for 5 minutes

**Execution**:
```bash
python main.py \
  --connection serial \
  --port /dev/ttyUSB0 \
  --baudrate 115200 \
  --log-dir ./relay_comparison_test \
  --enable-validation \
  --enable-mode-tracking
```

**Expected Results**:
- Mode transitions are detected and logged
- Relay mode shows increased latency (expected: +50-200ms)
- Packet rate may be slightly lower in relay mode
- RSSI/SNR values reflect relay link quality

**Validation**:
- Generate mode comparison report:
  ```bash
  python -c "from src.report_generator import ReportGenerator; \
             rg = ReportGenerator('./relay_comparison_test'); \
             print(rg.generate_mode_comparison_report())"
  ```
- Verify percentage differences are within acceptable ranges

### Scenario 4: Validation Rule Testing

**Objective**: Verify validation rules detect anomalies correctly

**Setup**:
1. Configure validation rules in `config/validation_rules.json`
2. Include rules for:
   - Low battery voltage (< 10.5V)
   - Weak signal (RSSI < -100 dBm)
   - GPS altitude jumps (> 50m/s)
   - Packet loss (> 20% over 10s)

**Execution**:
```bash
python main.py \
  --connection serial \
  --port /dev/ttyUSB0 \
  --baudrate 115200 \
  --log-dir ./validation_test \
  --enable-validation \
  --enable-alerts
```

**Expected Results**:
- Violations are detected when thresholds are exceeded
- Alerts are generated with correct severity levels
- Alert history is maintained
- No false positives during normal operation

**Validation**:
- Review violation log:
  ```bash
  grep "VIOLATION" ./validation_test/*.csv
  ```
- Verify violations correspond to actual anomalies in QGC

### Scenario 5: Long-Duration Flight Testing

**Objective**: Verify system stability and performance over extended operations

**Setup**:
1. Prepare for 30+ minute flight
2. Ensure sufficient disk space for logs
3. Monitor system resource usage

**Execution**:
```bash
python main.py \
  --connection serial \
  --port /dev/ttyUSB0 \
  --baudrate 115200 \
  --log-dir ./long_duration_test \
  --enable-validation \
  --enable-visualization \
  --max-file-size-mb 100
```

**Expected Results**:
- System runs without crashes or hangs
- CPU usage remains < 50%
- Memory usage remains stable (no leaks)
- File rotation occurs automatically
- All telemetry is captured without gaps

**Validation**:
- Check system resource usage:
  ```bash
  top -p $(pgrep -f main.py)
  ```
- Verify log file integrity:
  ```bash
  ls -lh ./long_duration_test/
  wc -l ./long_duration_test/*.csv
  ```

### Scenario 6: Binary Protocol Error Handling

**Objective**: Verify system handles protocol errors gracefully

**Setup**:
1. Intentionally introduce errors (if possible):
   - Disconnect/reconnect USB cable during operation
   - Send malformed packets (if test harness available)
2. Monitor error rates and recovery

**Execution**:
```bash
python main.py \
  --connection serial \
  --port /dev/ttyUSB0 \
  --baudrate 115200 \
  --log-dir ./error_handling_test \
  --enable-validation
```

**Expected Results**:
- Checksum errors are detected and logged
- System recovers from temporary disconnections
- No crashes or data corruption
- Error rates are reported in metrics

**Validation**:
- Check parser statistics:
  ```bash
  grep "checksum_error" ./error_handling_test/*.csv
  ```
- Verify system reconnects automatically after disconnection

## Performance Metrics

### Key Performance Indicators (KPIs)

1. **Packet Reception Rate**
   - Target: > 95% of expected packets received
   - Measure: Compare packet count with QGC

2. **Checksum Error Rate**
   - Target: < 1% of packets
   - Measure: Parser statistics

3. **Latency**
   - Target: < 100ms for direct mode, < 300ms for relay mode
   - Measure: COMMAND_LONG to COMMAND_ACK timing

4. **CPU Usage**
   - Target: < 50% on modern laptop
   - Measure: System monitor

5. **Memory Usage**
   - Target: < 500MB
   - Measure: System monitor

6. **Disk I/O**
   - Target: < 10 MB/s write rate
   - Measure: System monitor

## Validation Against QGroundControl

### Comparison Checklist

- [ ] Packet counts match (within 1%)
- [ ] RSSI values match (within 2 dBm)
- [ ] SNR values match (within 1 dB)
- [ ] Message types match
- [ ] Sequence numbers are consistent
- [ ] Timestamps are synchronized

### Comparison Procedure

1. **Export QGC Telemetry**:
   - In QGC, go to Analyze Tools > MAVLink Inspector
   - Export telemetry log for comparison period

2. **Export Validation System Telemetry**:
   ```bash
   python -c "from src.report_generator import ReportGenerator; \
              rg = ReportGenerator('./field_test_logs'); \
              rg.export_to_csv('comparison.csv', start_time=..., end_time=...)"
   ```

3. **Compare Metrics**:
   - Packet counts
   - Message type distribution
   - RSSI/SNR averages
   - Latency measurements

4. **Document Discrepancies**:
   - Note any differences > 5%
   - Investigate root causes
   - Update validation rules if needed

## Troubleshooting

### Issue: No Packets Received

**Symptoms**: Parser shows 0 packets received

**Possible Causes**:
- Wrong serial port
- Incorrect baud rate
- USB cable disconnected
- GCS not transmitting

**Solutions**:
1. Verify serial port: `ls /dev/tty*`
2. Check baud rate in GCS configuration
3. Test with QGC first to confirm telemetry is working
4. Try different USB cable/port

### Issue: High Checksum Error Rate

**Symptoms**: > 5% checksum errors

**Possible Causes**:
- Electrical interference
- Faulty USB cable
- Baud rate mismatch
- Hardware issue with GCS

**Solutions**:
1. Use shielded USB cable
2. Move away from sources of interference
3. Verify baud rate matches GCS
4. Test with different GCS if available

### Issue: Packet Loss

**Symptoms**: Gaps in sequence numbers, drop rate > 10%

**Possible Causes**:
- UDP buffer overflow (UDP mode)
- CPU overload
- Disk I/O bottleneck
- LoRa link quality issues

**Solutions**:
1. Increase UDP buffer size (UDP mode)
2. Reduce visualization update rate
3. Use faster disk (SSD)
4. Improve LoRa antenna placement

### Issue: System Crashes

**Symptoms**: Python process terminates unexpectedly

**Possible Causes**:
- Unhandled exception
- Memory exhaustion
- Disk full

**Solutions**:
1. Check logs for error messages
2. Monitor memory usage
3. Ensure sufficient disk space
4. Report bug with stack trace

## Test Report Template

### Test Information
- **Date**: YYYY-MM-DD
- **Duration**: HH:MM:SS
- **Connection Type**: Serial / UDP
- **Baud Rate**: 115200
- **Test Scenario**: [Scenario name]

### System Configuration
- **Python Version**: 3.x.x
- **OS**: Linux / macOS / Windows
- **CPU**: [Model]
- **RAM**: [Amount]

### Results Summary
- **Packets Received**: [count]
- **Checksum Errors**: [count] ([percentage]%)
- **Parse Errors**: [count] ([percentage]%)
- **Average RSSI**: [value] dBm
- **Average SNR**: [value] dB
- **Packet Rate**: [value] packets/sec
- **Drop Rate**: [percentage]%

### Validation Results
- [ ] All KPIs met
- [ ] Matches QGC telemetry
- [ ] No crashes or hangs
- [ ] Acceptable performance

### Issues Encountered
1. [Issue description]
   - Severity: Low / Medium / High
   - Resolution: [How it was resolved]

### Recommendations
1. [Recommendation 1]
2. [Recommendation 2]

### Conclusion
[Overall assessment of system performance and readiness]

## Next Steps

After successful field testing:

1. **Document Results**: Fill out test report template
2. **Archive Logs**: Save all telemetry logs for future reference
3. **Update Configuration**: Adjust validation rules based on findings
4. **Report Issues**: File bug reports for any issues discovered
5. **Performance Tuning**: Optimize based on performance metrics

## Safety Considerations

- **Do not interfere with flight operations**: The validation system is for monitoring only
- **Backup critical data**: Always maintain QGC as primary telemetry system
- **Test on ground first**: Verify system works before actual flight
- **Monitor system health**: Watch for high CPU/memory usage that could impact laptop performance
- **Have contingency plan**: Be prepared to disconnect validation system if issues arise

## Contact

For issues or questions about field testing:
- Review documentation in `telemetry_validation/README.md`
- Check examples in `telemetry_validation/examples/`
- Review test results in `telemetry_validation/tests/`
