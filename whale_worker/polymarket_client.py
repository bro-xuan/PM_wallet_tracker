"""
Polymarket API client for fetching trades and market metadata.

This module handles:
- Data API: For fetching recent trades (no category info)
- Gamma API: For fetching market metadata including categories
"""
from typing import List, Optional, Set, Dict
import httpx
import asyncio
import httpx as httpx_async
from whale_worker.types import Trade, MarketMetadata, TradeMarker
from whale_worker.config import Config
from whale_worker.categorization import derive_categories_for_market
from whale_worker.db import get_db
from datetime import datetime, timedelta


def fetch_recent_trades(
    last_marker: Optional[TradeMarker] = None,
    min_notional: float = 0.0
) -> List[Trade]:
    """
    Fetch recent trades from Polymarket Data API.
    
    Note: The Data API doesn't provide category information.
    You'll need to fetch market metadata from Gamma API separately
    using fetch_market_metadata() to get category data.
    
    IMPORTANT: The Data API does NOT support minTimestamp parameter.
    We always fetch the latest N trades and rely on deduplication
    (processedTrades TTL collection) to filter out already-processed trades.
    
    Args:
        last_marker: Optional TradeMarker (kept for compatibility, not used for filtering).
        min_notional: Minimum notional value to filter trades (from GLOBAL_MIN_NOTIONAL_USD).
    
    Returns:
        List of Trade objects, sorted by timestamp (newest first).
        
    API Endpoint:
        GET https://data-api.polymarket.com/trades
        ?takerOnly=true
        &limit=2000
        &filterType=CASH
        &filterAmount={min_notional}
        
    Supported Parameters (from API docs):
        - limit: Max number of trades to return
        - offset: Pagination offset
        - takerOnly: Only taker trades
        - filterType: CASH or CREDIT
        - filterAmount: Minimum notional filter
        - market: Filter by market
        - eventId: Filter by event
        - user: Filter by user address
        - side: BUY or SELL
    """
    config = Config.get_config()
    data_api_url = config.POLYMARKET_DATA_API_URL
    
    # Construct URL with required parameters
    url = f"{data_api_url}/trades"
    params = {
        "takerOnly": "true",
        "limit": str(config.MAX_TRADES_PER_POLL),
        "filterType": "CASH",
    }
    
    # Add minimum notional filter if configured
    if min_notional > 0:
        params["filterAmount"] = str(min_notional)
    
    # NOTE: We do NOT use minTimestamp - it's not a supported parameter.
    # We always fetch the latest N trades and rely on processedTrades
    # deduplication collection to filter out already-processed trades.
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        # Convert to Trade objects
        # NOTE: We do NOT deduplicate by transaction_hash here.
        # Each fill (row) from the API is treated as a separate Trade.
        # Deduplication happens later at the fill level using fillKey.
        trades = []
        seen_fill_keys = set()  # Deduplicate exact duplicate fills (same all fields)
        
        for item in data:
            # Extract transaction hash (required field)
            tx_hash = item.get("transactionHash")
            if not tx_hash:
                continue
            
            # Extract required fields
            size = float(item.get("size", 0))
            price = float(item.get("price", 0))
            timestamp = int(item.get("timestamp", 0))
            proxy_wallet = item.get("proxyWallet", "")
            side = item.get("side", "").upper()
            condition_id = item.get("conditionId")
            outcome = item.get("outcome")
            
            # Skip trades with invalid data
            if size <= 0 or price <= 0 or timestamp <= 0:
                continue
            
            # Skip if side is not BUY or SELL
            if side not in ["BUY", "SELL"]:
                continue
            
            # Create Trade object first to generate fill key
            trade = Trade(
                transaction_hash=tx_hash,
                proxy_wallet=proxy_wallet.lower() if proxy_wallet else "",
                side=side,
                size=size,
                price=price,
                condition_id=condition_id,
                outcome=outcome,
                timestamp=timestamp,
            )
            
            # Only deduplicate exact duplicate fills (same fill key)
            # This handles API-level duplicates, not multi-fill transactions
            fill_key = trade.get_fill_key()
            if fill_key in seen_fill_keys:
                continue  # Skip exact duplicate fill
            seen_fill_keys.add(fill_key)
            
            # Skip if this exact fill was already processed (check by fill key, not tx hash)
            # Note: This check is now done later in main.py using processedTrades
            # We keep this here for backward compatibility with last_marker
            if last_marker and last_marker.last_processed_tx_hash == tx_hash:
                # Only skip if we're still using cursor-based deduplication
                # (This will be removed once fill-level deduplication is fully implemented)
                pass  # Don't skip - we want all fills now
            
            # Extract required fields
            size = float(item.get("size", 0))
            price = float(item.get("price", 0))
            timestamp = int(item.get("timestamp", 0))
            proxy_wallet = item.get("proxyWallet", "")
            side = item.get("side", "").upper()
            condition_id = item.get("conditionId")
            outcome = item.get("outcome")
            
            # Skip trades with invalid data
            if size <= 0 or price <= 0 or timestamp <= 0:
                continue
            
            # Skip if side is not BUY or SELL
            if side not in ["BUY", "SELL"]:
                continue
            
            trade = Trade(
                transaction_hash=tx_hash,
                proxy_wallet=proxy_wallet.lower() if proxy_wallet else "",
                side=side,
                size=size,
                price=price,
                condition_id=condition_id,
                outcome=outcome,
                timestamp=timestamp,
            )
            trades.append(trade)
        
        # Sort by timestamp descending (newest first)
        trades.sort(key=lambda t: t.timestamp, reverse=True)
        
        return trades
        
    except httpx.HTTPStatusError as e:
        print(f"❌ Error fetching trades: HTTP {e.response.status_code}")
        if e.response.status_code == 429:
            print("   Rate limited - consider increasing POLL_INTERVAL_SECONDS")
        try:
            error_body = e.response.json()
            print(f"   Error details: {error_body}")
        except:
            print(f"   Response: {e.response.text[:200]}")
        raise
    except httpx.TimeoutException:
        print("❌ Timeout fetching trades from Polymarket API")
        raise
    except Exception as e:
        print(f"❌ Error fetching trades: {e}")
        raise


