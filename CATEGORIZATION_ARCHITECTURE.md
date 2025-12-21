# Trade Categorization Architecture

## Overview
Build a categorization layer on top of Gamma's tag system to classify trades into user-friendly categories.

## Categories
The following categories are supported:
- Politics
- Sports
- Crypto
- Finance
- Geopolitics
- Earnings
- Tech
- Culture
- World
- Economy
- Trump
- Elections
- Mentions

## Data Flow

### 1. Tag ID → Category Mapping (Dictionary)
- **Storage**: MongoDB collection `tagCategoryMappings`
- **Structure**: 
  ```typescript
  {
    _id: tagId (string),
    categories: string[], // e.g., ["Politics", "Elections"]
    label: string, // Tag label from Gamma
    slug: string, // Tag slug from Gamma
    inferredAt: Date, // When categorization was inferred
    updatedAt: Date
  }
  ```
- **Purpose**: Cache tag categorizations to avoid re-analyzing the same tags

### 2. Market Categorization Process
For each trade/market:
1. Get market's tag IDs from Gamma API
2. For each tag ID:
   - Check `tagCategoryMappings` collection
   - If found → use cached categories
   - If not found → infer category from tag label/slug, then save to collection
3. Combine all tag categories → final market categories (union of all tag categories)
4. Use categories to filter trades based on user preferences

### 3. Category Inference Logic
When a tag is not in the dictionary:
- Analyze tag's `label` and `slug` fields
- Match against keyword patterns for each category
- Assign one or more categories based on matches
- Save mapping to database for future use

## Component Structure

### Frontend (UI)
**File**: `src/app/app/page.tsx`
- Replace `excludeCategories` with `selectedCategories: string[]`
- Add toggles for all 13 categories
- User can select which categories they want to receive alerts for

### Backend API
**File**: `src/app/api/whale-alerts/config/route.ts`
- Update config schema to include `selectedCategories: string[]`
- Store/retrieve user's category preferences

### Categorization Service
**New File**: `lib/categorization.ts` (TypeScript) or `whale_worker/categorization.py` (Python)
- `getTagCategories(tagId: string, tagLabel: string, tagSlug: string): string[]`
  - Check dictionary first
  - If not found, infer and save
  - Return categories
- `getMarketCategories(tagIds: string[], tagsDict: Dict): string[]`
  - For each tag ID, get categories
  - Combine (union) all categories
  - Return final list
- `inferCategoryFromTag(label: string, slug: string): string[]`
  - Keyword matching logic
  - Return matching categories

### Database Layer
**File**: `whale_worker/db.py` (Python) or `lib/mongodb.ts` (TypeScript)
- `getTagCategoryMapping(tagId: string): Dict | None`
- `saveTagCategoryMapping(tagId: string, categories: string[], label: string, slug: string): void`
- `getMarketCategories(tagIds: string[]): string[]` (helper that calls categorization service)

### Worker Integration
**File**: `whale_worker/main.py`
- After fetching market metadata, categorize the market
- Add `categories: string[]` field to `MarketMetadata` type
- Pass categories to filter matching logic

**File**: `whale_worker/filters.py`
- Update `trade_matches_user_filter()` to check:
  - If user has `selectedCategories` configured
  - Check if market's categories intersect with user's selected categories
  - If no intersection → trade doesn't match

**File**: `whale_worker/types.py`
- Add `categories: List[str]` to `MarketMetadata` dataclass

## Implementation Order

1. **Database Schema**: Create MongoDB collection structure for tag mappings
2. **Categorization Service**: Build inference logic and dictionary lookup
3. **Type Updates**: Add categories to MarketMetadata
4. **Worker Integration**: Integrate categorization into market metadata fetching
5. **Filter Updates**: Update filter matching to use categories
6. **UI Updates**: Replace excludeCategories with selectedCategories toggles
7. **API Updates**: Update config API to handle new structure

## Category Inference Rules (Skeleton)

```python
CATEGORY_KEYWORDS = {
    "Politics": ["politics", "political", "election", "president", "congress", "senate", "house", "democrat", "republican", "vote", "voting"],
    "Sports": ["sports", "sport", "football", "basketball", "baseball", "soccer", "nfl", "nba", "mlb", "nhl", "olympics"],
    "Crypto": ["crypto", "cryptocurrency", "bitcoin", "ethereum", "btc", "eth", "blockchain", "defi", "nft"],
    "Finance": ["finance", "financial", "stock", "market", "trading", "investment", "bank", "banking", "economy"],
    "Geopolitics": ["geopolitics", "geopolitical", "war", "conflict", "diplomacy", "international", "foreign policy"],
    "Earnings": ["earnings", "quarterly", "q1", "q2", "q3", "q4", "revenue", "profit", "financial report"],
    "Tech": ["tech", "technology", "ai", "artificial intelligence", "software", "hardware", "startup", "silicon valley"],
    "Culture": ["culture", "entertainment", "movie", "tv", "television", "celebrity", "music", "art", "media"],
    "World": ["world", "global", "international", "country", "nation", "worldwide"],
    "Economy": ["economy", "economic", "gdp", "inflation", "unemployment", "recession", "growth"],
    "Trump": ["trump", "donald trump", "trump administration"],
    "Elections": ["election", "elections", "presidential election", "midterm", "primary", "general election"],
    "Mentions": [] # Special category - might need different logic
}
```

## Notes
- Categories are case-insensitive
- A tag can belong to multiple categories
- A market inherits all categories from its tags (union)
- User selects which categories they want (inclusion filter, not exclusion)

