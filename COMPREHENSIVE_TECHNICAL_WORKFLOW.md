# Comprehensive Technical Workflow: Telegram Connection → Trade Polling → Notification Sending

## Overview

This document describes the complete technical workflow from when a user connects their Telegram account to when they receive trade notifications. The system consists of two main components:

1. **Next.js Web Application** (Frontend + API Routes)
2. **Python Worker** (Background trade monitoring)

---

## Phase 1: Telegram Connection Flow

### Step 1.1: User Initiates Connection (Frontend)

**Location**: `src/app/app/page.tsx` (Whale Alerts tab)

**Flow**:
1. User clicks "Connect Telegram" button
2. Frontend calls `POST /api/telegram/connect-token`
3. This endpoint (`src/app/api/telegram/connect-token/route.ts`) generates a secure token

### Step 1.2: Token Generation (Backend API)

**Location**: `src/app/api/telegram/connect-token/route.ts`

**Process**:
1. **Authentication Check**: Verifies user is logged in via NextAuth session
2. **Token Generation**: Creates a 64-character hex token using `crypto.randomBytes(32)`
3. **Token Storage**: Stores token in MongoDB `telegramConnectTokens` collection with:
   - `token`: The generated token
   - `userId`: Authenticated user's ID
   - `expiresAt`: Current time + 5 minutes
   - `used`: `false`
   - `createdAt`: Current timestamp
4. **Response**: Returns token and expiration time to frontend

**Security**: Token is one-time use, expires in 5 minutes, and is linked to the authenticated user

### Step 1.3: Deep Link Creation (Frontend)

**Location**: `src/app/app/page.tsx`

**Process**:
1. Frontend receives token from API
2. Constructs Telegram deep link: `https://t.me/PM_Intel_bot?start={token}`
3. Opens link in new window/tab
4. User is redirected to Telegram app/web

### Step 1.4: Telegram Bot Receives /start Command

**Location**: `lib/telegram-bot.ts`

**Bot Initialization**:
- Bot uses lazy initialization pattern (serverless-friendly)
- In development: Uses polling if `TELEGRAM_USE_POLLING=true`
- In production: Uses webhook mode only (no polling)
- Bot instance stored in `globalThis._telegramBot` (dev) or module variable (prod)

**Handler Setup** (`setupHandlers()` function):
1. Registers `/start` command handler with regex: `/\/start(?: (.+))?/`
2. Extracts token from command: `/start {token}`
3. Verifies token in MongoDB:
   - Checks `telegramConnectTokens` collection
   - Validates token exists, not expired, not used
   - Retrieves associated `userId`
4. **Token Verification**:
   - Queries: `{ token: providedToken, expiresAt: { $gt: now }, used: false }`
   - If valid: Marks token as `used: true`
   - Links `chatId` to `userId` in `telegramAccounts` collection
5. **Account Linking**:
   - Upserts document in `telegramAccounts`:
     - `userId`: From token
     - `chatId`: From Telegram message
     - `username`: From Telegram message (if available)
     - `isActive`: `true`
     - `connectedAt`: Current timestamp
6. **Response**: Sends confirmation message to user

**Error Handling**:
- Invalid/expired token: Sends error message
- Token already used: Sends error message
- Database errors: Logged, user notified

---

## Phase 2: User Filter Configuration

### Step 2.1: User Configures Alert Settings (Frontend)

**Location**: `src/app/app/page.tsx` (Whale Alerts tab)

**UI Elements**:
- Min Notional (USD)
- Price Range (min/max as percentages)
- Side filter (Buy/Sell)
- Category filters
- Enable/Disable toggle
- "Save Settings" button

### Step 2.2: Settings Saved to Database (Backend API)

**Location**: `src/app/api/whale-alerts/config/route.ts` (PUT handler)

