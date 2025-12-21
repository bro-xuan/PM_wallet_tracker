#!/usr/bin/env python3
"""
Tag sync job - fetches all tags from Gamma API with pagination.

This script:
1. Fetches all tags using pagination (limit=1000, offset increments)
2. Stores them in gammaCache collection as tags_dictionary
3. Should result in 4k-9k tags instead of just 300
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from whale_worker.polymarket_client import fetch_tags_dictionary
from whale_worker.db import get_or_cache_tags_dictionary


def sync_tags():
    """Sync all tags from Gamma API."""
    print("\n" + "="*60)
    print("TAG SYNC JOB")
    print("="*60)
    print("\nFetching all tags from Gamma API (paginated)...\n")
    
    # Fetch all tags with pagination
    tags_dict = fetch_tags_dictionary()
    
    if not tags_dict:
        print("\n❌ Failed to fetch tags!")
        return False
    
    print(f"\n✅ Fetched {len(tags_dict)} tags from API")
    
    # Cache the tags dictionary
    print("\nCaching tags dictionary...")
    cached_dict = get_or_cache_tags_dictionary(tags_dict)
    
    print(f"✅ Cached {len(cached_dict)} tags in database")
    
    # Verify
    print("\n📊 Verification:")
    print(f"   Tags in dictionary: {len(cached_dict)}")
    
    # Check some common tag IDs
    common_tags = ['1', '100639', '21', '2', '102169', '1312', '101757', '235']
    found = 0
    print("\n   Checking common tag IDs:")
    for tag_id in common_tags:
        if tag_id in cached_dict:
            found += 1
            label = cached_dict[tag_id].get('label', 'N/A')
            print(f"      ✅ Tag {tag_id}: {label}")
        else:
            print(f"      ❌ Tag {tag_id}: NOT FOUND")
    
    print(f"\n   Found {found}/{len(common_tags)} common tags")
    
    if len(cached_dict) >= 4000:
        print(f"\n✅ Success! Tag dictionary now has {len(cached_dict)} tags (expected 4k-9k)")
    else:
        print(f"\n⚠️  Only {len(cached_dict)} tags (expected 4k-9k)")
    
    return True


if __name__ == '__main__':
    try:
        success = sync_tags()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

