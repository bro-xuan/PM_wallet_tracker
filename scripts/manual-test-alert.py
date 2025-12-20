#!/usr/bin/env python3
"""
Manually test sending an alert for a specific trade.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whale_worker.db import get_db, get_all_user_filters
from whale_worker.polymarket_client import fetch_recent_trades, fetch_market_metadata_batch, fetch_sports_tag_ids, fetch_tags_dictionary
from whale_worker.filters import get_matching_users_for_trade
from whale_worker.notifications import send_alerts_for_trade

def main():
    print("🧪 Manual Alert Test\n")
    
    # Get filter
    filters = get_all_user_filters()
    if not filters:
        print("❌ No filters found")
        return
    
    uf = filters[0]
    print(f"Filter: >= ${uf.min_notional_usd:,.2f}, {uf.min_price:.1%}-{uf.max_price:.1%}, {uf.sides}")
    print()
    
    # Load categorization
    sports_tag_ids = fetch_sports_tag_ids()
    tags_dict = fetch_tags_dictionary()
    
    # Fetch trades
    trades = fetch_recent_trades(last_marker=None, min_notional=0)
    
    # Find a matching trade
    matching = None
    for trade in trades:
        if (trade.notional >= uf.min_notional_usd and
            uf.min_price <= trade.price <= uf.max_price and
            trade.side in uf.sides and
            trade.condition_id):
            matching = trade
            break
    
    if not matching:
        print("❌ No matching trade found")
        return
    
    print(f"Found matching trade:")
    print(f"  - Notional: ${matching.notional:,.2f}")
    print(f"  - Side: {matching.side}")
    print(f"  - Price: {matching.price:.2%}")
    print(f"  - Condition ID: {matching.condition_id}")
    print()
    
    # Get market metadata
    print("Fetching market metadata...")
    batch_metadata = fetch_market_metadata_batch(
        [matching.condition_id],
        sports_tag_ids=sports_tag_ids,
        tags_dict=tags_dict
    )
    
    if matching.condition_id not in batch_metadata:
        print("❌ Market metadata not found")
        return
    
    market = batch_metadata[matching.condition_id]
    print(f"✅ Market: {market.title[:60]}")
    print()
    
    # Check filter match
    matching_users = get_matching_users_for_trade(matching, market, filters)
    
    if not matching_users:
        print("❌ Trade does not match filter (category/sports exclusion)")
        return
    
    print(f"✅ Trade matches filter for {len(matching_users)} user(s)")
    print()
    print("Sending alert...")
    send_alerts_for_trade(matching, market, matching_users)
    print("✅ Alert queued!")
    print()
    print("💡 Check your Telegram in a few seconds")

if __name__ == "__main__":
    main()

