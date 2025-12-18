# Installation Guide

This guide provides detailed installation instructions for the Telemetry Validation System on different platforms.

## Table of Contents

- [System Requirements](#system-requirements)
- [Quick Installation](#quick-installation)
- [Platform-Specific Instructions](#platform-specific-instructions)
- [Dependency Installation](#dependency-installation)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

## System Requirements

### Minimum Requirements

- **Python**: 3.8 or higher
- **RAM**: 512 MB minimum, 1 GB recommended
- **Disk Space**: 100 MB for application, additional space for logs
- **CPU**: Any modern processor (x86, ARM)

### Supported Platforms

- **Linux**: Ubuntu 18.04+, Debian 10+, Fedora 30+, Arch Linux
- **macOS**: 10.14 (Mojave) or higher
- **Windows**: Windows 10 or higher
- **Raspberry Pi**: Raspberry Pi 3 or higher with Raspberry Pi OS

### Hardware Requirements

- **Serial Port**: USB-to-serial adapter or built-in serial port
- **Network**: For UDP connection mode
- **Display**: For visualization (optional)

## Quick Installation

### Linux/macOS

```bash
# Clone or download the repository
cd telemetry_validation

# Install dependencies
pip3 install -r requirements.txt

# Verify installation
python3 main.py --help
```

### Windows

```cmd
# Open Command Prompt or PowerShell
cd telemetry_validation

# Install dependencies
pip install -r requirements.txt

# Verify installation
python main.py --help
```

## Platform-Specific Instructions

### Ubuntu/Debian Linux

1. **Install Python and pip**:
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip python3-venv
   ```

2. **Install system dependencies**:
   ```bash
   # For serial port support
   sudo apt install python3-serial
   
   # For visualization (matplotlib)
   sudo apt install python3-tk
   
   # For development tools
   sudo apt install python3-dev build-essential
   ```

3. **Create virtual environment** (recommended):
   ```bash
   cd telemetry_validation
   python3 -m venv venv
   source venv/bin/activate
   ```

4. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure serial port permissions**:
   ```bash
   # Add user to dialout group
   sudo usermod -a -G dialout $USER
   
   # Log out and log back in for changes to take effect
   ```

6. **Verify installation**:
   ```bash
   python main.py --help
   ```

### Fedora/RHEL/CentOS

1. **Install Python and pip**:
   ```bash
   sudo dnf install python3 python3-pip python3-virtualenv
   ```

2. **Install system dependencies**:
   ```bash
   sudo dnf install python3-tkinter python3-devel gcc
   ```

3. **Create virtual environment**:
   ```bash
   cd telemetry_validation
   python3 -m venv venv
   source venv/bin/activate
   ```

4. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure serial port permissions**:
   ```bash
   sudo usermod -a -G dialout $USER
   ```

### macOS

1. **Install Homebrew** (if not already installed):
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. **Install Python**:
   ```bash
   brew install python@3.11
   ```

3. **Create virtual environment**:
   ```bash
   cd telemetry_validation
   python3 -m venv venv
   source venv/bin/activate
   ```

4. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Install USB-to-serial drivers** (if needed):
   - For FTDI chips: Download from [FTDI website](https://ftdichip.com/drivers/vcp-drivers/)
   - For CH340/CH341 chips: Download from manufacturer website
   - For CP210x chips: Usually work without additional drivers

6. **Verify installation**:
   ```bash
   python main.py --help
   ```

### Windows

1. **Install Python**:
   - Download Python 3.11 from [python.org](https://www.python.org/downloads/)
   - Run installer and check "Add Python to PATH"
   - Verify installation: `python --version`

2. **Install Visual C++ Build Tools** (for some dependencies):
   - Download from [Microsoft](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
   - Install "Desktop development with C++" workload

3. **Create virtual environment**:
   ```cmd
   cd telemetry_validation
   python -m venv venv
   venv\Scripts\activate
   ```

4. **Install Python dependencies**:
   ```cmd
   pip install -r requirements.txt
   ```

5. **Install USB-to-serial drivers**:
   - For FTDI chips: Download from [FTDI website](https://ftdichip.com/drivers/vcp-drivers/)
   - For CH340/CH341 chips: Download from manufacturer website
   - For CP210x chips: Download from [Silicon Labs](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers)

6. **Verify installation**:
   ```cmd
   python main.py --help
   ```

### Raspberry Pi

1. **Update system**:
   ```bash
   sudo apt update
   sudo apt upgrade
   ```

2. **Install Python and dependencies**:
   ```bash
   sudo apt install python3 python3-pip python3-venv
   sudo apt install python3-serial python3-tk
   ```

3. **Create virtual environment**:
   ```bash
   cd telemetry_validation
   python3 -m venv venv
   source venv/bin/activate
   ```

4. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure serial port**:
   ```bash
   # Add user to dialout group
   sudo usermod -a -G dialout $USER
   
   # Disable serial console (if using GPIO serial)
   sudo raspi-config
   # Navigate to: Interface Options -> Serial Port
   # Disable login shell, enable serial port hardware
   ```

6. **Verify installation**:
   ```bash
   python main.py --help
   ```

## Dependency Installation

### Core Dependencies

The `requirements.txt` file includes:

```
pymavlink>=2.4.37      # MAVLink protocol support
pyserial>=3.5          # Serial port communication
matplotlib>=3.5.0      # Visualization
numpy>=1.21.0          # Numerical operations
```

### Optional Dependencies

For development and testing:

```bash
pip install pytest pytest-cov  # Testing
pip install black flake8       # Code formatting and linting
pip install sphinx             # Documentation generation
```

### Installing from requirements.txt

```bash
# Install all dependencies
pip install -r requirements.txt

# Install with specific versions
pip install -r requirements.txt --no-cache-dir

# Upgrade existing packages
pip install -r requirements.txt --upgrade
```

### Manual Dependency Installation

If `requirements.txt` installation fails, install dependencies manually:

```bash
pip install pymavlink
pip install pyserial
pip install matplotlib
pip install numpy
```

## Verification

### Verify Python Installation

```bash
python3 --version
# Should show: Python 3.8.x or higher
```

### Verify pip Installation

```bash
pip3 --version
# Should show: pip 20.x.x or higher
```

### Verify Dependencies

```bash
python3 -c "import pymavlink; print('pymavlink:', pymavlink.__version__)"
python3 -c "import serial; print('pyserial:', serial.VERSION)"
python3 -c "import matplotlib; print('matplotlib:', matplotlib.__version__)"
python3 -c "import numpy; print('numpy:', numpy.__version__)"
```

### Verify Serial Port Access

**Linux/macOS**:
```bash
# List serial ports
python3 -m serial.tools.list_ports

# Check permissions
ls -l /dev/ttyUSB0
# Should show: crw-rw---- 1 root dialout ...
```

**Windows**:
```cmd
# List serial ports
python -m serial.tools.list_ports

# Or use Device Manager
devmgmt.msc
```

### Test Installation

```bash
# Run help command
python3 main.py --help

# Run with dummy connection (no hardware required)
python3 main.py --connection-type udp --port 14550 --no-visualization

# Run validation scripts
python3 validate_connection_manager.py
python3 validate_binary_protocol_parser.py
```

## Troubleshooting

### Python Version Issues

**Problem**: `python3: command not found`

**Solution**:
```bash
# Try 'python' instead of 'python3'
python --version

# Or install Python 3
sudo apt install python3  # Linux
brew install python@3.11  # macOS
```

### pip Installation Issues

**Problem**: `pip: command not found`

**Solution**:
```bash
# Install pip
sudo apt install python3-pip  # Linux
python3 -m ensurepip         # macOS/Windows

# Or use python -m pip
python3 -m pip install -r requirements.txt
```

### Permission Denied (Serial Port)

**Problem**: `Permission denied: '/dev/ttyUSB0'`

**Solution**:
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER

# Or change permissions temporarily
sudo chmod 666 /dev/ttyUSB0

# Log out and log back in
```

### matplotlib Backend Issues

**Problem**: `ImportError: No module named '_tkinter'`

**Solution**:
```bash
# Install tkinter
sudo apt install python3-tk  # Linux
brew install python-tk       # macOS

# Or use different backend
export MPLBACKEND=Agg
```

### Serial Port Not Found

**Problem**: Serial port not listed

**Solution**:
```bash
# Check USB connection
lsusb  # Linux
system_profiler SPUSBDataType  # macOS

# Check kernel messages
dmesg | grep tty  # Linux

# Install drivers (see platform-specific instructions)
```

### Dependency Conflicts

**Problem**: Conflicting package versions

**Solution**:
```bash
# Use virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Install in clean environment
pip install -r requirements.txt
```

### Build Errors (Windows)

**Problem**: `error: Microsoft Visual C++ 14.0 is required`

**Solution**:
1. Install Visual C++ Build Tools
2. Or use pre-built wheels:
   ```cmd
   pip install --only-binary :all: -r requirements.txt
   ```

### Memory Issues (Raspberry Pi)

**Problem**: Installation fails due to low memory

**Solution**:
```bash
# Increase swap space
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Set CONF_SWAPSIZE=1024
sudo dphys-swapfile setup
sudo dphys-swapfile swapon

# Install dependencies one at a time
pip install pymavlink
pip install pyserial
pip install matplotlib
pip install numpy
```

## Post-Installation

### Configure System

1. **Copy configuration files**:
   ```bash
   cp config/config.json.example config/config.json
   cp config/validation_rules.json.example config/validation_rules.json
   ```

2. **Edit configuration**:
   ```bash
   nano config/config.json
   # Update serial port, baud rate, etc.
   ```

3. **Create log directory**:
   ```bash
   mkdir -p telemetry_logs
   ```

### Run First Test

```bash
# Test with serial connection
python3 main.py --connection-type serial --port /dev/ttyUSB0 --baudrate 115200

# Test with UDP connection
python3 main.py --connection-type udp --port 14550

# Test with configuration file
python3 main.py --config config/config.json
```

### Set Up Autostart (Optional)

**Linux (systemd)**:
```bash
# Create service file
sudo nano /etc/systemd/system/telemetry-validation.service

# Add content:
[Unit]
Description=Telemetry Validation System
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/telemetry_validation
ExecStart=/usr/bin/python3 main.py --config config/config.json
Restart=always

[Install]
WantedBy=multi-user.target

# Enable and start service
sudo systemctl enable telemetry-validation
sudo systemctl start telemetry-validation
```

**macOS (launchd)**:
```bash
# Create plist file
nano ~/Library/LaunchAgents/com.telemetry.validation.plist

# Add content (see macOS documentation)
```

**Windows (Task Scheduler)**:
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (At startup)
4. Set action (Start a program)
5. Program: `python.exe`
6. Arguments: `main.py --config config/config.json`
7. Start in: `C:\path\to\telemetry_validation`

## Next Steps

After installation:

1. Read [USAGE.md](USAGE.md) for usage instructions
2. Review [VALIDATION_RULES.md](VALIDATION_RULES.md) for validation rules
3. Check [BINARY_PROTOCOL.md](BINARY_PROTOCOL.md) for protocol details
4. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
5. Run example scripts in `examples/` directory

## Getting Help

If you encounter issues:

1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Review error messages carefully
3. Enable debug logging: `python3 main.py --log-level DEBUG`
4. Run validation scripts to test components
5. Check system requirements and dependencies

## See Also

- [README.md](README.md) - Main documentation
- [USAGE.md](USAGE.md) - Usage guide
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Troubleshooting guide
- [requirements.txt](requirements.txt) - Python dependencies