**Process**:
1. **Authentication**: Verifies user session
2. **Validation**: Validates all input parameters:
   - `minNotionalUsd`: Number >= 0
   - `minPrice`: Number 0-1
   - `maxPrice`: Number 0-1
   - `minPrice < maxPrice`
   - `sides`: Array of "BUY" and/or "SELL"
   - `excludeCategories`: Array of strings
   - `categoryFilter`: Array of strings (tag IDs)
   - `enabled`: Boolean
3. **Database Update**: Upserts to `whaleAlertConfigs` collection:
   - `userId`: From session
   - All filter parameters
   - `updatedAt`: Current timestamp
   - `createdAt`: Set on insert only
4. **Response**: Returns success status

**Note**: Worker reloads filters periodically (every 60 seconds by default)

---

## Phase 3: Worker Initialization

### Step 3.1: Worker Startup

**Location**: `whale_worker/main.py` (`run_worker()` function)

**Initialization Sequence**:

1. **Load Configuration** (`whale_worker/config.py`):
   - `POLL_INTERVAL_SECONDS`: How often to poll (default: 10s)
   - `MAX_TRADES_PER_POLL`: Max trades per API call (default: 1000)
   - `GLOBAL_MIN_NOTIONAL_USD`: Global minimum (default: 0)
   - `FILTER_RELOAD_INTERVAL_SECONDS`: How often to reload filters (default: 60s)
   - `MONGODB_URI`: Database connection string
   - `TELEGRAM_BOT_TOKEN`: Bot API token

2. **Connect to MongoDB**:
   - Creates singleton MongoDB client
   - Tests connection with `db.command('ping')`
   - Ensures TTL index exists on `processedTrades` collection

3. **Initialize Notification Queue** (`whale_worker/notification_queue.py`):
   - Creates `NotificationQueue` singleton
   - Starts worker thread for async message sending
   - Configures rate limits:
     - Global: ~30 msg/sec (0.034s interval)
     - Per-chat: 1 msg/sec (1.0s interval)

4. **Load Market Categorization Data**:
   - **Sports Tag IDs**: Fetches from Gamma API `/sports` endpoint
     - Caches in MongoDB `sportsTagIds` collection (24h TTL)
     - Used to identify sports markets
   - **Tags Dictionary**: Fetches from Gamma API `/tags` endpoint
     - Caches in MongoDB `tagsDictionary` collection (24h TTL)
     - Maps tag IDs to labels/metadata

5. **Load User Filters**:
   - Queries `whaleAlertConfigs` collection
   - Joins with `telegramAccounts` to get `chatId`
   - Filters: `enabled: true`, `isActive: true`
   - Creates `UserFilter` objects for each active user

6. **Load Last Processed Trade Marker**:
   - Reads from `lastProcessedTradeMarker` collection
   - Contains: `last_processed_timestamp`, `last_processed_tx_hash`
   - Used to avoid re-processing trades

---

## Phase 4: Trade Polling Loop

### Step 4.1: Poll Cycle Starts

**Location**: `whale_worker/main.py` (main `while True` loop)

**Frequency**: Every `POLL_INTERVAL_SECONDS` (default: 10 seconds)

**Each Poll Cycle**:

1. **Reload User Filters** (if interval elapsed):
   - Checks if `FILTER_RELOAD_INTERVAL_SECONDS` has passed
   - Re-fetches all user filters from MongoDB
   - Updates in-memory `all_user_filters` list
   - This allows filter changes without worker restart

2. **Fetch Recent Trades** (`whale_worker/polymarket_client.py`):
   - **API Call**: `GET https://data-api.polymarket.com/trades`
   - **Parameters**:
     - `takerOnly=true`: Only taker trades
     - `limit={MAX_TRADES_PER_POLL}`: Max trades to fetch
     - `filterType=CASH`: Cash markets only
     - `filterAmount={GLOBAL_MIN_NOTIONAL_USD}`: Global minimum (if > 0)
     - `minTimestamp={last_processed_timestamp}`: Only new trades (if marker exists)
   - **Response Parsing**:
     - Converts JSON to `Trade` objects
     - Extracts: `transaction_hash`, `proxy_wallet`, `side`, `size`, `price`, `condition_id`, `timestamp`
     - Calculates `notional = size * price`
     - Deduplicates by `transaction_hash`
   - **Returns**: List of `Trade` objects (newest first)

