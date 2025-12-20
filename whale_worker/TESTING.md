# Testing the Whale Worker

## Step 1: Trade Polling ✅

### Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables in `.env.local`:**
   ```
   MONGODB_URI=your_mongodb_uri
   MONGODB_DB_NAME=pm-wallet-tracker
   TELEGRAM_BOT_TOKEN=your_bot_token
   GLOBAL_MIN_NOTIONAL_USD=0  # Set to 0 to fetch all trades, or set minimum
   POLL_INTERVAL_SECONDS=10
   MAX_TRADES_PER_POLL=1000
   ```

### Run the Worker

```bash
python -m whale_worker.main
# or
npm run dev:worker
```

### Expected Output

```
🚀 Starting whale worker
   Poll interval: 10s
   Min notional filter: $0.00
   Max trades per poll: 1000
✅ Connected to MongoDB
📍 No previous marker - will process all new trades from now on

📊 Poll #1 - Fetching trades...
   Fetched 100 trades from API
   Found 100 new trades to process
   [1/100] Trade 0x1234abcd... | $15,234.50 | BUY | 65.00% | Market: Will X happen? | politics | tags: election, president
   [2/100] Trade 0x5678efgh... | $8,900.00 | SELL | 45.00% | Market: Bitcoin Price | crypto | tags: bitcoin, crypto
   ...
   ✅ Updated marker: timestamp=1734567890

   ⏳ Sleeping for 10s...

📊 Poll #2 - Fetching trades...
   Fetched 5 trades from API
   Found 5 new trades to process
   ...
```

## Step 2: Market Metadata Fetching ✅

### What It Does

1. **For each trade**, the worker:
   - Checks MongoDB cache for market metadata (keyed by `conditionId`)
   - If not cached or cache expired (>24 hours), fetches from Gamma API
   - Stores metadata in MongoDB for future use

2. **Gamma API Call:**
   ```
   GET https://gamma-api.polymarket.com/markets
   ?condition_ids={conditionId}
   &include_tag=true
   &closed=false
   &limit=1
   ```

3. **Extracts:**
   - Title/question
   - Slug
   - Tags (for classification)
   - Category (inferred from tags)
   - Description, image URL

4. **Caching:**
   - Markets are cached in `marketMetadata` collection
   - Cache TTL: 24 hours (configurable)
   - Reduces API calls significantly

## Step 3: Market Categorization ✅

### What It Does

1. **For each trade**, the worker:
   - Checks MongoDB cache for market metadata (keyed by `conditionId`)
   - If not cached or cache expired (>24 hours), fetches from Gamma API
   - Stores metadata in MongoDB for future use

2. **Gamma API Call:**
   ```
   GET https://gamma-api.polymarket.com/markets
   ?condition_ids={conditionId}
   &include_tag=true
   &closed=false
   &limit=1
   ```

3. **Extracts:**
   - Title/question
   - Slug
   - Tags (for classification)
   - Category (inferred from tags)
   - Description, image URL

4. **Caching:**
   - Markets are cached in `marketMetadata` collection
   - Cache TTL: 24 hours (configurable)
   - Reduces API calls significantly

### Verifying in MongoDB

Check cached market metadata:

```javascript
// In MongoDB shell or Compass
db.marketMetadata.findOne({ conditionId: "0x..." })
```

Should show:
```json
{
  "_id": ObjectId("..."),
  "conditionId": "0x...",
  "title": "Will X happen?",
  "slug": "will-x-happen",
  "tags": ["politics", "election"],
  "category": "politics",
  "updatedAt": ISODate("2025-12-18T..."),
  "createdAt": ISODate("2025-12-18T...")
}
```

### Troubleshooting

**Error: "Failed to fetch market metadata"**
- Check if Gamma API is accessible
- Verify API endpoint URL is correct
- Some markets may not exist (returns None)

**Markets not being cached:**
- Check MongoDB connection
- Verify `marketMetadata` collection exists
- Check for write permissions

**Category not detected:**
- Tags are used to infer category
- If no matching tags, category will be None
- You can manually add category filters later

