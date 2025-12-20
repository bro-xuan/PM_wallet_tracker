#!/usr/bin/env python3
"""
Quick test to check if worker can process trades and match filters.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whale_worker.config import load_config
from whale_worker.db import get_db, get_all_user_filters
from whale_worker.polymarket_client import fetch_recent_trades
from whale_worker.filters import get_matching_users_for_trade
from whale_worker.types import Trade, MarketMetadata

def main():
    print("🔍 Testing Worker Status\n")
    
    # Load config
    config = load_config()
    print(f"✅ Config loaded")
    print(f"   GLOBAL_MIN_NOTIONAL_USD: ${config.GLOBAL_MIN_NOTIONAL_USD:,.2f}\n")
    
    # Get user filters
    user_filters = get_all_user_filters()
    print(f"✅ Found {len(user_filters)} active filter(s)\n")
    
    if len(user_filters) == 0:
        print("❌ No active filters - alerts won't be sent!")
        return
    
    # Show filter details
    for uf in user_filters:
        print(f"Filter:")
        print(f"  - Min Notional: ${uf.min_notional_usd:,.2f}")
        print(f"  - Price Range: {uf.min_price:.1%} - {uf.max_price:.1%}")
        print(f"  - Sides: {uf.sides}")
        print(f"  - Enabled: {uf.enabled}")
        print()
    
    # Fetch recent trades
    print("Fetching recent trades...")
    trades = fetch_recent_trades(
        last_marker=None,
        min_notional=0  # Get all trades for testing
    )
    print(f"✅ Fetched {len(trades)} trades\n")
    
    if len(trades) == 0:
        print("❌ No trades fetched - API might be down or rate limited")
        return
    
    # Check how many trades match the filter
    matching_count = 0
    sample_matches = []
    
    print("Checking trades against filters...")
    for trade in trades[:100]:  # Check first 100 trades
        # Create a dummy market metadata (for testing)
        # In real worker, this would come from Gamma API
        market = MarketMetadata(
            condition_id=trade.condition_id or "unknown",
            title="Test Market",
            is_sports=False,
            tag_ids=[],
            tags=[],
        )
        
        matching_users = get_matching_users_for_trade(trade, market, user_filters)
        if matching_users:
            matching_count += 1
            if len(sample_matches) < 5:
                sample_matches.append({
                    'notional': trade.notional,
                    'price': trade.price,
                    'side': trade.side,
                })
    
    print(f"\n📊 Results:")
    print(f"  - Total trades checked: 100")
    print(f"  - Trades matching filter: {matching_count}")
    
    if matching_count > 0:
        print(f"\n✅ Found {matching_count} matching trade(s)!")
        print(f"\nSample matches:")
        for i, match in enumerate(sample_matches, 1):
            print(f"  {i}. ${match['notional']:,.2f} | {match['side']} | {match['price']:.2%}")
        print(f"\n💡 If worker is running, you should receive alerts for these trades")
    else:
        print(f"\n⚠️  No trades match your filter criteria")
        print(f"\nPossible reasons:")
        print(f"  1. Min Notional (${user_filters[0].min_notional_usd:,.2f}) is too high")
        print(f"  2. Price range ({user_filters[0].min_price:.1%} - {user_filters[0].max_price:.1%}) excludes most trades")
        print(f"  3. Trade sides don't match")
        print(f"\n💡 Try lowering minNotional or adjusting price range")
    
    print(f"\n🔧 To start the worker:")
    print(f"   python3 -m whale_worker.main")
    print(f"   # or")
    print(f"   npm run dev:worker")

if __name__ == "__main__":
    main()