def fetch_sports_tag_ids() -> Set[str]:
    """
    Fetch all sports from Gamma API and extract all tag IDs.
    
    Returns:
        Set of tag IDs that are associated with sports.
        
    API Endpoint:
        GET https://gamma-api.polymarket.com/sports
        
    Each sport has a 'tags' field which is a comma-separated string of tag IDs.
    """
    config = Config.get_config()
    gamma_api_url = config.POLYMARKET_GAMMA_API_URL
    
    url = f"{gamma_api_url}/sports"
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()
            sports = response.json()
        
        # Build set of all sports tag IDs
        sports_tag_ids = set()
        for sport in sports:
            tags_str = sport.get("tags", "")
            if tags_str:
                # Tags are comma-separated string
                tag_ids = [tid.strip() for tid in tags_str.split(",") if tid.strip()]
                sports_tag_ids.update(tag_ids)
        
        print(f"✅ Fetched {len(sports)} sports, found {len(sports_tag_ids)} unique sports tag IDs")
        return sports_tag_ids
        
    except Exception as e:
        print(f"❌ Error fetching sports: {e}")
        return set()


def fetch_tags_dictionary() -> Dict[str, Dict]:
    """
    Fetch all tags from Gamma API and build a dictionary.
    
    Returns:
        Dictionary mapping tag ID -> {label, slug, ...}
        
    API Endpoint:
        GET https://gamma-api.polymarket.com/tags
    """
    config = Config.get_config()
    gamma_api_url = config.POLYMARKET_GAMMA_API_URL
    
    url = f"{gamma_api_url}/tags"
    
    try:
        with httpx.Client(timeout=30.0) as client:
            # Request with limit=1000 to get more tags (API returns 300 with limit, 100 without)
            response = client.get(url, params={"limit": "1000"})
            response.raise_for_status()
            tags = response.json()
        
        # Build dictionary: tag_id -> tag_info
        tags_dict = {}
        for tag in tags:
            tag_id = str(tag.get("id", ""))
            if tag_id:
                tags_dict[tag_id] = {
                    "label": tag.get("label", ""),
                    "slug": tag.get("slug", ""),
                    "publishedAt": tag.get("publishedAt"),
                    "createdAt": tag.get("createdAt"),
                    "updatedAt": tag.get("updatedAt"),
                    "requiresTranslation": tag.get("requiresTranslation", False),
                }
        
        print(f"✅ Fetched {len(tags_dict)} tags")
        return tags_dict
        
    except Exception as e:
        print(f"❌ Error fetching tags: {e}")
        return {}


