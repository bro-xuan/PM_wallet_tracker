# Gamma API Usage for Category Filtering

## Overview

The Polymarket **Data API** provides trade data but **doesn't include category information**. To filter trades by category (e.g., exclude sports markets), you need to use the **Gamma API** to fetch market metadata.

## Workflow

1. **Fetch trades from Data API** → Get list of trades with `condition_id`
2. **For each trade, fetch market metadata from Gamma API** → Get category information
3. **Filter by category** → Check if market category matches/excludes user's filter

## Example Implementation

```python
from whale_worker.polymarket_client import fetch_recent_trades, fetch_market_metadata
from whale_worker.filters import trade_matches_user_filter
from whale_worker.types import UserFilter

# 1. Fetch recent trades (no category info)
trades = fetch_recent_trades()

# 2. For each trade, fetch market metadata (includes category)
for trade in trades:
    # Fetch metadata from Gamma API
    market = fetch_market_metadata(trade.condition_id)
    
    # market.category will be something like:
    # - "sports"
    # - "politics" 
    # - "crypto"
    # - "entertainment"
    # - etc.
    
    # 3. Check if trade matches user filter (includes category check)
    user_filter = UserFilter(
        user_id="...",
        min_notional_usd=10000,
        min_price=0.05,
        max_price=0.95,
        sides=["BUY", "SELL"],
        category_filter=[],  # Empty = all categories
        exclude_categories=["sports"],  # Exclude sports markets
    )
    
    if trade_matches_user_filter(trade, market, user_filter):
        # Send alert
        pass
```

## Gamma API Endpoint

```
GET https://gamma-api.polymarket.com/condition/{condition_id}
```

### Response Example

```json
{
  "conditionId": "0x123...",
  "question": "Will Team X win the Super Bowl?",
  "slug": "will-team-x-win-super-bowl",
  "image": "https://...",
  "description": "...",
  "category": "sports",
  "subcategory": "nfl",
  "tags": ["football", "nfl", "super-bowl"]
}
```

## Category Values

Common categories from Gamma API:
- `"sports"`
- `"politics"`
- `"crypto"`
- `"entertainment"`
- `"economics"`
- `"technology"`
- (and others)

## Performance Considerations

Since you need to fetch metadata for each trade, consider:

1. **Caching**: Cache market metadata in MongoDB to avoid repeated API calls
2. **Batch fetching**: If Gamma API supports batch requests, use those
3. **Rate limiting**: Respect API rate limits
4. **Parallel requests**: Use async/threading to fetch multiple metadata in parallel

## Database Schema Update

You may want to store market metadata in MongoDB:

```python
# In db.py
def get_or_upsert_market(condition_id: str) -> dict:
    """
    Get market from cache, or fetch from Gamma API if not cached.
    """
    # Check MongoDB markets collection
    # If exists and recent (< 1 hour old), return cached
    # Otherwise, fetch from Gamma API and cache
    pass
```

This avoids fetching the same market metadata multiple times.

