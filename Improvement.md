different user login with different monitored wallet 

-----

Given where you’re going (multiple users, Telegram alerts, etc.), I’d do:
Short‑term (what you have now)
Keep SQLite poller + trades as the ingestion cache.
Use Mongo for user, wallets, labels, Telegram, configs (already done).
This is fine for experimentation and a single deployment.
Medium‑term (when you’re ready to stabilize)
Introduce Mongo collections:
user_wallets (already), user_trades or trades with userId + wallet.
cursors keyed by userId + wallet.
Change lib/poller.ts to:
Either write directly into Mongo, or
Read from SQLite and write per‑user views into Mongo (bridge phase).
Update:
/api/trades/recent
/api/stream
To read from Mongo instead of SQLite.
Long‑term
Retire SQLite completely for production, or keep it only as a local cache / dev tool.

------ 
Track wallet categorization
-----