def _parse_gamma_market_response(
    market: Dict,
    sports_tag_ids: Set[str],
    tags_dict: Dict[str, Dict]
) -> Optional[MarketMetadata]:
    """
    Parse a single market response from Gamma API into MarketMetadata.
    
    Args:
        market: Market data dict from Gamma API response.
        sports_tag_ids: Set of tag IDs that identify sports markets.
        tags_dict: Dictionary mapping tag IDs to their full metadata.
    
    Returns:
        MarketMetadata object or None if parsing fails.
    """
    condition_id = market.get("conditionId") or market.get("id")
    if not condition_id:
        return None
    
    # Extract fields from Gamma API response
    title = market.get("question") or market.get("title") or market.get("name") or "Unknown Market"
    slug = market.get("slug")
    description = market.get("description")
    image_url = market.get("image") or market.get("imageUrl")
    
    # Extract raw tag IDs and tag labels
    market_tag_ids: List[str] = []
    market_tag_labels: List[str] = []
    raw_tags = market.get("tags", [])
    
    for tag_obj in raw_tags:
        if isinstance(tag_obj, dict):
            tag_id = str(tag_obj.get("id", ""))
            if tag_id:
                market_tag_ids.append(tag_id)
                # Use label from tags_dict if available, otherwise from tag_obj
                market_tag_labels.append(
                    tags_dict.get(tag_id, {}).get("label", 
                        tag_obj.get("label", tag_obj.get("slug", tag_id)))
                )
        elif isinstance(tag_obj, str):
            # Fallback for string tags
            market_tag_labels.append(tag_obj)
    
    # Determine if it's a sports market
    is_sports = bool(sports_tag_ids.intersection(set(market_tag_ids)))
    
    # Infer a primary category from tags if not explicitly provided
    inferred_category = None
    if market_tag_labels:
        tag_labels_lower = [label.lower() for label in market_tag_labels]
        
        if is_sports:
            inferred_category = "sports"
        elif any(kw in " ".join(tag_labels_lower) for kw in ["politics", "election", "president", "congress", "senate", "house"]):
            inferred_category = "politics"
        elif any(kw in " ".join(tag_labels_lower) for kw in ["crypto", "bitcoin", "ethereum", "blockchain", "btc", "eth"]):
            inferred_category = "crypto"
        elif any(kw in " ".join(tag_labels_lower) for kw in ["entertainment", "movie", "tv", "celebrity", "culture"]):
            inferred_category = "culture"
    
    # Create MarketMetadata object
    market_metadata = MarketMetadata(
        condition_id=condition_id,
        title=title,
        slug=slug,
        description=description,
        image_url=image_url,
        category=inferred_category,
        subcategory=market.get("subcategory"),
        tags=market_tag_labels,
        tag_ids=market_tag_ids,
        is_sports=is_sports,
    )
    
    # Derive categories from tags
    db = get_db()
    categories = derive_categories_for_market(market_metadata, db)
    market_metadata.categories = categories
    
    return market_metadata


