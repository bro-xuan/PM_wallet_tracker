import { auth } from '@/lib/auth';
import clientPromise from '@/lib/mongodb';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function PUT(req: Request) {
  const session = await auth();
  if (!session?.user?.id) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const url = new URL(req.url);
  const segments = url.pathname.split('/').filter(Boolean);
  const addressIndex = segments.indexOf('wallets') + 1;
  const address = decodeURIComponent(segments[addressIndex] || '').toLowerCase();

  if (!address || !/^0x[a-fA-F0-9]{40}$/.test(address)) {
    return Response.json({ error: 'Invalid address format' }, { status: 400 });
  }

  const body = await req.json().catch(() => ({}));
  const { label } = body;

  if (typeof label !== 'string') {
    return Response.json({ error: 'Label must be a string' }, { status: 400 });
  }

  const client = await clientPromise;
  const db = client.db(process.env.MONGODB_DB_NAME || 'pm-wallet-tracker');
  const walletsCollection = db.collection('wallets');

  // Update label for this user's wallet
  const result = await walletsCollection.updateOne(
    { userId: session.user.id, address: address },
    { $set: { label: label.trim(), updatedAt: new Date() } }
  );

  if (result.matchedCount === 0) {
    return Response.json({ error: 'Wallet not found' }, { status: 404 });
  }

  return Response.json({ success: true, address, label: label.trim() });
}

