# Complete Whale Trade Alert Workflow - Technical Deep Dive

## Overview

This document provides a comprehensive, step-by-step technical workflow of the whale trade alert system, from initial Telegram connection through to notification delivery. Every component, data flow, and decision point is documented in detail.

---

## Phase 1: Telegram Connection & Authentication

### Step 1.1: User Initiates Connection (Frontend)

**Location**: `src/app/app/page.tsx` (Whale Alerts tab)

**User Action**: 
- User clicks "Connect Telegram" button
- User must be authenticated (logged in via NextAuth)

**Frontend Process**:
1. Checks if user has active session (`useSession()` hook)
2. If not authenticated, redirects to login
3. Calls `POST /api/telegram/connect-token` API endpoint
4. Displays loading state while waiting for response

**Data Flow**:
```
User Click → Frontend API Call → POST /api/telegram/connect-token
```

---

### Step 1.2: Token Generation (Backend API)

**Location**: `src/app/api/telegram/connect-token/route.ts`

**API Endpoint**: `POST /api/telegram/connect-token`

**Authentication Check**:
1. Calls `auth()` from NextAuth to get session
2. Verifies `session?.user?.id` exists
3. Returns `401 Unauthorized` if no session

**Index Initialization**:
1. Calls `ensureTelegramTokenIndexes()` from `lib/telegram-tokens-indexes.ts`
2. **Unique Index Creation**:
   - Creates unique index on `token` field
   - Index name: `token_unique_idx`
   - Prevents duplicate tokens at database level
   - If index exists, skips creation (idempotent)
3. **TTL Index Creation**:
   - Creates TTL index on `expiresAt` field
   - Index name: `expiresAt_ttl_idx`
   - `expireAfterSeconds: 0` (deletes immediately when expired)
   - MongoDB automatically deletes expired documents every ~60 seconds
   - If index exists, skips creation (idempotent)

**Token Generation**:
1. Generates secure random token: `randomBytes(32).toString('hex')`
   - 32 bytes = 64 hexadecimal characters
   - Cryptographically secure random number
2. Calculates expiration: `Date.now() + TOKEN_EXPIRY_MS`
   - `TOKEN_EXPIRY_MS = 5 * 60 * 1000` (5 minutes)
   - Token expires 5 minutes after creation

**Database Storage**:
1. Connects to MongoDB using `clientPromise` (singleton connection)
2. Accesses database: `process.env.MONGODB_DB_NAME || 'pm-wallet-tracker'`
3. Inserts document into `telegramConnectTokens` collection:
   ```javascript
   {
     token: "64-char-hex-string",
     userId: "user-mongodb-objectid",
     expiresAt: Date, // 5 minutes from now
     createdAt: Date,
     used: false
   }
   ```
4. **Unique Constraint**: Database enforces uniqueness on `token` field
5. **TTL Cleanup**: MongoDB will auto-delete this document when `expiresAt` is reached

