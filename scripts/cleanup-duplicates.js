// Script to remove duplicate wallets for a user
const { MongoClient } = require('mongodb');
const fs = require('fs');
const path = require('path');

// Load .env.local
try {
  const envPath = path.join(__dirname, '..', '.env.local');
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
} catch (e) {
  console.error('Error loading .env.local:', e.message);
  process.exit(1);
}

async function cleanupDuplicates() {
  const email = 'zhixuan_wang@outlook.de';
  
  if (!process.env.MONGODB_URI) {
    console.error('MONGODB_URI not set');
    process.exit(1);
  }

  const client = new MongoClient(process.env.MONGODB_URI);
  
  try {
    await client.connect();
    const db = client.db(process.env.MONGODB_DB_NAME || 'pm-wallet-tracker');
    const usersCollection = db.collection('users');
    const walletsCollection = db.collection('wallets');

    // Find user
    const user = await usersCollection.findOne({ 
      email: email.toLowerCase() 
    });

    if (!user) {
      console.error(`User ${email} not found`);
      process.exit(1);
    }

    const userId = user._id.toString();
    console.log(`Found user: ${email} (ID: ${userId})`);

    // Get all wallets for this user
    const allWallets = await walletsCollection.find({
      userId: userId,
      isActive: true
    }).toArray();

    console.log(`\nTotal wallets found: ${allWallets.length}`);

    // Group by address
    const addressMap = new Map();
    allWallets.forEach(wallet => {
      const addr = wallet.address.toLowerCase();
      if (!addressMap.has(addr)) {
        addressMap.set(addr, []);
      }
      addressMap.get(addr).push(wallet);
    });

    console.log(`Unique addresses: ${addressMap.size}`);

    // Find duplicates
    const duplicates = [];
    addressMap.forEach((wallets, address) => {
      if (wallets.length > 1) {
        duplicates.push({ address, wallets });
      }
    });

    if (duplicates.length === 0) {
      console.log('\n✅ No duplicates found!');
      return;
    }

    console.log(`\nFound ${duplicates.length} addresses with duplicates:`);
    duplicates.forEach(({ address, wallets }) => {
      console.log(`  ${address}: ${wallets.length} copies`);
    });

    // Remove duplicates, keeping the oldest one (earliest createdAt)
    let removed = 0;
    for (const { address, wallets } of duplicates) {
      // Sort by createdAt, keep the oldest
      wallets.sort((a, b) => {
        const aTime = a.createdAt ? new Date(a.createdAt).getTime() : 0;
        const bTime = b.createdAt ? new Date(b.createdAt).getTime() : 0;
        return aTime - bTime;
      });

      const keep = wallets[0];
      const remove = wallets.slice(1);

      console.log(`\nKeeping wallet ${keep._id} (created: ${keep.createdAt || 'unknown'})`);
      
      for (const wallet of remove) {
        await walletsCollection.deleteOne({ _id: wallet._id });
        removed++;
        console.log(`  Removed duplicate ${wallet._id}`);
      }
    }

    // Verify final count
    const finalWallets = await walletsCollection.find({
      userId: userId,
      isActive: true
    }).toArray();

    console.log(`\n✅ Cleanup complete!`);
    console.log(`   Removed: ${removed} duplicate wallets`);
    console.log(`   Final count: ${finalWallets.length} unique wallets`);

  } catch (error) {
    console.error('Error:', error);
    process.exit(1);
  } finally {
    await client.close();
  }
}

cleanupDuplicates();

