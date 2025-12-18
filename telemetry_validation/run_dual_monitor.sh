#!/bin/bash
# Dual Telemetry Monitor - Ground and Drone
# Opens two terminal tabs to monitor both ends of the telemetry link

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Open new Terminal window with two tabs
osascript <<EOF
tell application "Terminal"
    activate
    
    -- First tab: Ground monitoring (UDP from QGC)
    do script "cd '$SCRIPT_DIR' && source venv/bin/activate && echo '🌍 GROUND NODE - Monitoring UDP from QGC' && python main.py --connection-type udp --port 14445 --protocol-mode mavlink --log-prefix ground"
    
    -- Second tab: Drone monitoring (Serial)
    tell application "System Events" to keystroke "t" using command down
    delay 0.5
    do script "cd '$SCRIPT_DIR' && source venv/bin/activate && echo '🚁 DRONE NODE - Monitoring Serial from Flight Controller' && python main.py --connection-type serial --port /dev/tty.usbserial-4 --baudrate 57600 --protocol-mode mavlink --log-prefix drone" in front window
end tell
EOF

echo "✅ Dual monitoring started in new Terminal window"
echo "   Tab 1: Ground node (UDP)"
echo "   Tab 2: Drone node (Serial)"
