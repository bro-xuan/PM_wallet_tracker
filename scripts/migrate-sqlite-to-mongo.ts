// One-time migration script: move trades and cursors from SQLite to MongoDB
//
// Usage (run from project root):
//   npx tsx scripts/migrate-sqlite-to-mongo.ts
//
// NOTE: This script should be run in your local environment where:
// - pm_tracker.db exists with wallets/cursors/trades
// - .env.local contains MONGODB_URI and MONGODB_DB_NAME

import Database from 'better-sqlite3';
import { MongoClient } from 'mongodb';
import fs from 'fs';
import path from 'path';

function loadEnv() {
  try {
    const envPath = path.join(process.cwd(), '.env.local');
    if (fs.existsSync(envPath)) {
      const envContent = fs.readFileSync(envPath, 'utf8');
      envContent.split('\n').forEach(line => {
        const match = line.match(/^([^#=]+)=(.*)$/);
        if (match) {
          const key = match[1].trim();
          const value = match[2].trim().replace(/^[\"']|[\"']$/g, '');
          if (!process.env[key]) {
            process.env[key] = value;
          }
        }
      });
    }
  } catch (e: any) {
    console.error('Failed to load .env.local:', e.message);
  }
}

async function main() {
  console.log('🚚 Migrating SQLite data to MongoDB...');
  loadEnv();

  const uri = process.env.MONGODB_URI;
  if (!uri) {
    console.error('MONGODB_URI is not set. Please configure it in .env.local.');
    process.exit(1);
  }

  const dbName = process.env.MONGODB_DB_NAME || 'pm-wallet-tracker';

  // Open SQLite
  const sqlitePath = path.join(process.cwd(), 'pm_tracker.db');
  if (!fs.existsSync(sqlitePath)) {
    console.error(`SQLite database not found at ${sqlitePath}`);
    process.exit(1);
  }

  const sqlite = new Database(sqlitePath, { readonly: true });

  const client = new MongoClient(uri);

  try {
    await client.connect();
    const mongo = client.db(dbName);
    const tradesCollection = mongo.collection('trades');
    const cursorsCollection = mongo.collection('cursors');

    // Ensure indexes
    await tradesCollection.createIndex({ txhash: 1 }, { unique: true }).catch(() => {});
    await tradesCollection.createIndex({ proxyWallet: 1, timestamp: -1 }).catch(() => {});
    await tradesCollection.createIndex({ timestamp: -1 }).catch(() => {});
    await cursorsCollection.createIndex({ address: 1 }, { unique: true }).catch(() => {});

    // Migrate cursors
    console.log('\n📍 Migrating cursors...');
    const cursorRows = sqlite.prepare('SELECT address, last_ts FROM cursors').all();
    let cursorUpserts = 0;
    for (const row of cursorRows) {
      const address = String(row.address).toLowerCase();
      const last_ts = Number(row.last_ts || 0);
      await cursorsCollection.updateOne(
        { address },
        { $set: { address, last_ts } },
        { upsert: true }
      );
      cursorUpserts++;
    }
    console.log(`   → Migrated ${cursorUpserts} cursor entries`);

    // Migrate trades
    console.log('\n📊 Migrating trades...');
    const tradeStmt = sqlite.prepare(`
      SELECT txhash, proxyWallet, side, size, price, outcome, title, slug, timestamp
      FROM trades
      ORDER BY timestamp ASC
    `);
    const trades = tradeStmt.all();
    console.log(`   Found ${trades.length} trades in SQLite`);

    let migrated = 0;
    for (const row of trades) {
      const txhash = String(row.txhash);
      const proxyWallet = String(row.proxyWallet).toLowerCase();
      const side = String(row.side);
      const size = Number(row.size);
      const price = Number(row.price);
      const outcome = row.outcome ?? null;
      const title = row.title ?? null;
      const slug = row.slug ?? null;
      const timestamp = Number(row.timestamp);

      await tradesCollection.updateOne(
        { txhash },
        {
          $set: {
            txhash,
            proxyWallet,
            side,
            size,
            price,
            outcome,
            title,
            slug,
            timestamp,
          },
        },
        { upsert: true }
      );
      migrated++;
      if (migrated % 1000 === 0) {
        console.log(`   → Migrated ${migrated}/${trades.length} trades...`);
      }
    }

    console.log(`   → Migrated ${migrated} trades`);

    console.log('\n✅ Migration completed successfully.');
    console.log('   You can now retire SQLite usage in the app.');
  } catch (error: any) {
    console.error('Migration failed:', error);
    process.exit(1);
  } finally {
    sqlite.close();
    await client.close();
  }
}

main();


