# Whale Alerts Troubleshooting Guide

## Issue: Not Receiving Telegram Notifications

### Step 1: Verify Configuration ✅

Your configuration looks correct:
- ✅ Telegram connected: `@erc721_stefan`
- ✅ Settings saved: "Settings saved successfully!"
- ✅ Filter configured: Min Notional $10,000, Price 5%-95%, Enabled

### Step 2: Check if Python Worker is Running

**The Python worker must be running for alerts to work!**

Check if worker is running:
```bash
ps aux | grep whale_worker
```

If not running, start it:
```bash
# Option 1: Using npm
npm run dev:worker

# Option 2: Direct Python
python3 -m whale_worker.main
```

### Step 3: Check Worker Logs

When the worker is running, you should see:
```
🚀 Starting whale worker
✅ Connected to MongoDB
👥 Loading user filters...
   ✅ Loaded 1 active user filters
📊 Poll #1 - Fetching trades...
   Fetched X trades from API
```

**Look for:**
- `✅ Loaded 1 active user filters` - Confirms your filter is loaded
- `Fetched X trades from API` - Confirms trades are being fetched
- `Matches X user(s)` - Confirms trades match your filter
- `📬 Queued X alert(s)` - Confirms alerts are being sent

### Step 4: Check if Trades Match Your Filter

**Your current filter:**
- Min Notional: **$10,000**
- Price Range: **5% - 95%**
- Sides: **BUY, SELL**

**Common issues:**

1. **Min Notional too high**: Most trades are < $10,000
   - **Solution**: Lower minNotional to $1,000 or $5,000 for testing

2. **Price range too narrow**: Many trades are at 0-5% or 95-100%
   - **Solution**: Expand price range to 0-100% for testing

3. **No trades matching**: Even with correct settings, there might not be matching trades right now
   - **Solution**: Wait for a large trade to occur, or lower thresholds

### Step 5: Test with Lower Thresholds

For testing, try:
- Min Notional: **$100** (instead of $10,000)
- Price Range: **0% - 100%** (instead of 5%-95%)

This will help verify the system is working, then you can increase thresholds.

### Step 6: Verify Notification Queue

The notification queue should be running. Check worker logs for:
```
✅ Notification queue initialized
```

If you see errors like:
- `❌ User blocked bot` - Telegram account needs to be reconnected
- `❌ Invalid chat_id` - Telegram connection issue
- `⏳ Rate limited` - Normal, will retry automatically

### Step 7: Manual Test

Test the notification system directly:
```bash
# In the web UI, click "Test Notification" button
# This should send a test message to your Telegram
```

If test notification works but real alerts don't:
- Worker might not be running
- Trades might not match your filter
- Check worker logs for details

## Quick Checklist

- [ ] Python worker is running (`python3 -m whale_worker.main`)
- [ ] Worker logs show "Loaded 1 active user filters"
- [ ] Worker logs show "Fetched X trades from API"
- [ ] Worker logs show "Matches X user(s)" when trades match
- [ ] "Test Notification" button works in web UI
- [ ] Filter thresholds are reasonable (not too high)
- [ ] Telegram account is connected and active

## Common Solutions

1. **Start the worker**: `npm run dev:worker` or `python3 -m whale_worker.main`
2. **Lower thresholds**: Set minNotional to $100 for testing
3. **Check logs**: Look for errors in worker output
4. **Wait for matching trades**: Large trades ($10k+) might be rare
5. **Test notification**: Use "Test Notification" button to verify Telegram connection

