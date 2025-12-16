import { auth } from '@/lib/auth';
import { stmt } from '@/lib/db';
import clientPromise from '@/lib/mongodb';
import { isAddress } from '@/lib/util';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function DELETE(req: Request) {
  const session = await auth();
  if (!session?.user?.id) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const url = new URL(req.url);
  const segments = url.pathname.split('/').filter(Boolean);
  const raw = decodeURIComponent(segments[segments.length - 1] || '');
  const a = raw.trim().toLowerCase();
  
  if (!isAddress(a)) {
    return Response.json({ error: 'Invalid address format' }, { status: 400 });
  }

  const client = await clientPromise;
  const db = client.db(process.env.MONGODB_DB_NAME || 'pm-wallet-tracker');
  const walletsCollection = db.collection('wallets');

  // Delete wallet from MongoDB (user-specific)
  const result = await walletsCollection.deleteOne({
    userId: session.user.id,
    address: a,
  });

  if (result.deletedCount === 0) {
    return Response.json({ error: 'Wallet not found' }, { status: 404 });
  }

  // Also clean up SQLite data (cursors and trades) for this wallet
  // Note: In future, trades should also be user-specific
  stmt.deleteCursor.run(a);
  stmt.deleteTradesByWallet.run(a);

  return Response.json({ removed: a });
}

