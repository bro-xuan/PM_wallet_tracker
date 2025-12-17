// Comprehensive test script to verify MongoDB migration and architecture
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

interface TestResult {
  name: string;
  passed: boolean;
  message: string;
  details?: any;
}

async function runTests(): Promise<TestResult[]> {
  const results: TestResult[] = [];
  
  loadEnv();
  
  const uri = process.env.MONGODB_URI;
  if (!uri) {
    results.push({
      name: 'Environment Setup',
      passed: false,
      message: 'MONGODB_URI is not set',
    });
    return results;
  }

  const dbName = process.env.MONGODB_DB_NAME || 'pm-wallet-tracker';
  const client = new MongoClient(uri);

  try {
    await client.connect();
    const db = client.db(dbName);
    console.log('✅ Connected to MongoDB\n');

    // Test 1: Database Connection
    results.push({
      name: 'MongoDB Connection',
      passed: true,
      message: 'Successfully connected to MongoDB',
    });

    // Test 2: Collections Exist
    const collections = await db.listCollections().toArray();
    const collectionNames = collections.map(c => c.name);
    const requiredCollections = ['trades', 'cursors', 'wallets', 'users'];
    const missingCollections = requiredCollections.filter(c => !collectionNames.includes(c));
    
    results.push({
      name: 'Collections Exist',
      passed: missingCollections.length === 0,
      message: missingCollections.length === 0
        ? 'All required collections exist'
        : `Missing collections: ${missingCollections.join(', ')}`,
      details: { found: collectionNames, required: requiredCollections },
    });

    // Test 3: Trades Collection
    const tradesCollection = db.collection('trades');
    const tradeCount = await tradesCollection.countDocuments();
    const sampleTrade = await tradesCollection.findOne({});
    
    results.push({
      name: 'Trades Collection',
      passed: tradeCount > 0 && sampleTrade !== null,
      message: `Found ${tradeCount} trades`,
      details: {
        count: tradeCount,
        sample: sampleTrade ? {
          txhash: sampleTrade.txhash,
          proxyWallet: sampleTrade.proxyWallet,
          timestamp: sampleTrade.timestamp,
          hasRequiredFields: !!(sampleTrade.txhash && sampleTrade.proxyWallet && sampleTrade.timestamp),
        } : null,
      },
    });

    // Test 4: Trades Indexes
    const tradeIndexes = await tradesCollection.indexes();
    const hasTxhashIndex = tradeIndexes.some(idx => idx.key?.txhash);
    const hasProxyWalletTimestampIndex = tradeIndexes.some(idx => 
      idx.key?.proxyWallet && idx.key?.timestamp
    );
    
    results.push({
      name: 'Trades Indexes',
      passed: hasTxhashIndex && hasProxyWalletTimestampIndex,
      message: hasTxhashIndex && hasProxyWalletTimestampIndex
        ? 'Required indexes exist'
        : `Missing indexes. Found: ${JSON.stringify(tradeIndexes.map(i => i.key))}`,
      details: { indexes: tradeIndexes.map(i => i.key) },
    });

    // Test 5: Cursors Collection
    const cursorsCollection = db.collection('cursors');
    const cursorCount = await cursorsCollection.countDocuments();
    const sampleCursor = await cursorsCollection.findOne({});
    
    results.push({
      name: 'Cursors Collection',
      passed: cursorCount > 0 && sampleCursor !== null,
      message: `Found ${cursorCount} cursors`,
      details: {
        count: cursorCount,
        sample: sampleCursor ? {
          address: sampleCursor.address,
          last_ts: sampleCursor.last_ts,
        } : null,
      },
    });

    // Test 6: Wallets Collection
    const walletsCollection = db.collection('wallets');
    const walletCount = await walletsCollection.countDocuments();
    const activeWalletCount = await walletsCollection.countDocuments({ isActive: true });
    const sampleWallet = await walletsCollection.findOne({});
    
    results.push({
      name: 'Wallets Collection',
      passed: walletCount > 0 && sampleWallet !== null,
      message: `Found ${walletCount} total wallets, ${activeWalletCount} active`,
      details: {
        total: walletCount,
        active: activeWalletCount,
        sample: sampleWallet ? {
          address: sampleWallet.address,
          userId: sampleWallet.userId,
          isActive: sampleWallet.isActive,
          hasLabel: !!sampleWallet.label,
        } : null,
      },
    });

    // Test 7: User Isolation
    const usersCollection = db.collection('users');
    const userCount = await usersCollection.countDocuments();
    const users = await usersCollection.find({}).limit(5).toArray();
    
    if (userCount > 0) {
      // Check if wallets are properly associated with users
      const userWallets = await walletsCollection.aggregate([
        { $group: { _id: '$userId', count: { $sum: 1 } } },
        { $limit: 5 },
      ]).toArray();
      
      results.push({
        name: 'User Isolation',
        passed: userWallets.length > 0 && userWallets.every((uw: any) => uw._id),
        message: `Found ${userCount} users, wallets are user-scoped`,
        details: {
          userCount,
          userWalletCounts: userWallets,
        },
      });
    } else {
      results.push({
        name: 'User Isolation',
        passed: true,
        message: 'No users yet (expected for new setup)',
      });
    }

    // Test 8: Data Consistency - Trades match wallets
    const allWallets = await walletsCollection.find({ isActive: true }).toArray();
    const walletAddresses = allWallets.map((w: any) => w.address.toLowerCase());
    
    if (walletAddresses.length > 0) {
      const tradesForWallets = await tradesCollection.countDocuments({
        proxyWallet: { $in: walletAddresses },
      });
      const totalTrades = await tradesCollection.countDocuments({});
      
      results.push({
        name: 'Data Consistency',
        passed: tradesForWallets > 0,
        message: `${tradesForWallets} trades match ${walletAddresses.length} active wallets (${totalTrades} total trades)`,
        details: {
          activeWallets: walletAddresses.length,
          matchingTrades: tradesForWallets,
          totalTrades,
        },
      });
    } else {
      results.push({
        name: 'Data Consistency',
        passed: true,
        message: 'No active wallets to check',
      });
    }

    // Test 9: Wallet Address Normalization
    const walletsWithMixedCase = await walletsCollection.find({
      address: { $regex: /[A-F]/ },
    }).limit(5).toArray();
    
    results.push({
      name: 'Wallet Address Normalization',
      passed: walletsWithMixedCase.length === 0,
      message: walletsWithMixedCase.length === 0
        ? 'All wallet addresses are lowercase'
        : `Found ${walletsWithMixedCase.length} wallets with uppercase letters`,
      details: walletsWithMixedCase.length > 0 ? {
        examples: walletsWithMixedCase.map((w: any) => w.address),
      } : null,
    });

    // Test 10: Trade Address Normalization
    const tradesWithMixedCase = await tradesCollection.find({
      proxyWallet: { $regex: /[A-F]/ },
    }).limit(5).toArray();
    
    results.push({
      name: 'Trade Address Normalization',
      passed: tradesWithMixedCase.length === 0,
      message: tradesWithMixedCase.length === 0
        ? 'All trade proxyWallet addresses are lowercase'
        : `Found ${tradesWithMixedCase.length} trades with uppercase proxyWallet`,
      details: tradesWithMixedCase.length > 0 ? {
        examples: tradesWithMixedCase.map((t: any) => ({
          txhash: t.txhash,
          proxyWallet: t.proxyWallet,
        })),
      } : null,
    });

    // Test 11: Recent Trades Query Performance
    if (walletAddresses.length > 0) {
      const startTime = Date.now();
      const recentTrades = await tradesCollection
        .find({ proxyWallet: { $in: walletAddresses } })
        .sort({ timestamp: -1 })
        .limit(10)
        .toArray();
      const queryTime = Date.now() - startTime;
      
      results.push({
        name: 'Query Performance',
        passed: queryTime < 1000,
        message: `Recent trades query took ${queryTime}ms`,
        details: {
          queryTime,
          resultsReturned: recentTrades.length,
        },
      });
    } else {
      results.push({
        name: 'Query Performance',
        passed: true,
        message: 'Skipped (no active wallets)',
      });
    }

    // Test 12: Cursor-Wallet Consistency
    const cursorAddresses = await cursorsCollection.distinct('address');
    const cursorAddressesLower = cursorAddresses.map((a: string) => a.toLowerCase());
    const walletAddressesLower = walletAddresses.map((a: string) => a.toLowerCase());
    
    const cursorsWithoutWallets = cursorAddressesLower.filter(
      (addr: string) => !walletAddressesLower.includes(addr)
    );
    const walletsWithoutCursors = walletAddressesLower.filter(
      (addr: string) => !cursorAddressesLower.includes(addr)
    );
    
    results.push({
      name: 'Cursor-Wallet Consistency',
      passed: cursorsWithoutWallets.length === 0,
      message: cursorsWithoutWallets.length === 0
        ? 'All cursors have corresponding active wallets'
        : `Found ${cursorsWithoutWallets.length} cursors without active wallets`,
      details: {
        cursorCount: cursorAddresses.length,
        walletCount: walletAddresses.length,
        cursorsWithoutWallets: cursorsWithoutWallets.slice(0, 5),
        walletsWithoutCursors: walletsWithoutCursors.slice(0, 5),
      },
    });

  } catch (error: any) {
    results.push({
      name: 'Test Execution',
      passed: false,
      message: `Error during testing: ${error.message}`,
      details: { error: error.stack },
    });
  } finally {
    await client.close();
  }

  return results;
}

async function main() {
  console.log('🧪 Running MongoDB Migration Tests...\n');
  console.log('='.repeat(60));
  
  const results = await runTests();
  
  console.log('\n📊 Test Results:\n');
  let passed = 0;
  let failed = 0;
  
  results.forEach((result, index) => {
    const icon = result.passed ? '✅' : '❌';
    const status = result.passed ? 'PASS' : 'FAIL';
    console.log(`${index + 1}. ${icon} [${status}] ${result.name}`);
    console.log(`   ${result.message}`);
    if (result.details && Object.keys(result.details).length > 0) {
      console.log(`   Details: ${JSON.stringify(result.details, null, 2).split('\n').join('\n   ')}`);
    }
    console.log();
    
    if (result.passed) passed++;
    else failed++;
  });
  
  console.log('='.repeat(60));
  console.log(`\n📈 Summary: ${passed} passed, ${failed} failed\n`);
  
  if (failed === 0) {
    console.log('🎉 All tests passed! Migration is successful.\n');
    process.exit(0);
  } else {
    console.log('⚠️  Some tests failed. Please review the issues above.\n');
    process.exit(1);
  }
}

main().catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});