### What It Does

1. **At startup**, the worker:
   - Fetches all sports from `/sports` endpoint
   - Extracts all tag IDs from sports (comma-separated strings)
   - Builds `SPORTS_TAG_IDS` set
   - Fetches all tags from `/tags` endpoint
   - Builds `tags_dict`: `tag_id -> {label, slug, ...}`
   - Caches both in MongoDB (`gammaCache` collection)

2. **For each market**, the worker:
   - Extracts tag IDs from market metadata
   - Checks if any tag ID intersects with `SPORTS_TAG_IDS` → marks as sports
   - Uses `tags_dict` to get tag labels for display
   - Stores `tag_ids` and `is_sports` flag in market metadata

3. **Categorization Logic:**
   - **Sports**: If any market tag ID is in `SPORTS_TAG_IDS` → `is_sports = True`
   - **Other categories**: Exposed via tags (politics, crypto, etc. inferred from tag labels)
   - **Tags are many-to-many**: A market can have multiple tags/categories

4. **Caching:**
   - Sports tag IDs and tags dictionary cached in `gammaCache` collection
   - Refreshed at startup (or periodically)
   - Reduces API calls significantly

### Expected Output

```
📋 Loading market categorization data...
   Fetching sports tag IDs from Gamma API...
   ✅ Fetched 94 sports, found 150 unique sports tag IDs
   Fetching tags dictionary from Gamma API...
   ✅ Fetched 500 tags
   ✅ Loaded 150 sports tag IDs, 500 tags

📊 Poll #1 - Fetching trades...
   [1/100] Trade 0x1234abcd... | $15,234.50 | BUY | 65.00% | 
   Market: Super Bowl Winner? | 🏈 SPORTS | tags: NFL, Football, Super Bowl
   [2/100] Trade 0x5678efgh... | $8,900.00 | SELL | 45.00% | 
   Market: Bitcoin Price | crypto | tags: Crypto, Bitcoin
```

### Verifying in MongoDB

Check cached categorization data:

```javascript
// Sports tag IDs
db.gammaCache.findOne({ _id: "sports_tag_ids" })

// Tags dictionary
db.gammaCache.findOne({ _id: "tags_dictionary" })

// Market with categorization
db.marketMetadata.findOne({ conditionId: "0x..." })
// Should show: tagIds, isSports, tags
```

## Step 4: Match Trades Against User Filters ✅

### What It Does

1. **At startup**, the worker:
   - Loads all active user filters from MongoDB
   - Joins with `telegramAccounts` to get chat IDs
   - Only includes filters where `enabled=True` and user has active Telegram

2. **For each trade**, the worker:
   - Applies user filter rules:
     - ✅ `notional >= minNotional`
     - ✅ `price in [minPrice, maxPrice]`
     - ✅ `side in user's sides list`
     - ✅ `excludeSports` → drop if `market.is_sports == True`
     - ✅ `excludeCategories` → drop if market category matches
     - ✅ `category_filter` (include tag IDs) → require overlap with market tag IDs
     - ✅ `markets_filter` → require condition_id in list

3. **Filter Matching Logic:**
   - All conditions must pass for a trade to match
   - Returns list of matching users for each trade
   - Logs matches for debugging

### Expected Output

```
👥 Loading user filters...
   ✅ Loaded 3 active user filters

📊 Poll #1 - Fetching trades...
   [1/100] Trade 0x1234abcd... | $15,234.50 | BUY | 65.00% | 
   Market: Super Bowl Winner? | 🏈 SPORTS | tags: NFL, Football
      🔔 Matches 2 user(s): user1234, user5678
   [2/100] Trade 0x5678efgh... | $8,900.00 | SELL | 45.00% | 
   Market: Bitcoin Price | crypto | tags: Crypto, Bitcoin
      ⏭️  No matching users
```

### Filter Rules

**User Filter Example:**
```json
{
  "userId": "user123",
  "minNotionalUsd": 10000,
  "minPrice": 0.05,
  "maxPrice": 0.95,
  "sides": ["BUY", "SELL"],
  "excludeCategories": ["sports"],
  "categoryFilter": ["766"],  // Tag IDs to include
  "enabled": true
}
```