**Cleanup**:
1. Deletes used tokens: `deleteMany({ used: true })`
   - Runs asynchronously (doesn't block response)
   - TTL index handles expired tokens automatically
   - Manual cleanup only needed for `used: true` tokens

**Response**:
```json
{
  "token": "64-char-hex-string",
  "expiresIn": 300  // seconds
}
```

**Error Handling**:
- Database errors: Returns `500 Internal Server Error`
- Logs error details for debugging
- Token generation failures are caught and handled gracefully

---

### Step 1.3: Deep Link Creation (Frontend)

**Location**: `src/app/app/page.tsx`

**Process**:
1. Receives token from API response
2. Constructs Telegram deep link:
   ```
   https://t.me/PM_Intel_bot?start={token}
   ```
   - `PM_Intel_bot` is the bot username (from `TELEGRAM_BOT_USERNAME` env var)
   - `{token}` is the 64-character hex token
3. Opens link in new window/tab
4. User is redirected to Telegram (app or web)

**Security Note**: Token is one-time use, expires in 5 minutes, and is linked to authenticated user ID

---

### Step 1.4: Telegram Bot Receives /start Command

**Location**: `lib/telegram-bot.ts`

**Bot Initialization** (Lazy, Serverless-Safe):

**Development Mode**:
- Uses `globalThis._telegramBot` to persist across HMR reloads
- Only initializes if `TELEGRAM_USE_POLLING=true` env var is set
- Uses polling to receive updates

**Production Mode**:
- Uses module-level variable (no global)
- No polling (webhook-only)
- Bot initialized only when webhook endpoint is called

**Handler Registration** (`setupHandlers()` function):
1. Registers `/start` command handler with regex: `/\/start(?: (.+))?/`
2. Extracts token from command: `/start {token}`
3. Handler is registered only once (checked via `_telegramBotHandlersInitialized` flag)

**Index Initialization**:
1. Calls `ensureTelegramTokenIndexes()` before accessing collection
2. Ensures indexes exist (idempotent, only runs once per process)

**Token Verification**:
1. Connects to MongoDB using `clientPromise`
2. Queries `telegramConnectTokens` collection:
   ```javascript
   {
     token: providedToken,
     used: false,
     expiresAt: { $gt: new Date() }  // Not expired
   }
   ```
3. **Index Usage**:
   - Unique index on `token` speeds up lookup
   - Query is fast even with many tokens
4. If token not found or expired:
   - Sends error message to user
   - Returns early (doesn't proceed with connection)

**Token Marking**:
1. If token is valid, marks it as used:
   ```javascript
   updateOne(
     { token: token },
     { $set: { used: true, usedAt: new Date() } }
   )
   ```
2. Token cannot be reused (security)

**Account Linking**:
1. Retrieves `userId` from token document
2. Upserts document in `telegramAccounts` collection:
   ```javascript
   {
     userId: "from-token-document",
     chatId: "from-telegram-message",
     username: "from-telegram-message (optional)",
     isActive: true,
     connectedAt: Date,
     createdAt: Date (on insert only),
     updatedAt: Date
   }
   ```
3. **Connection Established**: `chatId` is now linked to `userId`

**Confirmation Message**:
1. Sends success message to user via Telegram
2. User is now connected and can receive alerts

**Error Handling**:
- Invalid token: Sends error message, doesn't link account
- Expired token: Sends error message, suggests getting new link
- Database errors: Logged, user notified
- Bot API errors: Handled gracefully

---

## Phase 2: Alert Settings Configuration

### Step 2.1: User Configures Settings (Frontend)

**Location**: `src/app/app/page.tsx` (Whale Alerts tab)

**UI Components**:
- Min Notional input (USD)
- Price Range inputs (min/max as percentages 0-100)
- Side checkboxes (Buy/Sell)
- Category filters (exclude/include)
- Enable/Disable toggle
- "Save Settings" button

**Validation** (Client-side):
- Min Notional: Must be >= 0
- Price Range: Min < Max, both 0-100
- Sides: At least one must be selected
- All inputs validated before submission

---

### Step 2.2: Settings Saved to Database (Backend API)

**Location**: `src/app/api/whale-alerts/config/route.ts` (PUT handler)

**API Endpoint**: `PUT /api/whale-alerts/config`

**Authentication**:
1. Verifies user session via `auth()`
2. Returns `401` if not authenticated

**Request Validation**:
1. Parses JSON body
2. Validates each field:
   - `minNotionalUsd`: Number >= 0
   - `minPrice`: Number 0-1 (converted from percentage)
   - `maxPrice`: Number 0-1 (converted from percentage)
   - `minPrice < maxPrice` (must be valid range)
   - `sides`: Array of "BUY" and/or "SELL"
   - `excludeCategories`: Array of strings (optional)
   - `categoryFilter`: Array of strings (tag IDs, optional)
   - `enabled`: Boolean

**Database Update**:
1. Connects to MongoDB
2. Upserts to `whaleAlertConfigs` collection:
   ```javascript
   {
     userId: "from-session",
     minNotionalUsd: number,
     minPrice: number,  // 0-1 (e.g., 0.05 for 5%)
     maxPrice: number,  // 0-1 (e.g., 0.95 for 95%)
     sides: ["BUY", "SELL"],
     excludeCategories: ["sports"],  // optional
     categoryFilter: ["tag-id-1", "tag-id-2"],  // optional
     enabled: boolean,
     updatedAt: Date,
     createdAt: Date  // only on insert
   }
   ```
3. Uses `updateOne` with `upsert: true` to create or update

**Filter Reload Signal**:
1. **Critical**: Sets reload signal in MongoDB
2. Updates `filterReloadSignals` collection:
   ```javascript
   {
     _id: "global",
     requestedAt: Date,
     requestedBy: userId
   }
   ```
3. **Purpose**: Signals worker to reload filters immediately (not wait 60 seconds)
4. Only sets signal if settings were actually updated (`modifiedCount > 0` or `upsertedCount > 0`)

**Response**:
```json
{
  "success": true,
  "updated": true
}
```

**Error Handling**:
- Validation errors: Returns `400 Bad Request` with specific error message
- Database errors: Returns `500 Internal Server Error`
- All errors logged for debugging

---

## Phase 3: Worker Initialization

### Step 3.1: Worker Startup Sequence

**Location**: `whale_worker/main.py` (`run_worker()` function)

**Entry Point**: `python3 -m whale_worker.main`

**Initialization Steps**:

#### 3.1.1: Load Configuration
**Location**: `whale_worker/config.py`

**Configuration Values**:
- `POLL_INTERVAL_SECONDS`: How often to poll (default: 10 seconds)
- `MAX_TRADES_PER_POLL`: Max trades per API call (default: 1000)
- `GLOBAL_MIN_NOTIONAL_USD`: Global minimum filter (default: 0)
- `FILTER_RELOAD_INTERVAL_SECONDS`: Periodic reload interval (default: 60 seconds)
- `MONGODB_URI`: Database connection string
- `MONGODB_DB`: Database name
- `TELEGRAM_BOT_TOKEN`: Bot API token
- `POLYMARKET_DATA_API_URL`: Data API endpoint
- `POLYMARKET_GAMMA_API_URL`: Gamma API endpoint

**Environment Variables**: Loaded from `.env` file or environment

---

#### 3.1.2: Connect to MongoDB
**Location**: `whale_worker/db.py`

**Connection Process**:
1. Creates MongoDB client singleton (reused across calls)
2. Connection settings:
   - `serverSelectionTimeoutMS: 5000` (5 seconds)
   - `connectTimeoutMS: 10000` (10 seconds)
3. Tests connection with `db.command('ping')`
4. Raises exception if connection fails

**Database Access**:
- Gets database: `client[MONGODB_DB]`
- All collections accessed via `db['collectionName']`

---

#### 3.1.3: Initialize TTL Index for Deduplication
**Location**: `whale_worker/db.py` (`ensure_processed_trades_ttl_index()`)

**Purpose**: Prevents duplicate trade processing

**Index Creation**:
1. Accesses `processedTrades` collection
2. Creates TTL index on `expiresAt` field:
   - `expireAfterSeconds: 0` (deletes immediately when expired)
   - Auto-deletes documents after TTL expires
3. TTL: 15 minutes (trades marked as processed expire after 15 min)
4. **Idempotent**: If index exists, skips creation

**Collection Structure**:
```python
{
  'txHash': 'transaction-hash',
  'expiresAt': datetime,  # 15 minutes from now
  'createdAt': datetime
}
```

---

#### 3.1.4: Initialize Notification Queue
**Location**: `whale_worker/notification_queue.py`

**Queue Initialization**:
1. Creates `NotificationQueue` singleton
2. **Rate Limiting Configuration**:
   - Global rate limit: `0.034s` interval (~30 msg/sec)
   - Per-chat rate limit: `1.0s` interval (1 msg/sec per chat)
3. Creates worker thread (daemon thread)
4. Thread runs continuously, processing queue

**Queue Structure**:
- Thread-safe `Queue` from Python's `queue` module
- Stores tuples: `(chat_id, message)`
- Worker thread processes messages asynchronously

**Start Process**:
1. Sets `running = True`
2. Creates worker thread: `threading.Thread(target=_worker_loop, daemon=True)`
3. Starts thread: `thread.start()`
4. Thread runs in background, independent of main loop

**Shutdown Handling**:
- Registers `atexit` handler to stop queue gracefully
- On shutdown: Sets `running = False`, joins thread with timeout

---

#### 3.1.5: Load Market Categorization Data
**Location**: `whale_worker/polymarket_client.py`

**Sports Tag IDs**:
1. **Cache Check**: Tries to get from MongoDB `sportsTagIds` collection
2. **Cache Hit**: Returns cached data if exists and not expired (24h TTL)
3. **Cache Miss**: Fetches from Gamma API `/sports` endpoint
4. **API Call**: `GET https://gamma-api.polymarket.com/sports`
5. **Processing**:
   - Extracts all sport objects from response
   - Collects all `tagIds` from all sports
   - Creates set of unique tag IDs
   - Used to identify sports markets
6. **Cache Storage**: Stores in MongoDB with 24h TTL
7. **Result**: Set of tag IDs (e.g., `{"tag-id-1", "tag-id-2", ...}`)

**Tags Dictionary**:
1. **Cache Check**: Tries to get from MongoDB `tagsDictionary` collection
2. **Cache Hit**: Returns cached data if exists and not expired (24h TTL)
3. **Cache Miss**: Fetches from Gamma API `/tags` endpoint
4. **API Call**: `GET https://gamma-api.polymarket.com/tags?limit=100`
5. **Processing**:
   - Maps each tag to its metadata
   - Creates dictionary: `{tagId: {label, slug, ...}}`
   - Used for tag lookups and categorization
6. **Cache Storage**: Stores in MongoDB with 24h TTL
7. **Result**: Dictionary mapping tag IDs to metadata

**Caching Benefits**:
- Reduces API calls (only fetch once per 24 hours)
- Faster worker startup (uses cached data)
- Handles API failures gracefully (uses cache if API fails)

---

#### 3.1.6: Load User Filters
**Location**: `whale_worker/db.py` (`get_all_user_filters()`)

**Query Process**:
1. Queries `whaleAlertConfigs` collection:
   - Filter: `{ enabled: True }`
   - Only gets enabled configurations
2. For each config:
   - Gets `userId` from config
   - Queries `telegramAccounts` collection:
     - Filter: `{ userId: userId, isActive: True }`
     - Gets `chatId` for Telegram notifications
   - Skips if no active Telegram connection
3. Builds `UserFilter` objects:
   ```python
   UserFilter(
       user_id=str,
       min_notional_usd=float,
       min_price=float,  # 0-1
       max_price=float,  # 0-1
       sides=["BUY", "SELL"],
       markets_filter=[],  # optional
       category_filter=[],  # optional (tag IDs)
       exclude_categories=[],  # optional
       enabled=bool,
       telegram_chat_id=str
   )
   ```
4. Returns list of active user filters

**Initial Load**: Happens once at startup
**Reload Mechanism**: Filters reloaded periodically (see Phase 4)

---

#### 3.1.7: Load Last Processed Trade Marker
**Location**: `whale_worker/db.py` (`get_last_processed_trade_marker()`)

**Purpose**: Prevents re-processing trades on worker restart

**Query Process**:
1. Queries `lastProcessedTradeMarker` collection
2. Gets document with `_id: 'whale_worker_global'` (fixed ID for global cursor)
3. If document exists:
   - Extracts `lastProcessedTimestamp` (Unix timestamp)
   - Extracts `lastProcessedTxhash` (transaction hash)
   - Returns `TradeMarker` object
4. If document doesn't exist:
   - Returns `None` (no previous processing)
   - Worker will process all new trades from now on

**Cursor Structure**:
```python
TradeMarker(
    last_processed_timestamp=int,  # Unix timestamp
    last_processed_tx_hash=str,    # Transaction hash
    updated_at=datetime
)
```

**Usage**: Used to fetch only trades newer than last processed trade

---

### Step 3.2: Worker Ready State

**After Initialization**:
- ✅ MongoDB connected
- ✅ Notification queue running
- ✅ Market categorization data loaded
- ✅ User filters loaded
- ✅ Cursor loaded (or None if first run)
- ✅ Ready to start polling loop

**Logging**: All initialization steps logged with ✅ or ❌ indicators

---

## Phase 4: Trade Polling Loop

### Step 4.1: Poll Cycle Start

**Location**: `whale_worker/main.py` (main `while True` loop)

**Frequency**: Every `POLL_INTERVAL_SECONDS` (default: 10 seconds)

**Poll Counter**: Increments on each cycle for logging

---

### Step 4.2: Filter Reload Check (CRITICAL - Happens FIRST)

**Location**: `whale_worker/main.py` (before fetching trades)

**Why First**: Ensures new filters are used for all trades in this poll cycle

**Reload Triggers**:

#### 4.2.1: Immediate Reload Signal
1. Checks `filterReloadSignals` collection:
   - Query: `{ _id: 'global' }`
   - If document exists: Signal is set
2. **If Signal Exists**:
   - Sets `should_reload = True`
   - Sets `reload_reason = "settings changed"`
   - **This happens on every poll cycle** (not just every 60s)
   - Ensures immediate response to settings changes

#### 4.2.2: Periodic Reload
1. Checks if `FILTER_RELOAD_INTERVAL_SECONDS` has elapsed since last reload
2. **If Interval Elapsed**:
   - Sets `should_reload = True`
   - Sets `reload_reason = "periodic refresh"`
   - Fallback mechanism (in case signal is missed)

**Reload Process** (if `should_reload = True`):
1. Calls `get_all_user_filters()` to fetch latest from MongoDB
2. **Change Detection**:
   - Compares count of filters
   - Compares actual filter values:
     - `min_notional_usd`
     - `min_price`, `max_price`
     - `sides` (set comparison)
     - `enabled` status
   - Detects if any values actually changed
3. Updates in-memory `all_user_filters` list
4. Updates `last_filter_reload` timestamp
5. **Clears Signal**: If reload was triggered by signal, clears it from MongoDB
6. **Logging**:
   - Logs if values changed
   - Logs new filter values (e.g., "New minNotional: $300.00")

**Result**: `all_user_filters` now contains latest filter configurations

---

### Step 4.3: Fetch Recent Trades

**Location**: `whale_worker/polymarket_client.py` (`fetch_recent_trades()`)

**API Call**:
```
GET https://data-api.polymarket.com/trades
```

**Query Parameters**:
- `takerOnly=true`: Only taker trades (not maker)
- `limit={MAX_TRADES_PER_POLL}`: Max trades to fetch (default: 1000)
- `filterType=CASH`: Cash markets only (not credit)
- `filterAmount={GLOBAL_MIN_NOTIONAL_USD}`: Global minimum (if > 0)
- `minTimestamp={last_processed_timestamp}`: Only trades newer than cursor (if marker exists)

**Response Parsing**:
1. Receives JSON array of trade objects
2. For each trade object:
   - Extracts `transactionHash` (required, skip if missing)
   - Extracts `proxyWallet` (trader address)
   - Extracts `side` ("BUY" or "SELL")
   - Extracts `size` (trade size)
   - Extracts `price` (trade price, 0-1)
   - Extracts `conditionId` (market identifier)
   - Extracts `timestamp` (Unix timestamp)
   - Calculates `notional = size * price`
3. Creates `Trade` objects:
   ```python
   Trade(
       transaction_hash=str,
       proxy_wallet=str,
       side="BUY" | "SELL",
       size=float,
       price=float,  # 0-1
       notional=float,  # size * price
       condition_id=str,
       timestamp=int  # Unix timestamp
   )
   ```
4. Deduplicates by `transaction_hash` (handles API duplicates)
5. Sorts by timestamp (newest first)

**Returns**: List of `Trade` objects (newest first)

**Error Handling**:
- API errors: Logged, returns empty list
- Timeout: 30 second timeout, returns empty list on timeout
- Network errors: Handled gracefully

---

### Step 4.4: Deduplication

**Location**: `whale_worker/main.py` (after fetching trades)

**Two-Layer Deduplication Strategy**:

#### 4.4.1: Cursor-Based Deduplication (Primary)
1. If `last_marker` exists and has `last_processed_tx_hash`:
   - Iterates through trades (newest first)
   - Stops when reaching trade with matching `transaction_hash`
   - All trades before this point are new (not yet processed)
   - Sets `seen_cursor = True` flag
2. **Edge Case**: If cursor trade not found in API response:
   - Logs warning
   - Falls back to TTL-based deduplication for all trades

#### 4.4.2: TTL-Based Deduplication (Secondary)
1. For each trade in the new trades list:
   - Calls `is_trade_processed(trade.transaction_hash)`
   - Queries `processedTrades` collection:
     ```python
     {
       'txHash': transaction_hash,
       'expiresAt': { '$gt': datetime.utcnow() }
     }
     ```
   - If document exists: Trade was processed recently (within 15 min)
   - Skips trade if already processed
2. **Purpose**: Handles edge cases:
   - Same timestamp trades
   - Worker restart scenarios
   - Cursor reset scenarios

**Result**: `new_trades` list contains only unprocessed trades

**Logging**: Logs count of new trades found

---

### Step 4.5: Batch Fetch Market Metadata (Optimization)

**Location**: `whale_worker/main.py` (before processing trades)

**Purpose**: Fetch all missing market metadata in one batch (more efficient)

#### 4.5.1: Collect Missing Markets
1. Iterates through `new_trades`
2. For each trade with `condition_id`:
   - Calls `get_or_upsert_market(condition_id)` to check cache
   - If `None` (not in cache):
     - Adds `condition_id` to `missing_condition_ids` list
     - Maps `condition_id` to list of trades (for later processing)

#### 4.5.2: Batch API Call
**Location**: `whale_worker/polymarket_client.py` (`fetch_market_metadata_batch()`)

**Process**:
1. **Attempt Batch Fetch**:
   - API Call: `GET /markets?condition_ids=id1,id2,id3&include_tag=true&closed=false&limit=N`
   - **Note**: Gamma API batch endpoint doesn't work reliably (returns empty)
   - Kept for potential future API improvements

2. **Fallback: Concurrent Individual Fetches**:
   - Uses `asyncio` and `httpx.AsyncClient` for concurrent requests
   - Creates async task for each missing `condition_id`
   - Fetches: `GET /markets?condition_ids={id}&include_tag=true&closed=false&limit=1`
   - If not found with `closed=false`, tries without `closed` parameter (includes closed markets)
   - All fetches happen in parallel (much faster than sequential)

3. **Response Parsing**:
   - For each market response:
     - Extracts `conditionId`
     - Extracts `question` (market title)
     - Extracts `slug` (market URL slug)
     - Extracts `tags` array (for categorization)
     - Extracts `tagIds` from tags
     - Determines `is_sports`: Checks if any tag ID is in `sports_tag_ids` set
     - Infers `category`: "sports", "politics", "crypto", "culture" based on tags
     - Creates `MarketMetadata` object

4. **Returns**: Dictionary mapping `condition_id` → `MarketMetadata`

#### 4.5.3: Cache Storage
1. For each fetched market:
   - Calls `get_or_upsert_market(condition_id, metadata)`
   - Stores in MongoDB `marketMetadata` collection:
     ```python
     {
       'conditionId': str,
       'title': str,
       'slug': str,
       'tags': [str],  # tag labels
       'tagIds': [str],  # tag IDs
       'isSports': bool,
       'category': str,  # optional
       'updatedAt': datetime,
       'createdAt': datetime  # on insert only
     }
     ```
2. **TTL**: 24 hours (cache expires after 24h)
3. **Benefits**: Subsequent trades for same market use cached data

**Logging**: Logs count of markets fetched

---

### Step 4.6: Process Each Trade

**Location**: `whale_worker/main.py` (main processing loop)

**Iteration**: For each trade in `new_trades` (newest first)

#### 4.6.1: Mark as Processed (Immediate)
1. Calls `mark_trade_as_processed(trade.transaction_hash)`
2. Stores in `processedTrades` collection:
   ```python
   {
     'txHash': transaction_hash,
     'expiresAt': datetime.utcnow() + timedelta(minutes=15),
     'createdAt': datetime.utcnow()
   }
   ```
3. **Purpose**: Prevents duplicate processing even if later steps fail
4. **TTL**: Document auto-deletes after 15 minutes

#### 4.6.2: Get Market Metadata
1. If trade has `condition_id`:
   - Calls `get_or_upsert_market(condition_id)`
   - Should be in cache (from batch fetch in Step 4.5)
   - Returns `MarketMetadata` object or `None`
2. **If Market Not Found** (`None`):
   - Logs trade as "Market: Unknown"
   - Skips filter matching (can't match without market)
   - Continues to next trade

#### 4.6.3: Filter Matching
**Location**: `whale_worker/filters.py` (`get_matching_users_for_trade()`)

**Process**:
1. Iterates through all user filters in `all_user_filters`
2. For each filter, calls `trade_matches_user_filter(trade, market, user_filter)`
3. **Matching Logic** (all must pass):

   **a) Filter Enabled Check**:
   - If `user_filter.enabled == False`: Skip

   **b) Notional Threshold**:
   - `trade.notional >= user_filter.min_notional_usd`
   - Trade must meet minimum value

   **c) Price Range**:
   - `user_filter.min_price <= trade.price <= user_filter.max_price`
   - Trade price must be within range

   **d) Side Check**:
   - `trade.side in user_filter.sides`
   - Trade side must be in user's allowed sides

   **e) Exclude Categories**:
   - If `"sports" in user_filter.exclude_categories`:
     - If `market.is_sports == True`: Skip trade
   - If other categories in `exclude_categories`:
     - If `market.category` matches: Skip trade

   **f) Category Filter (Include)**:
   - If `user_filter.category_filter` is not empty:
     - Checks if any `market.tag_ids` overlap with `category_filter`
     - If no overlap: Skip trade
     - Also checks legacy `category` field as fallback

   **g) Markets Filter (Specific Markets)**:
   - If `user_filter.markets_filter` is not empty:
     - Checks if `trade.condition_id in markets_filter`
     - If not in list: Skip trade

