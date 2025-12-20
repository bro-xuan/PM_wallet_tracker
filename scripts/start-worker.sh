#!/bin/bash
# Script to start the whale worker

cd "$(dirname "$0")/.."

echo "🚀 Starting Whale Worker..."
echo ""
echo "This will start the Python worker that monitors trades and sends alerts."
echo "Press Ctrl+C to stop the worker."
echo ""
echo "=========================================="
echo ""

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ python3 not found. Please install Python 3."
    exit 1
fi

# Check if .env.local exists
if [ ! -f .env.local ]; then
    echo "⚠️  Warning: .env.local not found. Make sure environment variables are set."
fi

# Start the worker
python3 -m whale_worker.main

