# Bug Fix: Trade Notifications Not Being Sent

## 🐛 Root Cause

The worker was processing trades but **not sending alerts** because:

1. **Batch fetch was failing**: The Gamma API's batch fetch (comma-separated condition IDs) was returning 0 markets
2. **No fallback**: When batch fetch failed, the code didn't retry with individual fetches
3. **Trades were skipped**: When `market` was `None`, trades were logged as "Market: Unknown" but **filter matching was skipped entirely**
4. **No alerts sent**: Without filter matching, `send_alerts_for_trade()` was never called

## ✅ Fix Applied

**File**: `whale_worker/polymarket_client.py`

**Change**: Added fallback logic in `fetch_market_metadata_batch()`:
- When batch fetch returns 0 markets, automatically fall back to individual fetches
- Each condition ID is fetched individually with `closed=false` parameter
- All successfully fetched markets are combined and returned

**Code**:
```python
# If batch fetch returns empty but we know individual fetches work,
# fall back to individual fetches
if not markets and len(condition_ids) > 1:
    print(f"   ⚠️  Batch fetch returned 0 markets, falling back to individual fetches...")
    # Fetch each condition ID individually
    for condition_id in condition_ids:
        individual_params = {
            "condition_ids": condition_id,
            "include_tag": "true",
            "closed": "false",
            "limit": "1",
        }
        # ... fetch and add to markets list
```

## 🧪 Testing

✅ Tested: Fallback successfully fetches all markets individually when batch fails
✅ Verified: Markets are processed correctly and filter matching works
✅ Confirmed: Manual alert test works (Telegram notifications received)

## 📋 Next Steps

1. **Restart the worker**:
   ```bash
   python3 -m whale_worker.main
   ```

2. **Watch for**:
   - `⚠️  Batch fetch returned 0 markets, falling back to individual fetches...` messages
   - `🔔 Matches X user(s)` messages when trades match
   - `📬 Queued X alert(s)` messages when alerts are sent

3. **Expected behavior**:
   - Worker processes trades every 10 seconds
   - When markets aren't in cache, batch fetch is attempted first
   - If batch fails, individual fetches are used automatically
   - Trades with market metadata are matched against filters
   - Matching trades trigger Telegram alerts

## 🎯 Impact

- **Before**: Trades were processed but alerts were never sent (market=None → skip filter matching)
- **After**: Trades are processed, markets are fetched (with fallback), filters are matched, alerts are sent

## 📊 Performance Note

The fallback uses individual API calls, which is slower than batch fetching but:
- Still functional (alerts are sent)
- Only happens when batch fetch fails
- Better than silently skipping trades
- Can be optimized later if Gamma API fixes batch endpoint

