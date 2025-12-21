"""
Telegram notification sending for whale trade alerts.

Uses queue-based rate limiting for efficient, non-blocking message sending.
"""
from typing import List
from whale_worker.types import Trade, AggregatedTrade, MarketMetadata, UserFilter
from whale_worker.notification_queue import enqueue_notification


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


# Legacy function kept for backward compatibility, but now uses queue
def send_alert_to_chat(chat_id: str, message: str) -> bool:
    """
    Enqueue a Telegram message to be sent (queue-based, non-blocking).
    
    This function now uses the notification queue for proper rate limiting.
    The message will be sent asynchronously with per-chat and global throttling.
    
    Args:
        chat_id: Telegram chat ID.
        message: Message text (HTML formatted).
    
    Returns:
        True (message is queued, actual send happens asynchronously).
    """
    enqueue_notification(chat_id, message)
    return True  # Return True since message is queued successfully


def send_alerts_for_trade(
    trade: Trade,
    market: MarketMetadata,
    matching_users: List[UserFilter]
) -> None:
    """
    Enqueue alerts for all matching users for a trade.
    
    Messages are queued and sent asynchronously with proper rate limiting:
    - Per-chat throttling (1 msg/sec per chat to avoid spam)
    - Global throttling (~30 msg/sec globally)
    - Respects retry_after on 429 errors
    - Marks accounts as inactive on 403/400 errors
    
    Args:
        trade: Trade that triggered alerts.
        market: Market metadata.
        matching_users: List of UserFilter objects for users who should receive alerts.
    """
    if not matching_users:
        return
    
    # Build message once (same for all users)
    message = build_trade_alert_message(trade, market, matching_users[0])
    
    # Enqueue messages for all users (non-blocking)
    queued_count = 0
    skipped_count = 0
    
    for user_filter in matching_users:
        if not user_filter.telegram_chat_id:
            print(f"      ⚠️  User {user_filter.user_id[:8]}... has no chat_id, skipping")
            skipped_count += 1
            continue
        
        # Enqueue message (queue handles rate limiting)
        enqueue_notification(user_filter.telegram_chat_id, message)
        queued_count += 1
    
    if queued_count > 0:
        print(f"      📬 Queued {queued_count} alert(s) (sending asynchronously with rate limiting)")
    if skipped_count > 0:
        print(f"      ⚠️  Skipped {skipped_count} user(s) (no chat_id)")


def build_aggregated_trade_alert_message(
    agg_trade: AggregatedTrade,
    market: MarketMetadata,
    user_filter: UserFilter
) -> str:
    """
    Build a formatted Telegram message for an aggregated whale trade alert.
    
    Args:
        agg_trade: AggregatedTrade that triggered the alert.
        market: Market metadata.
        user_filter: User's filter (for context, though all users get same message).
    
    Returns:
        Formatted message string using HTML formatting for Telegram.
    """
    # Format wallet address (truncate for display)
    wallet_display = f"{agg_trade.proxy_wallet[:6]}...{agg_trade.proxy_wallet[-4:]}" if len(agg_trade.proxy_wallet) > 10 else agg_trade.proxy_wallet
    
    # Build market link
    market_link = "https://polymarket.com"
    if market.slug:
        market_link = f"https://polymarket.com/event/{market.slug}"
    elif market.condition_id:
        market_link = f"https://polymarket.com/condition/{market.condition_id}"
    
    # Build wallet profile link
    wallet_link = f"https://polymarket.com/profile/{agg_trade.proxy_wallet}"
    
    # Format side with emoji
    side_emoji = "🟢" if agg_trade.side == "BUY" else "🔴"
    
    # Build category/tags info
    category_info = ""
    if market.is_sports:
        category_info = "🏈 Sports"
    elif market.category:
        category_info = market.category.capitalize()
    
    tags_info = ""
    if market.tags:
        tags_info = f"\n🏷️ Tags: {', '.join(market.tags[:3])}"
    
    # Build fill count info
    fill_count_str = ""
    if agg_trade.fill_count > 1:
        fill_count_str = f" ({agg_trade.fill_count} fills in one tx)"
    
    # Build message
    message = f"""🐋 <b>Whale Trade Alert!</b>

📊 <b>Market:</b> {market.title}
{category_info}{tags_info}

💰 <b>Trade Details:</b>
{side_emoji} <b>{agg_trade.side}</b> ${agg_trade.total_notional_usd:,.2f} @ {agg_trade.vwap_price:.1%}{fill_count_str}
Total Size: {agg_trade.total_size:,.2f} | VWAP: {agg_trade.vwap_price:.2%}

👤 <b>Trader:</b> <a href="{wallet_link}">{wallet_display}</a>

🔗 <a href="{market_link}">View Market on Polymarket</a>
"""
    
    return message


def send_alerts_for_aggregated_trade(
    agg_trade: AggregatedTrade,
    market: MarketMetadata,
    matching_users: List[UserFilter]
) -> None:
    """
    Enqueue alerts for all matching users for an aggregated trade.
    
    Messages are queued and sent asynchronously with proper rate limiting:
    - Per-chat throttling (1 msg/sec per chat to avoid spam)
    - Global throttling (~30 msg/sec globally)
    - Respects retry_after on 429 errors
    - Marks accounts as inactive on 403/400 errors
    
    Args:
        agg_trade: AggregatedTrade that triggered alerts.
        market: Market metadata.
        matching_users: List of UserFilter objects for users who should receive alerts.
    """
    if not matching_users:
        return
    
    # Build message once (same for all users)
    message = build_aggregated_trade_alert_message(agg_trade, market, matching_users[0])
    
    # Enqueue messages for all users (non-blocking)
    queued_count = 0
    skipped_count = 0
    
    for user_filter in matching_users:
        if not user_filter.telegram_chat_id:
            print(f"      ⚠️  User {user_filter.user_id[:8]}... has no chat_id, skipping")
            skipped_count += 1
            continue
        
        # Enqueue message (queue handles rate limiting)
        enqueue_notification(user_filter.telegram_chat_id, message)
        queued_count += 1
    
    if queued_count > 0:
        print(f"      📬 Queued {queued_count} alert(s) (sending asynchronously with rate limiting)")
    if skipped_count > 0:
        print(f"      ⚠️  Skipped {skipped_count} user(s) (no chat_id)")

