// GET /api/telegram/status - Check if user has Telegram connected
import { auth } from '@/lib/auth';
import clientPromise from '@/lib/mongodb';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const client = await clientPromise;
    const db = client.db(process.env.MONGODB_DB_NAME || 'pm-wallet-tracker');
    const telegramAccountsCollection = db.collection('telegramAccounts');
    
    const account = await telegramAccountsCollection.findOne({
      userId: session.user.id,
      isActive: true,
    });
    
    if (!account) {
      return Response.json({ connected: false });
    }
    
    return Response.json({
      connected: true,
      username: account.username || null,
      chatId: account.chatId,
      linkedAt: account.linkedAt,
    });
  } catch (error: any) {
    console.error('[api/telegram/status] Error:', error);
    return Response.json({ error: 'Internal server error' }, { status: 500 });
  }
}

