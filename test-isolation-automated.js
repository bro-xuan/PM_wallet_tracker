// Automated test to verify user isolation
// This tests the database and API logic directly

const { MongoClient } = require('mongodb');
const Database = require('better-sqlite3');

async function testUserIsolation() {
  console.log('🧪 Automated User Isolation Test\n');
  console.log('='.repeat(60));

  // Test 1: Check SQLite wallets (what should be migrated)
  console.log('\n1️⃣ Checking SQLite wallets...');
  let sqliteDb;
  try {
    sqliteDb = new Database('pm_tracker.db', { readonly: true });
    const sqliteWallets = sqliteDb.prepare('SELECT address FROM wallets ORDER BY address').all();
    console.log(`   Found ${sqliteWallets.length} wallets in SQLite:`);
    sqliteWallets.slice(0, 5).forEach(w => console.log(`     - ${w.address}`));
    if (sqliteWallets.length > 5) {
      console.log(`     ... and ${sqliteWallets.length - 5} more`);
    }
  } catch (error) {
    console.log(`   ⚠️  Could not read SQLite: ${error.message}`);
  } finally {
    if (sqliteDb) sqliteDb.close();
  }

  // Test 2: Check MongoDB wallets by user
  console.log('\n2️⃣ Checking MongoDB wallets by user...');
  
  if (!process.env.MONGODB_URI) {
    console.log('   ⚠️  MONGODB_URI not set, skipping MongoDB tests');
    console.log('\n📋 Manual Test Required:');
    console.log('   1. Login as zhixuan_wang@outlook.de');
    console.log('   2. Verify wallets are visible');
    console.log('   3. Login as different user');
    console.log('   4. Verify no wallets visible');
    return;
  }

  let client;
  try {
    client = new MongoClient(process.env.MONGODB_URI);
    await client.connect();
    const db = client.db(process.env.MONGODB_DB_NAME || 'pm-wallet-tracker');
    const usersCollection = db.collection('users');
    const walletsCollection = db.collection('wallets');

    // Find zhixuan_wang@outlook.de
    const targetUser = await usersCollection.findOne({ 
      email: 'zhixuan_wang@outlook.de'.toLowerCase() 
    });

    if (!targetUser) {
      console.log('   ❌ zhixuan_wang@outlook.de not found in database');
      console.log('   ⚠️  User needs to register first');
    } else {
      const targetUserId = targetUser._id.toString();
      console.log(`   ✅ Found user: zhixuan_wang@outlook.de (ID: ${targetUserId})`);
      
      // Get wallets for this user
      const targetWallets = await walletsCollection.find({
        userId: targetUserId,
        isActive: true
      }).toArray();
      
      console.log(`   📊 Wallets for zhixuan_wang@outlook.de: ${targetWallets.length}`);
      if (targetWallets.length > 0) {
        targetWallets.slice(0, 5).forEach(w => {
          console.log(`     - ${w.address}${w.label ? ` (${w.label})` : ''}`);
        });
        if (targetWallets.length > 5) {
          console.log(`     ... and ${targetWallets.length - 5} more`);
        }
      } else {
        console.log('   ⚠️  No wallets found - migration may not have run yet');
        console.log('   💡 Wallets will auto-migrate on first API call');
      }
    }

    // Check for other users
    console.log('\n3️⃣ Checking other users...');
    const allUsers = await usersCollection.find({}).toArray();
    console.log(`   Found ${allUsers.length} total users in database`);
    
    for (const user of allUsers) {
      if (user.email?.toLowerCase() === 'zhixuan_wang@outlook.de'.toLowerCase()) {
        continue; // Skip target user
      }
      
      const userId = user._id.toString();
      const userWallets = await walletsCollection.find({
        userId: userId,
        isActive: true
      }).toArray();
      
      console.log(`   📧 ${user.email}: ${userWallets.length} wallets`);
      if (userWallets.length > 0) {
        userWallets.forEach(w => {
          console.log(`     - ${w.address}`);
        });
      }
    }

    // Test 4: Verify isolation
    console.log('\n4️⃣ Verifying data isolation...');
    const allWallets = await walletsCollection.find({ isActive: true }).toArray();
    const userIds = new Set(allWallets.map(w => w.userId?.toString()));
    
    console.log(`   Total active wallets: ${allWallets.length}`);
    console.log(`   Unique users with wallets: ${userIds.size}`);
    
    // Check for any wallets without userId (shouldn't exist)
    const orphanedWallets = allWallets.filter(w => !w.userId);
    if (orphanedWallets.length > 0) {
      console.log(`   ⚠️  WARNING: Found ${orphanedWallets.length} wallets without userId!`);
    } else {
      console.log(`   ✅ All wallets are associated with users`);
    }

    // Check for duplicate addresses across users (this is OK, but verify)
    const addressToUsers = {};
    allWallets.forEach(w => {
      const addr = w.address.toLowerCase();
      if (!addressToUsers[addr]) {
        addressToUsers[addr] = new Set();
      }
      addressToUsers[addr].add(w.userId?.toString());
    });
    
    const sharedAddresses = Object.entries(addressToUsers)
      .filter(([_, userIds]) => userIds.size > 1);
    
    if (sharedAddresses.length > 0) {
      console.log(`   ℹ️  ${sharedAddresses.length} wallet addresses are monitored by multiple users (this is OK)`);
    } else {
      console.log(`   ✅ No wallet addresses shared between users`);
    }

  } catch (error) {
    console.error('   ❌ Error:', error.message);
  } finally {
    if (client) await client.close();
  }

  console.log('\n' + '='.repeat(60));
  console.log('\n✅ Database-level isolation test complete!');
  console.log('\n📋 Next Steps for Manual Testing:');
  console.log('   1. Open http://localhost:3000/app');
  console.log('   2. Login as zhixuan_wang@outlook.de');
  console.log('   3. Verify wallets appear in UI');
  console.log('   4. Logout and register new user');
  console.log('   5. Verify empty wallets list');
  console.log('   6. Add wallet and verify it only appears for that user');
}

// Try to load environment variables from .env.local manually
try {
  const fs = require('fs');
  const path = require('path');
  const envPath = path.join(__dirname, '.env.local');
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
  // Ignore if can't read .env.local
}

testUserIsolation()
  .then(() => {
    console.log('\n✅ Test complete!');
    process.exit(0);
  })
  .catch((error) => {
    console.error('\n❌ Test failed:', error);
    process.exit(1);
  });

