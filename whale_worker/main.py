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
)
from whale_worker.polymarket_client import (
    fetch_recent_trades,
    fetch_market_metadata,
    fetch_sports_tag_ids,
    fetch_tags_dictionary,
)
from whale_worker.filters import get_matching_users_for_trade
from whale_worker.notifications import send_alerts_for_trade
from whale_worker.types import TradeMarker


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
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        raise
    
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
            
            # Reload user filters periodically to pick up changes
            current_time = time.time()
            if current_time - last_filter_reload >= filter_reload_interval:
                print("   🔄 Reloading user filters (checking for updates)...")
                try:
                    new_filters = get_all_user_filters()
                    old_count = len(all_user_filters)
                    new_count = len(new_filters)
                    all_user_filters = new_filters
                    last_filter_reload = current_time
                    if new_count != old_count:
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
                    # Filter out trades we've already processed (by tx hash)
                    new_trades = []
                    if last_marker and last_marker.last_processed_tx_hash:
                        for trade in trades:
                            if trade.transaction_hash != last_marker.last_processed_tx_hash:
                                new_trades.append(trade)
                            else:
                                # Found the last processed trade, stop here
                                break
                    else:
                        new_trades = trades
                    
                    print(f"   Found {len(new_trades)} new trades to process")
                    
                    # Process each new trade
                    for i, trade in enumerate(new_trades, 1):
                        notional = trade.notional
                        
                        # Step 2: Fetch market metadata (with caching)
                        # Step 3: Categorize market using sports tag IDs and tags dictionary
                        market = None
                        if trade.condition_id:
                            # Check cache first
                            market = get_or_upsert_market(trade.condition_id)
                            
                            # If not in cache, fetch from Gamma API with categorization
                            if not market:
                                market = fetch_market_metadata(
                                    trade.condition_id,
                                    sports_tag_ids=sports_tag_ids,
                                    tags_dict=tags_dict
                                )
                                
                                # Store in cache
                                if market:
                                    get_or_upsert_market(trade.condition_id, market)
                            
                            # Log trade with market info and categorization
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
                                
                                print(f"   [{i}/{len(new_trades)}] Trade {trade.transaction_hash[:10]}... | "
                                      f"${notional:,.2f} | {trade.side} | {trade.price:.2%} | "
                                      f"Market: {market.title[:50]}{category_str}{tags_str}")
                                
                                # Step 4: Match trade against user filters
                                matching_users = get_matching_users_for_trade(trade, market, all_user_filters)
                                if matching_users:
                                    print(f"      🔔 Matches {len(matching_users)} user(s): {', '.join([f.user_id[:8] for f in matching_users])}")
                                    # Step 5: Send Telegram notifications
                                    send_alerts_for_trade(trade, market, matching_users)
                                else:
                                    print(f"      ⏭️  No matching users")
                            else:
                                print(f"   [{i}/{len(new_trades)}] Trade {trade.transaction_hash[:10]}... | "
                                      f"${notional:,.2f} | {trade.side} | {trade.price:.2%} | "
                                      f"Market: Unknown (conditionId: {trade.condition_id[:10]}...)")
                        else:
                            print(f"   [{i}/{len(new_trades)}] Trade {trade.transaction_hash[:10]}... | "
                                  f"${notional:,.2f} | {trade.side} | {trade.price:.2%} | "
                                  f"No conditionId")
                    
                    # Update marker to the newest trade we processed
                    if new_trades:
                        newest_trade = new_trades[0]  # Already sorted newest first
                        last_marker = TradeMarker(
                            last_processed_timestamp=newest_trade.timestamp,
                            last_processed_tx_hash=newest_trade.transaction_hash,
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
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    # TODO: Parse CLI args if needed (e.g., --config, --verbose)
    # import argparse
    # parser = argparse.ArgumentParser(description='Whale Trades Alert Worker')
    # parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    # args = parser.parse_args()
    
    # Run the worker
    run_worker()
