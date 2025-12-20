"""
Type definitions and dataclasses for the whale worker.
"""
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class Trade:
    """Represents a trade from Polymarket."""
    transaction_hash: str
    proxy_wallet: str
    side: str  # "BUY" or "SELL"
    size: float
    price: float
    condition_id: Optional[str] = None
    outcome: Optional[str] = None
    timestamp: int = 0  # Unix timestamp
    
    @property
    def notional(self) -> float:
        """Calculate notional value (size * price)."""
        return self.size * self.price


@dataclass
class MarketMetadata:
    """Market/condition metadata from Polymarket."""
    condition_id: str
    title: str
    slug: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    category: Optional[str] = None  # e.g., "sports", "politics", "crypto", etc. (deprecated, use tag_ids)
    subcategory: Optional[str] = None
    tags: List[str] = field(default_factory=list)  # Tag labels (for display)
    tag_ids: List[str] = field(default_factory=list)  # Tag IDs (for categorization)
    is_sports: bool = False  # True if any tag_id intersects with sports tag IDs


@dataclass
class UserFilter:
    """User's whale alert filter configuration."""
    user_id: str
    min_notional_usd: float
    min_price: float  # 0.0 to 1.0
    max_price: float  # 0.0 to 1.0
    sides: List[str]  # ["BUY", "SELL"] or subset
    markets_filter: List[str] = field(default_factory=list)  # Optional: specific condition_ids
    category_filter: List[str] = field(default_factory=list)  # Optional: categories to include/exclude (e.g., ["sports"])
    exclude_categories: List[str] = field(default_factory=list)  # Optional: categories to exclude
    enabled: bool = True
    telegram_chat_id: Optional[str] = None  # User's Telegram chat ID


@dataclass
class TradeMarker:
    """Marker for tracking the last processed trade."""
    last_processed_timestamp: int
    last_processed_tx_hash: Optional[str] = None
    updated_at: Optional[datetime] = None

