⚠️ Deployment note: Background timers are not reliable on serverless (e.g., Vercel autoscaling). For production serverless you’d:

Move the poller to a small Node worker (or a cron job) and

Use a shared store / pubsub (Postgres LISTEN/NOTIFY, Upstash Redis Pub/Sub) for the SSE route.
For local or a single VPS/container, the below setup works great.





This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

## Whale Worker (Python)

The whale trades alert system uses a separate Python background worker (`whale_worker/`) that monitors all Polymarket trades and sends Telegram notifications to users when trades match their configured filters.

### Architecture

- **Frontend (Next.js)**: Users configure their alert filters (notional, price range, sides) and connect their Telegram accounts
- **Backend (Next.js API)**: Stores user configurations and Telegram connections in MongoDB
- **Worker (Python)**: Continuously polls Polymarket API for new trades, matches them against user filters, and sends Telegram notifications

The worker runs independently from the Next.js application and can be deployed as a separate service or background job.

### Setup

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Ensure environment variables are set in `.env.local`:
   - `MONGODB_URI` - MongoDB connection string
   - `MONGODB_DB_NAME` - Database name
   - `TELEGRAM_BOT_TOKEN` - Telegram bot token
   - `POLL_INTERVAL_SECONDS` - Polling interval (default: 10 seconds)

3. Run the worker in development:
   ```bash
   npm run dev:worker
   # or directly:
   python -m whale_worker.main
   ```

### Development Status

The worker is currently scaffolded with stub implementations. Each module contains:
- Function/class definitions with proper signatures
- Docstrings explaining purpose and parameters
- TODO comments indicating what needs to be implemented
- `NotImplementedError` or `pass` placeholders

Modules:
- `config.py` - Environment variable loading
- `db.py` - MongoDB helpers for filters, cursors, and user data
- `polymarket_client.py` - Polymarket Data API and Gamma API clients
- `filters.py` - Trade matching logic against user filters
- `notifications.py` - Telegram message formatting and sending
- `main.py` - Main worker loop orchestration
- `types.py` - Type definitions and dataclasses
