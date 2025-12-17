import { publish } from './bus';
import { fetchTradesForUser, DataTrade } from './polymarket';
import clientPromise from './mongodb';

const globalAny = globalThis as any;
const POLL_INTERVAL_MS = Number(process.env.POLL_INTERVAL_MS || 1000);

async function getDb() {
  const client = await clientPromise;
  return client.db(process.env.MONGODB_DB_NAME || 'pm-wallet-tracker');
}

// Get distinct active wallet addresses across all users from MongoDB
async function wallets(): Promise<string[]> {
  try {
    const db = await getDb();
    const walletsCollection = db.collection('wallets');
    const allWallets = await walletsCollection.find(
      { isActive: true },
      { projection: { address: 1, _id: 0 } }
    ).toArray();
    // Ensure lowercase + uniqueness
    const set = new Set<string>();
    allWallets.forEach((w: any) => {
      if (w.address) set.add(String(w.address).toLowerCase());
    });
    return Array.from(set);
  } catch (error) {
    console.error('[poller] Error fetching wallets from MongoDB:', error);
    return [];
  }
}

async function getCursor(address: string): Promise<number> {
  try {
    const db = await getDb();
    const cursors = db.collection('cursors');
    const doc = await cursors.findOne<{ last_ts?: number }>({ address });
    return doc?.last_ts ?? 0;
  } catch (error) {
    console.error('[poller] Error reading cursor:', error);
    return 0;
  }
}

async function updateCursor(address: string, lastTs: number) {
  try {
    const db = await getDb();
    const cursors = db.collection('cursors');
    await cursors.updateOne(
      { address },
      { $set: { address, last_ts: lastTs } },
      { upsert: true }
    );
  } catch (error) {
    console.error('[poller] Error updating cursor:', error);
  }
}

async function upsertTrade(t: DataTrade): Promise<boolean> {
  try {
    const db = await getDb();
    const trades = db.collection('trades');
    // Ensure proxyWallet is always lowercase for consistent filtering
    const proxyWalletLower = String(t.proxyWallet).toLowerCase();
    const result = await trades.updateOne(
      { txhash: t.transactionHash },
      {
        $set: {
          txhash: t.transactionHash,
          proxyWallet: proxyWalletLower,
          side: t.side,
          size: t.size,
          price: t.price,
          outcome: t.outcome ?? null,
          title: t.title ?? null,
          slug: t.slug ?? null,
          timestamp: t.timestamp,
          updatedAt: new Date(), // Track when trade was last updated
        },
        $setOnInsert: {
          createdAt: new Date(), // Track when trade was first created
        },
      },
      { upsert: true }
    );
    // Return true if trade was inserted or updated
    return result.upsertedCount > 0 || result.modifiedCount > 0 || result.matchedCount > 0;
  } catch (error) {
    console.error('[poller] Error upserting trade:', error);
    return false;
  }
}

let rotatingIndex = 0;

async function processNextWallet() {
  const ws = await wallets();
  if (ws.length === 0) return;
  const idx = rotatingIndex % ws.length;
  rotatingIndex++;
  const address = ws[idx];

  try {
    const rows = await fetchTradesForUser(address, 50);
    const lastTs = await getCursor(address);

    // rows are newest-first; we only want trades with txHash not seen AND ts > cursor
    const fresh: DataTrade[] = [];
    for (const r of rows) {
      if (!r.transactionHash) continue;
      if (lastTs && r.timestamp <= lastTs) continue;
      fresh.push(r);
    }

    // oldest -> newest for deterministic inserts & UI
    for (let i = fresh.length - 1; i >= 0; i--) {
      const t = fresh[i];
      // Save to MongoDB first (await to ensure it's committed before publishing)
      const saved = await upsertTrade(t);
      if (!saved) {
        console.warn(`[poller:${address}] Failed to save trade ${t.transactionHash}`);
        continue; // Skip publishing if save failed
      }
      // Small delay to ensure MongoDB write is fully committed
      await new Promise(r => setTimeout(r, 10));
      // Then publish to SSE for real-time updates
      // Use lowercase wallet address for consistency with API queries
      const walletLower = String(t.proxyWallet).toLowerCase();
      publish({
        txhash: t.transactionHash,
        wallet: walletLower,
        side: t.side,
        size: t.size,
        price: t.price,
        notional: Number(t.size) * Number(t.price),
        outcome: t.outcome,
        title: t.title,
        slug: t.slug,
        timestamp: t.timestamp,
      });
      await new Promise(r => setTimeout(r, 5)); // small pacing to smooth bursts
    }

    const newest = Math.max(lastTs, 0, ...rows.map(r => r.timestamp || 0));
    if (newest > lastTs) await updateCursor(address, newest);
  } catch (e: any) {
    console.error(`[poller:${address}]`, e.message);
  }
}

function start() {
  setInterval(processNextWallet, Math.max(POLL_INTERVAL_MS, 250));
  console.log(`[poller] started. interval=${POLL_INTERVAL_MS}ms`);
}

if (!globalAny.__PM_POLLER__) {
  start();
  globalAny.__PM_POLLER__ = true;
}
export {};
