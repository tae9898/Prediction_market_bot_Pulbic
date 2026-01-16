#!/bin/bash

# Activate virtual environment
source .venv/bin/activate

# Check if wallets.json exists
if [ ! -f wallets.json ]; then
    echo "Error: wallets.json not found. Please run 'python -m scripts.setup_api_keys' to add at least one wallet."
    exit 1
fi

echo "Starting Polymarket Trading Bot..."

# Start Redeemer in background
python -m src.processes.redeemer &
REDEEMER_PID=$!
echo "Redeemer started (PID: $REDEEMER_PID)"

# Start Trader in foreground (or background if preferred)
echo "Starting Trader..."
python -m src.processes.trader

# Cleanup on exit
trap "kill $REDEEMER_PID" EXIT
