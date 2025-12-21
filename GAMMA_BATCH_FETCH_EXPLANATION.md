# Gamma API Batch Fetch Explanation

## What is Batch Fetch?

**Batch fetch** is an optimization technique where instead of making multiple individual API calls (one per condition ID), we make a single API call with multiple condition IDs to fetch all market metadata at once.

### Example:

**Without batch fetch (inefficient):**
```
API Call 1: GET /markets?condition_ids=0x123... → Market 1
API Call 2: GET /markets?condition_ids=0x456... → Market 2
API Call 3: GET /markets?condition_ids=0x789... → Market 3
Total: 3 API calls
```

**With batch fetch (efficient):**
```
API Call 1: GET /markets?condition_ids=0x123...,0x456...,0x789... → Markets 1, 2, 3
Total: 1 API call
```

## How It Works in Our Code

### Step 1: Collect Missing Markets
When the worker processes trades, it:
1. Checks if market metadata is already cached in MongoDB
2. Collects all `condition_id`s that are NOT in cache
3. Groups them into a list for batch fetching

```python
missing_condition_ids = []
for trade in new_trades:
    if trade.condition_id:
        cached_market = get_or_upsert_market(trade.condition_id)
        if not cached_market:
            missing_condition_ids.append(trade.condition_id)
```

### Step 2: Batch Fetch
Makes a single API call with all missing condition IDs:

```python
# Current implementation (BROKEN)
condition_ids_str = ','.join(condition_ids)  # "0x123,0x456,0x789"
params = {
    "condition_ids": condition_ids_str,
    "include_tag": "true",
    "closed": "false",
    "limit": "10"
}
# GET /markets?condition_ids=0x123,0x456,0x789&include_tag=true&closed=false&limit=10
```

### Step 3: Process Results
Parses the response and creates `MarketMetadata` objects for each market found.

## The Problem

**The Gamma API batch fetch is returning 0 markets** even though:
- Individual fetches work: `GET /markets?condition_ids=0x123` → ✅ Returns market
- Batch fetch fails: `GET /markets?condition_ids=0x123,0x456` → ❌ Returns []

### Why This Happens

Based on testing, the Gamma API appears to have issues with:
1. **Comma-separated format**: `condition_ids=0x123,0x456` doesn't work
2. **The `closed=false` parameter**: May cause batch requests to fail
3. **API limitations**: The batch endpoint might not be fully functional

### Current Workaround

We have a fallback that fetches each condition ID individually when batch fails:
- ✅ Works (alerts are sent)
- ⚠️ Slower (N API calls instead of 1)
- ⚠️ More API load

## Impact

When batch fetch fails:
- Worker still processes trades (fallback works)
- Alerts are still sent (individual fetches succeed)
- Performance is reduced (more API calls)
- But functionality is maintained

