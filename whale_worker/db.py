"""
MongoDB database helpers for the whale worker.
"""
from typing import List, Optional, Set, Dict
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from whale_worker.types import UserFilter, TradeMarker, MarketMetadata
from whale_worker.config import Config
from datetime import datetime, timedelta


_client: Optional[MongoClient] = None
_db: Optional[Database] = None


def get_mongo_client() -> MongoClient:
    """
    Get or create MongoDB client (singleton).
    
    Returns:
        MongoClient instance.
    """
    global _client
    if _client is None:
        config = Config.get_config()
        if not config.MONGODB_URI:
            raise ValueError("MONGODB_URI not set in configuration")
        _client = MongoClient(
            config.MONGODB_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
        )
    return _client


def get_db() -> Database:
    """
    Get MongoDB database instance.
    
    Returns:
        Database instance.
    """
    global _db
    if _db is None:
        config = Config.get_config()
        client = get_mongo_client()
        _db = client[config.MONGODB_DB]
    return _db


def check_filter_reload_signal() -> bool:
    """
    Check if filters should be reloaded immediately (set by settings save).
    
    Returns:
        True if reload signal exists, False otherwise.
    """
    db = get_db()
    signals_collection = db['filterReloadSignals']
    signal = signals_collection.find_one({ '_id': 'global' })
    return signal is not None


def clear_filter_reload_signal() -> None:
    """
    Clear the filter reload signal after reloading.
    """
    db = get_db()
    signals_collection = db['filterReloadSignals']
    signals_collection.delete_one({ '_id': 'global' })


def get_all_user_filters() -> List[UserFilter]:
    """
    Fetch all active user filter configurations from MongoDB.
    
    Joins whaleAlertConfigs with telegramAccounts to get chatId for each user.
    Only returns filters where enabled=True and user has active Telegram connection.
    
    Returns:
        List of UserFilter objects for users with enabled alerts and active Telegram.
    """
    db = get_db()
    configs_collection = db['whaleAlertConfigs']
    telegram_collection = db['telegramAccounts']
    
    # Find all enabled configs
    configs = configs_collection.find({ 'enabled': True }).to_list(None)
    
    user_filters = []
    for config in configs:
        user_id = str(config.get('userId', ''))
        if not user_id:
            continue
        
        # Get Telegram chat ID for this user
        telegram_account = telegram_collection.find_one({
            'userId': user_id,
            'isActive': True
        })
        
        if not telegram_account:
            # Skip users without active Telegram connection
            continue
        
        chat_id = str(telegram_account.get('chatId', ''))
        
        # Build UserFilter from MongoDB document
        # Handle migration from excludeCategories to selectedCategories
        selected_categories = config.get('selectedCategories', [])
        exclude_categories = config.get('excludeCategories', [])
        
        # Migration: If selectedCategories doesn't exist but excludeCategories does,
        # invert excludeCategories to create selectedCategories
        if not selected_categories and exclude_categories:
            # All available categories (must match exactly with categorization.py)
            all_categories = [
                "Politics", "Sports", "Crypto", "Finance", "Geopolitics",
                "Earnings", "Tech", "Culture", "World", "Economy",
                "Trump", "Elections", "Mentions"
            ]
            # Normalize excludeCategories to match category names (case-insensitive)
            # Map common variations to canonical names
            category_map = {
                "politics": "Politics",
                "sports": "Sports",
                "crypto": "Crypto",
                "finance": "Finance",
                "geopolitics": "Geopolitics",
                "earnings": "Earnings",
                "tech": "Tech",
                "culture": "Culture",
                "world": "World",
                "economy": "Economy",
                "trump": "Trump",
                "elections": "Elections",
                "mentions": "Mentions"
            }
            # Normalize excluded categories to canonical names
            excluded_canonical = set()
            for cat in exclude_categories:
                cat_lower = cat.lower().strip()
                if cat_lower in category_map:
                    excluded_canonical.add(category_map[cat_lower])
                elif cat in all_categories:
                    excluded_canonical.add(cat)
            
            # Invert: selectedCategories = all categories except excluded ones
            selected_categories = [
                cat for cat in all_categories
                if cat not in excluded_canonical
            ]
        
        user_filter = UserFilter(
            user_id=user_id,
            min_notional_usd=float(config.get('minNotionalUsd', 0)),
            min_price=float(config.get('minPrice', 0)),
            max_price=float(config.get('maxPrice', 1)),
            sides=config.get('sides', ['BUY', 'SELL']),
            markets_filter=config.get('marketsFilter', []),
            category_filter=config.get('categoryFilter', []),  # Legacy
            exclude_categories=exclude_categories,  # Legacy (kept for backward compatibility)
            selected_categories=selected_categories,  # New preferred method (migrated if needed)
            enabled=bool(config.get('enabled', False)),
            telegram_chat_id=chat_id,
        )
        
        user_filters.append(user_filter)
    
    return user_filters


