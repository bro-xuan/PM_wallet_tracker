# Categorization System - Skeleton Structure

## Files Created/Modified

### 1. Architecture Document
- ✅ `CATEGORIZATION_ARCHITECTURE.md` - High-level design and flow

### 2. Python Worker Files

#### `whale_worker/categorization.py` (NEW)
- `get_tag_category_mapping(tag_id)` - Lookup from DB
- `save_tag_category_mapping(tag_id, categories, label, slug)` - Save to DB
- `infer_categories_from_tag(label, slug)` - Keyword-based inference
- `get_tag_categories(tag_id, label, slug)` - Main entry point (cache + infer)
- `get_market_categories(tag_ids, tags_dict)` - Combine tag categories

#### `whale_worker/db_categorization.py` (NEW)
- `get_tag_category_mapping(tag_id)` - DB lookup helper
- `save_tag_category_mapping(tag_id, categories, label, slug)` - DB save helper

#### `whale_worker/types.py` (TO MODIFY)
```python
@dataclass
class MarketMetadata:
    # ... existing fields ...
    categories: List[str] = field(default_factory=list)  # ADD THIS
```

#### `whale_worker/polymarket_client.py` (TO MODIFY)
- In `_parse_gamma_market_response()`:
  - After extracting tag_ids, call `get_market_categories(tag_ids, tags_dict)`
  - Add `categories=market_categories` to MarketMetadata

#### `whale_worker/filters.py` (TO MODIFY)
- Update `trade_matches_user_filter()`:
  - Check if user has `selectedCategories` configured
  - If yes, check intersection: `set(market.categories) & set(user_filter.selected_categories)`
  - If no intersection and user has selected categories → return False

#### `whale_worker/main.py` (TO MODIFY)
- After fetching market metadata, ensure categories are populated
- Categories should already be set in `_parse_gamma_market_response()`

### 3. Frontend Files

#### `src/app/app/page.tsx` (TO MODIFY)
- Replace `excludeCategories` state with `selectedCategories: string[]`
- Update UI to show toggles for all 13 categories:
  - Politics, Sports, Crypto, Finance, Geopolitics, Earnings, Tech, Culture, World, Economy, Trump, Elections, Mentions
- Update save handler to send `selectedCategories` instead of `excludeCategories`

#### `src/app/api/whale-alerts/config/route.ts` (TO MODIFY)
- Update GET handler to return `selectedCategories` instead of `excludeCategories`
- Update PUT handler to accept and validate `selectedCategories: string[]`
- Update MongoDB schema to store `selectedCategories`

### 4. Database Schema

#### MongoDB Collection: `tagCategoryMappings`
```javascript
{
  _id: "123",  // tag_id (string)
  categories: ["Politics", "Elections"],  // string[]
  label: "Presidential Elections",  // string
  slug: "presidential-elections",  // string
  inferredAt: ISODate,  // when first categorized
  updatedAt: ISODate  // last update
}
```

#### MongoDB Collection: `whaleAlertConfigs` (UPDATE)
```javascript
{
  userId: "...",
  // ... existing fields ...
  selectedCategories: ["Politics", "Crypto", "Finance"],  // ADD THIS (replaces excludeCategories)
  // Remove: excludeCategories
  // Remove: categoryFilter (tag IDs)
}
```

## Implementation Checklist

### Phase 1: Core Categorization Logic
- [ ] Implement `infer_categories_from_tag()` in `categorization.py`
- [ ] Implement `get_tag_category_mapping()` in `db_categorization.py`
- [ ] Implement `save_tag_category_mapping()` in `db_categorization.py`
- [ ] Implement `get_tag_categories()` in `categorization.py`
- [ ] Implement `get_market_categories()` in `categorization.py`

### Phase 2: Worker Integration
- [ ] Add `categories` field to `MarketMetadata` in `types.py`
- [ ] Update `_parse_gamma_market_response()` to call `get_market_categories()`
- [ ] Test categorization on sample markets

### Phase 3: Filter Updates
- [ ] Add `selectedCategories` to `UserFilter` in `types.py`
- [ ] Update `trade_matches_user_filter()` to check category intersection
- [ ] Update `get_all_user_filters()` to include `selectedCategories`

### Phase 4: API Updates
- [ ] Update config API GET to return `selectedCategories`
- [ ] Update config API PUT to accept `selectedCategories`
- [ ] Update MongoDB schema migration (if needed)

### Phase 5: UI Updates
- [ ] Replace `excludeCategories` with `selectedCategories` in state
- [ ] Create UI toggles for all 13 categories
- [ ] Update save handler to send new format
- [ ] Test end-to-end flow

## Category List (13 total)
1. Politics
2. Sports
3. Crypto
4. Finance
5. Geopolitics
6. Earnings
7. Tech
8. Culture
9. World
10. Economy
11. Trump
12. Elections
13. Mentions

## Key Design Decisions

1. **Inclusion vs Exclusion**: Users select which categories they WANT (inclusion), not which to exclude
2. **Multiple Categories**: A tag/market can belong to multiple categories
3. **Caching**: Tag categorizations are cached in MongoDB to avoid re-inference
4. **Inference**: Keyword-based matching on tag label and slug
5. **Union Logic**: Market categories = union of all tag categories

