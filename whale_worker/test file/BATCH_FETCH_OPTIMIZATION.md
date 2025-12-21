# Batch Market Metadata Fetching Optimization

## Problem

Previously, the worker fetched market metadata **one at a time** for each trade:

```python
for trade in trades:
    market = get_or_upsert_market(trade.condition_id)  # Check cache
    if not market:
        market = fetch_market_metadata(trade.condition_id, ...)  # 1 API call per trade
        get_or_upsert_market(trade.condition_id, market)
```

**Issues:**
- **N trades = N API calls** to Gamma API
- High latency during bursts (many new markets)
- Increased rate limiting risk
- Network overhead

## Solution

**Batch fetch all missing markets in a single API call:**

1. **First pass**: Collect all `condition_ids` that are missing from cache
2. **Batch fetch**: Call Gamma API once with all missing `condition_ids`
3. **Store**: Upsert all fetched markets to cache
4. **Second pass**: Process trades (markets now in cache)

## Implementation

### New Function: `fetch_market_metadata_batch()`

**Location**: `whale_worker/polymarket_client.py`

**Signature**:
```python
def fetch_market_metadata_batch(
    condition_ids: List[str],
    sports_tag_ids: Set[str],
    tags_dict: Dict[str, Dict]
) -> Dict[str, MarketMetadata]:
```

**Features**:
- Accepts list of condition IDs
- Makes single API call: `GET /markets?condition_ids=id1,id2,id3,...`
- Returns dictionary: `{condition_id: MarketMetadata, ...}`
- Handles errors gracefully (returns empty dict on failure)

### Updated Processing Flow

**Before** (N API calls):
```
Trade 1 → Check cache → Not found → API call 1
Trade 2 → Check cache → Not found → API call 2
Trade 3 → Check cache → Not found → API call 3
...
Trade N → Check cache → Not found → API call N
```

**After** (1 API call):
```
Pass 1: Collect missing condition_ids
  Trade 1 → Check cache → Not found → Add to batch
  Trade 2 → Check cache → Not found → Add to batch
  Trade 3 → Check cache → Found → Skip
  ...
  Trade N → Check cache → Not found → Add to batch

Pass 2: Batch fetch all missing markets
  → Single API call with all condition_ids
  → Store all in cache

Pass 3: Process trades (markets now in cache)
  Trade 1 → Get from cache → Process
  Trade 2 → Get from cache → Process
  ...
```

## Performance Impact

### Example Scenario

**Before optimization:**
- 50 new trades with 30 unique markets
- 30 API calls to Gamma API
- ~30 seconds (1 second per call)

**After optimization:**
- 50 new trades with 30 unique markets
- 1 API call to Gamma API
- ~1 second total

**Improvement: 30x faster** 🚀

### Benefits

- ✅ **Massive reduction in API calls**: N → 1
- ✅ **Lower latency**: Single round-trip instead of N
- ✅ **Reduced rate limiting risk**: Fewer API calls
- ✅ **Better burst handling**: Handles spikes efficiently
- ✅ **Network efficiency**: Less overhead

## Code Changes

### `whale_worker/polymarket_client.py`

Added `fetch_market_metadata_batch()` function that:
- Accepts list of condition IDs
- Makes single API call with comma-separated IDs
- Processes all markets in response
- Returns dictionary mapping condition_id → MarketMetadata

### `whale_worker/main.py`

Updated processing loop:
1. **Collection phase**: Gather all missing condition_ids
2. **Batch fetch phase**: Fetch all missing markets in one call
3. **Storage phase**: Store all fetched markets in cache
4. **Processing phase**: Process trades (markets in cache)

## API Details

**Gamma API Endpoint**:
```
GET https://gamma-api.polymarket.com/markets
?condition_ids=0x123...,0x456...,0x789...
&include_tag=true
&closed=false
&limit=100
```

**Response**: Array of market objects (one per condition_id)

**Limits**:
- Gamma API supports multiple condition_ids in a single call
- No documented limit, but we use `limit` parameter
- If batch is too large, can split into chunks (future enhancement)

## Edge Cases Handled

1. **Empty batch**: Returns empty dict immediately
2. **Some markets not found**: Returns only found markets
3. **API errors**: Returns empty dict, logs error
4. **Timeout**: Returns empty dict, logs timeout
5. **Partial cache hits**: Only fetches missing markets

## Example Output

```
📊 Poll #42 - Fetching trades...
   Fetched 25 trades from API
   Found 25 new trades to process (after deduplication)
   📦 Batch fetching metadata for 12 markets...
   ✅ Fetched 12/12 markets
   [1/25] Trade 0xabc123... | $15,000.00 | BUY | 65.00% | Market: Will BTC hit $100k? | 🏈 SPORTS | tags: Crypto, Bitcoin
   ...
```

## Future Enhancements

- [ ] **Chunking**: If batch > 100 markets, split into chunks
- [ ] **Parallel batches**: Fetch multiple chunks in parallel
- [ ] **Metrics**: Track batch size, API call reduction
- [ ] **Fallback**: If batch fails, fall back to individual fetches

## Testing

To verify the optimization:

1. **Monitor logs**: Look for "Batch fetching metadata for N markets"
2. **Check API calls**: Should see 1 call instead of N
3. **Verify correctness**: All markets should be fetched and cached
4. **Test with bursts**: Process many new trades at once

## Conclusion

This optimization **dramatically improves performance** during bursts when many new markets appear. Instead of making N API calls, we make 1, reducing latency, network overhead, and rate limiting risk.

**Impact**: 10-100x faster during bursts, depending on number of unique markets.

