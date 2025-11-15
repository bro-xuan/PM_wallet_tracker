// server-only SQLite with better-sqlite3 (Node runtime)
import Database from 'better-sqlite3';

const globalAny = globalThis as any;

let db: Database.Database;
if (!globalAny.__PM_DB__) {
  db = new Database('pm_tracker.db');
  db.pragma('journal_mode = WAL');
  db.exec(`
    CREATE TABLE IF NOT EXISTS wallets (
      address TEXT PRIMARY KEY
    );
    CREATE TABLE IF NOT EXISTS cursors (
      address TEXT PRIMARY KEY,
      last_ts INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS trades (
      txhash TEXT PRIMARY KEY,
      proxyWallet TEXT NOT NULL,
      side TEXT NOT NULL,
      size REAL NOT NULL,
      price REAL NOT NULL,
      outcome TEXT,
      title TEXT,
      slug TEXT,
      timestamp INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_trades_time ON trades(timestamp DESC);
  `);
  globalAny.__PM_DB__ = db;
} else {
  db = globalAny.__PM_DB__;
}

export default db;

// prepared statements (optional helpers)
export const stmt = {
  insertWallet: db.prepare('INSERT OR IGNORE INTO wallets(address) VALUES (?)'),
  deleteWallet: db.prepare('DELETE FROM wallets WHERE address = ?'),
  deleteCursor: db.prepare('DELETE FROM cursors WHERE address = ?'),
  listWallets: db.prepare('SELECT address FROM wallets ORDER BY address'),
  getCursor:   db.prepare('SELECT last_ts FROM cursors WHERE address = ?'),
  upsertCursor: db.prepare(`
    INSERT INTO cursors(address, last_ts) VALUES (?, ?)
    ON CONFLICT(address) DO UPDATE SET last_ts=excluded.last_ts
  `),
  deleteTradesByWallet: db.prepare('DELETE FROM trades WHERE proxyWallet = ?'),
  insertTrade: db.prepare(`
    INSERT OR REPLACE INTO trades
      (txhash, proxyWallet, side, size, price, outcome, title, slug, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  `),
  listRecent: db.prepare(`
    SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?
  `),
};
