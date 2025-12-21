# Type Changes for Categorization System

## 1. MarketMetadata (whale_worker/types.py)

### Current:
```python
@dataclass
class MarketMetadata:
    condition_id: str
    title: str
    slug: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    category: Optional[str] = None  # deprecated
    subcategory: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    tag_ids: List[str] = field(default_factory=list)
    is_sports: bool = False
```

### Add:
```python
@dataclass
class MarketMetadata:
    # ... existing fields ...
    categories: List[str] = field(default_factory=list)  # NEW: e.g., ["Politics", "Elections"]
```

## 2. UserFilter (whale_worker/types.py)

### Current:
```python
@dataclass
class UserFilter:
    user_id: str
    min_notional_usd: float
    min_price: float
    max_price: float
    sides: List[str]
    markets_filter: List[str] = field(default_factory=list)
    category_filter: List[str] = field(default_factory=list)  # OLD: tag IDs
    exclude_categories: List[str] = field(default_factory=list)  # OLD: exclude list
    enabled: bool = True
    telegram_chat_id: Optional[str] = None
```

### Change to:
```python
@dataclass
class UserFilter:
    user_id: str
    min_notional_usd: float
    min_price: float
    max_price: float
    sides: List[str]
    markets_filter: List[str] = field(default_factory=list)
    selected_categories: List[str] = field(default_factory=list)  # NEW: inclusion list
    enabled: bool = True
    telegram_chat_id: Optional[str] = None
    # REMOVE: category_filter
    # REMOVE: exclude_categories
```

## 3. Frontend State (src/app/app/page.tsx)

### Current:
```typescript
const [alertConfig, setAlertConfig] = useState({
  minNotionalUsd: 10000,
  minPrice: 0.05,
  maxPrice: 0.95,
  sides: ['BUY', 'SELL'] as ('BUY' | 'SELL')[],
  excludeCategories: [] as string[],  // OLD
  categoryFilter: [] as string[],  // OLD
  enabled: false,
});
```

### Change to:
```typescript
const [alertConfig, setAlertConfig] = useState({
  minNotionalUsd: 10000,
  minPrice: 0.05,
  maxPrice: 0.95,
  sides: ['BUY', 'SELL'] as ('BUY' | 'SELL')[],
  selectedCategories: [] as string[],  // NEW: inclusion list
  // REMOVE: excludeCategories
  // REMOVE: categoryFilter
  // REMOVE: enabled
});
```

## 4. MongoDB Schema (whaleAlertConfigs collection)

### Current:
```javascript
{
  userId: "...",
  minNotionalUsd: 10000,
  minPrice: 0.05,
  maxPrice: 0.95,
  sides: ["BUY", "SELL"],
  excludeCategories: ["sports"],  // OLD
  categoryFilter: ["123", "456"],  // OLD: tag IDs
  enabled: true,  // OLD
  createdAt: ISODate,
  updatedAt: ISODate
}
```

### Change to:
```javascript
{
  userId: "...",
  minNotionalUsd: 10000,
  minPrice: 0.05,
  maxPrice: 0.95,
  sides: ["BUY", "SELL"],
  selectedCategories: ["Politics", "Crypto", "Finance"],  // NEW
  createdAt: ISODate,
  updatedAt: ISODate
  // REMOVE: excludeCategories
  // REMOVE: categoryFilter
  // REMOVE: enabled
}
```

## 5. New MongoDB Collection (tagCategoryMappings)

### Schema:
```javascript
{
  _id: "123",  // tag_id (string, primary key)
  categories: ["Politics", "Elections"],  // string[]
  label: "Presidential Elections",  // string
  slug: "presidential-elections",  // string
  inferredAt: ISODate,  // when first categorized
  updatedAt: ISODate  // last update
}
```

## Summary of Changes

### Add:
- `MarketMetadata.categories: List[str]`
- `UserFilter.selected_categories: List[str]`
- Frontend `alertConfig.selectedCategories: string[]`
- MongoDB collection `tagCategoryMappings`

### Remove:
- `UserFilter.category_filter` (tag IDs)
- `UserFilter.exclude_categories` (exclusion list)
- `UserFilter.enabled` (always enabled if configured)
- Frontend `alertConfig.excludeCategories`
- Frontend `alertConfig.categoryFilter`
- Frontend `alertConfig.enabled`

### Change Logic:
- **Before**: Users exclude categories they don't want
- **After**: Users select categories they DO want (inclusion filter)

