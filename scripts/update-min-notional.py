#!/usr/bin/env python3
"""Update minNotionalUsd to $1000 for testing."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whale_worker.db import get_db
from pymongo import MongoClient

# Get user ID from command line or use a default
# In production, you'd get this from the session
# For now, we'll update all enabled configs or you can specify a user ID

def main():
    db = get_db()
    configs_collection = db['whaleAlertConfigs']
    
    # Find all configs
    all_configs = list(configs_collection.find({}))
    
    if len(all_configs) == 0:
        print("❌ No whale alert configs found in database")
        return
    
    print(f"Found {len(all_configs)} config(s) in database\n")
    
    # Update all configs to $1000 minNotional
    updated_count = 0
    for config in all_configs:
        user_id = str(config.get('userId', ''))
        current_min = config.get('minNotionalUsd', 0)
        
        result = configs_collection.update_one(
            { 'userId': user_id },
            { '$set': { 'minNotionalUsd': 100.0 } }  # Lowered to $100 for testing
        )
        
        if result.modified_count > 0:
            updated_count += 1
            print(f"✅ Updated user {user_id[:8]}...: ${current_min:,.2f} → $1,000.00")
        else:
            print(f"   User {user_id[:8]}...: Already at $1,000.00 (no change)")
    
    print(f"\n✅ Updated {updated_count} config(s)")
    print(f"\n💡 Worker will reload filters within 60 seconds")
    print(f"   Or restart the worker to reload immediately")

if __name__ == "__main__":
    main()

