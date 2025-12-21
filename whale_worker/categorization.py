"""
Trade categorization service.

Maps Gamma tag IDs to user-friendly categories (Politics, Sports, Crypto, etc.)
by maintaining a dictionary of tag -> categories mappings.
"""
from typing import List, Set, Dict, Optional
from whale_worker.db import get_db


# Category keywords for inference
CATEGORY_KEYWORDS = {
    "Politics": ["politics", "political", "election", "president", "congress", "senate", "house", 
                "democrat", "republican", "vote", "voting", "candidate", "campaign"],
    "Sports": ["sports", "sport", "football", "basketball", "baseball", "soccer", "nfl", "nba", 
               "mlb", "nhl", "olympics", "championship", "tournament"],
    "Crypto": ["crypto", "cryptocurrency", "bitcoin", "ethereum", "btc", "eth", "blockchain", 
               "defi", "nft", "web3", "token"],
    "Finance": ["finance", "financial", "stock", "market", "trading", "investment", "bank", 
                "banking", "economy", "federal reserve", "fed"],
    "Geopolitics": ["geopolitics", "geopolitical", "war", "conflict", "diplomacy", "international", 
                    "foreign policy", "military", "nato", "united nations"],
    "Earnings": ["earnings", "quarterly", "q1", "q2", "q3", "q4", "revenue", "profit", 
                 "financial report", "earnings report"],
    "Tech": ["tech", "technology", "ai", "artificial intelligence", "software", "hardware", 
             "startup", "silicon valley", "tech company"],
    "Culture": ["culture", "entertainment", "movie", "tv", "television", "celebrity", "music", 
                "art", "media", "film", "show"],
    "World": ["world", "global", "international", "country", "nation", "worldwide"],
    "Economy": ["economy", "economic", "gdp", "inflation", "unemployment", "recession", 
                "growth", "economic growth"],
    "Trump": ["trump", "donald trump", "trump administration"],
    "Elections": ["election", "elections", "presidential election", "midterm", "primary", 
                  "general election", "ballot"],
    "Mentions": []  # Special category - might need different logic
}


def get_tag_category_mapping(tag_id: str) -> Optional[Dict]:
    """
    Get category mapping for a tag ID from database.
    
    Args:
        tag_id: Tag ID from Gamma API
        
    Returns:
        Dictionary with 'categories', 'label', 'slug', etc., or None if not found
    """
    # TODO: Implement database lookup
    # Collection: tagCategoryMappings
    # Query: { _id: tag_id }
    pass


def save_tag_category_mapping(
    tag_id: str, 
    categories: List[str], 
    label: str, 
    slug: str
) -> None:
    """
    Save category mapping for a tag ID to database.
    
    Args:
        tag_id: Tag ID from Gamma API
        categories: List of category names (e.g., ["Politics", "Elections"])
        label: Tag label from Gamma
        slug: Tag slug from Gamma
    """
    # TODO: Implement database save
    # Collection: tagCategoryMappings
    # Upsert: { _id: tag_id, categories, label, slug, inferredAt, updatedAt }
    pass


def infer_categories_from_tag(label: str, slug: str) -> List[str]:
    """
    Infer categories for a tag based on its label and slug.
    
    Uses keyword matching against CATEGORY_KEYWORDS.
    
    Args:
        label: Tag label from Gamma
        slug: Tag slug from Gamma
        
    Returns:
        List of matching category names
    """
    # TODO: Implement inference logic
    # 1. Normalize label and slug to lowercase
    # 2. For each category in CATEGORY_KEYWORDS:
    #    - Check if any keyword appears in label or slug
    #    - If match found, add category to result
    # 3. Return list of matching categories
    pass


def get_tag_categories(
    tag_id: str, 
    tag_label: str, 
    tag_slug: str
) -> List[str]:
    """
    Get categories for a tag ID.
    
    First checks database cache, then infers if not found.
    
    Args:
        tag_id: Tag ID from Gamma API
        tag_label: Tag label from Gamma
        tag_slug: Tag slug from Gamma
        
    Returns:
        List of category names for this tag
    """
    # TODO: Implement
    # 1. Check database: get_tag_category_mapping(tag_id)
    # 2. If found, return cached categories
    # 3. If not found:
    #    - Infer: categories = infer_categories_from_tag(tag_label, tag_slug)
    #    - Save: save_tag_category_mapping(tag_id, categories, tag_label, tag_slug)
    #    - Return categories
    pass


def get_market_categories(
    tag_ids: List[str], 
    tags_dict: Dict[str, Dict]
) -> List[str]:
    """
    Get all categories for a market by combining categories from all its tags.
    
    Args:
        tag_ids: List of tag IDs for the market
        tags_dict: Dictionary mapping tag_id -> {label, slug, ...} from Gamma
        
    Returns:
        List of unique category names (union of all tag categories)
    """
    # TODO: Implement
    # 1. Initialize empty set for categories
    # 2. For each tag_id in tag_ids:
    #    - Get tag info from tags_dict: tag_info = tags_dict.get(tag_id, {})
    #    - Get categories: tag_categories = get_tag_categories(
    #        tag_id, 
    #        tag_info.get("label", ""), 
    #        tag_info.get("slug", "")
    #      )
    #    - Add to set
    # 3. Return sorted list of unique categories
    pass