3. **Deduplication**:
   - **Primary**: Uses cursor (`last_processed_tx_hash`)
     - Stops processing when reaching cursor trade
     - Prevents re-processing known trades
   - **Secondary**: Checks `processedTrades` collection (TTL-based)
     - Queries: `{ txHash: trade.transaction_hash, expiresAt: { $gt: now } }`
     - TTL: 15 minutes (auto-expires)
     - Prevents duplicate processing on restarts/edge cases
   - **Result**: `new_trades` list (only unprocessed trades)

4. **Batch Fetch Market Metadata** (Optimization):
   - **Collect Missing Markets**:
     - For each `new_trade`, checks if market is cached
     - Calls `get_or_upsert_market(condition_id)` (returns cached or `None`)
     - Collects all `condition_id`s not in cache
   - **Batch API Call** (`whale_worker/polymarket_client.py`):
     - Attempts batch fetch: `GET /markets?condition_ids=id1,id2,...`
     - **Note**: Gamma API batch endpoint doesn't work reliably
     - **Fallback**: Concurrent individual fetches using `asyncio`
       - Creates async tasks for each missing `condition_id`
       - Fetches: `GET /markets?condition_ids={id}&include_tag=true&closed=false&limit=1`
       - If not found with `closed=false`, tries without `closed` parameter
     - **Parsing**: Each market response parsed into `MarketMetadata`:
       - Extracts: `title`, `slug`, `tags`, `tag_ids`, `is_sports`, `category`
       - Uses `sports_tag_ids` to determine if market is sports
       - Uses `tags_dict` to map tag IDs to labels
   - **Cache Storage**:
     - For each fetched market, calls `get_or_upsert_market(condition_id, metadata)`
     - Stores in MongoDB `marketMetadata` collection
     - TTL: 24 hours (cache expiration)

5. **Process Each Trade**:
   - Iterates through `new_trades` (newest first)
   - **Mark as Processed** (immediately):
     - Calls `mark_trade_as_processed(trade.transaction_hash)`
     - Stores in `processedTrades` with 15-minute TTL
   - **Get Market Metadata**:
     - Calls `get_or_upsert_market(trade.condition_id)`
     - Should be in cache after batch fetch
     - If `None`: Trade is skipped (market not found)
   - **Filter Matching** (`whale_worker/filters.py`):
     - For each user filter in `all_user_filters`:
       - Calls `trade_matches_user_filter(trade, market, user_filter)`
       - **Checks**:
         1. `trade.notional >= user_filter.min_notional_usd`
         2. `user_filter.min_price <= trade.price <= user_filter.max_price`
         3. `trade.side in user_filter.sides`
         4. If `"sports" in exclude_categories` and `market.is_sports`: Skip
         5. If `category_filter` specified: Market tags must overlap
         6. If `markets_filter` specified: `condition_id` must be in list
       - Returns list of matching `UserFilter` objects
   - **Send Alerts** (if matches found):
     - Calls `send_alerts_for_trade(trade, market, matching_users)`
     - **Message Building** (`whale_worker/notifications.py`):
       - Creates formatted HTML message:
         - Market title, category, tags
         - Trade details (side, notional, price, size)
         - Trader wallet (with link)
         - Market link
     - **Enqueue Notifications**:
       - For each matching user:
         - Calls `notification_queue.enqueue(chat_id, message)`
         - Adds to queue (non-blocking)

6. **Update Cursor**:
   - After processing all trades:
     - Gets newest trade: `new_trades[0]` (already sorted newest first)
     - Updates `lastProcessedTradeMarker`:
       - `last_processed_timestamp`: Trade timestamp
       - `last_processed_tx_hash`: Trade transaction hash
       - `updatedAt`: Current timestamp

