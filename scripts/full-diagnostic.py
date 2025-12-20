#!/usr/bin/env python3
"""
Comprehensive diagnostic script to check the entire whale alerts pipeline.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whale_worker.config import load_config
from whale_worker.db import get_db, get_all_user_filters, get_last_processed_trade_marker
from whale_worker.polymarket_client import fetch_recent_trades, fetch_market_metadata_batch, fetch_sports_tag_ids, fetch_tags_dictionary
from whale_worker.filters import get_matching_users_for_trade
from whale_worker.notification_queue import get_notification_queue
from whale_worker.types import Trade, MarketMetadata, TradeMarker
import httpx

def main():
    print("🔍 Full Whale Alerts Diagnostic\n")
    print("=" * 70)
    
    # 1. Configuration
    print("\n1️⃣ CONFIGURATION CHECK")
    print("-" * 70)
    try:
        config = load_config()
        print(f"✅ Config loaded")
        print(f"   - MONGODB_URI: {'✅ Set' if config.MONGODB_URI else '❌ Not set'}")
        print(f"   - TELEGRAM_BOT_TOKEN: {'✅ Set' if config.TELEGRAM_BOT_TOKEN else '❌ Not set'}")
        print(f"   - GLOBAL_MIN_NOTIONAL_USD: ${config.GLOBAL_MIN_NOTIONAL_USD:,.2f}")
        print(f"   - POLL_INTERVAL_SECONDS: {config.POLL_INTERVAL_SECONDS}s")
        if not config.TELEGRAM_BOT_TOKEN:
            print("   ❌ CRITICAL: TELEGRAM_BOT_TOKEN not set - notifications won't work!")
            return
    except Exception as e:
        print(f"❌ Config error: {e}")
        return
    
    # 2. MongoDB Connection
    print("\n2️⃣ MONGODB CONNECTION")
    print("-" * 70)
    try:
        db = get_db()
        db.command('ping')
        print("✅ MongoDB connected")
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        return
    
    # 3. Telegram Account Check
    print("\n3️⃣ TELEGRAM ACCOUNT CHECK")
    print("-" * 70)
    try:
        telegram_collection = db['telegramAccounts']
        all_accounts = list(telegram_collection.find({}))
        print(f"Total Telegram accounts: {len(all_accounts)}")
        
        active_accounts = [a for a in all_accounts if a.get('isActive', False)]
        print(f"Active accounts: {len(active_accounts)}")
        
        for acc in all_accounts:
            user_id = str(acc.get('userId', ''))
            is_active = acc.get('isActive', False)
            chat_id = acc.get('chatId', '')
            username = acc.get('username', '')
            print(f"   - User {user_id[:8]}...: active={is_active}, chatId={chat_id[:15] if chat_id else 'N/A'}..., username={username}")
        
        if len(active_accounts) == 0:
            print("   ❌ CRITICAL: No active Telegram accounts!")
            return
    except Exception as e:
        print(f"❌ Error checking Telegram accounts: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 4. User Filter Check
    print("\n4️⃣ USER FILTER CHECK")
    print("-" * 70)
    try:
        user_filters = get_all_user_filters()
        print(f"Active user filters: {len(user_filters)}")
        
        if len(user_filters) == 0:
            print("   ❌ CRITICAL: No active user filters!")
            print("   Checking all configs...")
            configs_collection = db['whaleAlertConfigs']
            all_configs = list(configs_collection.find({}))
            for cfg in all_configs:
                user_id = str(cfg.get('userId', ''))
                enabled = cfg.get('enabled', False)
                min_notional = cfg.get('minNotionalUsd', 0)
                print(f"   - User {user_id[:8]}...: enabled={enabled}, minNotional=${min_notional:,.2f}")
            return
        
        for i, uf in enumerate(user_filters, 1):
            print(f"\n   Filter {i}:")
            print(f"   - User ID: {uf.user_id[:8]}...")
            print(f"   - Chat ID: {uf.telegram_chat_id[:15] if uf.telegram_chat_id else 'N/A'}...")
            print(f"   - Min Notional: ${uf.min_notional_usd:,.2f}")
            print(f"   - Price Range: {uf.min_price:.1%} - {uf.max_price:.1%}")
            print(f"   - Sides: {uf.sides}")
            print(f"   - Exclude Categories: {uf.exclude_categories}")
            print(f"   - Category Filter: {uf.category_filter}")
            print(f"   - Enabled: {uf.enabled}")
    except Exception as e:
        print(f"❌ Error checking filters: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 5. Trade Fetching Test
    print("\n5️⃣ TRADE FETCHING TEST")
    print("-" * 70)
    try:
        print("Fetching recent trades from Polymarket API...")
        trades = fetch_recent_trades(
            last_marker=None,
            min_notional=0
        )
        print(f"✅ Fetched {len(trades)} trades")
        
        if len(trades) == 0:
            print("   ❌ CRITICAL: No trades fetched from API!")
            return
        
        # Check for matching trades
        matching_trades = []
        for trade in trades[:50]:  # Check first 50
            if (trade.notional >= user_filters[0].min_notional_usd and
                user_filters[0].min_price <= trade.price <= user_filters[0].max_price and
                trade.side in user_filters[0].sides):
                matching_trades.append(trade)
        
        print(f"\n   Trades matching basic criteria (notional + price + side): {len(matching_trades)}")
        if matching_trades:
            print(f"   Sample matching trades:")
            for i, t in enumerate(matching_trades[:3], 1):
                print(f"      {i}. ${t.notional:,.2f} | {t.side} | {t.price:.2%} | conditionId: {t.condition_id[:20] if t.condition_id else 'N/A'}...")
        else:
            print(f"   ⚠️  No trades match basic criteria")
    except Exception as e:
        print(f"❌ Error fetching trades: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 6. Market Metadata Test
    print("\n6️⃣ MARKET METADATA TEST")
    print("-" * 70)
    try:
        # Load categorization data
        sports_tag_ids = fetch_sports_tag_ids()
        tags_dict = fetch_tags_dictionary()
        print(f"✅ Loaded {len(sports_tag_ids)} sports tag IDs, {len(tags_dict)} tags")
        
        # Test fetching metadata for a matching trade
        if matching_trades and matching_trades[0].condition_id:
            test_trade = matching_trades[0]
            print(f"\n   Testing market metadata fetch for conditionId: {test_trade.condition_id[:20]}...")
            
            batch_metadata = fetch_market_metadata_batch(
                [test_trade.condition_id],
                sports_tag_ids=sports_tag_ids,
                tags_dict=tags_dict
            )
            
            if test_trade.condition_id in batch_metadata:
                market = batch_metadata[test_trade.condition_id]
                print(f"   ✅ Market metadata fetched:")
                print(f"      - Title: {market.title[:50]}")
                print(f"      - Is Sports: {market.is_sports}")
                print(f"      - Tags: {market.tags[:3] if market.tags else 'None'}")
                print(f"      - Tag IDs: {market.tag_ids[:3] if market.tag_ids else 'None'}")
            else:
                print(f"   ⚠️  Market metadata not found for conditionId")
    except Exception as e:
        print(f"❌ Error testing market metadata: {e}")
        import traceback
        traceback.print_exc()
    
    # 7. Filter Matching Test
    print("\n7️⃣ FILTER MATCHING TEST")
    print("-" * 70)
    try:
        if matching_trades and matching_trades[0].condition_id:
            test_trade = matching_trades[0]
            
            # Get market metadata
            batch_metadata = fetch_market_metadata_batch(
                [test_trade.condition_id],
                sports_tag_ids=sports_tag_ids,
                tags_dict=tags_dict
            )
            
            if test_trade.condition_id in batch_metadata:
                market = batch_metadata[test_trade.condition_id]
                
                # Test matching
                matching_users = get_matching_users_for_trade(test_trade, market, user_filters)
                print(f"   Trade: ${test_trade.notional:,.2f} | {test_trade.side} | {test_trade.price:.2%}")
                print(f"   Market: {market.title[:50]}")
                print(f"   Matching users: {len(matching_users)}")
                
                if len(matching_users) > 0:
                    print(f"   ✅ Trade matches filter - should trigger alert!")
                else:
                    print(f"   ❌ Trade does NOT match filter")
                    print(f"   Debugging filter checks:")
                    uf = user_filters[0]
                    print(f"      - Notional check: ${test_trade.notional:,.2f} >= ${uf.min_notional_usd:,.2f}? {test_trade.notional >= uf.min_notional_usd}")
                    print(f"      - Price check: {uf.min_price:.2%} <= {test_trade.price:.2%} <= {uf.max_price:.2%}? {uf.min_price <= test_trade.price <= uf.max_price}")
                    print(f"      - Side check: {test_trade.side} in {uf.sides}? {test_trade.side in uf.sides}")
                    print(f"      - Exclude sports: {market.is_sports} and 'sports' in {uf.exclude_categories}? {market.is_sports and 'sports' in [c.lower() for c in uf.exclude_categories]}")
                    print(f"      - Category filter: {uf.category_filter}")
            else:
                print(f"   ⚠️  Cannot test - market metadata not available")
    except Exception as e:
        print(f"❌ Error testing filter matching: {e}")
        import traceback
        traceback.print_exc()
    
    # 8. Notification Queue Test
    print("\n8️⃣ NOTIFICATION QUEUE TEST")
    print("-" * 70)
    try:
        queue = get_notification_queue()
        print(f"✅ Notification queue initialized")
        print(f"   - Queue size: {queue.queue.qsize()}")
        print(f"   - Worker running: {queue.running}")
        
        if not queue.running:
            print("   ❌ CRITICAL: Notification queue worker is not running!")
            print("   Starting queue...")
            queue.start()
            print("   ✅ Queue started")
    except Exception as e:
        print(f"❌ Error checking notification queue: {e}")
        import traceback
        traceback.print_exc()
    
    # 9. Telegram Bot API Test
    print("\n9️⃣ TELEGRAM BOT API TEST")
    print("-" * 70)
    try:
        if not config.TELEGRAM_BOT_TOKEN:
            print("   ⚠️  TELEGRAM_BOT_TOKEN not set - skipping API test")
        else:
            # Test sending a message to the first active chat
            if active_accounts and active_accounts[0].get('chatId'):
                test_chat_id = str(active_accounts[0]['chatId'])
                print(f"   Testing send to chatId: {test_chat_id[:15]}...")
                
                url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
                payload = {
                    "chat_id": test_chat_id,
                    "text": "🧪 Test message from Whale Alerts diagnostic script",
                    "parse_mode": "HTML",
                }
                
                try:
                    with httpx.Client(timeout=10.0) as client:
                        response = client.post(url, json=payload)
                        response.raise_for_status()
                        result = response.json()
                        
                        if result.get("ok"):
                            print(f"   ✅ Test message sent successfully!")
                            print(f"   💡 Check your Telegram - you should have received a test message")
                        else:
                            print(f"   ❌ Failed to send: {result.get('description', 'Unknown error')}")
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 403:
                        print(f"   ❌ User blocked bot (403)")
                    elif e.response.status_code == 400:
                        print(f"   ❌ Invalid chat_id (400)")
                    else:
                        print(f"   ❌ HTTP {e.response.status_code}")
                except Exception as e:
                    print(f"   ❌ Error: {e}")
            else:
                print("   ⚠️  No active chat ID found for testing")
    except Exception as e:
        print(f"❌ Error testing Telegram API: {e}")
        import traceback
        traceback.print_exc()
    
    # 10. Worker Process Check
    print("\n🔟 WORKER PROCESS CHECK")
    print("-" * 70)
    import subprocess
    try:
        result = subprocess.run(['pgrep', '-f', 'whale_worker.main'], capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            print(f"✅ Worker process(es) running: {', '.join(pids)}")
        else:
            print("❌ CRITICAL: Worker process is NOT running!")
            print("   Start it with: python3 -m whale_worker.main")
            print("   Or: npm run dev:worker")
    except Exception as e:
        print(f"⚠️  Could not check worker process: {e}")
    
    # 11. Cursor Check
    print("\n1️⃣1️⃣ CURSOR CHECK")
    print("-" * 70)
    try:
        last_marker = get_last_processed_trade_marker()
        if last_marker:
            print(f"✅ Last processed trade:")
            print(f"   - Timestamp: {last_marker.last_processed_timestamp}")
            print(f"   - Tx Hash: {last_marker.last_processed_tx_hash[:20] if last_marker.last_processed_tx_hash else 'N/A'}...")
            print(f"   - Updated: {last_marker.updated_at}")
        else:
            print("⚠️  No cursor found - worker will process all trades from now on")
    except Exception as e:
        print(f"❌ Error checking cursor: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("\n📊 DIAGNOSTIC SUMMARY")
    print("=" * 70)
    
    issues = []
    if not config.TELEGRAM_BOT_TOKEN:
        issues.append("❌ TELEGRAM_BOT_TOKEN not set")
    if len(active_accounts) == 0:
        issues.append("❌ No active Telegram accounts")
    if len(user_filters) == 0:
        issues.append("❌ No active user filters")
    if len(matching_trades) == 0:
        issues.append("⚠️  No trades match filter criteria (might be normal)")
    
    result = subprocess.run(['pgrep', '-f', 'whale_worker.main'], capture_output=True, text=True)
    if result.returncode != 0:
        issues.append("❌ Worker process is NOT running")
    
    if issues:
        print("\n⚠️  Issues found:")
        for issue in issues:
            print(f"   {issue}")
    else:
        print("\n✅ All checks passed!")
        print("\n💡 If you're still not receiving notifications:")
        print("   1. Wait for a trade that matches your filter")
        print("   2. Check worker logs for 'Matches X user(s)' messages")
        print("   3. Check worker logs for 'Queued X alert(s)' messages")
        print("   4. Verify Telegram bot is working (use 'Test Notification' button)")
    
    print("\n")

if __name__ == "__main__":
    main()

