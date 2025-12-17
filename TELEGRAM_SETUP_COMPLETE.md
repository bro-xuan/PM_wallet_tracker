# ✅ Telegram Whale Alerts Setup - Complete

## What's Been Implemented

### ✅ Backend Infrastructure

1. **Telegram Bot Handler** (`lib/telegram-bot.ts`)
   - Bot initialization with token
   - Handles `/start <userId>` command
   - Stores connections in MongoDB
   - Sends confirmation messages
   - Notification sending function

2. **API Endpoints**
   - `GET /api/telegram/status` - Check connection status
   - `POST /api/telegram/disconnect` - Disconnect Telegram
   - `GET /api/whale-alerts/config` - Get alert configuration
   - `PUT /api/whale-alerts/config` - Update alert configuration
   - `POST /api/whale-alerts/test` - Send test notification
   - `POST /api/telegram/webhook` - Webhook endpoint (for future use)

3. **Database Collections**
   - `telegramAccounts` - Stores user Telegram connections
   - `whaleAlertConfigs` - Stores user alert filter settings
   - `whaleAlertCursors` - Tracks processed trades (for future poller)

4. **Database Indexes**
   - All required indexes created ✅

### ✅ Frontend UI

1. **Connection Flow**
   - "Connect Telegram" button
   - Opens Telegram with deep link: `t.me/PM_Intel_bot?start=<userId>`
   - Polls for connection status
   - Shows "Connected ✅" when linked

2. **Filter Settings**
   - Min Notional input (default: $10,000)
   - Price Range: Min (5%) and Max (95%)
   - Side checkboxes: Buy, Sell
   - Enable/Disable toggle
   - Save button

3. **Test Notification**
   - "Test Notification" button
   - Sends test message to user's Telegram

---

## User Experience Flow

1. ✅ User logs in
2. ✅ Goes to "Whale trades alerts" tab
3. ✅ Clicks "Connect Telegram" → Opens Telegram
4. ✅ User taps "Start" in bot DM
5. ✅ Bot confirms "Connected"
6. ✅ Website shows "Telegram: Connected ✅"
7. ✅ User sets filters → Clicks "Save"
8. ✅ User can send test notification
9. ⏳ User receives alerts (poller to be implemented)

---

## Environment Variables

Make sure these are set in `.env.local`:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_BOT_USERNAME=PM_Intel_bot  # Optional, defaults to PM_Intel_bot
TELEGRAM_USE_POLLING=true  # Set to true for development, false for production webhook
```

---

## How It Works

### Connection Flow

1. User clicks "Connect Telegram"
2. Opens: `https://t.me/PM_Intel_bot?start=<userId>`
3. Telegram app opens with bot chat
4. User taps "Start" button
5. Bot receives `/start <userId>` command
6. Bot stores `chatId` + `userId` in MongoDB
7. Bot sends confirmation: "✅ Connected!"
8. Website polls `/api/telegram/status` every second
9. When connected, shows "Connected ✅"

### Configuration Flow

1. User sets filters:
   - Min Notional: $10,000
   - Price Range: 5% - 95%
   - Sides: Buy, Sell
   - Enabled: true/false
2. User clicks "Save Settings"
3. Config saved to MongoDB
4. User can test notification

---

## Next Steps (To Complete Full Feature)

### Phase 3: Trade Monitoring Worker

1. **Research Polymarket API**
   - Find endpoint for ALL trades (not user-specific)
   - Options:
     - `/trades` without `user` parameter
     - Alternative endpoint
     - WebSocket stream

2. **Create Whale Poller** (`lib/whale-poller.ts`)
   - Poll Polymarket API every 5-10 seconds
   - Track `lastProcessedTimestamp` in `whaleAlertCursors`
   - For each new trade:
     - Check against all users' filters
     - Send notifications to matching users

3. **Filter Matching Logic**
   ```typescript
   function tradeMatchesConfig(trade, config) {
     // Check notional >= minNotional
     // Check price between minPrice and maxPrice
     // Check side in config.sides
     return matches;
   }
   ```

4. **Notification Format**
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

---

## Testing

### Test Connection Flow

1. Start dev server: `npm run dev`
2. Login to website
3. Go to "Whale trades alerts" tab
4. Click "Connect Telegram"
5. In Telegram, tap "Start"
6. Verify website shows "Connected ✅"

### Test Configuration

1. Set filters:
   - Min Notional: $10,000
   - Price: 5% - 95%
   - Sides: Buy, Sell
   - Enabled: true
2. Click "Save Settings"
3. Verify success message

### Test Notification

1. Click "Test Notification"
2. Check Telegram for test message
3. Verify message received

---

## Troubleshooting

### Bot Not Responding

- Check `TELEGRAM_BOT_TOKEN` is set correctly
- Verify bot is running (check server logs)
- Check if polling is enabled: `TELEGRAM_USE_POLLING=true`

### Connection Not Working

- Verify userId is being passed in Telegram link
- Check MongoDB `telegramAccounts` collection
- Check server logs for errors

### Test Notification Fails

- Verify Telegram is connected
- Check `chatId` in MongoDB
- Verify bot token is valid
- Check server logs for Telegram API errors

---

## Files Created/Modified

### New Files
- `lib/telegram-bot.ts` - Bot handler
- `src/app/api/telegram/status/route.ts` - Status endpoint
- `src/app/api/telegram/disconnect/route.ts` - Disconnect endpoint
- `src/app/api/telegram/webhook/route.ts` - Webhook endpoint
- `src/app/api/whale-alerts/config/route.ts` - Config endpoints
- `src/app/api/whale-alerts/test/route.ts` - Test notification
- `scripts/setup-whale-alerts.ts` - Database setup

### Modified Files
- `src/app/app/page.tsx` - Added whale alerts UI
- `package.json` - Added `node-telegram-bot-api`

---

## Status

✅ **Phase 1 & 2 Complete**: Telegram connection and user configuration  
⏳ **Phase 3 Pending**: Trade monitoring worker  
⏳ **Phase 4 Pending**: Notification sending for real trades

---

## Ready to Test!

1. Make sure `TELEGRAM_BOT_TOKEN` is in `.env.local`
2. Start dev server: `npm run dev`
3. Login and go to "Whale trades alerts" tab
4. Test the connection flow!

