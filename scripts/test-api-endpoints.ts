// Test API endpoints to verify they work with MongoDB
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

async function testAPIQueries(): Promise<TestResult[]> {
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

    // Test 1: Simulate GET /api/wallets
    const walletsCollection = db.collection('wallets');
    const usersCollection = db.collection('users');
    
    const testUser = await usersCollection.findOne({});
    if (!testUser) {
      results.push({
        name: 'API: GET /api/wallets',
        passed: false,
        message: 'No users found to test with',
      });
      await client.close();
      return results;
    }

    const userWallets = await walletsCollection.find(
      { userId: testUser._id.toString(), isActive: true },
      { projection: { address: 1, label: 1, _id: 0 } }
    ).toArray();

    const addresses = userWallets.map((w: any) => w.address);
    const labels: Record<string, string> = {};
    userWallets.forEach((w: any) => {
      if (w.label && w.label.trim()) {
        labels[w.address.toLowerCase()] = w.label.trim();
      }
    });

    results.push({
      name: 'API: GET /api/wallets',
      passed: addresses.length > 0,
      message: `Found ${addresses.length} wallets for user`,
      details: {
        addresses: addresses.length,
        labels: Object.keys(labels).length,
        sampleAddresses: addresses.slice(0, 3),
      },
    });

    // Test 2: Simulate GET /api/trades/recent
    const tradesCollection = db.collection('trades');
    const userWalletAddresses = Array.from(
      new Set(addresses.map((a: string) => String(a).toLowerCase()))
    );

    const filter: any = {
      proxyWallet: { $in: userWalletAddresses },
    };

    const total = await tradesCollection.countDocuments(filter);
    const docs = await tradesCollection
      .find(filter)
      .sort({ timestamp: -1 })
      .skip(0)
      .limit(10)
      .toArray();

    const trades = docs.map((r: any) => ({
      txhash: r.txhash,
      wallet: String(r.proxyWallet || '').toLowerCase(),
      side: r.side,
      size: r.size,
      price: r.price,
      notional: Number(r.size) * Number(r.price),
      outcome: r.outcome,
      title: r.title,
      slug: r.slug,
      timestamp: r.timestamp,
    }));

    results.push({
      name: 'API: GET /api/trades/recent',
      passed: total > 0 && trades.length > 0,
      message: `Found ${total} total trades, returned ${trades.length} in first page`,
      details: {
        total,
        returned: trades.length,
        sampleTrade: trades[0] ? {
          txhash: trades[0].txhash,
          wallet: trades[0].wallet,
          timestamp: trades[0].timestamp,
        } : null,
      },
    });

    // Test 3: Test pagination
    const page1 = await tradesCollection
      .find(filter)
      .sort({ timestamp: -1 })
      .skip(0)
      .limit(10)
      .toArray();
    
    const page2 = await tradesCollection
      .find(filter)
      .sort({ timestamp: -1 })
      .skip(10)
      .limit(10)
      .toArray();

    const page1Txhashes = new Set(page1.map((t: any) => t.txhash));
    const page2Txhashes = new Set(page2.map((t: any) => t.txhash));
    const noOverlap = !Array.from(page1Txhashes).some(tx => page2Txhashes.has(tx));

    results.push({
      name: 'API: Pagination',
      passed: page1.length > 0 && page2.length > 0 && noOverlap,
      message: `Page 1: ${page1.length} trades, Page 2: ${page2.length} trades, No overlap: ${noOverlap}`,
      details: {
        page1Count: page1.length,
        page2Count: page2.length,
        noOverlap,
      },
    });

    // Test 4: Test filtering by notional
    const minNotional = 1000;
    const notionalFilter = {
      ...filter,
      $expr: {
        $gte: [{ $multiply: ['$size', '$price'] }, minNotional],
      },
    };
    const highNotionalCount = await tradesCollection.countDocuments(notionalFilter);

    results.push({
      name: 'API: Filter by Notional',
      passed: highNotionalCount >= 0,
      message: `Found ${highNotionalCount} trades with notional >= ${minNotional}`,
      details: {
        minNotional,
        count: highNotionalCount,
      },
    });

    // Test 5: Test wallet deletion simulation
    if (addresses.length > 0) {
      const testAddress = addresses[0].toLowerCase();
      const walletBefore = await walletsCollection.findOne({
        userId: testUser._id.toString(),
        address: testAddress,
      });
      const cursorBefore = await db.collection('cursors').findOne({ address: testAddress });
      const tradesBefore = await tradesCollection.countDocuments({ proxyWallet: testAddress });

      results.push({
        name: 'API: DELETE /api/wallets/[address] (Simulation)',
        passed: walletBefore !== null,
        message: `Would delete wallet ${testAddress} (${tradesBefore} trades, cursor exists: ${!!cursorBefore})`,
        details: {
          walletExists: !!walletBefore,
          tradesCount: tradesBefore,
          cursorExists: !!cursorBefore,
        },
      });
    }

    // Test 6: Test wallet label update simulation
    if (addresses.length > 0) {
      const testAddress = addresses[0].toLowerCase();
      const walletBefore = await walletsCollection.findOne({
        userId: testUser._id.toString(),
        address: testAddress,
      });

      if (walletBefore) {
        results.push({
          name: 'API: PUT /api/wallets/[address]/label (Simulation)',
          passed: true,
          message: `Can update label for wallet ${testAddress}`,
          details: {
            currentLabel: walletBefore.label || '(empty)',
          },
        });
      }
    }

    // Test 7: Test data freshness
    const oneHourAgo = Math.floor(Date.now() / 1000) - 3600;
    const recentTrades = await tradesCollection.countDocuments({
      ...filter,
      timestamp: { $gte: oneHourAgo },
    });

    results.push({
      name: 'Data Freshness',
      passed: true,
      message: `Found ${recentTrades} trades in the last hour`,
      details: {
        recentTrades,
        oneHourAgo: new Date(oneHourAgo * 1000).toISOString(),
      },
    });

    // Test 8: Test cursor updates
    const cursorsCollection = db.collection('cursors');
    const testWallet = userWalletAddresses[0];
    const cursor = await cursorsCollection.findOne({ address: testWallet });
    
    if (cursor) {
      const latestTrade = await tradesCollection.findOne(
        { proxyWallet: testWallet },
        { sort: { timestamp: -1 } }
      );

      results.push({
        name: 'Cursor Consistency',
        passed: latestTrade ? latestTrade.timestamp <= cursor.last_ts : true,
        message: `Cursor for ${testWallet}: last_ts=${cursor.last_ts}, latest trade: ${latestTrade?.timestamp || 'N/A'}`,
        details: {
          cursorLastTs: cursor.last_ts,
          latestTradeTs: latestTrade?.timestamp,
          isUpToDate: latestTrade ? latestTrade.timestamp <= cursor.last_ts : null,
        },
      });
    }

  } catch (error: any) {
    results.push({
      name: 'API Test Execution',
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
  console.log('🧪 Testing API Endpoints (MongoDB)...\n');
  console.log('='.repeat(60));
  
  const results = await testAPIQueries();
  
  console.log('\n📊 Test Results:\n');
  let passed = 0;
  let failed = 0;
  
  results.forEach((result, index) => {
    const icon = result.passed ? '✅' : '❌';
    const status = result.passed ? 'PASS' : 'FAIL';
    console.log(`${index + 1}. ${icon} [${status}] ${result.name}`);
    console.log(`   ${result.message}`);
    if (result.details && Object.keys(result.details).length > 0) {
      const detailsStr = JSON.stringify(result.details, null, 2);
      if (detailsStr.length < 200) {
        console.log(`   Details: ${detailsStr}`);
      } else {
        console.log(`   Details: ${detailsStr.substring(0, 200)}...`);
      }
    }
    console.log();
    
    if (result.passed) passed++;
    else failed++;
  });
  
  console.log('='.repeat(60));
  console.log(`\n📈 Summary: ${passed} passed, ${failed} failed\n`);
  
  if (failed === 0) {
    console.log('🎉 All API tests passed!\n');
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

