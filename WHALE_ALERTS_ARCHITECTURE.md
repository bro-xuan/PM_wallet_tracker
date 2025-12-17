# Whale Alerts Architecture - Step-by-Step Plan

## Overview
Build a system to monitor ALL Polymarket trades (not just user wallets) and send Telegram notifications when trades match user-defined criteria.

---

## Architecture Components

### 1. **Data Layer (MongoDB Collections)**

#### `telegramAccounts` Collection
```typescript
{
  _id: ObjectId,
  userId: ObjectId, // ref User
  chatId: string,    // Telegram chat ID
  username: string | null,
  linkedAt: Date,
  isActive: boolean
}
```

#### `whaleAlertConfigs` Collection
```typescript
{
  _id: ObjectId,
  userId: ObjectId, // ref User
  minNotionalUsd: number, // e.g. 10000
  minPrice: number,       // 0-1, e.g. 0.05
  maxPrice: number,       // 0-1, e.g. 0.95
  sides: string[],         // ["BUY", "SELL"] or ["BUY"] or ["SELL"]
  marketsFilter: string[], // Optional: specific market slugs/IDs
  enabled: boolean,
  createdAt: Date,
  updatedAt: Date
}
```

#### `whaleAlertCursors` Collection
```typescript
{
  _id: ObjectId,
  lastProcessedTimestamp: number, // Unix timestamp
  lastProcessedTxhash: string,     // Last trade txhash processed
  updatedAt: Date
}
```

---

## Step-by-Step Implementation Plan

### **Phase 1: Telegram Bot Setup & Connection**

#### Step 1.1: Create Telegram Bot
- [ ] Get bot token from @BotFather on Telegram
- [ ] Add `TELEGRAM_BOT_TOKEN` to `.env.local`
- [ ] Store bot username for connection link

#### Step 1.2: Telegram Webhook/Handler
- [ ] Create `/api/telegram/webhook` endpoint to receive bot messages
- [ ] Handle `/start` command with deep link: `/start <userId>`
- [ ] Extract `chatId` from incoming message
- [ ] Store `chatId` + `userId` in `telegramAccounts` collection
- [ ] Send confirmation message to user

#### Step 1.3: Frontend - Connect Telegram Button
- [ ] Add "Connect Telegram" button in Whale Alerts tab
- [ ] Generate unique connection link: `https://t.me/YourBot?start=<userId>`
- [ ] Open link in new window/tab
- [ ] Poll API to check connection status
- [ ] Show "Connected to @username" when linked
- [ ] Add "Disconnect" button

---

### **Phase 2: User Configuration (Filters)**

#### Step 2.1: API - Get/Update Alert Config
- [ ] `GET /api/whale-alerts/config` - Get user's current config
- [ ] `PUT /api/whale-alerts/config` - Update user's config
- [ ] Default config: `minNotional: 10000, minPrice: 0.05, maxPrice: 0.95, sides: ["BUY", "SELL"], enabled: false`

#### Step 2.2: Frontend - Settings Panel
- [ ] Add filter UI in Whale Alerts tab:
  - [ ] Min Notional input (default: $10,000)
  - [ ] Price Range: Min (default: 5%) and Max (default: 95%)
  - [ ] Side checkboxes: Buy, Sell (default: both)
  - [ ] Enable/Disable toggle
  - [ ] Save button
- [ ] Show current config when loaded
- [ ] Validate inputs (min < max, positive numbers, etc.)

---

### **Phase 3: Trade Monitoring Worker**

#### Step 3.1: Polymarket API - Fetch All Trades
- [ ] Research Polymarket API endpoint for ALL trades (not user-specific)
- [ ] Options:
  - `/trades` without `user` parameter (if available)
  - `/events` or `/markets` endpoint with trades
  - WebSocket stream (if available)
- [ ] Create `lib/polymarket-whale.ts` with `fetchAllTrades()` function
- [ ] Handle pagination if needed
- [ ] Return trades sorted by timestamp (newest first)

#### Step 3.2: Whale Alert Poller
- [ ] Create `lib/whale-poller.ts` (separate from wallet poller)
- [ ] Poll Polymarket API for new trades every N seconds (e.g., 5-10s)
- [ ] Track `lastProcessedTimestamp` in `whaleAlertCursors` collection
- [ ] Only process trades newer than cursor
- [ ] For each new trade:
  1. Check if trade matches any user's filter criteria
  2. For each matching user:
     - Check if user has Telegram connected
     - Check if alerts are enabled
     - Send Telegram notification
- [ ] Update cursor after processing batch

#### Step 3.3: Filter Matching Logic
```typescript
function tradeMatchesConfig(trade: DataTrade, config: WhaleAlertConfig): boolean {
  // Check notional
  const notional = trade.size * trade.price;
  if (notional < config.minNotionalUsd) return false;
  
  // Check price range
  if (trade.price < config.minPrice || trade.price > config.maxPrice) return false;
  
  // Check side
  if (!config.sides.includes(trade.side)) return false;
  
  // Check market filter (if specified)
  if (config.marketsFilter.length > 0) {
    if (!config.marketsFilter.includes(trade.slug || '')) return false;
  }
  
  return true;
}
```