4. **If All Checks Pass**: Filter matches, user added to `matching_users` list

**Returns**: List of `UserFilter` objects for users who should receive alerts

#### 4.6.4: Send Alerts (If Matches Found)
**Location**: `whale_worker/notifications.py` (`send_alerts_for_trade()`)

**Process**:
1. If `matching_users` list is empty: Skip (no alerts to send)
2. **Build Message** (once, reused for all users):
   - Calls `build_trade_alert_message(trade, market, matching_users[0])`
   - Creates formatted HTML message:
     ```
     🐋 Whale Trade Alert!
     
     📊 Market: {market.title}
     {category info}
     🏷️ Tags: {tags}
     
     💰 Trade Details:
     {side emoji} {side} ${notional} @ {price}%
     Size: {size} | Price: {price}%
     
     👤 Trader: {wallet link}
     
     🔗 View Market on Polymarket
     ```
3. **Enqueue for Each User**:
   - For each user in `matching_users`:
     - Checks if `telegram_chat_id` exists
     - Calls `notification_queue.enqueue(chat_id, message)`
     - Adds to queue (non-blocking)
4. **Logging**: Logs count of alerts queued

**Result**: Messages added to notification queue for async processing

---

### Step 4.7: Update Cursor

**Location**: `whale_worker/main.py` (after processing all trades)

