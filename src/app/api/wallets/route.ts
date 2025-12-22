import { auth } from '@/lib/auth';
import clientPromise from '@/lib/mongodb';
import { isAddress } from '@/lib/util';
import type { Collection } from 'mongodb';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// Make sure we only create indexes for the wallets collection once per
// server process. Without this, every page load that hits this endpoint
// can pay extra round-trips to MongoDB.
const globalAny = globalThis as any;

async function ensureWalletsIndexes(walletsCollection: Collection) {
  if (!globalAny.__PM_WALLETS_INDEXES_PROMISE__) {
    globalAny.__PM_WALLETS_INDEXES_PROMISE__ = (async () => {
      try {
        await walletsCollection.createIndex(
          { userId: 1, isActive: 1, address: 1 },
          { name: 'user_active_address' },
        );
      } catch (err) {
        console.error('Failed to ensure wallets indexes', err);
      }
    })();
  }
  await globalAny.__PM_WALLETS_INDEXES_PROMISE__;
}

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const client = await clientPromise;
  const db_mongo = client.db(process.env.MONGODB_DB_NAME || 'pm-wallet-tracker');
  const walletsCollection = db_mongo.collection('wallets');

  await ensureWalletsIndexes(walletsCollection);

  const wallets = await walletsCollection.find(
    { userId: session.user.id, isActive: true },
    { projection: { address: 1, label: 1, _id: 0 } }
  ).toArray();

  // Return both addresses and labels
  const addresses = wallets.map((w: any) => w.address);
  const labels: Record<string, string> = {};
  wallets.forEach((w: any) => {
    if (w.label && w.label.trim()) {
      labels[w.address.toLowerCase()] = w.label.trim();
    }
  });

  return Response.json({ addresses, labels });
}

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.id) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const body = await req.json().catch(() => ({}));
  const { addresses } = body || {};
  if (!Array.isArray(addresses) || addresses.length === 0) {
    return new Response(JSON.stringify({ error: 'addresses[] required' }), { status: 400 });
  }

  const client = await clientPromise;
  const db = client.db(process.env.MONGODB_DB_NAME || 'pm-wallet-tracker');
  const walletsCollection = db.collection('wallets');

  await ensureWalletsIndexes(walletsCollection);

  const added: string[] = [];
  const rejected: string[] = [];
  const now = new Date();

  for (const raw of addresses) {
    const a = String(raw).trim();
    if (!isAddress(a)) { rejected.push(a); continue; }
    
    // Upsert wallet for this user
    await walletsCollection.updateOne(
      { userId: session.user.id, address: a.toLowerCase() },
      {
        $set: {
          userId: session.user.id,
          address: a.toLowerCase(),
          isActive: true,
          updatedAt: now,
        },
        $setOnInsert: {
          label: '',
          createdAt: now,
        },
      },
      { upsert: true }
    );
    added.push(a);
  }

  return Response.json({ added, rejected });
}
