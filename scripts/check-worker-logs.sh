#!/bin/bash
# Check if we can see worker output

echo "Checking worker process..."
WORKER_PID=$(pgrep -f "whale_worker.main" | head -1)

if [ -z "$WORKER_PID" ]; then
    echo "❌ Worker is not running"
    exit 1
fi

echo "✅ Worker is running (PID: $WORKER_PID)"
echo ""
echo "To see worker output, you need to:"
echo "1. Stop the current worker (kill $WORKER_PID)"
echo "2. Restart it in foreground: python3 -m whale_worker.main"
echo ""
echo "The worker should print:"
echo "  - Poll #X messages"
echo "  - Fetched X trades"
echo "  - Trade processing messages"
echo "  - '🔔 Matches X user(s)' when trades match"
echo "  - '📬 Queued X alert(s)' when alerts are sent"

