#!/usr/bin/env python3
"""
Comprehensive test of the notification sending process.

Tests:
1. Filter loading and matching
2. Trade fetching and processing
3. Market metadata fetching
4. Filter matching logic
5. Notification queue enqueuing
6. Telegram message sending
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whale_worker.db import (
    get_all_user_filters,
    get_last_processed_trade_marker,
    get_or_upsert_market,
)
from whale_worker.polymarket_client import (
    fetch_recent_trades,
    fetch_market_metadata_batch,
    fetch_sports_tag_ids,
    fetch_tags_dictionary,
)
from whale_worker.filters import get_matching_users_for_trade
from whale_worker.notifications import send_alerts_for_trade, build_trade_alert_message
from whale_worker.notification_queue import get_notification_queue
from whale_worker.types import Trade
import time

def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def test_filter_loading():
    """Test 1: Load user filters."""
    print_section("TEST 1: Loading User Filters")
    
    filters = get_all_user_filters()
    print(f"✅ Loaded {len(filters)} active user filter(s)\n")
    
    if not filters:
        print("❌ No active filters found!")
        print("   Make sure you have:")
        print("   1. Connected Telegram")
        print("   2. Enabled alerts in settings")
        print("   3. Saved filter configuration")
        return None
    
    for i, uf in enumerate(filters, 1):
        print(f"Filter {i}:")
        print(f"  User ID: {uf.user_id[:8]}...")
        print(f"  Chat ID: {uf.telegram_chat_id[:15] if uf.telegram_chat_id else 'N/A'}...")
        print(f"  Min Notional: ${uf.min_notional_usd:,.2f}")
        print(f"  Price Range: {uf.min_price:.1%} - {uf.max_price:.1%}")
        print(f"  Sides: {', '.join(uf.sides)}")
        print(f"  Enabled: {uf.enabled}")
        print()
    
    return filters

def test_trade_fetching(filters):
    """Test 2: Fetch recent trades."""
    print_section("TEST 2: Fetching Recent Trades")
    
    marker = get_last_processed_trade_marker()
    print(f"Cursor: timestamp={marker.last_processed_timestamp if marker else 'None'}\n")
    
    trades = fetch_recent_trades(last_marker=marker, min_notional=0)
    print(f"✅ Fetched {len(trades)} trades from Polymarket API\n")
    
    if not trades:
        print("⚠️  No trades found. This might be normal if there are no recent trades.")
        return None, None
    
    # Find trades that match basic criteria
    uf = filters[0]
    matching_trades = []
    
    print(f"Looking for trades matching:")
    print(f"  - Notional >= ${uf.min_notional_usd:,.2f}")
    print(f"  - Price: {uf.min_price:.1%} - {uf.max_price:.1%}")
    print(f"  - Side: {', '.join(uf.sides)}\n")
    
    for trade in trades[:100]:
        if (trade.notional >= uf.min_notional_usd and
            uf.min_price <= trade.price <= uf.max_price and
            trade.side in uf.sides and
            trade.condition_id):
            matching_trades.append(trade)
            if len(matching_trades) >= 3:
                break
    
    print(f"Found {len(matching_trades)} trades matching basic criteria\n")
    
    if matching_trades:
        for i, trade in enumerate(matching_trades, 1):
            print(f"Trade {i}:")
            print(f"  Hash: {trade.transaction_hash[:30]}...")
            print(f"  Notional: ${trade.notional:,.2f}")
            print(f"  Side: {trade.side}")
            print(f"  Price: {trade.price:.2%}")
            print(f"  Condition ID: {trade.condition_id[:30]}...")
            print()
    
    return matching_trades, trades

def test_market_fetching(matching_trades):
    """Test 3: Fetch market metadata."""
    print_section("TEST 3: Fetching Market Metadata")
    
    if not matching_trades:
        print("⚠️  No matching trades to fetch markets for")
        return None
    
    condition_ids = [t.condition_id for t in matching_trades]
    print(f"Fetching metadata for {len(condition_ids)} markets...\n")
    
    sports_tag_ids = fetch_sports_tag_ids()
    tags_dict = fetch_tags_dictionary()
    
    batch_metadata = fetch_market_metadata_batch(condition_ids, sports_tag_ids, tags_dict)
    print(f"✅ Fetched {len(batch_metadata)}/{len(condition_ids)} markets\n")
    
    # Store in cache
    for cid, metadata in batch_metadata.items():
        get_or_upsert_market(cid, metadata)
    
    for cid, market in batch_metadata.items():
        print(f"Market: {market.title[:60]}")
        print(f"  Slug: {market.slug}")
        print(f"  Is Sports: {market.is_sports}")
        print(f"  Category: {market.category or 'N/A'}")
        print(f"  Tags: {', '.join(market.tags[:3]) if market.tags else 'N/A'}")
        print()
    
    return batch_metadata

def test_filter_matching(matching_trades, batch_metadata, filters):
    """Test 4: Match trades against filters."""
    print_section("TEST 4: Matching Trades Against Filters")
    
    if not matching_trades or not batch_metadata:
        print("⚠️  No trades or markets to match")
        return []
    
    matching_results = []
    
    for trade in matching_trades:
        if trade.condition_id not in batch_metadata:
            print(f"⚠️  Trade {trade.transaction_hash[:20]}... - Market not found")
            continue
        
        market = batch_metadata[trade.condition_id]
        matching_users = get_matching_users_for_trade(trade, market, filters)
        
        print(f"Trade: ${trade.notional:,.2f} | {trade.side} | {trade.price:.2%}")
        print(f"  Market: {market.title[:50]}")
        
        if matching_users:
            print(f"  ✅ MATCHES {len(matching_users)} filter(s)!")
            matching_results.append((trade, market, matching_users))
        else:
            print(f"  ❌ Does not match full filter criteria")
        print()
    
    return matching_results

def test_notification_building(matching_results):
    """Test 5: Build notification messages."""
    print_section("TEST 5: Building Notification Messages")
    
    if not matching_results:
        print("⚠️  No matching trades to build notifications for")
        return
    
    for trade, market, matching_users in matching_results:
        message = build_trade_alert_message(trade, market, matching_users[0])
        print(f"Message for ${trade.notional:,.2f} trade:")
        print("-" * 70)
        print(message)
        print("-" * 70)
        print()

def test_notification_queue(matching_results):
    """Test 6: Enqueue notifications."""
    print_section("TEST 6: Enqueuing Notifications")
    
    if not matching_results:
        print("⚠️  No matching trades to enqueue")
        return
    
    queue = get_notification_queue()
    
    if not queue.running:
        print("⚠️  Notification queue is not running. Starting it...")
        queue.start()
        time.sleep(1)  # Give it a moment to start
    
    print(f"Queue status:")
    print(f"  Running: {queue.running}")
    print(f"  Queue size: {queue.queue.qsize()}")
    print(f"  Worker thread alive: {queue.worker_thread.is_alive() if queue.worker_thread else 'N/A'}\n")
    
    enqueued_count = 0
    for trade, market, matching_users in matching_results:
        print(f"Enqueuing alerts for ${trade.notional:,.2f} trade...")
        send_alerts_for_trade(trade, market, matching_users)
        enqueued_count += len(matching_users)
    
    print(f"\n✅ Enqueued {enqueued_count} notification(s)")
    print(f"   Queue size after enqueue: {queue.queue.qsize()}")
    print(f"\n💡 Messages will be sent asynchronously with rate limiting")
    print(f"   Check your Telegram in a few seconds")

def test_telegram_send_direct():
    """Test 7: Direct Telegram API test."""
    print_section("TEST 7: Direct Telegram API Test")
    
    filters = get_all_user_filters()
    if not filters or not filters[0].telegram_chat_id:
        print("❌ No active Telegram connection found")
        return
    
    chat_id = filters[0].telegram_chat_id
    print(f"Testing direct send to chat ID: {chat_id[:15]}...\n")
    
    from whale_worker.config import Config
    config = Config.get_config()
    
    if not config.TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not configured")
        return
    
    import httpx
    
    test_message = """🧪 <b>Test Notification</b>

