"""
Type definitions and dataclasses for the whale worker.
"""
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class Trade:
    """Represents a single fill from Polymarket."""
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
    
    def get_fill_key(self) -> str:
        """
        Generate a unique key for this fill.
        
        Used for deduplication at the fill level (not transaction level).
        Format: {transaction_hash}:{proxy_wallet}:{condition_id}:{outcome}:{side}:{size}:{price}
        """
        outcome_str = str(self.outcome) if self.outcome else "None"
        condition_str = str(self.condition_id) if self.condition_id else "None"
        return f"{self.transaction_hash}:{self.proxy_wallet}:{condition_str}:{outcome_str}:{self.side}:{self.size}:{self.price}"
    
    def get_aggregation_key(self) -> tuple:
        """
        Generate a key for aggregating fills into whale trades.
        
        Groups fills by: (transaction_hash, proxy_wallet, condition_id, outcome, side)
        Returns a tuple for use as a dictionary key.
        """
        return (
            self.transaction_hash,
            self.proxy_wallet,
            str(self.condition_id) if self.condition_id else None,
            str(self.outcome) if self.outcome else None,
            self.side,
        )


@dataclass
class AggregatedTrade:
    """Represents an aggregated whale trade (multiple fills combined)."""
    transaction_hash: str
    proxy_wallet: str
    side: str  # "BUY" or "SELL"
    condition_id: Optional[str] = None
    outcome: Optional[str] = None
    total_size: float = 0.0
    total_notional_usd: float = 0.0
    vwap_price: float = 0.0  # Volume-weighted average price
    timestamp: int = 0  # Max timestamp from all fills
    fill_count: int = 0  # Number of fills aggregated
    
    @classmethod
    def from_fills(cls, fills: List[Trade]) -> 'AggregatedTrade':
        """
        Aggregate multiple fills into a single whale trade.
        
        Args:
            fills: List of Trade objects to aggregate (must have same aggregation key).
        
        Returns:
            AggregatedTrade object with aggregated values.
        """
        if not fills:
            raise ValueError("Cannot aggregate empty list of fills")
        
        # Use first fill for common fields
        first_fill = fills[0]
        
        # Calculate aggregates
        total_size = sum(fill.size for fill in fills)
        total_notional = sum(fill.notional for fill in fills)
        vwap_price = total_notional / total_size if total_size > 0 else 0.0
        max_timestamp = max(fill.timestamp for fill in fills)
        
        return cls(
            transaction_hash=first_fill.transaction_hash,
            proxy_wallet=first_fill.proxy_wallet,
            condition_id=first_fill.condition_id,
            outcome=first_fill.outcome,
            side=first_fill.side,
            total_size=total_size,
            total_notional_usd=total_notional,
            vwap_price=vwap_price,
            timestamp=max_timestamp,
            fill_count=len(fills),
        )


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
    categories: List[str] = field(default_factory=list)  # User-friendly categories (e.g., ["Politics", "Elections"])


@dataclass
class UserFilter:
    """User's whale alert filter configuration."""
    user_id: str
    min_notional_usd: float
    min_price: float  # 0.0 to 1.0
    max_price: float  # 0.0 to 1.0
    sides: List[str]  # ["BUY", "SELL"] or subset
    markets_filter: List[str] = field(default_factory=list)  # Optional: specific condition_ids
    category_filter: List[str] = field(default_factory=list)  # Optional: categories to include/exclude (e.g., ["sports"]) - DEPRECATED
    exclude_categories: List[str] = field(default_factory=list)  # Optional: categories to exclude - DEPRECATED
    selected_categories: List[str] = field(default_factory=list)  # Optional: categories to include (e.g., ["Politics", "Crypto"])
    enabled: bool = True
    telegram_chat_id: Optional[str] = None  # User's Telegram chat ID


@dataclass
class TradeMarker:
    """Marker for tracking the last processed trade."""
    last_processed_timestamp: int
    last_processed_tx_hash: Optional[str] = None
    updated_at: Optional[datetime] = None

