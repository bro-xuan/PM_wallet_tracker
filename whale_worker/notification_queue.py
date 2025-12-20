"""
Queue-based notification system with proper rate limiting.

Features:
- Queue-based message sending (no blocking sleep)
- Per-chat throttling (avoid spamming one user)
- Global throttling (respect Telegram's global limits)
- Respects retry_after on 429 errors
- Marks accounts as inactive on 403/400 errors
"""
import time
import threading
from queue import Queue, Empty
from typing import Dict, Optional
from collections import defaultdict
import httpx
from whale_worker.config import Config
from whale_worker.db import get_db


class NotificationQueue:
    """
    Thread-safe queue for Telegram notifications with rate limiting.
    """
    
    def __init__(self):
        self.queue: Queue = Queue()
        self.worker_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Rate limiting state
        self.last_global_send: float = 0.0
        self.last_chat_send: Dict[str, float] = {}  # chat_id -> timestamp
        
        # Rate limiting config
        self.global_min_interval: float = 0.034  # ~30 msg/sec global (conservative)
        self.per_chat_min_interval: float = 1.0  # 1 msg/sec per chat (avoid spam)
        
        # Lock for thread-safe access
        self.lock = threading.Lock()
        
    def start(self) -> None:
        """Start the notification worker thread."""
        if self.running:
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        print("✅ Notification queue worker started")
    
    def stop(self) -> None:
        """Stop the notification worker thread."""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5.0)
        print("🛑 Notification queue worker stopped")
    
    def enqueue(self, chat_id: str, message: str) -> None:
        """
        Add a notification to the queue.
        
        Args:
            chat_id: Telegram chat ID.
            message: Message text (HTML formatted).
        """
        self.queue.put((chat_id, message))
    
    def _worker_loop(self) -> None:
        """Worker thread that processes the notification queue."""
        config = Config.get_config()
        
        while self.running:
            try:
                # Get next message from queue (with timeout for graceful shutdown)
                try:
                    chat_id, message = self.queue.get(timeout=1.0)
                except Empty:
                    continue
                
                # Apply rate limiting
                self._apply_rate_limits(chat_id)
                
                # Send message
                success = self._send_message(chat_id, message, config)
                
                # Mark task as done
                self.queue.task_done()
                
                if not success:
                    # If send failed, we've already handled error (deactivation, etc.)
                    # Just continue to next message
                    continue
                    
            except Exception as e:
                print(f"   ❌ Error in notification worker: {e}")
                import traceback
                traceback.print_exc()
                # Continue processing other messages
    
    def _apply_rate_limits(self, chat_id: str) -> None:
        """
        Apply rate limiting (global and per-chat).
        
        Args:
            chat_id: Telegram chat ID.
        """
        current_time = time.time()
        
        with self.lock:
            # Global rate limiting
            time_since_global = current_time - self.last_global_send
            if time_since_global < self.global_min_interval:
                sleep_time = self.global_min_interval - time_since_global
                time.sleep(sleep_time)
                current_time = time.time()  # Update after sleep
            
            # Per-chat rate limiting
            if chat_id in self.last_chat_send:
                time_since_chat = current_time - self.last_chat_send[chat_id]
                if time_since_chat < self.per_chat_min_interval:
                    sleep_time = self.per_chat_min_interval - time_since_chat
                    time.sleep(sleep_time)
                    current_time = time.time()  # Update after sleep
            
            # Update timestamps
            self.last_global_send = current_time
            self.last_chat_send[chat_id] = current_time
    
    def _send_message(
        self,
        chat_id: str,
        message: str,
        config: Config
    ) -> bool:
        """
        Send a Telegram message with proper error handling.
        
        Args:
            chat_id: Telegram chat ID.
            message: Message text.
            config: Config instance.
        
        Returns:
            True if sent successfully, False otherwise.
        """
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
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                with httpx.Client(timeout=10.0) as client:
                    response = client.post(url, json=payload)
                    
                    # Handle 429 rate limiting
                    if response.status_code == 429:
                        try:
                            error_data = response.json()
                            retry_after = error_data.get("parameters", {}).get("retry_after", 1)
                            print(f"   ⏳ Rate limited (429), waiting {retry_after}s...")
                            time.sleep(retry_after)
                            retry_count += 1
                            continue  # Retry after waiting
                        except:
                            print(f"   ❌ Rate limited (429), failed to parse retry_after")
                            return False
                    
                    # Handle 403 (user blocked bot)
                    if response.status_code == 403:
                        print(f"   ❌ User blocked bot: {chat_id[:10]}...")
                        self._deactivate_chat(chat_id)
                        return False
                    
                    # Handle 400 (invalid chat_id)
                    if response.status_code == 400:
                        print(f"   ❌ Invalid chat_id: {chat_id[:10]}...")
                        self._deactivate_chat(chat_id)
                        return False
                    
                    # Check for other errors
                    response.raise_for_status()
                    result = response.json()
                    
                    if result.get("ok"):
                        return True
                    else:
                        print(f"   ❌ Telegram API error: {result.get('description', 'Unknown error')}")
                        return False
                        
            except httpx.HTTPStatusError as e:
                print(f"   ❌ Telegram API error: HTTP {e.response.status_code}")
                try:
                    error_data = e.response.json()
                    print(f"      Error: {error_data.get('description', 'Unknown')}")
                except:
                    pass
                return False
            except httpx.TimeoutException:
                print(f"   ❌ Timeout sending to {chat_id[:10]}...")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(1.0)  # Wait before retry
                    continue
                return False
            except Exception as e:
                print(f"   ❌ Error sending to {chat_id[:10]}...: {e}")
                return False
        
        return False
    
    def _deactivate_chat(self, chat_id: str) -> None:
        """
        Mark a Telegram account as inactive in MongoDB.
        
        Args:
            chat_id: Telegram chat ID to deactivate.
        """
        try:
            db = get_db()
            telegram_accounts_collection = db.collection('telegramAccounts')
            
            result = telegram_accounts_collection.update_one(
                { 'chatId': str(chat_id) },
                { '$set': { 'isActive': False } }
            )
            
            if result.modified_count > 0:
                print(f"      ✅ Marked chat {chat_id[:10]}... as inactive")
        except Exception as e:
            print(f"      ⚠️  Failed to deactivate chat {chat_id[:10]}...: {e}")


# Global notification queue instance
_notification_queue: Optional[NotificationQueue] = None


def get_notification_queue() -> NotificationQueue:
    """
    Get or create the global notification queue instance.
    
    Returns:
        NotificationQueue instance.
    """
    global _notification_queue
    if _notification_queue is None:
        _notification_queue = NotificationQueue()
        _notification_queue.start()
    return _notification_queue


def enqueue_notification(chat_id: str, message: str) -> None:
    """
    Enqueue a notification to be sent.
    
    This is the main entry point for sending notifications.
    Messages are queued and sent asynchronously with proper rate limiting.
    
    Args:
        chat_id: Telegram chat ID.
        message: Message text (HTML formatted).
    """
    queue = get_notification_queue()
    queue.enqueue(chat_id, message)

