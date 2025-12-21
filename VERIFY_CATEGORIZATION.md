# Verifying Categorization System

This guide helps you verify that the categorization system is working correctly.

## Quick Verification Methods

### Method 1: Run Python Diagnostic Script (Recommended)

```bash
cd /Users/wangstefan/pm-wallet-tracker
python scripts/verify-categorization.py
```

This script will check:
1. ✅ User configs have `selectedCategories` set
2. ✅ Markets have `categories` field populated
3. ✅ Tag category mappings exist
4. ✅ Sample market categorization works
5. ✅ Filter matching logic works

### Method 2: MongoDB Queries

#### Option A: Using mongosh

```bash
mongosh <your-db-name> scripts/check-categorization-mongo.js
```

#### Option B: Manual MongoDB Queries

```javascript
// 1. Check user configs
db.whaleAlertConfigs.find({}).forEach(config => {
  print(`User: ${config.userId}`);
  print(`  selectedCategories: ${JSON.stringify(config.selectedCategories || [])}`);
  print(`  excludeCategories: ${JSON.stringify(config.excludeCategories || [])}`);
  print(`  enabled: ${config.enabled}`);
  print('');
});

// 2. Check markets with/without categories
print(`Markets WITH categories: ${db.marketMetadata.countDocuments({ categories: { $exists: true, $ne: [] } })}`);
print(`Markets WITHOUT categories: ${db.marketMetadata.countDocuments({ $or: [{ categories: { $exists: false } }, { categories: [] }] })}`);

// 3. Sample a market
db.marketMetadata.findOne({ conditionId: "<some-condition-id>" });

// 4. Check tag mappings
print(`Total tag mappings: ${db.tagCategoryMappings.countDocuments({})}`);
db.tagCategoryMappings.findOne({});
```

## What to Look For

### ✅ Healthy State

1. **User Configs:**
   - Users have `selectedCategories: ["Politics", "Crypto", ...]` set
   - OR `selectedCategories: []` (means all categories allowed)
   - Legacy `excludeCategories` should be migrated automatically

2. **Markets:**
   - Most markets have `categories: ["Sports", ...]` populated
   - Markets with `tagIds` but no `categories` will get them derived on next load

3. **Tag Mappings:**
   - `tagCategoryMappings` collection has entries
   - Each entry has `_id` (tagId), `categories`, `label`, `slug`

### ⚠️ Issues to Watch For

1. **All trades passing through:**
   - Check if `selectedCategories` is empty → This means "all categories allowed"
   - Solution: User needs to select categories in UI

2. **Markets without categories:**
   - Old cached markets might not have categories
   - Solution: Categories will be derived automatically on next load (fixed in code)

3. **No tag mappings:**
   - Tag mappings are created automatically as tags are categorized
   - First time a tag is seen, it will be categorized and cached

## Common Issues and Solutions

### Issue: "Trades still passing through even though I selected categories"

**Check:**
```javascript
// Check if user has selectedCategories set
db.whaleAlertConfigs.findOne({ userId: "<your-user-id>" });
```

**Solution:**
- If `selectedCategories` is empty or missing → User needs to select categories in UI
- If `selectedCategories` has values → Check if markets have categories (see below)

### Issue: "Markets don't have categories"

**Check:**
```javascript
// Find markets without categories
db.marketMetadata.find({ 
  $or: [
    { categories: { $exists: false } },
    { categories: [] }
  ],
  tagIds: { $exists: true, $ne: [] }
}).limit(5);
```

**Solution:**
- Categories will be derived automatically when market is loaded next time
- The fix in `get_or_upsert_market()` handles this automatically

### Issue: "No tag mappings exist"

**Check:**
```javascript
db.tagCategoryMappings.countDocuments({});
```

**Solution:**
- Tag mappings are created automatically when tags are first categorized
- Check worker logs for `[DEBUG] New tag categorized` messages
- Mappings will be created as markets are processed

## Testing Filter Logic

To test if filter matching works:

```python
# Run this in Python shell
from whale_worker.filters import trade_matches_user_filter
from whale_worker.types import Trade, MarketMetadata, UserFilter

# Create test trade
trade = Trade(
    transaction_hash="0x123",
    proxy_wallet="0xabc",
    side="BUY",
    size=100.0,
    price=0.5,
    condition_id="condition123"
)

# Create test market
market = MarketMetadata(
    condition_id="condition123",
    title="Test Market",
    tag_ids=["123", "456"],
    categories=["Sports"]  # Test with different categories
)

# Create test filter
user_filter = UserFilter(
    user_id="test",
    min_notional_usd=1000,
    min_price=0.0,
    max_price=1.0,
    sides=["BUY"],
    selected_categories=["Politics", "Crypto"]  # No match with "Sports"
)

# Test
result = trade_matches_user_filter(trade, market, user_filter)
print(f"Match: {result}")  # Should be False (Sports not in selected)
```

## Monitoring Worker Logs

Watch for these log messages:

```
✅ Loaded X tagCategoryMappings, example: {...}
🔍 [DEBUG] New tag categorized: tagId=..., label='...', inferredCategories=[...]
```

If you see markets being processed but no categories, check:
1. Are tagIds present on the market?
2. Are tag mappings being created?
3. Is `derive_categories_for_market()` being called?