---

### **Phase 4: Telegram Notification Sending**

#### Step 4.1: Telegram Bot API Integration
- [ ] Install `node-telegram-bot-api` or use `fetch` to Telegram Bot API
- [ ] Create `lib/telegram.ts` with `sendNotification()` function
- [ ] Format message:
  ```
  🐋 Whale Alert!
  
  Market: {title}
  Side: {BUY/SELL}
  Size: {size}
  Price: {price} ({price%})
  Notional: ${notional}
  Wallet: {proxyWallet}
  
  View: https://polymarket.com/event/{slug}
  ```
- [ ] Handle rate limiting (30 messages/second for Telegram)
- [ ] Handle errors (invalid chatId, blocked bot, etc.)

#### Step 4.2: Notification Queue (Optional)
- [ ] Consider using a queue (Bull, BullMQ) if high volume
- [ ] Or batch notifications to avoid rate limits
- [ ] For MVP: Simple sequential sending with delays

---

### **Phase 5: Frontend UI Completion**

#### Step 5.1: Whale Alerts Tab UI
- [ ] Show connection status:
  - [ ] "Not Connected" → "Connect Telegram" button
  - [ ] "Connected to @username" → "Disconnect" button
- [ ] Show current filter settings
- [ ] Settings form (from Phase 2.2)
- [ ] "Test Notification" button (sends test message)
- [ ] Status indicator (enabled/disabled)

#### Step 5.2: Test Notification
- [ ] `POST /api/whale-alerts/test` endpoint
- [ ] Sends test message to user's Telegram
- [ ] Returns success/error

---

### **Phase 6: Error Handling & Edge Cases**

#### Step 6.1: Error Handling
- [ ] Handle Telegram API errors (blocked bot, invalid chatId)
- [ ] Handle Polymarket API rate limits
- [ ] Handle missing trade data (null fields)
- [ ] Log errors for debugging

#### Step 6.2: Edge Cases
- [ ] What if user disconnects Telegram mid-alert?
- [ ] What if cursor gets out of sync?
- [ ] What if Polymarket API is down?
- [ ] Handle duplicate notifications (same trade, multiple users)

---

## Implementation Order (Recommended)

### **Week 1: Foundation**
1. ✅ Phase 1: Telegram Bot Setup & Connection
2. ✅ Phase 2: User Configuration (Filters)
3. ✅ Phase 5.1: Basic UI (connection + settings)

### **Week 2: Core Functionality**
4. ✅ Phase 3: Trade Monitoring Worker
5. ✅ Phase 4: Telegram Notifications
6. ✅ Phase 5.2: Test Notification

### **Week 3: Polish**
7. ✅ Phase 6: Error Handling
8. ✅ Testing & Optimization
9. ✅ Rate limiting & performance tuning

---

## Technical Decisions Needed

### 1. **Polymarket API Endpoint**
- ❓ Does Polymarket have a public `/trades` endpoint without `user` parameter?
- ❓ Or do we need to use a different endpoint?
- ❓ Alternative: WebSocket stream?

### 2. **Polling Frequency**
- ⚡ How often should we poll? (5s, 10s, 30s?)
- ⚡ Balance between real-time alerts and API rate limits

### 3. **Notification Format**
- 📝 What information to include?
- 📝 Link to Polymarket profile/market?
- 📝 Emoji/formatting preferences?

### 4. **Rate Limiting**
- 🚦 Telegram: 30 messages/second
- 🚦 How to handle if many users match same trade?
- 🚦 Queue system or simple delays?

---

## Environment Variables Needed

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_BOT_USERNAME=your_bot_username
WHALE_POLL_INTERVAL_MS=10000  # 10 seconds
```

---

## Database Indexes Needed

```javascript
// telegramAccounts
db.telegramAccounts.createIndex({ userId: 1 }, { unique: true });
db.telegramAccounts.createIndex({ chatId: 1 }, { unique: true });

// whaleAlertConfigs
db.whaleAlertConfigs.createIndex({ userId: 1 }, { unique: true });
db.whaleAlertConfigs.createIndex({ enabled: 1 });

// whaleAlertCursors
db.whaleAlertCursors.createIndex({ lastProcessedTimestamp: -1 });
```

---

## Next Steps

1. **Research Polymarket API** - Find endpoint for all trades
2. **Create Telegram Bot** - Get token from @BotFather
3. **Start with Phase 1** - Telegram connection
4. **Then Phase 2** - User configuration
5. **Then Phase 3** - Trade monitoring
6. **Finally Phase 4** - Notifications

---

## Questions to Answer

1. ✅ Which Polymarket API endpoint for all trades?
2. ✅ How to handle rate limiting?
3. ✅ Should we store all trades or just process and notify?
4. ✅ How to handle duplicate trades (same txhash)?
5. ✅ Should we add market filtering UI (specific markets)?

