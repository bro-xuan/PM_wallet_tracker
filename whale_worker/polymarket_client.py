"""
Polymarket API client for fetching trades and market metadata.

This module handles:
- Data API: For fetching recent trades (no category info)
- Gamma API: For fetching market metadata including categories
"""
from typing import List, Optional, Set, Dict
import httpx
from whale_worker.types import Trade, MarketMetadata, TradeMarker
from whale_worker.config import Config
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
    
    Args:
        last_marker: Optional TradeMarker with last_processed_timestamp to fetch
                     only trades newer than this timestamp.
        min_notional: Minimum notional value to filter trades (from GLOBAL_MIN_NOTIONAL_USD).
    
    Returns:
        List of Trade objects, sorted by timestamp (newest first).
        
    API Endpoint:
        GET https://data-api.polymarket.com/trades
        ?takerOnly=true
        &limit=1000
        &filterType=CASH
        &filterAmount={min_notional}
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
    
    # Add timestamp filter if marker provided (to only get new trades)
    # Note: API might use minTimestamp or similar - adjust based on actual API
    if last_marker and last_marker.last_processed_timestamp:
        # Try minTimestamp first, fallback to other param names if needed
        params["minTimestamp"] = str(last_marker.last_processed_timestamp)
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        # Convert to Trade objects
        trades = []
        seen_hashes = set()  # Deduplicate by transaction hash
        
        for item in data:
            # Extract transaction hash (required field)
            tx_hash = item.get("transactionHash")
            if not tx_hash:
                continue
            
            # Skip if we've already seen this trade (deduplication within this batch)
            if tx_hash in seen_hashes:
                continue
            seen_hashes.add(tx_hash)
            
            # Skip if this trade was already processed (check by hash)
            if last_marker and last_marker.last_processed_tx_hash == tx_hash:
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
            response = client.get(url)
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
        
        return MarketMetadata(
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
