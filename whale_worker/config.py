"""
Configuration loading from environment variables.
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Load .env.local if it exists
load_dotenv('.env.local')
load_dotenv()  # Also load .env if it exists


class Config:
    """Application configuration loaded from environment variables."""
    
    # MongoDB configuration
    MONGODB_URI: str = os.getenv('MONGODB_URI', '')
    MONGODB_DB: str = os.getenv('MONGODB_DB_NAME', 'pm-wallet-tracker')
    
    # Telegram configuration
    TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    
    # Worker configuration
    GLOBAL_MIN_NOTIONAL_USD: float = float(os.getenv('GLOBAL_MIN_NOTIONAL_USD', '0'))
    POLL_INTERVAL_SECONDS: int = int(os.getenv('POLL_INTERVAL_SECONDS', '10'))
    MAX_TRADES_PER_POLL: int = int(os.getenv('MAX_TRADES_PER_POLL', '1000'))
    
    # Polymarket API URLs
    POLYMARKET_DATA_API_URL: str = os.getenv('POLYMARKET_DATA_API_URL', 'https://data-api.polymarket.com')
    POLYMARKET_GAMMA_API_URL: str = os.getenv('POLYMARKET_GAMMA_API_URL', 'https://gamma-api.polymarket.com')
    
    # TODO: Add additional settings as needed:
    # - MAX_TRADES_PER_POLL
    # - TELEGRAM_RATE_LIMIT_DELAY
    # - LOG_LEVEL
    # - HTTP_TIMEOUT_SECONDS
    # - MAX_RETRIES
    
    @classmethod
    def validate(cls) -> bool:
        """
        Validate that required configuration is present.
        
        Returns:
            True if all required config is present, False otherwise.
        """
        required = [
            ('MONGODB_URI', cls.MONGODB_URI),
            ('TELEGRAM_BOT_TOKEN', cls.TELEGRAM_BOT_TOKEN),
        ]
        
        missing = [name for name, value in required if not value]
        if missing:
            print(f"❌ Missing required configuration: {', '.join(missing)}")
            return False
        
        return True
    
    @classmethod
    def get_config(cls) -> 'Config':
        """
        Get a Config instance (singleton pattern).
        
        Returns:
            Config instance with loaded values.
        """
        return cls()


def load_config() -> Config:
    """
    Load and validate configuration.
    
    Returns:
        Config instance.
        
    Raises:
        ValueError: If required configuration is missing.
    """
    config = Config.get_config()
    if not config.validate():
        raise ValueError("Invalid configuration. Check environment variables.")
    return config

