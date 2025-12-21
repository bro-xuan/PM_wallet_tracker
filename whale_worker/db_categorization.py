"""
Database functions for tag category mappings.

Stores and retrieves tag ID -> categories mappings in MongoDB.
"""
from typing import List, Optional, Dict, TypedDict
from datetime import datetime
from whale_worker.db import get_db


class TagCategoryMapping(TypedDict, total=False):
    """Type definition for tag category mapping document."""
    _id: str  # tag_id (primary key)
    categories: List[str]  # List of category names
    label: str  # Tag label from Gamma
    slug: str  # Tag slug from Gamma
    inferredAt: datetime  # When categorization was first inferred
    updatedAt: datetime  # Last update timestamp


def ensure_tag_category_mappings_index() -> None:
    """
    Ensure unique index exists on tagId (_id) in tagCategoryMappings collection.
    
    Note: MongoDB automatically creates a unique index on _id, but we explicitly
    ensure it exists for clarity and to handle any edge cases.
    
    This should be called once at startup to create the index.
    """
    db = get_db()
    collection = db.tagCategoryMappings
    
    # Create unique index on _id (tag_id)
    # Note: _id is already unique by default in MongoDB, but we ensure it explicitly
    try:
        collection.create_index(
            '_id',
            unique=True,
            name='tagId_unique_idx'
        )
        print("   ✅ Created unique index on _id in tagCategoryMappings collection")
    except Exception as e:
        # Index might already exist, which is fine
        if 'already exists' not in str(e).lower() and 'duplicate key' not in str(e).lower():
            print(f"   ⚠️  Could not create tagId unique index: {e}")


def get_tag_category_mapping(tag_id: str) -> Optional[TagCategoryMapping]:
    """
    Get category mapping for a tag ID from database.
    
    Args:
        tag_id: Tag ID from Gamma API
        
    Returns:
        TagCategoryMapping dictionary with 'categories', 'label', 'slug', etc., or None if not found
    """
    db = get_db()
    collection = db.tagCategoryMappings
    doc = collection.find_one({ '_id': tag_id })
    
    if doc:
        # Convert MongoDB document to TagCategoryMapping
        return {
            '_id': str(doc.get('_id', tag_id)),
            'categories': doc.get('categories', []),
            'label': doc.get('label', ''),
            'slug': doc.get('slug', ''),
            'inferredAt': doc.get('inferredAt'),
            'updatedAt': doc.get('updatedAt'),
        }
    
    return None


def save_tag_category_mapping(
    tag_id: str,
    label: str,
    slug: str,
    categories: List[str]
) -> None:
    """
    Save category mapping for a tag ID to database.
    
    Args:
        tag_id: Tag ID from Gamma API
        label: Tag label from Gamma
        slug: Tag slug from Gamma
        categories: List of category names (e.g., ["Politics", "Elections"])
    """
    db = get_db()
    collection = db.tagCategoryMappings
    
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


def get_tag_category_mappings_count() -> int:
    """
    Get total count of tag category mappings in database.
    
    Returns:
        Number of tag category mappings stored.
    """
    db = get_db()
    collection = db.tagCategoryMappings
    return collection.count_documents({})


def get_tag_category_mapping_example() -> Optional[Dict]:
    """
    Get an example tag category mapping from database.
    
    Returns:
        Example TagCategoryMapping dictionary or None if no mappings exist.
    """
    db = get_db()
    collection = db.tagCategoryMappings
    example = collection.find_one({})
    
    if example:
        return {
            'tagId': str(example.get('_id', '')),
            'categories': example.get('categories', []),
            'label': example.get('label', ''),
        }
    
    return None