7. **Sleep**:
   - Waits `POLL_INTERVAL_SECONDS` before next poll

---

## Phase 5: Notification Queue Processing

### Step 5.1: Message Enqueuing

**Location**: `whale_worker/notifications.py` → `whale_worker/notification_queue.py`

**Process**:
1. `send_alerts_for_trade()` calls `enqueue_notification(chat_id, message)`
2. `NotificationQueue.enqueue()` adds `(chat_id, message)` tuple to queue
3. Returns immediately (non-blocking)

### Step 5.2: Worker Thread Processing

**Location**: `whale_worker/notification_queue.py` (`_worker_loop()` method)

**Worker Thread**:
- Runs continuously in background (daemon thread)
- Processes queue with rate limiting

**For Each Message**:

1. **Dequeue**: Gets next message from queue (1s timeout for graceful shutdown)

2. **Rate Limiting** (`_apply_rate_limits()`):
   - **Global Rate Limit**:
     - Checks time since last global send
     - If < `global_min_interval` (0.034s): Sleeps for remaining time
     - Updates `last_global_send` timestamp
   - **Per-Chat Rate Limit**:
     - Checks time since last send to this `chat_id`
     - If < `per_chat_min_interval` (1.0s): Sleeps for remaining time
     - Updates `last_chat_send[chat_id]` timestamp

3. **Send Message** (`_send_message()`):
   - **API Call**: `POST https://api.telegram.org/bot{TOKEN}/sendMessage`
   - **Payload**:
     ```json
     {
       "chat_id": "{chat_id}",
       "text": "{message}",
       "parse_mode": "HTML",
       "disable_web_page_preview": false
     }
     ```
   - **HTTP Client**: Uses `httpx` with 10s timeout

4. **Error Handling**:
   - **429 Too Many Requests**:
     - Extracts `retry_after` from response
     - Re-enqueues message with delay
     - Respects Telegram's rate limit
   - **403 Forbidden** (User blocked bot):
     - Marks account as inactive: `telegramAccounts.isActive = false`
     - Logs deactivation
     - Does not retry
   - **400 Bad Request** (Invalid chat ID):
     - Marks account as inactive
     - Logs deactivation
     - Does not retry
   - **Other Errors**:
     - Logs error
     - Re-enqueues for retry (up to 3 attempts)
     - Exponential backoff

5. **Task Complete**: Marks queue task as done

---

## Phase 6: User Receives Notification

### Step 6.1: Telegram Delivery

**Process**:
1. Telegram Bot API receives message request
2. Validates bot token and chat ID
3. Delivers message to user's Telegram app
4. User sees notification with:
   - Market title
   - Trade details (side, size, price, notional)
   - Trader wallet link
   - Market link

---

## Data Flow Diagram