def get_telegram_chats_for_user(user_id: str) -> Optional[str]:
    """
    Get Telegram chat ID for a user.
    
    Args:
        user_id: User's MongoDB ObjectId as string.
        
    Returns:
        Telegram chat ID if user has connected Telegram, None otherwise.
    """
    # TODO: Query telegramAccounts collection
    # TODO: Filter by userId=user_id and isActive=true
    # TODO: Return chatId
    raise NotImplementedError("get_telegram_chats_for_user() not implemented")


def get_last_processed_trade_marker() -> Optional[TradeMarker]:
    """
    Get the last processed trade marker from MongoDB.
    
    The marker is stored in whaleAlertCursors collection with a fixed _id
    to ensure there's only one global cursor for the whale worker.
    
    Returns:
        TradeMarker if exists, None if no trades have been processed yet.
    """
    db = get_db()
    cursors_collection = db['whaleAlertCursors']
    
    # Use a fixed document ID for the global whale worker cursor
    doc = cursors_collection.find_one({ '_id': 'whale_worker_global' })
    
    if not doc:
        return None
    
    return TradeMarker(
        last_processed_timestamp=doc.get('lastProcessedTimestamp', 0),
        last_processed_tx_hash=doc.get('lastProcessedTxhash'),
        updated_at=doc.get('updatedAt'),
    )


def set_last_processed_trade_marker(marker: TradeMarker) -> None:
    """
    Update the last processed trade marker in MongoDB.
    
    Args:
        marker: TradeMarker with updated timestamp and tx_hash.
    """
    db = get_db()
    cursors_collection = db['whaleAlertCursors']
    
    # Upsert with fixed _id for global cursor
    cursors_collection.update_one(
        { '_id': 'whale_worker_global' },
        {
            '$set': {
                'lastProcessedTimestamp': marker.last_processed_timestamp,
                'lastProcessedTxhash': marker.last_processed_tx_hash,
                'updatedAt': datetime.utcnow(),
            },
            '$setOnInsert': {
                'createdAt': datetime.utcnow(),
            },
        },
        upsert=True
    )


def mark_trade_as_processed(fill_key: str, ttl_minutes: int = 15) -> None:
    """
    Mark a fill as processed in the deduplication set.
    
    This creates a TTL-indexed document that will be automatically deleted
    after the TTL expires. This prevents re-processing the same fill
    even if the cursor is reset or there are timestamp collisions.
    
    Args:
        fill_key: Unique fill key (format: tx_hash:wallet:condition:outcome:side:size:price).
        ttl_minutes: TTL in minutes (default: 15 minutes).
    """
    db = get_db()
    processed_trades_collection = db['processedTrades']
    
    # Create document with TTL
    expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)
    
    processed_trades_collection.update_one(
        { 'fillKey': fill_key },
        {
            '$set': {
                'fillKey': fill_key,
                'processedAt': datetime.utcnow(),
                'expiresAt': expires_at,
            },
            '$setOnInsert': {
                'createdAt': datetime.utcnow(),
            },
        },
        upsert=True
    )


def is_trade_processed(fill_key: str) -> bool:
    """
    Check if a fill has already been processed.
    
    Args:
        fill_key: Unique fill key to check (format: tx_hash:wallet:condition:outcome:side:size:price).
        
    Returns:
        True if fill has been processed (and not expired), False otherwise.
    """
    db = get_db()
    processed_trades_collection = db['processedTrades']
    
    # Check if fill exists and hasn't expired
    doc = processed_trades_collection.find_one({
        'fillKey': fill_key,
        'expiresAt': { '$gt': datetime.utcnow() }
    })
    
    return doc is not None


def ensure_processed_trades_ttl_index() -> None:
    """
    Ensure TTL index and unique index exist on processedTrades collection.
    
    Creates:
    - Unique index on fillKey (prevents duplicate fills)
    - TTL index on expiresAt (auto-deletes expired documents)
    
    This should be called once at startup to create the indexes.
    """
    db = get_db()
    processed_trades_collection = db['processedTrades']
    
    # Create unique index on fillKey
    try:
        processed_trades_collection.create_index(
            'fillKey',
            unique=True,
            name='fillKey_unique_idx'
        )
        print("   ✅ Created unique index on fillKey in processedTrades collection")
    except Exception as e:
        # Index might already exist, which is fine
        if 'already exists' not in str(e).lower():
            print(f"   ⚠️  Could not create fillKey unique index: {e}")
    
    # Create TTL index on expiresAt field (if it doesn't exist)
    # MongoDB will automatically delete documents after expiresAt
    try:
        processed_trades_collection.create_index(
            'expiresAt',
            expireAfterSeconds=0,  # Delete immediately when expiresAt is reached
            name='ttl_index_expiresAt'
        )
        print("   ✅ Created TTL index on expiresAt in processedTrades collection")
    except Exception as e:
        # Index might already exist, which is fine
        if 'already exists' not in str(e).lower():
            print(f"   ⚠️  Could not create TTL index: {e}")


