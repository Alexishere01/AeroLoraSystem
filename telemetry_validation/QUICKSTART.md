# Quick Start Guide

## Setup (First Time Only)

Run the setup script:
```bash
cd telemetry_validation
./setup_and_run.sh
```

This will:
- Create/activate the virtual environment
- Install all required dependencies (pymavlink, pyserial, matplotlib, etc.)

## Running the System

### Option 1: Monitor UDP (QGroundControl MAVLink stream)

```bash
# Activate virtual environment
source venv/bin/activate

# Run in UDP mode
python main.py --connection-type udp --port 14550 --protocol-mode mavlink
```

This monitors the MAVLink traffic that QGroundControl receives.

### Option 2: Monitor Serial Port (Binary Protocol)

```bash
# Activate virtual environment
source venv/bin/activate

# List available serial ports
python -m serial.tools.list_ports

# Run with your serial port
python main.py --connection-type serial --port /dev/tty.usbserial-XXXX --baudrate 115200
```

Replace `/dev/tty.usbserial-XXXX` with your actual serial port.

### Option 3: Use Configuration File

```bash
# Activate virtual environment
source venv/bin/activate

# Edit config file first
nano config/config.json

# Run with config
python main.py --config config/config.json
```

## Manual Setup (Alternative)

If the script doesn't work, run these commands manually:

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Run the system
python main.py --connection-type udp --port 14550 --protocol-mode mavlink
```

## Troubleshooting

### "python: command not found"
Use `python3` instead of `python` on macOS.

### "No module named 'serial'"
You need to activate the virtual environment first:
```bash
source venv/bin/activate
```

### "Permission denied: /dev/ttyUSB0"
On macOS, serial ports are usually `/dev/tty.usbserial-*` or `/dev/cu.usbserial-*`.
List them with:
```bash
ls /dev/tty.*
```

### Can't find serial port
List all available ports:
```bash
python -m serial.tools.list_ports
```

## Stopping the System

Press `Ctrl+C` to stop gracefully.

## Deactivating Virtual Environment

When you're done:
```bash
deactivate
```

## Next Steps

- See [USAGE.md](USAGE.md) for detailed usage instructions
- See [INSTALLATION.md](INSTALLATION.md) for platform-specific setup
- See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
