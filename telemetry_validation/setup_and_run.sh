#!/bin/bash
# Setup and run script for Telemetry Validation System

echo "🚀 Setting up Telemetry Validation System..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "✅ Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "✨ Setup complete!"
echo ""
echo "To run the telemetry validation system:"
echo "  1. Make sure this terminal stays open"
echo "  2. Run: python main.py --connection-type udp --port 14550 --protocol-mode mavlink"
echo ""
echo "Or to monitor serial port:"
echo "  python main.py --connection-type serial --port /dev/tty.usbserial-XXXX --baudrate 115200"
echo ""
echo "To deactivate the virtual environment later, run: deactivate"
echo ""