This is a test message from the notification system.

If you received this, the Telegram Bot API connection is working correctly! ✅"""
    
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": test_message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            if result.get("ok"):
                print("✅ Test message sent successfully!")
                print("   Check your Telegram - you should have received a test message")
            else:
                print(f"❌ Telegram API error: {result.get('description', 'Unknown error')}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            print("❌ User blocked bot or chat_id invalid")
        elif e.response.status_code == 400:
            print(f"❌ Bad request: {e.response.text}")
        else:
            print(f"❌ HTTP error {e.response.status_code}: {e.response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("  COMPREHENSIVE NOTIFICATION PROCESS TEST")
    print("=" * 70)
    
    # Test 1: Load filters
    filters = test_filter_loading()
    if not filters:
        print("\n❌ Cannot continue without active filters")
        return
    
    # Test 2: Fetch trades
    matching_trades, all_trades = test_trade_fetching(filters)
    if not matching_trades:
        print("\n⚠️  No matching trades found. Testing with direct Telegram send instead...")
        test_telegram_send_direct()
        return
    
    # Test 3: Fetch markets
    batch_metadata = test_market_fetching(matching_trades)
    if not batch_metadata:
        print("\n❌ Could not fetch market metadata")
        return
    
    # Test 4: Match filters
    matching_results = test_filter_matching(matching_trades, batch_metadata, filters)
    if not matching_results:
        print("\n⚠️  No trades matched full filter criteria")
        print("   This could mean:")
        print("   - Markets are excluded (e.g., sports)")
        print("   - Category filters don't match")
        print("   - Other filter criteria not met")
        return
    
    # Test 5: Build messages
    test_notification_building(matching_results)
    
    # Test 6: Enqueue notifications
    test_notification_queue(matching_results)
    
    # Test 7: Direct Telegram test
    test_telegram_send_direct()
    
    print_section("TEST SUMMARY")
    print("✅ All tests completed!")
    print("\nIf notifications were enqueued, check your Telegram in a few seconds.")
    print("The notification queue processes messages asynchronously with rate limiting.")

if __name__ == "__main__":
    main()

