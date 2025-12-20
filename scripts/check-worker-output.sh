#!/bin/bash
# Check if worker is producing output

echo "Checking worker process..."
WORKER_PID=$(pgrep -f "whale_worker.main" | head -1)

if [ -z "$WORKER_PID" ]; then
    echo "❌ Worker is not running"
    exit 1
fi

echo "✅ Worker is running (PID: $WORKER_PID)"
echo ""
echo "To see worker output, check the terminal where you started it,"
echo "or restart it in a visible terminal with:"
echo "  python3 -m whale_worker.main"
echo ""
echo "The worker should be printing:"
echo "  - Poll #X messages"
echo "  - Fetched X trades messages"
echo "  - Trade processing messages"
echo "  - Matches X user(s) messages"

