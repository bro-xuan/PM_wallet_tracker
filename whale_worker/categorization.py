"""
Trade categorization service.

Maps Gamma tag IDs to user-friendly categories (Politics, Sports, Crypto, etc.)
by maintaining a dictionary of tag -> categories mappings.
"""
from typing import List, Set, Dict, Optional
from datetime import datetime
from pymongo.database import Database
from whale_worker.db import get_or_cache_sports_tag_ids, get_or_cache_tags_dictionary


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

# Type alias for category keys (just strings)
CategoryKey = str


def infer_categories_for_tag(tag_label: str, tag_slug: str) -> List[CategoryKey]:
    """
    Infer categories for a tag based on its label and slug using keyword matching.
    
    Uses keyword matching against CATEGORY_KEYWORDS.
    
    Args:
        tag_label: Tag label from Gamma
        tag_slug: Tag slug from Gamma
        
    Returns:
        List of matching category names (CategoryKey)
    """
    # Normalize to lowercase for matching
    label_lower = (tag_label or "").lower()
    slug_lower = (tag_slug or "").lower()
    
    # Combine label and slug for searching
    search_text = f"{label_lower} {slug_lower}"
    
    matched_categories = []
    
    # Check each category's keywords
    for category, keywords in CATEGORY_KEYWORDS.items():
        # Skip "Mentions" as it has no keywords (special logic needed)
        if category == "Mentions":
            continue
            
        # Check if any keyword appears in the search text
        for keyword in keywords:
            if keyword.lower() in search_text:
                matched_categories.append(category)
                break  # Found a match for this category, move to next
    
    return matched_categories


def get_categories_for_tag(
    tag_id: str,
    label: str,
    slug: str,
    db: Database
) -> List[CategoryKey]:
    """
    Get categories for a tag ID.
    
    First checks database cache, then infers if not found and persists the result.
    
    Args:
        tag_id: Tag ID from Gamma API
        label: Tag label from Gamma
        slug: Tag slug from Gamma
        db: MongoDB database instance
        
    Returns:
        List of category names (CategoryKey) for this tag
    """
    # Check database cache
    collection = db.tagCategoryMappings
    cached = collection.find_one({ '_id': tag_id })
    
    if cached and cached.get('categories'):
        # Return cached categories
        return cached.get('categories', [])
    
    # Not in cache, infer categories
    categories = infer_categories_for_tag(label, slug)
    
    # Debug log: New tag categorization
    print(f"   🔍 [DEBUG] New tag categorized: tagId={tag_id}, label='{label}', inferredCategories={categories}")
    
    # Persist to database
    now = datetime.utcnow()
    collection.update_one(
        { '_id': tag_id },
        {
            '$set': {
                'categories': categories,
                'label': label,
                'slug': slug,
                'updatedAt': now
            },
            '$setOnInsert': {
                'inferredAt': now
            }
        },
        upsert=True
    )
    
    return categories


def derive_categories_for_market(
    market_metadata,
    db: Database
) -> List[CategoryKey]:
    """
    Derive categories for a market by combining categories from all its tags.
    
    For each tagId on the market:
    - Get tag label/slug from tags dictionary (Gamma cache)
    - Call get_categories_for_tag
    - Add "Sports" if tagId in sportsTagIds
    
    Args:
        market_metadata: MarketMetadata object with tag_ids
        db: MongoDB database instance
        
    Returns:
        List of unique category names (CategoryKey)
    """
    # Get sports tag IDs and tags dictionary from cache
    sports_tag_ids = get_or_cache_sports_tag_ids()
    tags_dict = get_or_cache_tags_dictionary()
    
    # Initialize set to collect unique categories
    all_categories = set()
    
    # Get tag IDs from market metadata
    tag_ids = market_metadata.tag_ids if hasattr(market_metadata, 'tag_ids') else []
    
    # Process each tag ID
    for tag_id in tag_ids:
        # Get tag info from tags dictionary (Gamma cache)
        tag_info = tags_dict.get(tag_id, {})
        tag_label = tag_info.get('label', '')
        tag_slug = tag_info.get('slug', '')
        
        # Get categories for this tag
        tag_categories = get_categories_for_tag(tag_id, tag_label, tag_slug, db)
        all_categories.update(tag_categories)
        
        # Add "Sports" if tag ID is in sports tag IDs
        if tag_id in sports_tag_ids:
            all_categories.add("Sports")
    
    # Return sorted list of unique categories
    return sorted(list(all_categories))

