# Whale Worker

Python background worker for monitoring Polymarket trades and sending Telegram alerts.

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r ../requirements.txt
   ```

2. Set environment variables in `.env.local` (at repo root):
   ```
   MONGODB_URI=your_mongodb_uri
   MONGODB_DB_NAME=pm-wallet-tracker
   TELEGRAM_BOT_TOKEN=your_bot_token
   POLL_INTERVAL_SECONDS=10
   ```

3. Run the worker:
   ```bash
   python -m whale_worker.main
   # or from repo root:
   npm run dev:worker
   ```

## Development Status

✅ **Fully Implemented!** All core functionality is complete:

- ✅ `config.py` - Environment variable loading and validation
- ✅ `db.py` - MongoDB queries for filters, markets, cursors, caching
- ✅ `polymarket_client.py` - Data API and Gamma API integration
- ✅ `filters.py` - Trade matching logic against user filters
- ✅ `notifications.py` - Telegram Bot API integration
- ✅ `main.py` - Complete worker loop with all steps

**Implementation Steps:**
1. ✅ Poll trades from Polymarket Data API
2. ✅ Fetch market metadata from Gamma API (with caching)
3. ✅ Categorize markets (sports detection, tags)
4. ✅ Match trades against user filters
5. ✅ Send Telegram notifications

## Architecture

```
┌─────────────────┐
│  Next.js App    │
│  (User Config)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    MongoDB      │
│  - Filters      │
│  - Telegram     │
│  - Cursors      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Whale Worker   │
│  (Python)       │
│  1. Poll trades │
│  2. Match       │
│  3. Notify      │
└─────────────────┘
```

