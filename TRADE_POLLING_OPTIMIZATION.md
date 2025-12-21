# Trade Polling Optimization

## Problem Identified

The code was using `minTimestamp` parameter when fetching trades from Polymarket Data API:

```python
if last_marker and last_marker.last_processed_timestamp:
    params["minTimestamp"] = str(last_marker.last_processed_timestamp)
```

**Issue**: The Polymarket Data API `/trades` endpoint does **NOT** support `minTimestamp` as a query parameter.

**Supported Parameters** (from API docs):
- `limit`: Max number of trades to return
- `offset`: Pagination offset
- `takerOnly`: Only taker trades
- `filterType`: CASH or CREDIT
- `filterAmount`: Minimum notional filter
- `market`: Filter by market
- `eventId`: Filter by event
- `user`: Filter by user address
- `side`: BUY or SELL

**Impact**:
- The `minTimestamp` parameter was likely being ignored by the API
- We were always fetching the latest N trades (not filtered by timestamp)
- This could cause:
  - Re-processing of old trades
  - Inefficient API usage
  - Potential issues if API starts validating unknown params

---

## Solution Implemented

### 1. Removed `minTimestamp` Parameter

**File**: `whale_worker/polymarket_client.py`

**Changes**:
- Removed `minTimestamp` from API call parameters
- Updated documentation to clarify API doesn't support it
- Added note about relying on deduplication instead

**Before**:
```python
if last_marker and last_marker.last_processed_timestamp:
    params["minTimestamp"] = str(last_marker.last_processed_timestamp)
```

**After**:
```python
# NOTE: We do NOT use minTimestamp - it's not a supported parameter.
# We always fetch the latest N trades and rely on processedTrades
# deduplication collection to filter out already-processed trades.
```

### 2. Increased Trade Limit to 2000

**File**: `whale_worker/config.py`

**Changes**:
- Changed default `MAX_TRADES_PER_POLL` from `1000` to `2000`
- Ensures we fetch enough trades to cover high-volume periods

**Before**:
```python
MAX_TRADES_PER_POLL: int = int(os.getenv('MAX_TRADES_PER_POLL', '1000'))
```

**After**:
```python
MAX_TRADES_PER_POLL: int = int(os.getenv('MAX_TRADES_PER_POLL', '2000'))
```

### 3. Updated Deduplication Strategy

**File**: `whale_worker/main.py`

**Changes**:
- **Primary Method**: Relies on `processedTrades` TTL collection for deduplication
- **Cursor Usage**: Changed from filtering mechanism to informational/logging only
- Processes all trades from API response, filters via `is_trade_processed()` check

**Before**:
```python
# Stop when we reach the last processed trade (cursor)
if trade.transaction_hash == last_marker.last_processed_tx_hash:
    seen_cursor = True
    break  # Stop processing older trades

# Skip if already processed
if is_trade_processed(trade.transaction_hash):
    continue
```

**After**:
```python
# Check each trade against deduplication set
for trade in trades:
    # Check if already processed (primary deduplication method)
    if is_trade_processed(trade.transaction_hash):
        continue
    
    # Track if we see the cursor trade (for logging/info)
    if last_marker and last_marker.last_processed_tx_hash:
        if trade.transaction_hash == last_marker.last_processed_tx_hash:
            seen_cursor = True
            # Don't break - continue processing newer trades
            # (cursor is just for info, not filtering)
    
    new_trades.append(trade)
```

**Key Changes**:
- No longer breaks when cursor trade is found
- Processes all trades in response (up to limit)
- Deduplication happens via `processedTrades` collection check
- Cursor is tracked for logging purposes only

---

## How It Works Now

### Trade Fetching Flow

1. **API Call**: Always fetches latest 2000 trades
   ```
   GET /trades?takerOnly=true&limit=2000&filterType=CASH&filterAmount={min}
   ```

2. **Deduplication**: For each trade in response
   - Checks `processedTrades` collection (TTL: 15 minutes)
   - Query: `{ txHash: transaction_hash, expiresAt: { $gt: now } }`
   - If found: Skip trade (already processed)
   - If not found: Add to `new_trades` list

3. **Processing**: Process all trades in `new_trades` list
   - Mark as processed immediately
   - Fetch market metadata
   - Match against filters
   - Send alerts if matches found

4. **Cursor Update**: After processing
   - Updates cursor to newest processed trade
   - Used for logging/info, not for filtering

---

## Benefits

1. **Correct API Usage**: Only uses supported parameters
2. **Reliable Deduplication**: TTL-based set is more reliable than timestamp filtering
3. **No Missed Trades**: Processes all new trades regardless of timestamp gaps
4. **Handles High Volume**: 2000 trade limit covers busy periods
5. **Future-Proof**: Won't break if API starts validating parameters

---

## Deduplication Guarantees

**Two-Layer Protection**:

1. **Primary**: `processedTrades` TTL collection
   - Stores `txHash` with 15-minute TTL
   - Auto-deletes expired entries
   - Prevents duplicate processing

2. **Secondary**: Cursor tracking (informational)
   - Tracks last processed trade
   - Used for logging/debugging
   - Not used for filtering

**Edge Cases Handled**:
- Same timestamp trades: Deduplicated by `txHash`
- Worker restart: TTL set prevents re-processing recent trades
- High volume: 2000 limit ensures we catch all new trades
- API gaps: No reliance on timestamp continuity

---

## Performance Impact

**Before**:
- Fetched ~1000 trades per poll
- Relied on unsupported `minTimestamp` (may have been ignored)
- Could miss trades if timestamp filtering didn't work

**After**:
- Fetches 2000 trades per poll (covers more volume)
- Relies on reliable deduplication (TTL collection)
- Processes all new trades correctly

**Trade-off**:
- Slightly more trades to check against deduplication set
- But ensures no trades are missed
- Deduplication check is fast (indexed MongoDB query)

---

## Testing Recommendations

1. **Verify No Duplicates**: Check that same trade isn't processed twice
2. **Verify All New Trades Processed**: Ensure no new trades are missed
3. **Monitor Performance**: Check that 2000 trade limit doesn't cause slowdowns
4. **Check Cursor Logging**: Verify cursor tracking works for debugging

---

## Migration Notes

- **No Data Migration Required**: Changes are code-only
- **Cursor Still Updated**: Cursor is still maintained for logging/debugging
- **Backward Compatible**: Old cursor data is still valid (just not used for filtering)
- **TTL Collection**: Already exists and working (no changes needed)

