#!/usr/bin/env python3
"""
Monitor categorization activity in real-time.

Watches for:
- New tag categorizations
- Markets getting categories
- Filter matching activity
"""

import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from whale_worker.db import get_db
from whale_worker.db_categorization import get_tag_category_mappings_count


def monitor_categorization():
    """Monitor categorization progress."""
    db = get_db()
    markets_collection = db['marketMetadata']
    tag_mappings_collection = db['tagCategoryMappings']
    
    print("\n" + "="*60)
    print("CATEGORIZATION MONITOR")
    print("="*60)
    print("Monitoring categorization activity...")
    print("Press Ctrl+C to stop\n")
    
    last_market_count = 0
    last_tag_count = 0
    
    try:
        while True:
            # Check market categories
            total_markets = markets_collection.count_documents({})
            markets_with_categories = markets_collection.count_documents({
                'categories': { '$exists': True, '$ne': [] }
            })
            
            # Check tag mappings
            tag_mappings_count = get_tag_category_mappings_count()
            
            # Calculate changes
            market_delta = markets_with_categories - last_market_count
            tag_delta = tag_mappings_count - last_tag_count
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            if market_delta > 0 or tag_delta > 0:
                print(f"[{timestamp}] 📊 Update:")
                if market_delta > 0:
                    print(f"   ✅ {market_delta} new markets categorized")
                if tag_delta > 0:
                    print(f"   ✅ {tag_delta} new tag mappings created")
            
            print(f"[{timestamp}] Markets: {markets_with_categories}/{total_markets} ({markets_with_categories/total_markets*100:.1f}%) | Tag mappings: {tag_mappings_count}")
            
            last_market_count = markets_with_categories
            last_tag_count = tag_mappings_count
            
            time.sleep(5)  # Check every 5 seconds
            
    except KeyboardInterrupt:
        print("\n\n✅ Monitoring stopped")


if __name__ == '__main__':
    monitor_categorization()

