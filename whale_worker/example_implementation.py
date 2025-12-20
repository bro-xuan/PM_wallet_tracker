"""
Example implementation showing how to use Gamma API for category filtering.

This is a reference implementation showing the pattern you should follow.
"""

import httpx
from typing import List
from whale_worker.types import Trade, MarketMetadata, UserFilter


def fetch_market_metadata_example(condition_id: str) -> MarketMetadata:
    """
    Example: How to fetch market metadata from Gamma API.
    
    This shows the actual implementation pattern.
    """
    gamma_api_url = "https://gamma-api.polymarket.com"
    url = f"{gamma_api_url}/condition/{condition_id}"
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
        
        # Extract category information
        return MarketMetadata(
            condition_id=condition_id,
            title=data.get('question', ''),
            slug=data.get('slug'),
            description=data.get('description'),
            image_url=data.get('image'),
            category=data.get('category'),  # e.g., "sports", "politics"
            subcategory=data.get('subcategory'),
            tags=data.get('tags', []),
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return MarketMetadata(
                condition_id=condition_id,
                title="Unknown Market",
                category=None,
            )
        raise
    except Exception as e:
        print(f"Error: {e}")
        return MarketMetadata(
            condition_id=condition_id,
            title="Unknown Market",
            category=None,
        )


def filter_trades_by_category_example(
    trades: List[Trade],
    exclude_categories: List[str] = None
) -> List[Trade]:
    """
    Example: How to filter trades by excluding certain categories.
    
    Args:
        trades: List of trades from Data API
        exclude_categories: Categories to exclude (e.g., ["sports"])
    
    Returns:
        Filtered list of trades
    """
    if not exclude_categories:
        return trades
    
    filtered = []
    for trade in trades:
        # Fetch market metadata to get category
        market = fetch_market_metadata_example(trade.condition_id)
        
        # Check if category should be excluded
        if market.category and market.category.lower() in [c.lower() for c in exclude_categories]:
            continue  # Skip this trade
        
        filtered.append(trade)
    
    return filtered


def example_usage():
    """
    Complete example showing the workflow.
    """
    # 1. Fetch trades from Data API (no category info)
    # trades = fetch_recent_trades()
    
    # 2. User wants to exclude sports markets
    user_filter = UserFilter(
        user_id="user123",
        min_notional_usd=10000,
        min_price=0.05,
        max_price=0.95,
        sides=["BUY", "SELL"],
        exclude_categories=["sports"],  # Exclude sports markets
    )
    
    # 3. For each trade, fetch metadata and check category
    # for trade in trades:
    #     market = fetch_market_metadata(trade.condition_id)
    #     
    #     # Check if matches filter (includes category check)
    #     if trade_matches_user_filter(trade, market, user_filter):
    #         # Send alert
    #         send_alert(...)
    
    print("See EXAMPLE_GAMMA_API_USAGE.md for full documentation")


if __name__ == "__main__":
    example_usage()