def fetch_market_metadata_batch(
    condition_ids: List[str],
    sports_tag_ids: Set[str],
    tags_dict: Dict[str, Dict]
) -> Dict[str, MarketMetadata]:
    """
    Fetch market metadata for multiple condition IDs.
    
    NOTE: The Gamma API does not properly support batch fetching with comma-separated
    condition IDs or multiple parameters. This function attempts batch fetch first,
    then falls back to concurrent individual fetches for better performance.
    
    Args:
        condition_ids: List of Polymarket condition IDs to fetch.
        sports_tag_ids: A set of tag IDs that identify sports markets.
        tags_dict: A dictionary mapping tag IDs to their full metadata.
    
    Returns:
        Dictionary mapping condition_id -> MarketMetadata (only for found markets).
        
    API Endpoint:
        GET https://gamma-api.polymarket.com/markets
        ?condition_ids={condition_id}
        &include_tag=true
        &closed=false
        &limit=1
    """
    if not condition_ids:
        return {}
    
    config = Config.get_config()
    gamma_api_url = config.POLYMARKET_GAMMA_API_URL
    url = f"{gamma_api_url}/markets"
    
    results = {}
    
    # Attempt batch fetch first (though it typically fails)
    # This is kept for potential future API improvements
    try:
        condition_ids_str = ','.join(condition_ids)
        params = {
            "condition_ids": condition_ids_str,
            "include_tag": "true",
            "closed": "false",
            "limit": str(len(condition_ids)),
        }
        
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            markets = response.json()
            
            # If batch fetch succeeds, process results
            if markets:
                for market in markets:
                    condition_id = market.get("conditionId") or market.get("id")
                    if condition_id:
                        metadata = _parse_gamma_market_response(market, sports_tag_ids, tags_dict)
                        if metadata:
                            results[condition_id] = metadata
                
                # If we got all markets from batch, return early
                if len(results) == len(condition_ids):
                    return results
    except Exception as e:
        # Batch fetch failed, will fall back to individual fetches
        pass
    
    # Fall back to concurrent individual fetches
    # This is more efficient than sequential fetches
    if len(results) < len(condition_ids):
        missing_ids = [cid for cid in condition_ids if cid not in results]
        
        if len(missing_ids) > 1:
            print(f"   ⚠️  Batch fetch failed/partial, fetching {len(missing_ids)} markets individually (concurrent)...")
        else:
            print(f"   📦 Fetching {len(missing_ids)} market(s) individually...")
        
        # Use httpx.AsyncClient for concurrent requests (faster than sequential)
        async def fetch_single_market(condition_id: str) -> Optional[MarketMetadata]:
            """Fetch a single market metadata."""
            # Try with closed=false first (for active markets)
            params = {
                "condition_ids": condition_id,
                "include_tag": "true",
                "closed": "false",
                "limit": "1",
            }
            try:
                async with httpx_async.AsyncClient(timeout=30.0) as async_client:
                    response = await async_client.get(url, params=params)
                    response.raise_for_status()
                    markets_data = response.json()
                    if markets_data and len(markets_data) > 0:
                        return _parse_gamma_market_response(markets_data[0], sports_tag_ids, tags_dict)
                    
                    # If not found with closed=false, try without closed parameter (includes closed markets)
                    params_no_closed = {
                        "condition_ids": condition_id,
                        "include_tag": "true",
                        "limit": "1",
                    }
                    response = await async_client.get(url, params=params_no_closed)
                    response.raise_for_status()
                    markets_data = response.json()
                    if markets_data and len(markets_data) > 0:
                        return _parse_gamma_market_response(markets_data[0], sports_tag_ids, tags_dict)
            except Exception as e:
                print(f"   ⚠️  Failed to fetch {condition_id[:20]}...: {e}")
            return None
        
        # Fetch all missing markets concurrently
        async def fetch_all_markets():
            tasks = [fetch_single_market(cid) for cid in missing_ids]
            return await asyncio.gather(*tasks)
        
        # Run async fetches
        try:
            fetched_markets = asyncio.run(fetch_all_markets())
            for condition_id, metadata in zip(missing_ids, fetched_markets):
                if metadata:
                    results[condition_id] = metadata
        except Exception as e:
            print(f"   ❌ Error in concurrent fetch: {e}")
            # Fall back to sequential if async fails
            with httpx.Client(timeout=30.0) as client:
                for condition_id in missing_ids:
                    params = {
                        "condition_ids": condition_id,
                        "include_tag": "true",
                        "closed": "false",
                        "limit": "1",
                    }
                    try:
                        response = client.get(url, params=params)
                        response.raise_for_status()
                        markets_data = response.json()
                        if markets_data and len(markets_data) > 0:
                            metadata = _parse_gamma_market_response(markets_data[0], sports_tag_ids, tags_dict)
                            if metadata:
                                results[condition_id] = metadata
                    except Exception as e:
                        print(f"   ⚠️  Failed to fetch {condition_id[:20]}...: {e}")
                        continue
    
    return results