**Process**:
1. If `new_trades` list is not empty:
   - Gets newest trade: `new_trades[0]` (already sorted newest first)
   - Creates `TradeMarker`:
     ```python
     TradeMarker(
         last_processed_timestamp=trade.timestamp,
         last_processed_tx_hash=trade.transaction_hash,
         updated_at=datetime.utcnow()
     )
     ```
2. Calls `set_last_processed_trade_marker(marker)`
3. Updates MongoDB `lastProcessedTradeMarker` collection:
   ```python
   {
     '_id': 'whale_worker_global',
     'lastProcessedTimestamp': int,
     'lastProcessedTxhash': str,
     'updatedAt': datetime
   }
   ```
4. Uses `updateOne` with `upsert: true` (creates if doesn't exist)

**Purpose**: Next poll cycle will only fetch trades newer than this marker

---

### Step 4.8: Sleep and Repeat

**Process**:
1. Sleeps for `POLL_INTERVAL_SECONDS` (default: 10 seconds)
2. Loops back to Step 4.1 (next poll cycle)

**Continuous Operation**: Worker runs indefinitely until stopped

---

## Phase 5: Notification Queue Processing

### Step 5.1: Message Enqueuing

**Location**: `whale_worker/notifications.py` → `whale_worker/notification_queue.py`

**Process**:
1. `send_alerts_for_trade()` calls `enqueue_notification(chat_id, message)`
2. `NotificationQueue.enqueue()` adds `(chat_id, message)` tuple to queue
3. **Non-Blocking**: Returns immediately, doesn't wait for send
4. **Thread-Safe**: Queue operations are thread-safe

**Queue Structure**:
- Python `queue.Queue` (thread-safe)
- Stores tuples: `(chat_id: str, message: str)`
- FIFO (First In, First Out) order

---

### Step 5.2: Worker Thread Processing

**Location**: `whale_worker/notification_queue.py` (`_worker_loop()` method)

**Thread**: Runs continuously in background (daemon thread)

**Loop Process** (runs while `running == True`):

#### 5.2.1: Dequeue Message
1. Gets next message from queue: `queue.get(timeout=1.0)`
2. **Timeout**: 1 second timeout allows graceful shutdown check
3. If queue empty: Continues loop (no message to process)

#### 5.2.2: Apply Rate Limiting
**Location**: `_apply_rate_limits()` method

**Global Rate Limit**:
1. Calculates time since last global send: `now - last_global_send`
2. If `time_since < global_min_interval` (0.034s):
   - Sleeps for remaining time: `sleep(global_min_interval - time_since)`
   - Updates `last_global_send` after sleep
3. **Purpose**: Respects Telegram's global rate limit (~30 msg/sec)

**Per-Chat Rate Limit**:
1. Gets last send time for this `chat_id`: `last_chat_send.get(chat_id)`
2. Calculates time since last send to this chat
3. If `time_since < per_chat_min_interval` (1.0s):
   - Sleeps for remaining time
   - Updates `last_chat_send[chat_id]` after sleep
4. **Purpose**: Prevents spamming one user (1 msg/sec per chat)

**Result**: Rate limits applied, message ready to send

#### 5.2.3: Send Message via Telegram Bot API
**Location**: `_send_message()` method

**API Call**:
```
POST https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage
```

**Request Payload**:
```json
{
  "chat_id": "telegram-chat-id",
  "text": "formatted-html-message",
  "parse_mode": "HTML",
  "disable_web_page_preview": false
}
```

**HTTP Client**: Uses `httpx` with 10 second timeout

**Response Handling**:
1. **Success** (`200 OK`):
   - Response contains `{"ok": true, "result": {...}}`
   - Returns `True` (message sent successfully)
   - Logs success (optional, can be verbose)

2. **Rate Limit** (`429 Too Many Requests`):
   - Extracts `retry_after` from response: `error.parameters.retry_after`
   - Sets `next_attempt_at = now + retry_after + 1s` (buffer)
   - Returns `False` (will be re-enqueued)
   - Message will be retried after `retry_after` seconds

3. **User Blocked Bot** (`403 Forbidden`):
   - Calls `_deactivate_telegram_account(user_id, chat_id)`
   - Updates MongoDB `telegramAccounts`:
     ```python
     {
       'isActive': False,
       'disconnectedAt': datetime.utcnow()
     }
     ```
   - Returns `True` (handled, no retry)
   - User won't receive further notifications until reconnected

4. **Invalid Chat ID** (`400 Bad Request`):
   - Calls `_deactivate_telegram_account(user_id, chat_id)`
   - Marks account as inactive
   - Returns `True` (handled, no retry)

5. **Other Errors**:
   - Logs error details
   - Returns `False` (will be retried)

#### 5.2.4: Retry Logic
1. If send failed (`False` returned):
   - Increments `attempts` counter
   - If `attempts < 3`:
     - Calculates exponential backoff: `5 * attempts` seconds
     - Sets `next_attempt_at = now + backoff`
     - Re-enqueues message
   - If `attempts >= 3`:
     - Logs failure
     - Drops message (no further retries)

2. **Retry Timing**:
   - Checks `next_attempt_at` before processing
   - If `now < next_attempt_at`: Re-enqueues and continues
   - Only processes when time has elapsed

#### 5.2.5: Mark Task Complete
1. Calls `queue.task_done()` to mark message processed
2. Continues to next message in queue

**Error Handling**: All exceptions caught, logged, and processing continues

---

## Phase 6: Telegram Message Delivery

### Step 6.1: Telegram Bot API Processing

**Process**:
1. Telegram Bot API receives `POST /sendMessage` request
2. Validates bot token
3. Validates chat ID (checks if bot can send to this chat)
4. Formats message according to `parse_mode` (HTML)
5. Delivers message to user's Telegram account

**Delivery Methods**:
- Mobile app (if user has Telegram app)
- Web client (if user has web Telegram open)
- Desktop client (if user has desktop app)
- All devices receive notification (if user has multiple devices)

---

### Step 6.2: User Receives Notification

**Message Content**:
- Market title and link
- Trade details (side, notional, price, size)
- Trader wallet address (clickable link)
- Market link (clickable)
- Category and tags information
- Formatted with HTML (bold, links, emojis)

**User Experience**:
- Notification appears in Telegram
- User can click links to view market or trader profile
- Message is persistent (stays in chat history)

---

## Data Flow Summary

```
┌─────────────────┐
│  User (Browser) │
└────────┬────────┘
         │
         │ 1. Click "Connect Telegram"
         ▼
┌─────────────────────────┐
│  POST /api/telegram/    │
│  connect-token          │
└────────┬─────────────────┘
         │
         │ 2. Generate token, store in MongoDB
         │    (with unique index + TTL index)
         ▼
┌─────────────────────────┐
│  MongoDB                │
│  telegramConnectTokens  │
└────────┬─────────────────┘
         │
         │ 3. Return token to frontend
         ▼
┌─────────────────────────┐
│  Frontend               │
│  Opens Telegram link    │
└────────┬─────────────────┘
         │
         │ 4. User clicks /start {token}
         ▼
┌─────────────────────────┐
│  Telegram Bot           │
│  Verifies token         │
└────────┬─────────────────┘
         │
         │ 5. Link chatId to userId
         ▼
┌─────────────────────────┐
│  MongoDB                │
│  telegramAccounts       │
└──────────────────────────┘

┌─────────────────┐
│  User Configures│
│  Alert Settings │
└────────┬────────┘
         │
         │ 6. Save settings
         ▼
┌─────────────────────────┐
│  PUT /api/whale-alerts/ │
│  config                 │
└────────┬─────────────────┘
         │
         │ 7. Store in MongoDB + set reload signal
         ▼
┌─────────────────────────┐
│  MongoDB                │
│  whaleAlertConfigs       │
│  filterReloadSignals    │
└──────────────────────────┘

┌─────────────────┐
│  Python Worker  │
│  (Background)   │
└────────┬────────┘
         │
         │ 8. Poll every 10s
         │    (Check reload signal FIRST)
         ▼
┌─────────────────────────┐
│  Polymarket Data API    │
│  GET /trades            │
└────────┬─────────────────┘
         │
         │ 9. Fetch market metadata
         ▼
┌─────────────────────────┐
│  Polymarket Gamma API    │
│  GET /markets            │
│  (Batch + Concurrent)    │
└────────┬─────────────────┘
         │
         │ 10. Match trades against filters
         ▼
┌─────────────────────────┐
│  Filter Matching Logic  │
│  (All criteria checked) │
└────────┬─────────────────┘
         │
         │ 11. Enqueue notifications
         ▼
┌─────────────────────────┐
│  Notification Queue     │
│  (Async, Rate-Limited)  │
└────────┬─────────────────┘
         │
         │ 12. Send via Telegram Bot API
         ▼
┌─────────────────────────┐
│  Telegram Bot API       │
│  POST /sendMessage      │
└────────┬─────────────────┘
         │
         │ 13. Deliver to user
         ▼
┌─────────────────────────┐
│  User's Telegram App    │
│  (Notification Received)│
└─────────────────────────┘
```

---

## Key Components & Collections

### MongoDB Collections

1. **`telegramConnectTokens`**
   - **Purpose**: Temporary tokens for Telegram connection
   - **Indexes**: 
     - Unique on `token`
     - TTL on `expiresAt` (5 min expiry)
   - **TTL**: Auto-deletes expired tokens
   - **Cleanup**: Manual cleanup of `used: true` tokens

2. **`telegramAccounts`**
   - **Purpose**: Links Telegram chat IDs to user accounts
   - **Fields**: `userId`, `chatId`, `username`, `isActive`, `connectedAt`
   - **Usage**: Lookup chat ID for notifications

3. **`whaleAlertConfigs`**
   - **Purpose**: User filter configurations
   - **Fields**: `userId`, `minNotionalUsd`, `minPrice`, `maxPrice`, `sides`, `enabled`, etc.
   - **Usage**: Loaded by worker for filter matching

4. **`filterReloadSignals`**
   - **Purpose**: Signals worker to reload filters immediately
   - **Structure**: `{ _id: 'global', requestedAt: Date, requestedBy: userId }`
   - **Usage**: Checked on every poll cycle

5. **`lastProcessedTradeMarker`**
   - **Purpose**: Cursor for trade processing
   - **Structure**: `{ _id: 'whale_worker_global', lastProcessedTimestamp, lastProcessedTxhash }`
   - **Usage**: Prevents re-processing trades

6. **`processedTrades`**
   - **Purpose**: Deduplication set (TTL-based)
   - **Index**: TTL on `expiresAt` (15 min expiry)
   - **Usage**: Prevents duplicate processing

7. **`marketMetadata`**
   - **Purpose**: Cached market data
   - **TTL**: 24 hours
   - **Usage**: Avoids repeated API calls

8. **`sportsTagIds`**
   - **Purpose**: Cached sports tag IDs
   - **TTL**: 24 hours
   - **Usage**: Identify sports markets

9. **`tagsDictionary`**
   - **Purpose**: Cached tag metadata
   - **TTL**: 24 hours
   - **Usage**: Tag lookups and categorization

---

## Performance Optimizations

1. **Batch Market Fetching**: Collects all missing markets, fetches concurrently
2. **Market Caching**: 24-hour TTL prevents repeated API calls
3. **Deduplication**: Two-layer system (cursor + TTL set)
4. **Filter Reloading**: Immediate signal + periodic fallback
5. **Queue-Based Notifications**: Non-blocking, rate-limited
6. **Concurrent API Calls**: Uses `asyncio` for parallel market fetches
7. **Index Optimization**: Unique and TTL indexes on tokens collection

---

## Error Handling & Resilience

1. **Token Expiration**: 5-minute expiry prevents token reuse
2. **Market Not Found**: Trade is skipped (logged, not processed)
3. **API Failures**: Retries with exponential backoff
4. **Rate Limiting**: Respects Telegram's `retry_after` header
5. **Account Deactivation**: Automatically marks inactive accounts
6. **Worker Restart**: Cursor + deduplication set prevents duplicate processing
7. **Index Creation**: Idempotent, handles existing indexes gracefully

---

## Security Considerations

1. **Token-Based Verification**: Secure random tokens, one-time use
2. **User Authentication**: All API routes require NextAuth session
3. **Token Expiration**: 5-minute window limits attack surface
4. **Chat ID Validation**: Telegram validates chat IDs
5. **No User ID in Deep Link**: Token prevents account hijacking
6. **Unique Token Constraint**: Database enforces uniqueness

---

## Timing & Latency

- **Filter Reload**: Immediate (within 10 seconds of settings save)
- **Trade Polling**: Every 10 seconds
- **Market Fetching**: Concurrent (typically < 2 seconds for multiple markets)
- **Notification Queue**: Processes asynchronously with rate limiting
- **Message Delivery**: Depends on Telegram API (typically < 1 second)
- **Total Latency**: ~10-15 seconds from trade occurrence to notification

---

This completes the comprehensive technical workflow of the whale trade alert system.

