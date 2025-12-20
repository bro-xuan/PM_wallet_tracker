#!/usr/bin/env python3
"""Check if there are any large trades matching the filter criteria."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whale_worker.polymarket_client import fetch_recent_trades
from whale_worker.types import TradeMarker

trades = fetch_recent_trades(last_marker=None, min_notional=0)
print(f'Total trades fetched: {len(trades)}')

if trades:
    # Check for trades >= $10,000
    large_trades = [t for t in trades if t.notional >= 10000]
    print(f'\nTrades >= $10,000: {len(large_trades)}')
    
    if large_trades:
        print(f'\nSample large trades:')
        for i, t in enumerate(large_trades[:10], 1):
            print(f'  {i}. ${t.notional:,.2f} | {t.side} | {t.price:.2%} | conditionId: {t.condition_id[:20] if t.condition_id else "N/A"}...')
    else:
        max_notional = max(t.notional for t in trades)
        print(f'\n⚠️  No trades >= $10,000 found')
        print(f'   Highest notional in sample: ${max_notional:,.2f}')
        print(f'\n💡 Your filter requires $10,000 minimum, but largest trade is only ${max_notional:,.2f}')
        print(f'   Consider lowering minNotional to ${max_notional:,.2f} or lower for testing')
    
    # Check price distribution
    in_range = [t for t in trades if 0.05 <= t.price <= 0.95]
    print(f'\nTrades in price range 5%-95%: {len(in_range)}/{len(trades)}')
    
    # Check combined criteria
    matching = [t for t in trades if t.notional >= 10000 and 0.05 <= t.price <= 0.95]
    print(f'Trades matching BOTH criteria (>= $10k AND 5%-95%): {len(matching)}')
    
    if matching:
        print(f'\n✅ Found {len(matching)} trades that should trigger alerts!')
        print(f'   If worker is running, you should receive notifications for these')
    else:
        print(f'\n⚠️  No trades match your filter criteria')
        print(f'   This is why you\'re not receiving notifications')

