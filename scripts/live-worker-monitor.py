#!/usr/bin/env python3
"""
Monitor the worker's live activity by checking recent database activity.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whale_worker.db import get_db, get_all_user_filters, get_last_processed_trade_marker
from whale_worker.polymarket_client import fetch_recent_trades, fetch_market_metadata_batch, fetch_sports_tag_ids, fetch_tags_dictionary
from whale_worker.filters import get_matching_users_for_trade
from datetime import datetime, timedelta
import time

def main():
    print("🔍 Live Worker Activity Monitor\n")
    print("=" * 70)
    
    db = get_db()
    
    # Get filters
    filters = get_all_user_filters()
    if not filters:
        print("❌ No active filters found!")
        return
    
    uf = filters[0]
    print(f"Filter: >= ${uf.min_notional_usd:,.2f}, {uf.min_price:.1%}-{uf.max_price:.1%}, {uf.sides}\n")
    
    # Load categorization
    sports_tag_ids = fetch_sports_tag_ids()
    tags_dict = fetch_tags_dictionary()
    
    # Get cursor
    marker = get_last_processed_trade_marker()
    
    print("Monitoring for 30 seconds...\n")
    start_time = time.time()
    last_cursor_ts = marker.last_processed_timestamp if marker else 0
    
    while time.time() - start_time < 30:
        # Check cursor updates
        current_marker = get_last_processed_trade_marker()
        if current_marker and current_marker.last_processed_timestamp != last_cursor_ts:
            print(f"✅ Cursor updated! New timestamp: {current_marker.last_processed_timestamp}")
            last_cursor_ts = current_marker.last_processed_timestamp
            
            # Fetch and check the trade that was just processed
            trades = fetch_recent_trades(last_marker=None, min_notional=0)
            matching_trade = None
            for trade in trades:
                if trade.transaction_hash == current_marker.last_processed_tx_hash:
                    matching_trade = trade
                    break
            
            if matching_trade:
                print(f"   Trade: ${matching_trade.notional:,.2f} | {matching_trade.side} | {matching_trade.price:.2%}")
                
                # Check if it should have matched
                if (matching_trade.notional >= uf.min_notional_usd and
                    uf.min_price <= matching_trade.price <= uf.max_price and
                    matching_trade.side in uf.sides and
                    matching_trade.condition_id):
                    
                    # Get market
                    batch_metadata = fetch_market_metadata_batch(
                        [matching_trade.condition_id],
                        sports_tag_ids=sports_tag_ids,
                        tags_dict=tags_dict
                    )
                    
                    if matching_trade.condition_id in batch_metadata:
                        market = batch_metadata[matching_trade.condition_id]
                        matching_users = get_matching_users_for_trade(matching_trade, market, filters)
                        
                        if matching_users:
                            print(f"   🔔 Should have triggered alert! Matches filter.")
                        else:
                            print(f"   ⏭️  Did not match filter (category/sports exclusion)")
                    else:
                        print(f"   ⚠️  Market metadata not found")
                else:
                    print(f"   ⏭️  Did not match basic criteria")
        
        # Check processed trades collection
        processed_collection = db['processedTrades']
        recent = list(processed_collection.find({
            'createdAt': { '$gte': datetime.utcnow() - timedelta(seconds=5) }
        }).limit(5))
        
        if recent:
            print(f"📊 Processed {len(recent)} trade(s) in last 5 seconds")
        
        time.sleep(2)
    
    print("\n" + "=" * 70)
    print("\n✅ Monitoring complete")
    print(f"Final cursor timestamp: {last_cursor_ts}")

if __name__ == "__main__":
    main()

