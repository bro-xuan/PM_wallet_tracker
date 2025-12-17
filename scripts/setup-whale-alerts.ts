// Setup script to create indexes for whale alerts collections
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
          if (!process.env[key]) process.env[key] = value;
        }
      });
    }
  } catch (e: any) {
    console.error('Failed to load .env.local:', e.message);
  }
}

async function setupIndexes() {
  console.log('🔧 Setting up Whale Alerts database indexes...\n');
  loadEnv();

  const uri = process.env.MONGODB_URI;
  if (!uri) {
    console.error('MONGODB_URI is not set');
    process.exit(1);
  }

  const dbName = process.env.MONGODB_DB_NAME || 'pm-wallet-tracker';
  const client = new MongoClient(uri);

  try {
    await client.connect();
    const db = client.db(dbName);
    console.log(`✅ Connected to MongoDB: ${dbName}\n`);

    // Create indexes for telegramAccounts
    console.log('📱 Creating indexes for telegramAccounts...');
    const telegramAccountsCollection = db.collection('telegramAccounts');
    await telegramAccountsCollection.createIndex({ userId: 1 }, { unique: true });
    await telegramAccountsCollection.createIndex({ chatId: 1 }, { unique: true });
    await telegramAccountsCollection.createIndex({ isActive: 1 });
    console.log('   ✅ telegramAccounts indexes created');

    // Create indexes for whaleAlertConfigs
    console.log('⚙️  Creating indexes for whaleAlertConfigs...');
    const configCollection = db.collection('whaleAlertConfigs');
    await configCollection.createIndex({ userId: 1 }, { unique: true });
    await configCollection.createIndex({ enabled: 1 });
    console.log('   ✅ whaleAlertConfigs indexes created');

    // Create indexes for whaleAlertCursors
    console.log('📍 Creating indexes for whaleAlertCursors...');
    const cursorsCollection = db.collection('whaleAlertCursors');
    await cursorsCollection.createIndex({ lastProcessedTimestamp: -1 });
    console.log('   ✅ whaleAlertCursors indexes created');

    console.log('\n✅ All indexes created successfully!\n');
  } catch (error: any) {
    console.error('❌ Error setting up indexes:', error);
    process.exit(1);
  } finally {
    await client.close();
  }
}

setupIndexes();