```
┌─────────────────┐
│  User (Browser) │
└────────┬────────┘
         │
         │ 1. Click "Connect Telegram"
         ▼
┌─────────────────────────┐
│  Next.js API Route      │
│  /api/telegram/connect-  │
│  token (POST)            │
└────────┬─────────────────┘
         │
         │ 2. Generate token, store in MongoDB
         ▼
┌─────────────────────────┐
│  MongoDB                 │
│  telegramConnectTokens   │
└────────┬─────────────────┘
         │
         │ 3. Return token to frontend
         ▼
┌─────────────────────────┐
│  Frontend                │
│  Opens Telegram deep link│
└────────┬─────────────────┘
         │
         │ 4. User clicks /start {token} in Telegram
         ▼
┌─────────────────────────┐
│  Telegram Bot            │
│  lib/telegram-bot.ts     │
└────────┬─────────────────┘
         │
         │ 5. Verify token, link chatId to userId
         ▼
┌─────────────────────────┐
│  MongoDB                 │
│  telegramAccounts        │
└──────────────────────────┘

┌─────────────────┐
│  User Configures│
│  Alert Settings │
└────────┬────────┘
         │
         │ 6. Save settings
         ▼
┌─────────────────────────┐
│  Next.js API Route      │
│  /api/whale-alerts/     │
│  config (PUT)           │
└────────┬─────────────────┘
         │
         │ 7. Store in MongoDB
         ▼
┌─────────────────────────┐
│  MongoDB                 │
│  whaleAlertConfigs       │
└──────────────────────────┘

┌─────────────────┐
│  Python Worker  │
│  (Background)   │
└────────┬────────┘
         │
         │ 8. Poll every 10s
         ▼
┌─────────────────────────┐
│  Polymarket Data API    │
│  GET /trades             │
└────────┬─────────────────┘
         │
         │ 9. Fetch market metadata
         ▼
┌─────────────────────────┐
│  Polymarket Gamma API    │
│  GET /markets            │
└────────┬─────────────────┘
         │
         │ 10. Match trades against filters
         ▼
┌─────────────────────────┐
│  Notification Queue     │
│  (Async, Rate-Limited)  │
└────────┬─────────────────┘
         │
         │ 11. Send via Telegram Bot API
         ▼
┌─────────────────────────┐
│  Telegram Bot API        │
│  POST /sendMessage       │
└────────┬─────────────────┘
         │
         │ 12. Deliver to user
         ▼
┌─────────────────────────┐
│  User's Telegram App    │
│  (Notification Received)│
└─────────────────────────┘
```

---

## Key Components Summary

### Frontend (Next.js)
- **Telegram Connection UI**: `src/app/app/page.tsx`
- **Token Generation API**: `src/app/api/telegram/connect-token/route.ts`
- **Settings API**: `src/app/api/whale-alerts/config/route.ts`

### Backend (Next.js API Routes)
- **Telegram Bot Handler**: `lib/telegram-bot.ts`
- **MongoDB Connection**: `lib/mongodb.ts`

### Worker (Python)
- **Main Loop**: `whale_worker/main.py`
- **Trade Fetching**: `whale_worker/polymarket_client.py`
- **Filter Matching**: `whale_worker/filters.py`
- **Notification Building**: `whale_worker/notifications.py`
- **Queue Processing**: `whale_worker/notification_queue.py`
- **Database Helpers**: `whale_worker/db.py`

### MongoDB Collections
- `telegramConnectTokens`: Temporary tokens for connection
- `telegramAccounts`: Linked Telegram accounts
- `whaleAlertConfigs`: User filter configurations
- `lastProcessedTradeMarker`: Cursor for trade processing
- `processedTrades`: Deduplication set (TTL: 15 min)
- `marketMetadata`: Cached market data (TTL: 24h)
- `sportsTagIds`: Cached sports tag IDs (TTL: 24h)
- `tagsDictionary`: Cached tags metadata (TTL: 24h)

---

## Performance Optimizations

1. **Batch Market Fetching**: Collects all missing markets, fetches concurrently
2. **Market Caching**: 24-hour TTL prevents repeated API calls
3. **Deduplication**: Two-layer system (cursor + TTL set) prevents duplicate processing
4. **Filter Reloading**: Periodic reload (60s) picks up changes without restart
5. **Queue-Based Notifications**: Non-blocking, rate-limited message sending
6. **Concurrent API Calls**: Uses `asyncio` for parallel market fetches

---

## Error Handling & Resilience

1. **Token Expiration**: 5-minute expiry prevents token reuse
2. **Market Not Found**: Trade is skipped (logged, not processed)
3. **API Failures**: Retries with exponential backoff
4. **Rate Limiting**: Respects Telegram's `retry_after` header
5. **Account Deactivation**: Automatically marks inactive accounts
6. **Worker Restart**: Cursor + deduplication set prevents duplicate processing

---

## Security Considerations

1. **Token-Based Verification**: Secure random tokens, one-time use
2. **User Authentication**: All API routes require NextAuth session
3. **Token Expiration**: 5-minute window limits attack surface
4. **Chat ID Validation**: Telegram validates chat IDs
5. **No User ID in Deep Link**: Token prevents account hijacking

