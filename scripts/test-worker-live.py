#!/usr/bin/env python3
"""
Test script to simulate what the worker does for a few trades.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whale_worker.config import load_config
from whale_worker.db import get_db, get_all_user_filters, get_last_processed_trade_marker, is_trade_processed, mark_trade_as_processed, get_or_upsert_market
from whale_worker.polymarket_client import fetch_recent_trades, fetch_market_metadata_batch, fetch_sports_tag_ids, fetch_tags_dictionary
from whale_worker.filters import get_matching_users_for_trade
from whale_worker.notifications import send_alerts_for_trade

def main():
    print("🧪 Simulating Worker Processing\n")
    print("=" * 70)
    
    config = load_config()
    db = get_db()
    
    # Load filters
    all_user_filters = get_all_user_filters()
    print(f"✅ Loaded {len(all_user_filters)} user filter(s)\n")
    
    if len(all_user_filters) == 0:
        print("❌ No user filters found!")
        return
    
    uf = all_user_filters[0]
    print(f"Filter config:")
    print(f"  - Min Notional: ${uf.min_notional_usd:,.2f}")
    print(f"  - Price Range: {uf.min_price:.1%} - {uf.max_price:.1%}")
    print(f"  - Sides: {uf.sides}")
    print()
    
    # Load categorization data
    print("Loading categorization data...")
    sports_tag_ids = fetch_sports_tag_ids()
    tags_dict = fetch_tags_dictionary()
    print(f"✅ Loaded {len(sports_tag_ids)} sports tag IDs, {len(tags_dict)} tags\n")
    
    # Get cursor
    last_marker = get_last_processed_trade_marker()
    if last_marker:
        print(f"📍 Cursor: timestamp={last_marker.last_processed_timestamp}, txHash={last_marker.last_processed_tx_hash[:20] if last_marker.last_processed_tx_hash else 'N/A'}...\n")
    
    # Fetch trades
    print("Fetching trades from API...")
    trades = fetch_recent_trades(
        last_marker=last_marker,
        min_notional=config.GLOBAL_MIN_NOTIONAL_USD
    )
    print(f"✅ Fetched {len(trades)} trades\n")
    
    if len(trades) == 0:
        print("⚠️  No trades fetched")
        return
    
    # Filter new trades (simulate worker logic)
    new_trades = []
    seen_cursor = False
    
    if last_marker and last_marker.last_processed_tx_hash:
        for trade in trades:
            if trade.transaction_hash == last_marker.last_processed_tx_hash:
                seen_cursor = True
                break
            
            if is_trade_processed(trade.transaction_hash):
                continue
            
            new_trades.append(trade)
    else:
        for trade in trades:
            if not is_trade_processed(trade.transaction_hash):
                new_trades.append(trade)
    
    print(f"📊 New trades to process: {len(new_trades)}\n")
    
    if len(new_trades) == 0:
        print("⚠️  No new trades to process")
        return
    
    # Process first 10 trades
    print("Processing first 10 trades...\n")
    processed_count = 0
    matched_count = 0
    
    for i, trade in enumerate(new_trades[:10], 1):
        print(f"Trade {i}: ${trade.notional:,.2f} | {trade.side} | {trade.price:.2%}")
        
        # Check basic criteria first
        basic_match = (
            trade.notional >= uf.min_notional_usd and
            uf.min_price <= trade.price <= uf.max_price and
            trade.side in uf.sides
        )
        
        if not basic_match:
            print(f"  ❌ Does not match basic criteria (notional/price/side)")
            continue
        
        print(f"  ✅ Matches basic criteria")
        
        # Get market metadata
        if not trade.condition_id:
            print(f"  ⚠️  No conditionId - skipping")
            continue
        
        # Check cache
        market = get_or_upsert_market(trade.condition_id)
        
        if not market:
            # Fetch metadata
            print(f"  📦 Fetching market metadata...")
            batch_metadata = fetch_market_metadata_batch(
                [trade.condition_id],
                sports_tag_ids=sports_tag_ids,
                tags_dict=tags_dict
            )
            
            if trade.condition_id in batch_metadata:
                market = batch_metadata[trade.condition_id]
                # Cache it
                get_or_upsert_market(trade.condition_id, market)
                print(f"  ✅ Market: {market.title[:50]}")
            else:
                print(f"  ❌ Market metadata not found")
                continue
        else:
            print(f"  ✅ Market (cached): {market.title[:50]}")
        
        # Check full filter match
        matching_users = get_matching_users_for_trade(trade, market, all_user_filters)
        
        if matching_users:
            print(f"  🔔 MATCHES FILTER! Would send alert to {len(matching_users)} user(s)")
            matched_count += 1
            
            # Actually send alert (for testing)
            print(f"  📬 Sending alert...")
            send_alerts_for_trade(trade, market, matching_users)
            print(f"  ✅ Alert queued")
        else:
            print(f"  ⏭️  Does not match full filter (category/sports exclusion)")
        
        # Mark as processed
        mark_trade_as_processed(trade.transaction_hash)
        processed_count += 1
        print()
    
    print("=" * 70)
    print(f"\n📊 Summary:")
    print(f"  - Processed: {processed_count} trades")
    print(f"  - Matched filter: {matched_count} trades")
    print(f"\n💡 Check your Telegram for notifications!")

if __name__ == "__main__":
    main()

