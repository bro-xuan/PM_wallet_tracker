#!/usr/bin/env python3
"""
Diagnostic script to verify categorization system is working correctly.

Checks:
1. User configs have selectedCategories set
2. Markets have categories field populated
3. Tag category mappings exist
4. Sample market categorization
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import whale_worker modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from whale_worker.db import get_db
from whale_worker.db_categorization import (
    get_tag_category_mappings_count,
    get_tag_category_mapping_example,
    get_tag_category_mapping
)
from whale_worker.categorization import derive_categories_for_market
from whale_worker.types import MarketMetadata


def check_user_configs():
    """Check if user configs have selectedCategories set."""
    print("\n" + "="*60)
    print("1. CHECKING USER CONFIGS")
    print("="*60)
    
    db = get_db()
    configs_collection = db['whaleAlertConfigs']
    
    all_configs = list(configs_collection.find({}))
    print(f"Total user configs: {len(all_configs)}")
    
    if not all_configs:
        print("⚠️  No user configs found!")
        return
    
    configs_with_selected = 0
    configs_with_exclude = 0
    configs_empty = 0
    
    for config in all_configs:
        user_id = config.get('userId', 'unknown')
        selected = config.get('selectedCategories', [])
        exclude = config.get('excludeCategories', [])
        enabled = config.get('enabled', False)
        
        if selected:
            configs_with_selected += 1
            print(f"\n✅ User {user_id[:8]}...")
            print(f"   selectedCategories: {selected}")
            print(f"   enabled: {enabled}")
        elif exclude:
            configs_with_exclude += 1
            print(f"\n⚠️  User {user_id[:8]}... (LEGACY)")
            print(f"   excludeCategories: {exclude}")
            print(f"   selectedCategories: {selected} (will be migrated)")
            print(f"   enabled: {enabled}")
        else:
            configs_empty += 1
            print(f"\n❌ User {user_id[:8]}... (NO CATEGORIES SET)")
            print(f"   selectedCategories: {selected} (empty = all categories allowed)")
            print(f"   enabled: {enabled}")
    
    print(f"\n📊 Summary:")
    print(f"   Configs with selectedCategories: {configs_with_selected}")
    print(f"   Configs with excludeCategories (legacy): {configs_with_exclude}")
    print(f"   Configs with no category filters: {configs_empty}")


def check_market_categories():
    """Check if markets have categories field populated."""
    print("\n" + "="*60)
    print("2. CHECKING MARKET CATEGORIES")
    print("="*60)
    
    db = get_db()
    markets_collection = db['marketMetadata']
    
    total_markets = markets_collection.count_documents({})
    markets_with_categories = markets_collection.count_documents({ 'categories': { '$exists': True, '$ne': [] } })
    markets_without_categories = markets_collection.count_documents({ '$or': [
        { 'categories': { '$exists': False } },
        { 'categories': [] }
    ]})
    markets_with_tag_ids = markets_collection.count_documents({ 'tagIds': { '$exists': True, '$ne': [] } })
    
    print(f"Total markets in cache: {total_markets}")
    print(f"Markets WITH categories: {markets_with_categories}")
    print(f"Markets WITHOUT categories: {markets_without_categories}")
    print(f"Markets with tagIds (can derive categories): {markets_with_tag_ids}")
    
    # Sample a few markets
    print("\n📋 Sample markets:")
    sample_markets = list(markets_collection.find({}).limit(5))
    
    for market in sample_markets:
        condition_id = market.get('conditionId', 'unknown')
        title = market.get('title', 'Unknown')[:50]
        categories = market.get('categories', [])
        tag_ids = market.get('tagIds', [])
        
        if categories:
            print(f"\n✅ {condition_id[:16]}...")
            print(f"   Title: {title}")
            print(f"   Categories: {categories}")
        elif tag_ids:
            print(f"\n⚠️  {condition_id[:16]}... (NO CATEGORIES, but has tagIds)")
            print(f"   Title: {title}")
            print(f"   TagIds: {tag_ids[:3]}... ({len(tag_ids)} total)")
            print(f"   → Will derive categories on next load")
        else:
            print(f"\n❌ {condition_id[:16]}... (NO CATEGORIES, NO TAGIDS)")
            print(f"   Title: {title}")


def check_tag_mappings():
    """Check tag category mappings."""
    print("\n" + "="*60)
    print("3. CHECKING TAG CATEGORY MAPPINGS")
    print("="*60)
    
    count = get_tag_category_mappings_count()
    example = get_tag_category_mapping_example()
    
    print(f"Total tag category mappings: {count}")
    
    if example:
        print(f"\n📋 Example mapping:")
        print(f"   tagId: {example.get('tagId')}")
        print(f"   label: {example.get('label')}")
        print(f"   categories: {example.get('categories')}")
    else:
        print("\n⚠️  No tag mappings found yet (will be created as tags are categorized)")


def test_market_categorization():
    """Test categorizing a sample market."""
    print("\n" + "="*60)
    print("4. TESTING MARKET CATEGORIZATION")
    print("="*60)
    
    db = get_db()
    markets_collection = db['marketMetadata']
    
    # Find a market with tagIds but potentially missing categories
    test_market_doc = markets_collection.find_one({
        'tagIds': { '$exists': True, '$ne': [] }
    })
    
    if not test_market_doc:
        print("⚠️  No markets with tagIds found to test")
        return
    
    condition_id = test_market_doc.get('conditionId')
    tag_ids = test_market_doc.get('tagIds', [])
    existing_categories = test_market_doc.get('categories', [])
    
    print(f"Testing market: {condition_id}")
    print(f"TagIds: {tag_ids[:5]}... ({len(tag_ids)} total)")
    print(f"Existing categories: {existing_categories}")
    
    # Create MarketMetadata object
    market_metadata = MarketMetadata(
        condition_id=condition_id,
        title=test_market_doc.get('title', 'Unknown'),
        slug=test_market_doc.get('slug'),
        description=test_market_doc.get('description'),
        image_url=test_market_doc.get('imageUrl'),
        category=test_market_doc.get('category'),
        subcategory=test_market_doc.get('subcategory'),
        tags=test_market_doc.get('tags', []),
        tag_ids=tag_ids,
        is_sports=test_market_doc.get('isSports', False),
        categories=existing_categories,
    )
    
    # Derive categories
    print("\n🔍 Deriving categories...")
    derived_categories = derive_categories_for_market(market_metadata, db)
    
    print(f"✅ Derived categories: {derived_categories}")
    
    if existing_categories:
        if set(existing_categories) == set(derived_categories):
            print("✅ Categories match existing cache")
        else:
            print(f"⚠️  Categories differ! Existing: {existing_categories}, Derived: {derived_categories}")
    else:
        print("⚠️  Market had no categories - should be updated in cache")


def check_filter_matching():
    """Check if filter matching logic would work."""
    print("\n" + "="*60)
    print("5. CHECKING FILTER MATCHING LOGIC")
    print("="*60)
    
    db = get_db()
    configs_collection = db['whaleAlertConfigs']
    markets_collection = db['marketMetadata']
    
    # Get a user config with selectedCategories
    user_config = configs_collection.find_one({
        'selectedCategories': { '$exists': True, '$ne': [] }
    })
    
    if not user_config:
        print("⚠️  No user configs with selectedCategories found")
        print("   → This means ALL categories are allowed for all users")
        return
    
    user_id = user_config.get('userId', 'unknown')
    selected_categories = user_config.get('selectedCategories', [])
    
    print(f"Testing with user: {user_id[:8]}...")
    print(f"Selected categories: {selected_categories}")
    
    # Get a few markets
    sample_markets = list(markets_collection.find({}).limit(3))
    
    print(f"\n📋 Testing filter matching on {len(sample_markets)} markets:")
    
    for market_doc in sample_markets:
        condition_id = market_doc.get('conditionId', 'unknown')
        market_categories = market_doc.get('categories', [])
        title = market_doc.get('title', 'Unknown')[:40]
        
        if not market_categories:
            print(f"\n❌ {condition_id[:16]}... - NO CATEGORIES")
            print(f"   Title: {title}")
            print(f"   → Would be FILTERED OUT (market has no categories)")
        else:
            # Check intersection
            has_intersection = any(cat in market_categories for cat in selected_categories)
            if has_intersection:
                print(f"\n✅ {condition_id[:16]}... - MATCHES")
                print(f"   Title: {title}")
                print(f"   Market categories: {market_categories}")
                print(f"   → Would PASS filter")
            else:
                print(f"\n🚫 {condition_id[:16]}... - NO MATCH")
                print(f"   Title: {title}")
                print(f"   Market categories: {market_categories}")
                print(f"   Selected categories: {selected_categories}")
                print(f"   → Would be FILTERED OUT")


def main():
    """Run all diagnostic checks."""
    print("\n" + "="*60)
    print("CATEGORIZATION SYSTEM DIAGNOSTICS")
    print("="*60)
    
    try:
        check_user_configs()
        check_market_categories()
        check_tag_mappings()
        test_market_categorization()
        check_filter_matching()
        
        print("\n" + "="*60)
        print("DIAGNOSTICS COMPLETE")
        print("="*60)
        print("\n💡 Tips:")
        print("   - If selectedCategories is empty, all categories are allowed")
        print("   - Markets without categories will get them derived on next load")
        print("   - Tag mappings are created automatically as tags are categorized")
        
    except Exception as e:
        print(f"\n❌ Error running diagnostics: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