**Matching Logic:**
1. Trade notional >= $10,000 ✅
2. Trade price between 5% and 95% ✅
3. Trade side is BUY or SELL ✅
4. Market is NOT sports (excludeCategories) ✅
5. Market has tag ID "766" (categoryFilter) ✅
6. → **MATCH** → Send alert to user

### Verifying in MongoDB

Check user filters:

```javascript
// All enabled filters
db.whaleAlertConfigs.find({ enabled: true })

// With Telegram accounts
db.whaleAlertConfigs.aggregate([
  { $match: { enabled: true } },
  { $lookup: {
      from: "telegramAccounts",
      localField: "userId",
      foreignField: "userId",
      as: "telegram"
    }
  },
  { $match: { "telegram.isActive": true } }
])
```

## Step 5: Send Telegram Notifications ✅

### What It Does

1. **For each matching user**, the worker:
   - Builds a formatted Telegram message with trade and market details
   - Sends message via Telegram Bot API to user's `chatId`
   - Handles rate limiting (429 errors) with automatic retry
   - Handles errors (403 = blocked, 400 = invalid chat_id)
   - Adds small delay between sends to respect rate limits

2. **Message Format:**
   - 🐋 Whale Trade Alert header
   - Market title and category/tags
   - Trade details (side, notional, size, price)
   - Trader wallet address (with link to Polymarket profile)
   - Link to market on Polymarket

3. **Error Handling:**
   - Rate limiting: Automatically waits and retries
   - Blocked users: Logs and continues
   - Invalid chat IDs: Logs and continues
   - Network errors: Logs and continues

### Expected Output

```
   [1/100] Trade 0x1234abcd... | $15,234.50 | BUY | 65.00% | 
   Market: Super Bowl Winner? | 🏈 SPORTS | tags: NFL, Football
      🔔 Matches 2 user(s): user1234, user5678
      ✅ Sent 2 alert(s)
   [2/100] Trade 0x5678efgh... | $8,900.00 | SELL | 45.00% | 
   Market: Bitcoin Price | crypto | tags: Crypto, Bitcoin
      ⏭️  No matching users
```

### Telegram Message Example

```
🐋 Whale Trade Alert!

📊 Market: Will Trump win the 2024 election?
Politics
🏷️ Tags: Politics, Election, US

💰 Trade Details:
🟢 BUY $15,234.50 @ 65.0%
Size: 23,437.69 | Price: 65.00%

👤 Trader: 0xabcd...7890

🔗 View Market on Polymarket
```

### Rate Limiting

- Telegram allows ~30 messages/second
- Worker adds 0.05s delay between sends (20 messages/second)
- Automatically handles 429 rate limit errors with retry

### Error Handling

**403 Forbidden:**
- User blocked the bot
- Logged and skipped (user won't receive alerts)

**400 Bad Request:**
- Invalid chat_id
- Logged and skipped

**429 Too Many Requests:**
- Rate limited
- Automatically waits for `retry_after` seconds and retries once

**Network Errors:**
- Timeouts and connection errors
- Logged and skipped

### Verifying Notifications

1. **Check Telegram:**
   - Users should receive messages in their Telegram chat
   - Messages should be formatted with HTML (bold, links)

2. **Check Logs:**
   - Worker logs show "✅ Sent X alert(s)" for successful sends
   - Worker logs show "❌ Failed to send X alert(s)" for failures

3. **Test with Test Notification:**
   - Use the "Test notification" button in the web UI
   - Should receive a test message immediately

### Configuration

Ensure `.env.local` has:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

The bot token is obtained from @BotFather on Telegram.

### Complete Workflow

1. ✅ Poll trades from Data API
2. ✅ Fetch market metadata from Gamma API
3. ✅ Categorize markets (sports detection, tags)
4. ✅ Match trades against user filters
5. ✅ Send Telegram notifications to matching users

**The whale worker is now fully functional! 🎉**
