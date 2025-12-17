// POST /api/whale-alerts/test - Send test notification
import { auth } from '@/lib/auth';
import clientPromise from '@/lib/mongodb';
import { sendTelegramNotification } from '@/lib/telegram-bot';

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
    
    const account = await telegramAccountsCollection.findOne({
      userId: session.user.id,
      isActive: true,
    });
    
    if (!account) {
      return Response.json({ error: 'Telegram not connected' }, { status: 400 });
    }
    
    const testMessage = 
      '🐋 <b>Whale Alert Test</b>\n\n' +
      'This is a test notification from PM Intel.\n\n' +
      'If you received this message, your Telegram connection is working correctly!\n\n' +
      'You will receive alerts when trades match your filter settings.';
    
    const sent = await sendTelegramNotification(account.chatId, testMessage);
    
    if (!sent) {
      return Response.json({ error: 'Failed to send notification' }, { status: 500 });
    }
    
    return Response.json({ success: true, message: 'Test notification sent' });
  } catch (error: any) {
    console.error('[api/whale-alerts/test] Error:', error);
    return Response.json({ error: 'Internal server error' }, { status: 500 });
  }
}

