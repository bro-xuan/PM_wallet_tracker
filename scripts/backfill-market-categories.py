#!/usr/bin/env python3
"""
Backfill categories for all markets that have tagIds but no categories.

This script will:
1. Find all markets without categories
2. Derive categories from their tagIds
3. Update the database with the derived categories
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from whale_worker.db import get_db
from whale_worker.categorization import derive_categories_for_market
from whale_worker.types import MarketMetadata


def backfill_categories():
    """Backfill categories for all markets."""
    db = get_db()
    markets_collection = db['marketMetadata']
    
    # Find all markets with tagIds but no categories
    markets_to_update = list(markets_collection.find({
        'tagIds': { '$exists': True, '$ne': [] },
        '$or': [
            { 'categories': { '$exists': False } },
            { 'categories': [] }
        ]
    }))
    
    total = len(markets_to_update)
    print(f"Found {total} markets without categories")
    
    if total == 0:
        print("✅ All markets already have categories!")
        return
    
    print(f"\nBackfilling categories for {total} markets...")
    print("This may take a while...\n")
    
    updated = 0
    errors = 0
    
    for i, market_doc in enumerate(markets_to_update, 1):
        try:
            condition_id = market_doc.get('conditionId')
            tag_ids = market_doc.get('tagIds', [])
            
            if not condition_id or not tag_ids:
                continue
            
            # Create MarketMetadata object
            market_metadata = MarketMetadata(
                condition_id=condition_id,
                title=market_doc.get('title', 'Unknown'),
                slug=market_doc.get('slug'),
                description=market_doc.get('description'),
                image_url=market_doc.get('imageUrl'),
                category=market_doc.get('category'),
                subcategory=market_doc.get('subcategory'),
                tags=market_doc.get('tags', []),
                tag_ids=tag_ids,
                is_sports=market_doc.get('isSports', False),
            )
            
            # Derive categories
            categories = derive_categories_for_market(market_metadata, db)
            
            # Update database
            markets_collection.update_one(
                { 'conditionId': condition_id },
                { '$set': { 'categories': categories } }
            )
            
            updated += 1
            
            # Progress indicator
            if i % 100 == 0:
                print(f"  Processed {i}/{total} markets... ({updated} updated, {errors} errors)")
            
        except Exception as e:
            errors += 1
            print(f"  ❌ Error processing market {condition_id}: {e}")
            if errors > 10:
                print("  Too many errors, stopping...")
                break
    
    print(f"\n✅ Backfill complete!")
    print(f"   Updated: {updated}")
    print(f"   Errors: {errors}")
    print(f"   Remaining: {total - updated - errors}")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("BACKFILLING MARKET CATEGORIES")
    print("="*60 + "\n")
    
    try:
        backfill_categories()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

