#!/usr/bin/env python3
"""
Monitor worker activity in real-time by checking database updates.
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
    print("🔍 Live Worker Monitor\n")
    print("=" * 70)
    
    db = get_db()
    filters = get_all_user_filters()
    if not filters:
        print("❌ No filters found!")
        return
    
    uf = filters[0]
    print(f"Filter: >= ${uf.min_notional_usd:,.2f}, {uf.min_price:.1%}-{uf.max_price:.1%}\n")
    
    # Load categorization
    sports_tag_ids = fetch_sports_tag_ids()
    tags_dict = fetch_tags_dictionary()
    
    # Get initial cursor
    last_cursor_ts = get_last_processed_trade_marker().last_processed_timestamp if get_last_processed_trade_marker() else 0
    last_processed_count = 0
    
    print("Monitoring for 60 seconds...\n")
    start_time = time.time()
    
    while time.time() - start_time < 60:
        # Check cursor updates
        current_marker = get_last_processed_trade_marker()
        if current_marker and current_marker.last_processed_timestamp != last_cursor_ts:
            print(f"✅ Cursor updated! New timestamp: {current_marker.last_processed_timestamp}")
            last_cursor_ts = current_marker.last_processed_timestamp
            
            # Check the trade that was just processed
            trades = fetch_recent_trades(last_marker=None, min_notional=0)
            processed_trade = None
            for trade in trades:
                if trade.transaction_hash == current_marker.last_processed_tx_hash:
                    processed_trade = trade
                    break
            
            if processed_trade:
                print(f"   Trade: ${processed_trade.notional:,.2f} | {processed_trade.side} | {processed_trade.price:.2%}")
                
                # Check if it matches
                if (processed_trade.notional >= uf.min_notional_usd and
                    uf.min_price <= processed_trade.price <= uf.max_price and
                    processed_trade.side in uf.sides and
                    processed_trade.condition_id):
                    
                    # Get market
                    from whale_worker.db import get_or_upsert_market
                    market = get_or_upsert_market(processed_trade.condition_id)
                    
                    if market:
                        matching_users = get_matching_users_for_trade(processed_trade, market, filters)
                        if matching_users:
                            print(f"   🔔 MATCHES FILTER! Should have sent alert!")
                        else:
                            print(f"   ⏭️  Does not match full filter")
                    else:
                        print(f"   ⚠️  Market not found (would be skipped)")
        
        # Check processed trades
        processed = list(db['processedTrades'].find({
            'createdAt': { '$gte': datetime.utcnow() - timedelta(seconds=5) }
        }))
        
        if len(processed) != last_processed_count:
            new_count = len(processed) - last_processed_count
            print(f"📊 Processed {new_count} new trade(s) in last 5 seconds")
            last_processed_count = len(processed)
        
        time.sleep(2)
    
    print("\n" + "=" * 70)
    print("\n✅ Monitoring complete")

if __name__ == "__main__":
    main()

