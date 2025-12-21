"""
Filter matching logic for determining which users should receive alerts.
"""
from typing import List
from whale_worker.types import Trade, AggregatedTrade, MarketMetadata, UserFilter


def trade_matches_user_filter(
    trade: Trade,
    market: MarketMetadata,
    user_filter: UserFilter
) -> bool:
    """
    Check if a trade matches a user's filter criteria.
    
    This function checks:
    1. Notional value threshold: notional >= minNotional
    2. Price range: price in [minPrice, maxPrice]
    3. Trade side: side in user's sides list
    4. Exclude sports: drop if market is sports (if excludeCategories includes "sports")
    5. Include tag IDs: require overlap with market tags (if category_filter specified)
    6. Specific market filter: condition_id in markets_filter (if specified)
    
    Args:
        trade: Trade to check.
        market: Market metadata from Gamma API (includes tags, tag_ids, is_sports).
        user_filter: User's filter configuration.
    
    Returns:
        True if trade matches all filter criteria, False otherwise.
    """
    # Filter must be enabled
    if not user_filter.enabled:
        return False
    
    # 1. Check notional threshold
    if trade.notional < user_filter.min_notional_usd:
        return False
    
    # 2. Check price range
    if not (user_filter.min_price <= trade.price <= user_filter.max_price):
        return False
    
    # 3. Check side
    if trade.side not in user_filter.sides:
        return False
    
    # 4. Check exclude sports (if "sports" is in exclude_categories)
    if "sports" in [c.lower() for c in user_filter.exclude_categories]:
        if market.is_sports:
            return False
    
    # 5. Check exclude categories (using legacy category field or is_sports)
    if user_filter.exclude_categories:
        for excluded_cat in user_filter.exclude_categories:
            excluded_cat_lower = excluded_cat.lower()
            # Check is_sports flag
            if excluded_cat_lower == "sports" and market.is_sports:
                return False
            # Check legacy category field
            if market.category and market.category.lower() == excluded_cat_lower:
                return False
    
    # 6. Check include tag IDs (if category_filter specified - treat as tag IDs to include)
    if user_filter.category_filter:
        # category_filter can contain tag IDs or category names
        # Check if any market tag ID is in the filter
        market_tag_ids = set(market.tag_ids or [])
        filter_tag_ids = set([str(tid) for tid in user_filter.category_filter])
        
        # If no overlap, trade doesn't match
        if not market_tag_ids.intersection(filter_tag_ids):
            # Also check legacy category field as fallback
            if not market.category or market.category.lower() not in [c.lower() for c in user_filter.category_filter]:
                return False
    
    # 7. Check specific market filter (condition_ids)
    if user_filter.markets_filter and trade.condition_id not in user_filter.markets_filter:
        return False
    
    # All checks passed
    return True


def get_matching_users_for_trade(
    trade: Trade,
    market: MarketMetadata,
    all_user_filters: List[UserFilter]
) -> List[UserFilter]:
    """
    Find all users whose filters match this trade.
    
    Args:
        trade: Trade to check.
        market: Market metadata for the trade.
        all_user_filters: List of all active user filters.
    
    Returns:
        List of UserFilter objects for users who should receive an alert.
    """
    matching = []
    for user_filter in all_user_filters:
        if trade_matches_user_filter(trade, market, user_filter):
            matching.append(user_filter)
    return matching


def aggregated_trade_matches_user_filter(
    agg_trade: AggregatedTrade,
    market: MarketMetadata,
    user_filter: UserFilter
) -> bool:
    """
    Check if an aggregated trade matches a user's filter criteria.
    
    This function checks:
    1. Notional value threshold: total_notional_usd >= minNotional
    2. Price range: vwap_price in [minPrice, maxPrice]
    3. Trade side: side in user's sides list
    4. Exclude sports: drop if market is sports (if excludeCategories includes "sports")
    5. Include tag IDs: require overlap with market tags (if category_filter specified)
    6. Specific market filter: condition_id in markets_filter (if specified)
    
    Args:
        agg_trade: AggregatedTrade to check.
        market: Market metadata from Gamma API (includes tags, tag_ids, is_sports).
        user_filter: User's filter configuration.
    
    Returns:
        True if aggregated trade matches all filter criteria, False otherwise.
    """
    # Filter must be enabled
    if not user_filter.enabled:
        return False
    
    # 1. Check notional threshold (using aggregated total_notional_usd)
    if agg_trade.total_notional_usd < user_filter.min_notional_usd:
        return False
    
    # 2. Check price range (using aggregated vwap_price)
    if not (user_filter.min_price <= agg_trade.vwap_price <= user_filter.max_price):
        return False
    
    # 3. Check side
    if agg_trade.side not in user_filter.sides:
        return False
    
    # 4. Check exclude sports (if "sports" is in exclude_categories)
    if "sports" in [c.lower() for c in user_filter.exclude_categories]:
        if market.is_sports:
            return False
    
    # 5. Check exclude categories (using legacy category field or is_sports)
    if user_filter.exclude_categories:
        for excluded_cat in user_filter.exclude_categories:
            excluded_cat_lower = excluded_cat.lower()
            # Check is_sports flag
            if excluded_cat_lower == "sports" and market.is_sports:
                return False
            # Check legacy category field
            if market.category and market.category.lower() == excluded_cat_lower:
                return False
    
    # 6. Check include tag IDs (if category_filter specified - treat as tag IDs to include)
    if user_filter.category_filter:
        # category_filter can contain tag IDs or category names
        # Check if any market tag ID is in the filter
        market_tag_ids = set(market.tag_ids or [])
        filter_tag_ids = set([str(tid) for tid in user_filter.category_filter])
        
        # If no overlap, trade doesn't match
        if not market_tag_ids.intersection(filter_tag_ids):
            # Also check legacy category field as fallback
            if not market.category or market.category.lower() not in [c.lower() for c in user_filter.category_filter]:
                return False
    
    # 7. Check specific market filter (condition_ids)
    if user_filter.markets_filter and agg_trade.condition_id not in user_filter.markets_filter:
        return False
    
    # All checks passed
    return True


def get_matching_users_for_aggregated_trade(
    agg_trade: AggregatedTrade,
    market: MarketMetadata,
    all_user_filters: List[UserFilter]
) -> List[UserFilter]:
    """
    Find all users whose filters match this aggregated trade.
    
    Args:
        agg_trade: AggregatedTrade to check.
        market: Market metadata for the trade.
        all_user_filters: List of all active user filters.
    
    Returns:
        List of UserFilter objects for users who should receive an alert.
    """
    matching = []
    for user_filter in all_user_filters:
        if aggregated_trade_matches_user_filter(agg_trade, market, user_filter):
            matching.append(user_filter)
    return matching

