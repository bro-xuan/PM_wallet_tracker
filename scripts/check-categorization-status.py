#!/usr/bin/env python3
"""
Check categorization status - backfill progress and worker activity.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from whale_worker.db import get_db
from whale_worker.db_categorization import get_tag_category_mappings_count


def check_status():
    """Check current categorization status."""
    db = get_db()
    markets_collection = db['marketMetadata']
    tag_mappings_collection = db['tagCategoryMappings']
    
    print("\n" + "="*60)
    print("CATEGORIZATION STATUS CHECK")
    print("="*60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 1. Market categories status
    total_markets = markets_collection.count_documents({})
    markets_with_categories = markets_collection.count_documents({
        'categories': { '$exists': True, '$ne': [] }
    })
    markets_without_categories = markets_collection.count_documents({
        '$or': [
            { 'categories': { '$exists': False } },
            { 'categories': [] }
        ],
        'tagIds': { '$exists': True, '$ne': [] }
    })
    
    print("📊 MARKET CATEGORIES:")
    print(f"   Total markets: {total_markets}")
    print(f"   ✅ With categories: {markets_with_categories} ({markets_with_categories/total_markets*100:.1f}%)")
    print(f"   ⚠️  Without categories: {markets_without_categories} ({markets_without_categories/total_markets*100:.1f}%)")
    
    # 2. Tag mappings status
    tag_mappings_count = get_tag_category_mappings_count()
    print(f"\n🏷️  TAG MAPPINGS:")
    print(f"   Total mappings: {tag_mappings_count}")
    
    # 3. Recent activity (markets updated in last hour)
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent_updates = markets_collection.count_documents({
        'updatedAt': { '$gte': one_hour_ago },
        'categories': { '$exists': True, '$ne': [] }
    })
    
    print(f"\n⏰ RECENT ACTIVITY (last hour):")
    print(f"   Markets updated with categories: {recent_updates}")
    
    # 4. Sample markets
    print(f"\n📋 SAMPLE MARKETS:")
    sample_with = list(markets_collection.find({
        'categories': { '$exists': True, '$ne': [] }
    }).limit(3))
    
    sample_without = list(markets_collection.find({
        '$or': [
            { 'categories': { '$exists': False } },
            { 'categories': [] }
        ],
        'tagIds': { '$exists': True, '$ne': [] }
    }).limit(3))
    
    if sample_with:
        print("   Markets WITH categories:")
        for market in sample_with:
            title = (market.get('title') or 'Unknown')[:40]
            categories = market.get('categories', [])
            print(f"      • {title} → {categories}")
    
    if sample_without:
        print("   Markets WITHOUT categories (will get them on next load):")
        for market in sample_without:
            title = (market.get('title') or 'Unknown')[:40]
            tag_count = len(market.get('tagIds', []))
            print(f"      • {title} ({tag_count} tags)")
    
    # 5. Check if worker is deriving categories
    print(f"\n🔍 WORKER ACTIVITY CHECK:")
    print("   Checking if markets are being categorized during normal operation...")
    
    # Check markets updated very recently (last 5 minutes)
    five_min_ago = datetime.utcnow() - timedelta(minutes=5)
    very_recent = markets_collection.count_documents({
        'updatedAt': { '$gte': five_min_ago },
        'categories': { '$exists': True, '$ne': [] }
    })
    
    if very_recent > 0:
        print(f"   ✅ {very_recent} markets categorized in last 5 minutes (worker is active!)")
    else:
        print(f"   ⚠️  No markets categorized in last 5 minutes")
        print(f"      → Worker may be processing cached markets (categories derived but not saved)")
        print(f"      → Or worker is not processing new markets right now")
    
    # 6. Check tag mapping activity
    recent_tag_mappings = tag_mappings_collection.count_documents({
        'inferredAt': { '$gte': one_hour_ago }
    })
    print(f"\n🏷️  TAG MAPPING ACTIVITY (last hour):")
    print(f"   New tag mappings created: {recent_tag_mappings}")
    
    if recent_tag_mappings > 0:
        print("   ✅ Tags are being categorized!")
    else:
        print("   ⚠️  No new tag mappings (may be using cached tags)")
    
    print("\n" + "="*60)


if __name__ == '__main__':
    try:
        check_status()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

