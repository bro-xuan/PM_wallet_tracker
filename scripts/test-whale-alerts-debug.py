#!/usr/bin/env python3
"""
Debug script to test whale alerts configuration and identify issues.

This script checks:
1. MongoDB connection
2. User filter configuration
3. Telegram account connection
4. Worker status
5. Recent trades from API
6. Filter matching logic
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whale_worker.config import load_config
from whale_worker.db import get_db, get_all_user_filters
from whale_worker.polymarket_client import fetch_recent_trades
from whale_worker.types import TradeMarker
from pymongo import MongoClient

def main():
    print("🔍 Whale Alerts Debug Script\n")
    print("=" * 60)
    
    # 1. Check configuration
    print("\n1️⃣ Checking configuration...")
    try:
        config = load_config()
        print(f"   ✅ Config loaded")
        print(f"   - MONGODB_URI: {'✅ Set' if config.MONGODB_URI else '❌ Not set'}")
        print(f"   - TELEGRAM_BOT_TOKEN: {'✅ Set' if config.TELEGRAM_BOT_TOKEN else '❌ Not set'}")
        print(f"   - GLOBAL_MIN_NOTIONAL_USD: ${config.GLOBAL_MIN_NOTIONAL_USD:,.2f}")
        print(f"   - POLL_INTERVAL_SECONDS: {config.POLL_INTERVAL_SECONDS}s")
    except Exception as e:
        print(f"   ❌ Failed to load config: {e}")
        return
    
    # 2. Check MongoDB connection
    print("\n2️⃣ Checking MongoDB connection...")
    try:
        db = get_db()
        db.command('ping')
        print("   ✅ MongoDB connected")
    except Exception as e:
        print(f"   ❌ MongoDB connection failed: {e}")
        return
    
    # 3. Check user filters
    print("\n3️⃣ Checking user filters...")
    try:
        user_filters = get_all_user_filters()
        print(f"   Found {len(user_filters)} active user filter(s)")
        
        if len(user_filters) == 0:
            print("\n   ⚠️  NO ACTIVE FILTERS FOUND!")
            print("   This could mean:")
            print("   - No users have enabled alerts (enabled=false)")
            print("   - No users have connected Telegram")
            print("   - Telegram accounts are marked as inactive")
            
            # Check all configs (even disabled)
            configs_collection = db.collection('whaleAlertConfigs')
            all_configs = list(configs_collection.find({}))
            print(f"\n   Total configs in DB: {len(all_configs)}")
            for cfg in all_configs:
                user_id = str(cfg.get('userId', ''))
                enabled = cfg.get('enabled', False)
                min_notional = cfg.get('minNotionalUsd', 0)
                print(f"   - User {user_id[:8]}...: enabled={enabled}, minNotional=${min_notional:,.2f}")
            
            # Check Telegram accounts
            telegram_collection = db.collection('telegramAccounts')
            all_accounts = list(telegram_collection.find({}))
            print(f"\n   Total Telegram accounts: {len(all_accounts)}")
            for acc in all_accounts:
                user_id = str(acc.get('userId', ''))
                is_active = acc.get('isActive', False)
                chat_id = acc.get('chatId', '')
                username = acc.get('username', '')
                print(f"   - User {user_id[:8]}...: active={is_active}, chatId={chat_id[:10] if chat_id else 'N/A'}..., username={username}")
        else:
            for i, uf in enumerate(user_filters, 1):
                print(f"\n   Filter {i}:")
                print(f"   - User ID: {uf.user_id[:8]}...")
                print(f"   - Chat ID: {uf.telegram_chat_id[:10] if uf.telegram_chat_id else 'N/A'}...")
                print(f"   - Min Notional: ${uf.min_notional_usd:,.2f}")
                print(f"   - Price Range: {uf.min_price:.1%} - {uf.max_price:.1%}")
                print(f"   - Sides: {uf.sides}")
                print(f"   - Exclude Categories: {uf.exclude_categories}")
                print(f"   - Category Filter (Tag IDs): {uf.category_filter}")
                print(f"   - Enabled: {uf.enabled}")
    except Exception as e:
        print(f"   ❌ Error checking filters: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 4. Check if worker is fetching trades
    print("\n4️⃣ Testing trade fetching...")
    try:
        # Fetch recent trades (without cursor to get latest)
        trades = fetch_recent_trades(
            last_marker=None,
            min_notional=0  # Get all trades for testing
        )
        print(f"   ✅ Fetched {len(trades)} trades from API")
        
        if len(trades) > 0:
            print(f"\n   Sample trades:")
            for i, trade in enumerate(trades[:5], 1):
                print(f"   {i}. ${trade.notional:,.2f} | {trade.side} | {trade.price:.2%} | conditionId: {trade.condition_id[:20] if trade.condition_id else 'N/A'}...")
            
            # Check if any trades match filters
            if user_filters:
                print(f"\n   Checking if trades match filters...")
                matching_count = 0
                for trade in trades[:10]:  # Check first 10 trades
                    # Simple check: does notional match?
                    for uf in user_filters:
                        if trade.notional >= uf.min_notional_usd:
                            matching_count += 1
                            print(f"   ✅ Trade ${trade.notional:,.2f} matches minNotional (${uf.min_notional_usd:,.2f})")
                            break
                
                if matching_count == 0:
                    print(f"   ⚠️  No trades in sample match minNotional threshold")
                    print(f"   (This is normal if threshold is high)")
        else:
            print("   ⚠️  No trades fetched from API")
    except Exception as e:
        print(f"   ❌ Error fetching trades: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. Check notification queue
    print("\n5️⃣ Checking notification queue...")
    try:
        from whale_worker.notification_queue import get_notification_queue
        queue = get_notification_queue()
        print(f"   ✅ Notification queue initialized")
        print(f"   - Queue size: {queue.queue.qsize()}")
        print(f"   - Worker running: {queue.running}")
    except Exception as e:
        print(f"   ❌ Error checking queue: {e}")
        import traceback
        traceback.print_exc()
    
    # 6. Summary and recommendations
    print("\n" + "=" * 60)
    print("\n📊 Summary:")
    
    if len(user_filters) == 0:
        print("\n❌ ISSUE FOUND: No active user filters!")
        print("\n   To fix:")
        print("   1. Ensure 'Enable Alerts' checkbox is checked in the UI")
        print("   2. Ensure Telegram is connected (shows username in UI)")
        print("   3. Click 'Save Settings' button")
        print("   4. Wait up to 60 seconds for worker to reload filters")
    else:
        print(f"\n✅ Found {len(user_filters)} active filter(s)")
        print("\n   Next steps to debug:")
        print("   1. Check if Python worker is running: python -m whale_worker.main")
        print("   2. Check worker logs for:")
        print("      - 'Loading user filters...' (should show filter count)")
        print("      - 'Fetched X trades from API'")
        print("      - 'Matches X user(s)' (when trades match)")
        print("      - 'Queued X alert(s)' (when alerts are sent)")
        print("   3. Check if trades match your filters:")
        print("      - Min Notional: Your threshold might be too high")
        print("      - Price Range: Trades might be outside your range")
        print("      - Categories: Trades might be excluded")
    
    print("\n")

if __name__ == "__main__":
    main()

