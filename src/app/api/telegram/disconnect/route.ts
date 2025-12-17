// POST /api/telegram/disconnect - Disconnect Telegram account
import { auth } from '@/lib/auth';
import clientPromise from '@/lib/mongodb';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST() {
  const session = await auth();
  if (!session?.user?.id) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const client = await clientPromise;
    const db = client.db(process.env.MONGODB_DB_NAME || 'pm-wallet-tracker');
    const telegramAccountsCollection = db.collection('telegramAccounts');
    
    const result = await telegramAccountsCollection.updateOne(
      { userId: session.user.id },
      { $set: { isActive: false, disconnectedAt: new Date() } }
    );
    
    if (result.matchedCount === 0) {
      return Response.json({ error: 'No Telegram account found' }, { status: 404 });
    }
    
    return Response.json({ success: true, disconnected: true });
  } catch (error: any) {
    console.error('[api/telegram/disconnect] Error:', error);
    return Response.json({ error: 'Internal server error' }, { status: 500 });
  }
}

