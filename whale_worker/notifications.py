"""
Telegram notification sending for whale trade alerts.
"""
import time
from typing import List
import httpx
from whale_worker.types import Trade, MarketMetadata, UserFilter
from whale_worker.config import Config


def build_trade_alert_message(
    trade: Trade,
    market: MarketMetadata,
    user_filter: UserFilter
) -> str:
    """
    Build a formatted Telegram message for a whale trade alert.
    
    Args:
        trade: Trade that triggered the alert.
        market: Market metadata.
        user_filter: User's filter (for context, though all users get same message).
    
    Returns:
        Formatted message string using HTML formatting for Telegram.
    """
    # Format wallet address (truncate for display)
    wallet_display = f"{trade.proxy_wallet[:6]}...{trade.proxy_wallet[-4:]}" if len(trade.proxy_wallet) > 10 else trade.proxy_wallet
    
    # Build market link
    market_link = "https://polymarket.com"
    if market.slug:
        market_link = f"https://polymarket.com/event/{market.slug}"
    elif market.condition_id:
        market_link = f"https://polymarket.com/condition/{market.condition_id}"
    
    # Build wallet profile link
    wallet_link = f"https://polymarket.com/profile/{trade.proxy_wallet}"
    
    # Format side with emoji
    side_emoji = "🟢" if trade.side == "BUY" else "🔴"
    
    # Build category/tags info
    category_info = ""
    if market.is_sports:
        category_info = "🏈 Sports"
    elif market.category:
        category_info = market.category.capitalize()
    
    tags_info = ""
    if market.tags:
        tags_info = f"\n🏷️ Tags: {', '.join(market.tags[:3])}"
    
    # Build message
    message = f"""🐋 <b>Whale Trade Alert!</b>

📊 <b>Market:</b> {market.title}
{category_info}{tags_info}

💰 <b>Trade Details:</b>
{side_emoji} <b>{trade.side}</b> ${trade.notional:,.2f} @ {trade.price:.1%}
Size: {trade.size:,.2f} | Price: {trade.price:.2%}

👤 <b>Trader:</b> <a href="{wallet_link}">{wallet_display}</a>

🔗 <a href="{market_link}">View Market on Polymarket</a>
"""
    
    return message


def send_alert_to_chat(chat_id: str, message: str) -> bool:
    """
    Send a Telegram message to a specific chat.
    
    Args:
        chat_id: Telegram chat ID.
        message: Message text (HTML formatted).
    
    Returns:
        True if sent successfully, False otherwise.
    """
    config = Config.get_config()
    
    if not config.TELEGRAM_BOT_TOKEN:
        print(f"   ❌ TELEGRAM_BOT_TOKEN not configured")
        return False
    
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            if result.get("ok"):
                return True
            else:
                print(f"   ❌ Telegram API error: {result.get('description', 'Unknown error')}")
                return False
                
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            # Rate limited - extract retry_after from response
            try:
                error_data = e.response.json()
                retry_after = error_data.get("parameters", {}).get("retry_after", 1)
                print(f"   ⏳ Rate limited, waiting {retry_after}s...")
                time.sleep(retry_after)
                # Retry once
                try:
                    with httpx.Client(timeout=10.0) as client:
                        response = client.post(url, json=payload)
                        response.raise_for_status()
                        return response.json().get("ok", False)
                except:
                    return False
            except:
                print(f"   ❌ Rate limited (429)")
                return False
        elif e.response.status_code == 403:
            print(f"   ❌ User blocked bot or chat_id invalid: {chat_id[:10]}...")
            return False
        elif e.response.status_code == 400:
            print(f"   ❌ Invalid chat_id: {chat_id[:10]}...")
            return False
        else:
            print(f"   ❌ Telegram API error: HTTP {e.response.status_code}")
            try:
                error_data = e.response.json()
                print(f"      Error: {error_data.get('description', 'Unknown')}")
            except:
                pass
            return False
    except httpx.TimeoutException:
        print(f"   ❌ Timeout sending to {chat_id[:10]}...")
        return False
    except Exception as e:
        print(f"   ❌ Error sending to {chat_id[:10]}...: {e}")
        return False


def send_alerts_for_trade(
    trade: Trade,
    market: MarketMetadata,
    matching_users: List[UserFilter]
) -> None:
    """
    Send alerts to all matching users for a trade.
    
    Args:
        trade: Trade that triggered alerts.
        market: Market metadata.
        matching_users: List of UserFilter objects for users who should receive alerts.
    """
    if not matching_users:
        return
    
    # Build message once (same for all users)
    message = build_trade_alert_message(trade, market, matching_users[0])
    
    # Send to each user
    success_count = 0
    failure_count = 0
    
    for user_filter in matching_users:
        if not user_filter.telegram_chat_id:
            print(f"      ⚠️  User {user_filter.user_id[:8]}... has no chat_id, skipping")
            failure_count += 1
            continue
        
        sent = send_alert_to_chat(user_filter.telegram_chat_id, message)
        
        if sent:
            success_count += 1
        else:
            failure_count += 1
        
        # Small delay between sends to respect rate limits (Telegram allows ~30 messages/second)
        # Using 0.05s = 20 messages/second to be safe
        time.sleep(0.05)
    
    if success_count > 0:
        print(f"      ✅ Sent {success_count} alert(s)")
    if failure_count > 0:
        print(f"      ❌ Failed to send {failure_count} alert(s)")

