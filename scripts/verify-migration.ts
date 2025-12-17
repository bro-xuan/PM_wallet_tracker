// Quick verification script to check MongoDB data after migration
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
          const value = match[2].trim().replace(/^["']|["']$/g, '');
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

async function verify() {
  console.log('🔍 Verifying MongoDB migration...\n');
  loadEnv();

  const uri = process.env.MONGODB_URI;
  if (!uri) {
    console.error('MONGODB_URI not set');
    process.exit(1);
  }

  const dbName = process.env.MONGODB_DB_NAME || 'pm-wallet-tracker';
  const client = new MongoClient(uri);

  try {
    await client.connect();
    const db = client.db(dbName);
    const tradesCollection = db.collection('trades');
    const cursorsCollection = db.collection('cursors');
    const walletsCollection = db.collection('wallets');

    // Check trades
    const tradeCount = await tradesCollection.countDocuments();
    const latestTrade = await tradesCollection.findOne(
      {},
      { sort: { timestamp: -1 } }
    );
    const oldestTrade = await tradesCollection.findOne(
      {},
      { sort: { timestamp: 1 } }
    );

    console.log('📊 Trades Collection:');
    console.log(`   Total trades: ${tradeCount.toLocaleString()}`);
    if (latestTrade) {
      console.log(`   Latest trade: ${new Date(latestTrade.timestamp * 1000).toISOString()}`);
      console.log(`   Wallet: ${latestTrade.proxyWallet}`);
    }
    if (oldestTrade) {
      console.log(`   Oldest trade: ${new Date(oldestTrade.timestamp * 1000).toISOString()}`);
    }

    // Check cursors
    const cursorCount = await cursorsCollection.countDocuments();
    const sampleCursors = await cursorsCollection.find({}).limit(3).toArray();
    console.log(`\n📍 Cursors Collection:`);
    console.log(`   Total cursors: ${cursorCount}`);
    if (sampleCursors.length > 0) {
      console.log(`   Sample cursors:`);
      sampleCursors.forEach(c => {
        console.log(`     - ${c.address}: last_ts = ${c.last_ts} (${new Date(c.last_ts * 1000).toISOString()})`);
      });
    }

    // Check wallets
    const walletCount = await walletsCollection.countDocuments({ isActive: true });
    console.log(`\n👛 Wallets Collection:`);
    console.log(`   Active wallets: ${walletCount}`);

    // Check indexes
    const tradeIndexes = await tradesCollection.indexes();
    console.log(`\n📑 Indexes on trades:`);
    tradeIndexes.forEach(idx => {
      console.log(`   - ${JSON.stringify(idx.key)}`);
    });

    console.log('\n✅ Verification complete!');
  } catch (error: any) {
    console.error('❌ Verification failed:', error);
    process.exit(1);
  } finally {
    await client.close();
  }
}

verify();

