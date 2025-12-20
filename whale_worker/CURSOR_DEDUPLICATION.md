# Cursor and Deduplication Solution

## Problem

The original cursor implementation had edge cases:

1. **Timestamp Collisions**: Multiple trades can have the same timestamp, causing us to miss trades
2. **Re-processing on Restart**: If we only use timestamp, we might re-process trades after restart
3. **Race Conditions**: Trades could be processed multiple times if the worker restarts mid-batch

## Solution

Implemented a **two-layer deduplication strategy**:

1. **Cursor-based filtering** (primary): Uses `{lastTimestamp, lastTxHash}` to skip already-seen trades
2. **TTL-based deduplication set** (safety net): Tracks processed tx hashes with automatic expiration

## Implementation

### 1. Enhanced Cursor (`TradeMarker`)

Already stores both:
- `last_processed_timestamp`: Unix timestamp of last processed trade
- `last_processed_tx_hash`: Transaction hash of last processed trade

**Location**: `whale_worker/types.py`, `whale_worker/db.py`

### 2. Deduplication Set (`processedTrades` collection)

New MongoDB collection with TTL index:

**Schema**:
```javascript
{
  txHash: "0x...",           // Transaction hash (unique)
  processedAt: ISODate,      // When it was processed
  expiresAt: ISODate,        // TTL expiration (15 minutes default)
  createdAt: ISODate
}
```

**TTL Index**: Automatically deletes documents after `expiresAt` is reached

**Functions**:
- `mark_trade_as_processed(tx_hash, ttl_minutes=15)`: Mark a trade as processed
- `is_trade_processed(tx_hash)`: Check if trade was already processed
- `ensure_processed_trades_ttl_index()`: Create TTL index (called at startup)

**Location**: `whale_worker/db.py`

### 3. Processing Logic

**Before processing trades**:
1. Fetch trades from API (filtered by `minTimestamp` from cursor)
2. Stop when we reach `last_processed_tx_hash` (cursor boundary)
3. For each trade before cursor:
   - Check deduplication set: `is_trade_processed(tx_hash)`
   - Skip if already processed
   - Add to `new_trades` list

**During processing**:
1. Mark trade as processed **immediately** (before processing)
   - Prevents duplicate processing if worker crashes mid-batch
   - Uses TTL of 15 minutes (configurable)

**After processing**:
1. Update cursor with newest trade's `{timestamp, tx_hash}`
2. Deduplication set entries expire automatically after TTL

**Location**: `whale_worker/main.py`

## Benefits

### ✅ Handles Timestamp Collisions
- Multiple trades with same timestamp are handled correctly
- Deduplication set prevents re-processing

### ✅ Prevents Re-processing on Restart
- Cursor provides fast skip (stops at last processed trade)
- Deduplication set catches any trades that slip through

### ✅ Handles Race Conditions
- Trades marked as processed immediately
- Even if worker crashes, won't re-process same trade

### ✅ Automatic Cleanup
- TTL index automatically deletes old entries
- No manual cleanup needed
- Memory-efficient (only recent trades tracked)

### ✅ Configurable TTL
- Default: 15 minutes
- Can be adjusted per trade if needed
- Balances safety vs. memory usage

## Edge Cases Handled

1. **Same Timestamp**: Multiple trades with identical timestamp
   - ✅ Cursor uses `tx_hash` for exact matching
   - ✅ Deduplication set tracks all processed hashes

2. **Worker Restart**: Worker restarts mid-batch
   - ✅ Cursor persists last processed trade
   - ✅ Deduplication set prevents re-processing recent trades

3. **API Returns Old Trades**: API returns trades we've already processed
   - ✅ Deduplication set catches them
   - ✅ Cursor provides fast skip

4. **Clock Skew**: System clock changes
   - ✅ Uses transaction hash (not just timestamp)
   - ✅ Deduplication set is hash-based

5. **Duplicate API Responses**: Same trade appears in multiple API calls
   - ✅ Deduplication set prevents duplicate processing

## Configuration

Default TTL: **15 minutes**

Can be customized per trade:
```python
mark_trade_as_processed(tx_hash, ttl_minutes=30)  # 30 minute TTL
```

Or set globally via environment variable (future enhancement):
```bash
PROCESSED_TRADES_TTL_MINUTES=15
```

## Performance

- **Cursor**: O(1) lookup - stops at last processed trade
- **Deduplication Set**: O(1) lookup - MongoDB index on `txHash`
- **TTL Cleanup**: Automatic - MongoDB handles expiration
- **Memory**: Only tracks recent trades (15 min window)

## Example Flow

```
1. Worker starts, loads cursor: {timestamp: 1234567890, txHash: "0xabc..."}
2. Fetches trades from API (minTimestamp: 1234567890)
3. API returns: [trade1, trade2, trade3, trade4, trade5]
4. Processing:
   - trade1: Not in dedup set → Process → Mark as processed
   - trade2: Not in dedup set → Process → Mark as processed
   - trade3: Already in dedup set → Skip
   - trade4: txHash == "0xabc..." → Stop (reached cursor)
5. Update cursor: {timestamp: trade2.timestamp, txHash: trade2.txHash}
6. Next poll: Start from trade2.timestamp, dedup set prevents re-processing trade1, trade2
```

## Database Collections

### `whaleAlertCursors`
- Stores cursor: `{_id: 'whale_worker_global', lastProcessedTimestamp, lastProcessedTxhash}`

### `processedTrades` (NEW)
- Stores processed tx hashes with TTL
- Index: `txHash` (unique)
- TTL Index: `expiresAt` (auto-delete after expiration)

## Testing

To verify deduplication works:

1. **Test timestamp collision**:
   - Process trade with timestamp T
   - Receive another trade with same timestamp T
   - Verify second trade is skipped

2. **Test restart**:
   - Process some trades
   - Restart worker
   - Verify trades aren't re-processed

3. **Test TTL expiration**:
   - Process trade
   - Wait > 15 minutes
   - Verify dedup entry is deleted (check MongoDB)

## Future Enhancements

- [ ] Configurable TTL via environment variable
- [ ] Metrics: Track deduplication hit rate
- [ ] Alerting: Monitor for high duplicate rates (might indicate API issues)