def get_or_upsert_market(condition_id: str, market_metadata: Optional[MarketMetadata] = None) -> Optional[MarketMetadata]:
    """
    Get market metadata from cache/DB, or fetch and store if not exists.
    
    This function implements caching to avoid hitting the Gamma API repeatedly
    for the same market. Markets are cached in MongoDB with a TTL (default: 24 hours).
    
    Args:
        condition_id: Polymarket condition ID.
        market_metadata: Optional MarketMetadata to store if not in cache.
                         If None, caller should fetch from API and call again.
        
    Returns:
        MarketMetadata if found in cache or provided, None if not found.
    """
    from whale_worker.types import MarketMetadata
    
    db = get_db()
    markets_collection = db['marketMetadata']
    
    # Try to get from cache first
    cached = markets_collection.find_one({ 'conditionId': condition_id })
    
    if cached:
        # Check if cache is still valid (default TTL: 24 hours)
        cache_ttl_hours = 24
        updated_at = cached.get('updatedAt')
        if updated_at:
            if isinstance(updated_at, datetime):
                age = datetime.utcnow() - updated_at
                if age < timedelta(hours=cache_ttl_hours):
                    # Cache is valid, return cached metadata
                    return MarketMetadata(
                        condition_id=condition_id,
                        title=cached.get('title', 'Unknown Market'),
                        slug=cached.get('slug'),
                        description=cached.get('description'),
                        image_url=cached.get('imageUrl'),
                        category=cached.get('category'),
                        subcategory=cached.get('subcategory'),
                        tags=cached.get('tags', []),
                        tag_ids=cached.get('tagIds', []),
                        is_sports=cached.get('isSports', False),
                        categories=cached.get('categories', []),
                    )
            else:
                # Handle case where updatedAt might be a string
                # If it's not a datetime, assume cache is valid (for now)
                return MarketMetadata(
                    condition_id=condition_id,
                    title=cached.get('title', 'Unknown Market'),
                    slug=cached.get('slug'),
                    description=cached.get('description'),
                    image_url=cached.get('imageUrl'),
                    category=cached.get('category'),
                    subcategory=cached.get('subcategory'),
                    tags=cached.get('tags', []),
                    tag_ids=cached.get('tagIds', []),
                    is_sports=cached.get('isSports', False),
                    categories=cached.get('categories', []),
                )
    
    # Not in cache or cache expired - store if metadata provided
    if market_metadata:
        markets_collection.update_one(
            { 'conditionId': condition_id },
            {
                '$set': {
                    'conditionId': condition_id,
                    'title': market_metadata.title,
                    'slug': market_metadata.slug,
                    'description': market_metadata.description,
                    'imageUrl': market_metadata.image_url,
                    'category': market_metadata.category,
                    'subcategory': market_metadata.subcategory,
                    'tags': market_metadata.tags,
                    'tagIds': market_metadata.tag_ids,
                    'isSports': market_metadata.is_sports,
                    'categories': market_metadata.categories,
                    'updatedAt': datetime.utcnow(),
                },
                '$setOnInsert': {
                    'createdAt': datetime.utcnow(),
                },
            },
            upsert=True
        )
        return market_metadata
    
    # Not in cache and no metadata provided
    return None


def get_or_cache_sports_tag_ids(sports_tag_ids: Optional[Set[str]] = None) -> Set[str]:
    """
    Get sports tag IDs from cache or store if provided.
    
    Args:
        sports_tag_ids: Optional set of sports tag IDs to cache.
        
    Returns:
        Set of sports tag IDs (from cache or provided).
    """
    db = get_db()
    cache_collection = db['gammaCache']
    
    # Try to get from cache
    cached = cache_collection.find_one({ '_id': 'sports_tag_ids' })
    
    if cached and cached.get('data'):
        # Return cached data
        return set(cached.get('data', []))
    
    # Not in cache - store if provided
    if sports_tag_ids:
        cache_collection.update_one(
            { '_id': 'sports_tag_ids' },
            {
                '$set': {
                    'data': list(sports_tag_ids),
                    'updatedAt': datetime.utcnow(),
                },
                '$setOnInsert': {
                    'createdAt': datetime.utcnow(),
                },
            },
            upsert=True
        )
        return sports_tag_ids
    
    # Not in cache and not provided
    return set()


def get_or_cache_tags_dictionary(tags_dict: Optional[Dict[str, Dict]] = None) -> Dict[str, Dict]:
    """
    Get tags dictionary from cache or store if provided.
    
    Args:
        tags_dict: Optional tags dictionary to cache.
        
    Returns:
        Tags dictionary (from cache or provided).
    """
    db = get_db()
    cache_collection = db['gammaCache']
    
    # Try to get from cache
    cached = cache_collection.find_one({ '_id': 'tags_dictionary' })
    
    if cached and cached.get('data'):
        # Return cached data
        return cached.get('data', {})
    
    # Not in cache - store if provided
    if tags_dict:
        cache_collection.update_one(
            { '_id': 'tags_dictionary' },
            {
                '$set': {
                    'data': tags_dict,
                    'updatedAt': datetime.utcnow(),
                },
                '$setOnInsert': {
                    'createdAt': datetime.utcnow(),
                },
            },
            upsert=True
        )
        return tags_dict
    
    # Not in cache and not provided
    return {}

