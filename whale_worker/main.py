"""
Main worker loop for monitoring Polymarket trades and sending alerts.
"""
import time
from whale_worker.config import load_config
from whale_worker.db import (
    get_db,
    get_last_processed_trade_marker,
    set_last_processed_trade_marker,
    get_or_upsert_market,
    get_or_cache_sports_tag_ids,
    get_or_cache_tags_dictionary,
    get_all_user_filters,
    mark_trade_as_processed,
    is_trade_processed,
    ensure_processed_trades_ttl_index,
    check_filter_reload_signal,
    clear_filter_reload_signal,
)
from whale_worker.polymarket_client import (
    fetch_recent_trades,
    fetch_market_metadata,
    fetch_market_metadata_batch,
    fetch_sports_tag_ids,
    fetch_tags_dictionary,
)
from whale_worker.filters import get_matching_users_for_trade, get_matching_users_for_aggregated_trade
from whale_worker.notifications import send_alerts_for_trade, send_alerts_for_aggregated_trade
from whale_worker.notification_queue import get_notification_queue
from whale_worker.types import Trade, AggregatedTrade, TradeMarker


def run_worker() -> None:
    """
    Main worker loop for polling Polymarket trades.
    
    Step 1: Poll trades from Data API
    - Fetches all trades matching filter criteria
    - Only processes new trades (using last processed marker)
    - Stores marker after processing
    
    Future steps (not yet implemented):
    - Fetch market metadata from Gamma API for each trade
    - Match trades against user filters
    - Send Telegram notifications
    """
    # Load configuration
    config = load_config()
    print(f"🚀 Starting whale worker")
    print(f"   Poll interval: {config.POLL_INTERVAL_SECONDS}s")
    print(f"   Min notional filter: ${config.GLOBAL_MIN_NOTIONAL_USD:,.2f}")
    print(f"   Max trades per poll: {config.MAX_TRADES_PER_POLL}")
    
    # Connect to MongoDB
    try:
        db = get_db()
        # Test connection
        db.command('ping')
        print("✅ Connected to MongoDB")
        
        # Ensure TTL index exists for processed trades deduplication
        ensure_processed_trades_ttl_index()
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        raise
    
    # Start notification queue worker (for async, rate-limited message sending)
    notification_queue = get_notification_queue()
    print("✅ Notification queue initialized")
    
    # Ensure queue is stopped on exit
    import atexit
    atexit.register(lambda: notification_queue.stop())
    
    # Step 3: Load sports tag IDs and tags dictionary (for categorization)
    print("\n📋 Loading market categorization data...")
    
    # Try to get from cache first
    sports_tag_ids = get_or_cache_sports_tag_ids()
    tags_dict = get_or_cache_tags_dictionary()
    
    # If not in cache, fetch from API
    if not sports_tag_ids:
        print("   Fetching sports tag IDs from Gamma API...")
        sports_tag_ids = fetch_sports_tag_ids()
        if sports_tag_ids:
            get_or_cache_sports_tag_ids(sports_tag_ids)
    
    if not tags_dict:
        print("   Fetching tags dictionary from Gamma API...")
        tags_dict = fetch_tags_dictionary()
        if tags_dict:
            get_or_cache_tags_dictionary(tags_dict)
    
    print(f"   ✅ Loaded {len(sports_tag_ids)} sports tag IDs, {len(tags_dict)} tags")
    
    # Step 4: Load all user filters (for matching trades)
    print("\n👥 Loading user filters...")
    all_user_filters = get_all_user_filters()
    print(f"   ✅ Loaded {len(all_user_filters)} active user filters")
    
    # Track when filters were last reloaded
    last_filter_reload = time.time()
    filter_reload_interval = config.FILTER_RELOAD_INTERVAL_SECONDS
    
    # Load last processed trade marker
    last_marker = get_last_processed_trade_marker()
    if last_marker:
        print(f"\n📍 Last processed: timestamp={last_marker.last_processed_timestamp} ({last_marker.last_processed_tx_hash[:10] if last_marker.last_processed_tx_hash else 'N/A'}...)")
    else:
        print("\n📍 No previous marker - will process all new trades from now on")
    
    print(f"\n⚙️  Filter reload interval: {filter_reload_interval}s (filters will refresh automatically)")
    
    # Main polling loop
    poll_count = 0
    try:
        while True:
            poll_count += 1
            print(f"\n📊 Poll #{poll_count} - Fetching trades...")
            
            # CRITICAL: Reload filters BEFORE fetching trades to ensure we use latest settings
            # Check if filters should be reloaded (immediate signal or periodic interval)
            current_time = time.time()
            should_reload = False
            reload_reason = ""
            
            # Check for immediate reload signal (set when user saves settings)
            if check_filter_reload_signal():
                should_reload = True
                reload_reason = "settings changed"
            # Or check if periodic reload interval has elapsed
            elif current_time - last_filter_reload >= filter_reload_interval:
                should_reload = True
                reload_reason = "periodic refresh"
            
            if should_reload:
                print(f"   🔄 Reloading user filters ({reload_reason})...")
                try:
                    new_filters = get_all_user_filters()
                    old_count = len(all_user_filters)
                    new_count = len(new_filters)
                    
                    # Compare filter values to detect actual changes
                    filters_changed = False
                    if old_count != new_count:
                        filters_changed = True
                    else:
                        # Check if any filter values changed
                        old_filter_dict = {f.user_id: f for f in all_user_filters}
                        for new_filter in new_filters:
                            old_filter = old_filter_dict.get(new_filter.user_id)
                            if old_filter:
                                if (old_filter.min_notional_usd != new_filter.min_notional_usd or
                                    old_filter.min_price != new_filter.min_price or
                                    old_filter.max_price != new_filter.max_price or
                                    set(old_filter.sides) != set(new_filter.sides) or
                                    old_filter.enabled != new_filter.enabled):
                                    filters_changed = True
                                    break
                    
                    all_user_filters = new_filters
                    last_filter_reload = current_time
                    
                    # Clear reload signal if it was set
                    if reload_reason == "settings changed":
                        clear_filter_reload_signal()
                    
                    if filters_changed:
                        print(f"   ✅ Filters updated: {old_count} → {new_count} active filters (values changed)")
                        # Log the new filter values for debugging
                        if all_user_filters:
                            uf = all_user_filters[0]
                            print(f"      New minNotional: ${uf.min_notional_usd:,.2f}, Price: {uf.min_price:.1%}-{uf.max_price:.1%}")
                    elif new_count != old_count:
                        print(f"   ✅ Filters updated: {old_count} → {new_count} active filters")
                    else:
                        print(f"   ✅ Filters refreshed: {new_count} active filters (no changes)")
                except Exception as e:
                    print(f"   ⚠️  Failed to reload filters: {e} (using cached filters)")
            
            try:
                # Fetch recent trades from Data API
                trades = fetch_recent_trades(
                    last_marker=last_marker,
                    min_notional=config.GLOBAL_MIN_NOTIONAL_USD
                )
                
                print(f"   Fetched {len(trades)} trades from API")
                
                if len(trades) == 0:
                    print("   No new trades found")
                else:
                    # Filter out trades we've already processed
                    # Step 1: Fill-level deduplication
                    # Each fill (row) from API is treated as a separate Trade.
                    # Deduplication happens at the fill level using fillKey.
                    new_fills = []
                    seen_cursor = False
                    
                    # Check each fill against deduplication set (by fillKey, not transaction_hash)
                    for fill in trades:
                        # Generate unique fill key for this fill
                        fill_key = fill.get_fill_key()
                        
                        # Check if this exact fill was already processed
                        if is_trade_processed(fill_key):
                            continue
                        
                        # Track if we see the cursor trade (for logging/info)
                        if last_marker and last_marker.last_processed_tx_hash:
                            if fill.transaction_hash == last_marker.last_processed_tx_hash:
                                seen_cursor = True
                                # Don't break - continue processing newer fills
                                # (cursor is just for info, not filtering)
                        
                        new_fills.append(fill)
                    
                    # Log cursor status (informational only)
                    if last_marker and last_marker.last_processed_tx_hash:
                        if seen_cursor:
                            print(f"   ℹ️  Cursor trade found in response (deduplication working correctly)")
                        else:
                            print(f"   ℹ️  Cursor trade not in response (may have expired from dedupe set or filtered by API)")
                    
                    print(f"   Found {len(new_fills)} new fills to process (after fill-level deduplication)")
                    
                    # Step 2: Aggregate fills into whale trades
                    # Group fills by: (transaction_hash, proxy_wallet, condition_id, outcome, side)
                    from collections import defaultdict
                    fill_groups = defaultdict(list)
                    
                    for fill in new_fills:
                        agg_key = fill.get_aggregation_key()
                        fill_groups[agg_key].append(fill)
                    
                    # Create AggregatedTrade objects from fill groups
                    aggregated_trades = []
                    for agg_key, fills in fill_groups.items():
                        # Mark all fills in this group as processed
                        for fill in fills:
                            fill_key = fill.get_fill_key()
                            mark_trade_as_processed(fill_key)
                        
                        # Aggregate fills into single whale trade
                        aggregated_trade = AggregatedTrade.from_fills(fills)
                        aggregated_trades.append(aggregated_trade)
                    
                    print(f"   Aggregated into {len(aggregated_trades)} whale trades (from {len(new_fills)} fills)")
                    
                    # Step 3: Batch fetch market metadata for all aggregated trades
                    # Collect all condition_ids that need metadata
                    missing_condition_ids = []
                    condition_id_to_aggregated_trades = {}  # Map condition_id -> list of aggregated trades
                    
                    for agg_trade in aggregated_trades:
                        if agg_trade.condition_id:
                            # Check cache first
                            cached_market = get_or_upsert_market(agg_trade.condition_id)
                            if not cached_market:
                                # Not in cache - add to batch fetch list
                                if agg_trade.condition_id not in condition_id_to_aggregated_trades:
                                    missing_condition_ids.append(agg_trade.condition_id)
                                    condition_id_to_aggregated_trades[agg_trade.condition_id] = []
                                condition_id_to_aggregated_trades[agg_trade.condition_id].append(agg_trade)
                    
                    # Batch fetch all missing markets in one API call
                    if missing_condition_ids:
                        print(f"   📦 Batch fetching metadata for {len(missing_condition_ids)} markets...")
                        batch_metadata = fetch_market_metadata_batch(
                            missing_condition_ids,
                            sports_tag_ids=sports_tag_ids,
                            tags_dict=tags_dict
                        )
                        
                        # Store all fetched markets in cache
                        for condition_id, metadata in batch_metadata.items():
                            get_or_upsert_market(condition_id, metadata)
                        
                        print(f"   ✅ Fetched {len(batch_metadata)}/{len(missing_condition_ids)} markets")
                    
                    # Step 4: Process each aggregated whale trade
                    for i, agg_trade in enumerate(aggregated_trades, 1):
                        # Get market metadata (now from cache or batch fetch)
                        market = None
                        if agg_trade.condition_id:
                            # Get from cache (should be there now after batch fetch)
                            market = get_or_upsert_market(agg_trade.condition_id)
                            
                            # Log aggregated trade with market info and categorization
                            if market:
                                # Build category string
                                category_parts = []
                                if market.is_sports:
                                    category_parts.append("🏈 SPORTS")
                                if market.category and not market.is_sports:
                                    category_parts.append(market.category.upper())
                                
                                category_str = f" | {' | '.join(category_parts)}" if category_parts else ""
                                
                                # Build tags string (show first 3 tag labels)
                                tags_str = ""
                                if market.tags:
                                    tags_str = f" | tags: {', '.join(market.tags[:3])}"
                                elif market.tag_ids and tags_dict:
                                    # Fallback: show tag IDs if labels not available
                                    tag_labels = [tags_dict.get(tid, {}).get("label", tid) for tid in market.tag_ids[:3]]
                                    tags_str = f" | tags: {', '.join(tag_labels)}"
                                
                                fill_count_str = f" ({agg_trade.fill_count} fills)" if agg_trade.fill_count > 1 else ""
                                print(f"   [{i}/{len(aggregated_trades)}] Whale Trade {agg_trade.transaction_hash[:10]}...{fill_count_str} | "
                                      f"${agg_trade.total_notional_usd:,.2f} | {agg_trade.side} | {agg_trade.vwap_price:.2%} | "
                                      f"{market.title[:50]}{category_str}{tags_str}")
                            else:
                                fill_count_str = f" ({agg_trade.fill_count} fills)" if agg_trade.fill_count > 1 else ""
                                print(f"   [{i}/{len(aggregated_trades)}] Whale Trade {agg_trade.transaction_hash[:10]}...{fill_count_str} | "
                                      f"${agg_trade.total_notional_usd:,.2f} | {agg_trade.side} | {agg_trade.vwap_price:.2%} | No market metadata")
                        else:
                            fill_count_str = f" ({agg_trade.fill_count} fills)" if agg_trade.fill_count > 1 else ""
                            print(f"   [{i}/{len(aggregated_trades)}] Whale Trade {agg_trade.transaction_hash[:10]}...{fill_count_str} | "
                                  f"${agg_trade.total_notional_usd:,.2f} | {agg_trade.side} | {agg_trade.vwap_price:.2%} | No condition_id")
                        
                        if market:
                            # Step 5: Match against user filters and send alerts (using aggregated trade)
                            matching_users = get_matching_users_for_aggregated_trade(agg_trade, market, all_user_filters)
                            if matching_users:
                                print(f"      🔔 Matches {len(matching_users)} user(s): {', '.join([f.user_id[:8] for f in matching_users])}")
                                send_alerts_for_aggregated_trade(agg_trade, market, matching_users)
                            else:
                                print(f"      ⏭️  No matching users")
                        else:
                            print(f"      ⚠️  No market metadata, skipping filter matching")
                    
                    # Update marker to the newest aggregated trade we processed
                    if aggregated_trades:
                        newest_agg_trade = aggregated_trades[0]  # Already sorted newest first
                        last_marker = TradeMarker(
                            last_processed_timestamp=newest_agg_trade.timestamp,
                            last_processed_tx_hash=newest_agg_trade.transaction_hash,
                        )
                        set_last_processed_trade_marker(last_marker)
                        print(f"   ✅ Updated marker: timestamp={last_marker.last_processed_timestamp}")
                
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"   ❌ Error in poll: {e}")
                import traceback
                traceback.print_exc()
            
            # Sleep before next poll
            print(f"   ⏳ Sleeping for {config.POLL_INTERVAL_SECONDS}s...")
            time.sleep(config.POLL_INTERVAL_SECONDS)
            
    except KeyboardInterrupt:
        print("\n🛑 Shutting down worker...")
        print(f"   Processed {poll_count} polls")
        if last_marker:
            print(f"   Last marker: timestamp={last_marker.last_processed_timestamp}")
        
        # Stop notification queue
        notification_queue.stop()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        
        # Stop notification queue on error
        notification_queue.stop()
        raise


if __name__ == "__main__":
    # TODO: Parse CLI args if needed (e.g., --config, --verbose)
    # import argparse
    # parser = argparse.ArgumentParser(description='Whale Trades Alert Worker')
    # parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    # args = parser.parse_args()
    
    # Run the worker
    run_worker()
