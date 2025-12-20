#!/usr/bin/env python3
"""
Test the complete flow: fetch trade -> get market -> match filter -> send alert
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whale_worker.config import load_config
from whale_worker.db import get_db, get_all_user_filters
from whale_worker.polymarket_client import fetch_recent_trades, fetch_market_metadata_batch, fetch_sports_tag_ids, fetch_tags_dictionary
from whale_worker.filters import get_matching_users_for_trade
from whale_worker.notifications import send_alerts_for_trade
from whale_worker.types import Trade
import time

def main():
    print("🧪 Complete Flow Test\n")
    print("=" * 70)
    
    config = load_config()
    db = get_db()
    
    # Get filters
    filters = get_all_user_filters()
    if not filters:
        print("❌ No filters found")
        return
    
    uf = filters[0]
    print(f"Filter: >= ${uf.min_notional_usd:,.2f}, {uf.min_price:.1%}-{uf.max_price:.1%}, {uf.sides}")
    print()
    
    # Load categorization
    print("Loading categorization data...")
    sports_tag_ids = fetch_sports_tag_ids()
    tags_dict = fetch_tags_dictionary()
    print(f"✅ Loaded {len(sports_tag_ids)} sports tag IDs, {len(tags_dict)} tags\n")
    
    # Fetch recent trades (no cursor, to see all)
    print("Fetching recent trades...")
    trades = fetch_recent_trades(last_marker=None, min_notional=0)
    print(f"✅ Fetched {len(trades)} trades\n")
    
    # Find trades that match basic criteria
    matching_trades = []
    for trade in trades:
        if (trade.notional >= uf.min_notional_usd and
            uf.min_price <= trade.price <= uf.max_price and
            trade.side in uf.sides and
            trade.condition_id):
            matching_trades.append(trade)
            if len(matching_trades) >= 5:  # Test with first 5
                break
    
    if not matching_trades:
        print("⚠️  No trades match basic criteria")
        print("\n💡 This could mean:")
        print("   1. No large trades are happening right now")
        print("   2. All large trades are outside the price range")
        print("   3. The API is not returning large trades")
        return
    
    print(f"Found {len(matching_trades)} trades matching basic criteria\n")
    
    # Process each trade
    for i, trade in enumerate(matching_trades, 1):
        print(f"Trade {i}: ${trade.notional:,.2f} | {trade.side} | {trade.price:.2%}")
        print(f"  Condition ID: {trade.condition_id[:30]}...")
        
        # Get market metadata
        print("  Fetching market metadata...")
        batch_metadata = fetch_market_metadata_batch(
            [trade.condition_id],
            sports_tag_ids=sports_tag_ids,
            tags_dict=tags_dict
        )
        
        if trade.condition_id not in batch_metadata:
            print("  ❌ Market metadata not found - skipping")
            print()
            continue
        
        market = batch_metadata[trade.condition_id]
        print(f"  ✅ Market: {market.title[:50]}")
        print(f"     Is Sports: {market.is_sports}")
        print(f"     Tags: {market.tags[:3] if market.tags else 'None'}")
        
        # Check filter match
        print("  Checking filter match...")
        matching_users = get_matching_users_for_trade(trade, market, filters)
        
        if not matching_users:
            print("  ❌ Does not match filter (category/sports exclusion)")
            print()
            continue
        
        print(f"  ✅ MATCHES FILTER! Sending alert to {len(matching_users)} user(s)...")
        
        # Send alert
        send_alerts_for_trade(trade, market, matching_users)
        print("  ✅ Alert queued!")
        print()
        
        # Small delay
        time.sleep(0.5)
    
    print("=" * 70)
    print("\n✅ Test complete!")
    print("💡 Check your Telegram in a few seconds for notifications")

if __name__ == "__main__":
    main()

