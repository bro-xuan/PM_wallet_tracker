import db, { stmt } from './db';
import { publish } from './bus';
import { fetchTradesForUser, DataTrade } from './polymarket';

const globalAny = globalThis as any;
const POLL_INTERVAL_MS = Number(process.env.POLL_INTERVAL_MS || 1000);

function wallets(): string[] {
  return stmt.listWallets.all().map((r: any) => r.address as string);
}

let rotatingIndex = 0;

async function processNextWallet() {
  const ws = wallets();
  if (ws.length === 0) return;
  const idx = rotatingIndex % ws.length;
  rotatingIndex++;
  const address = ws[idx];

  try {
    const rows = await fetchTradesForUser(address, 50);
    const c = stmt.getCursor.get(address) as { last_ts?: number } | undefined;
    const lastTs = c?.last_ts ?? 0;

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
      stmt.insertTrade.run(
        t.transactionHash, t.proxyWallet, t.side, t.size, t.price,
        t.outcome ?? null, t.title ?? null, t.slug ?? null, t.timestamp
      );
      publish({
        txhash: t.transactionHash,
        wallet: t.proxyWallet,
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
    if (newest > lastTs) stmt.upsertCursor.run(address, newest);
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
