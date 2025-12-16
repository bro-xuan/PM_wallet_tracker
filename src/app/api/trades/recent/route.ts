import { auth } from '@/lib/auth';
import db, { stmt } from '@/lib/db';
import clientPromise from '@/lib/mongodb';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(req: Request) {
  const session = await auth();
  if (!session?.user?.id) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 });
  }

  // Get user's monitored wallets
  const client = await clientPromise;
  const db_mongo = client.db(process.env.MONGODB_DB_NAME || 'pm-wallet-tracker');
  const walletsCollection = db_mongo.collection('wallets');
  const userWallets = await walletsCollection.find(
    { userId: session.user.id, isActive: true },
    { projection: { address: 1, _id: 0 } }
  ).toArray();

  const userWalletAddresses = new Set(
    userWallets.map((w: any) => w.address.toLowerCase())
  );

  // If user has no wallets, return empty
  if (userWalletAddresses.size === 0) {
    return new Response(JSON.stringify({ 
      trades: [],
      total: 0,
      limit: 0,
      offset: 0
    }), {
      headers: { 'content-type': 'application/json' }
    });
  }

  const url = new URL(req.url);
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '200', 10), 1000);
  const offset = Math.max(parseInt(url.searchParams.get('offset') || '0', 10), 0);
  const min = Number(url.searchParams.get('minNotional') || '0');

  // Get all trades and filter by user's wallets
  const allRows = (offset > 0 
    ? stmt.listRecentPaginated.all(limit + 1000, offset) // Get more to account for filtering
    : stmt.listRecent.all(limit + 1000)
  ).map((r: any) => ({
    txhash: r.txhash,
    wallet: r.proxyWallet,
    side: r.side,
    size: r.size,
    price: r.price,
    notional: Number(r.size) * Number(r.price),
    outcome: r.outcome,
    title: r.title,
    slug: r.slug,
    timestamp: r.timestamp,
  }));

  // Filter by user's wallets
  const userTrades = allRows.filter((r: any) => 
    userWalletAddresses.has(r.wallet.toLowerCase())
  );

  // Apply notional filter
  const filtered = min > 0 ? userTrades.filter(r => r.notional >= min) : userTrades;

  // Slice to requested limit
  const paginated = filtered.slice(0, limit);

  // Count total user trades (approximate - for better performance, could cache this)
  const totalUserTrades = allRows.filter((r: any) => 
    userWalletAddresses.has(r.wallet.toLowerCase())
  ).length;
  
  return new Response(JSON.stringify({ 
    trades: paginated,
    total: totalUserTrades,
    limit,
    offset 
  }), {
    headers: { 'content-type': 'application/json' }
  });
}