def fetch_market_metadata(
    condition_id: str,
    sports_tag_ids: Optional[Set[str]] = None,
    tags_dict: Optional[Dict[str, Dict]] = None
) -> Optional[MarketMetadata]:
    """
    Fetch market/condition metadata from Polymarket Gamma API.
    
    Uses the Gamma Markets endpoint which supports filtering by condition_ids
    and includes tags for classification.
    
    Args:
        condition_id: Polymarket condition ID.
    
    Returns:
        MarketMetadata object with market information including tags, or None if not found.
        
    API Endpoint:
        GET https://gamma-api.polymarket.com/markets
        ?condition_ids={condition_id}
        &include_tag=true
        &closed=false
        &limit=1
    """
    config = Config.get_config()
    gamma_api_url = config.POLYMARKET_GAMMA_API_URL
    
    # Construct endpoint URL with required parameters
    url = f"{gamma_api_url}/markets"
    params = {
        "condition_ids": condition_id,
        "include_tag": "true",
        "closed": "false",
        "limit": "1",
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        # The API returns a list of markets
        if not data or len(data) == 0:
            return None
        
        market = data[0]  # Get first (and only) result
        
        # Extract fields from Gamma API response
        title = market.get("question") or market.get("title") or market.get("name") or "Unknown Market"
        slug = market.get("slug")
        description = market.get("description")
        image_url = market.get("image") or market.get("imageUrl")
        
        # Extract tags (crucial for classification)
        # Tags are objects with 'id', 'label', and 'slug' fields
        tag_labels = []
        tag_ids = []
        raw_tags = market.get("tags", [])
        
        for tag_obj in raw_tags:
            if isinstance(tag_obj, dict):
                # Extract tag ID (for categorization)
                tag_id = str(tag_obj.get("id", ""))
                if tag_id:
                    tag_ids.append(tag_id)
                
                # Extract label (for display)
                tag_label = tag_obj.get("label") or tag_obj.get("slug")
                if tag_label:
                    tag_labels.append(tag_label)
            elif isinstance(tag_obj, str):
                # Handle case where tags might be strings
                tag_labels.append(tag_obj)
        
        # Check if market is sports by intersecting tag IDs with sports tag IDs
        is_sports = False
        if sports_tag_ids and tag_ids:
            is_sports = bool(sports_tag_ids.intersection(set(tag_ids)))
        
        # Build tag labels from tag IDs if tags_dict is provided
        if tags_dict and tag_ids:
            # Use tags_dict to get labels for tag IDs
            for tag_id in tag_ids:
                if tag_id in tags_dict:
                    label = tags_dict[tag_id].get("label", "")
                    if label and label not in tag_labels:
                        tag_labels.append(label)
        
        # Legacy category field (deprecated, use tag_ids and is_sports instead)
        category = None
        if is_sports:
            category = "sports"
        elif tags_dict and tag_ids:
            # Try to infer category from tag labels
            for tag_id in tag_ids:
                if tag_id in tags_dict:
                    label_lower = tags_dict[tag_id].get("label", "").lower()
                    if any(kw in label_lower for kw in ["politics", "election", "president", "congress"]):
                        category = "politics"
                        break
                    elif any(kw in label_lower for kw in ["crypto", "bitcoin", "ethereum"]):
                        category = "crypto"
                        break
        
        # Create MarketMetadata object
        market_metadata = MarketMetadata(
            condition_id=condition_id,
            title=title,
            slug=slug,
            description=description,
            image_url=image_url,
            category=category,
            subcategory=None,
            tags=tag_labels or [],
            tag_ids=tag_ids or [],
            is_sports=is_sports,
        )
        
        # Derive categories from tags
        db = get_db()
        categories = derive_categories_for_market(market_metadata, db)
        market_metadata.categories = categories
        
        return market_metadata
        
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            # Market not found
            return None
        print(f"❌ Error fetching market metadata: HTTP {e.response.status_code}")
        try:
            error_body = e.response.json()
            print(f"   Error details: {error_body}")
        except:
            print(f"   Response: {e.response.text[:200]}")
        return None
    except httpx.TimeoutException:
        print(f"❌ Timeout fetching market metadata for {condition_id}")
        return None
    except Exception as e:
        print(f"❌ Error fetching market metadata for {condition_id}: {e}")
        return None
