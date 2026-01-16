#!/bin/bash

# Activate virtual environment
source .venv/bin/activate

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found. Please copy .env.example to .env and fill in your keys."
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
