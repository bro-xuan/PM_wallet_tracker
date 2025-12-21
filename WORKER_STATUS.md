# Worker Status & Troubleshooting

## Current Status

✅ **Worker is running** (PID: 1329)
✅ **Notification queue is working** (manual tests send alerts)
✅ **Markets are being cached** correctly
✅ **Filter matching logic works** (manual tests confirm)

## Issue Identified

**The worker was not running** - this is why no notifications were being sent.

## Solution

The worker has been restarted. It should now:
1. Process trades every 10 seconds
2. Fetch market metadata for new trades
3. Match trades against your filter
4. Send Telegram alerts for matching trades

## How to Monitor

### Check if worker is running:
```bash
pgrep -f "whale_worker.main"
```

### Check worker logs:
```bash
tail -f /tmp/whale_worker.log
```

### Check recent activity:
```bash
python3 scripts/full-diagnostic.py
```

## Expected Behavior

When the worker is running correctly, you should see in the logs:
- `📊 Poll #X - Fetching trades...` (every 10 seconds)
- `Fetched X trades from API`
- `Found X new trades to process`
- `🔔 Matches X user(s)` (when trades match)
- `📬 Queued X alert(s)` (when alerts are sent)

## If Notifications Still Don't Arrive

1. **Check worker is running**: `pgrep -f "whale_worker.main"`
2. **Check worker logs**: `tail -f /tmp/whale_worker.log`
3. **Check filter settings**: Make sure minNotional is not too high
4. **Check Telegram connection**: Use "Test Notification" button
5. **Check for matching trades**: Run `python3 scripts/test-complete-flow.py`

## Filter Settings

Current filter:
- Min Notional: $500.00
- Price Range: 5.0% - 95.0%
- Sides: BUY, SELL

If you're not seeing alerts, consider:
- Lowering minNotional to $100-$200 for more frequent alerts
- Checking if large trades are happening (they may be rare)

