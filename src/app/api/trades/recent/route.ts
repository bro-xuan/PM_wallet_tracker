import { auth } from '@/lib/auth';
import clientPromise from '@/lib/mongodb';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(req: Request) {
  const session = await auth();
  if (!session?.user?.id) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const url = new URL(req.url);
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '200', 10), 1000);
  const offset = Math.max(parseInt(url.searchParams.get('offset') || '0', 10), 0);
  const min = Number(url.searchParams.get('minNotional') || '0');

  const client = await clientPromise;
  const db_mongo = client.db(process.env.MONGODB_DB_NAME || 'pm-wallet-tracker');

  // Get user's monitored wallets from MongoDB
  const walletsCollection = db_mongo.collection('wallets');
  const userWallets = await walletsCollection.find(
    { userId: session.user.id, isActive: true },
    { projection: { address: 1, _id: 0 } }
  ).toArray();

  const userWalletAddresses = Array.from(
    new Set(userWallets.map((w: any) => String(w.address).toLowerCase()))
  );

  if (userWalletAddresses.length === 0) {
    return new Response(JSON.stringify({
      trades: [],
      total: 0,
      limit,
      offset,
    }), {
      headers: { 'content-type': 'application/json' },
    });
  }

  const tradesCollection = db_mongo.collection('trades');

  // Ensure useful indexes (noop if they already exist)
  await tradesCollection.createIndex({ proxyWallet: 1, timestamp: -1 }).catch(() => {});
  await tradesCollection.createIndex({ timestamp: -1 }).catch(() => {});

  const filter: any = {
    proxyWallet: { $in: userWalletAddresses },
  };

  if (min > 0) {
    filter.$expr = {
      $gte: [{ $multiply: ['$size', '$price'] }, min],
    };
  }

  const total = await tradesCollection.countDocuments(filter);

  const docs = await tradesCollection
    .find(filter)
    .sort({ timestamp: -1 })
    .skip(offset)
    .limit(limit)
    .toArray();

  // Ensure wallet addresses are normalized to lowercase
  const trades = docs.map((r: any) => ({
    txhash: r.txhash,
    wallet: String(r.proxyWallet || '').toLowerCase(), // Normalize to lowercase
    side: r.side,
    size: r.size,
    price: r.price,
    notional: Number(r.size) * Number(r.price),
    outcome: r.outcome,
    title: r.title,
    slug: r.slug,
    timestamp: r.timestamp,
  }));

  return new Response(JSON.stringify({
    trades,
    total,
    limit,
    offset,
  }), {
    headers: { 'content-type': 'application/json' },
  });
}
