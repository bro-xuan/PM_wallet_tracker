// POST /api/telegram/connect-token - Generate a one-time token for Telegram connection
import { auth } from '@/lib/auth';
import clientPromise from '@/lib/mongodb';
import { ensureTelegramTokenIndexes } from '@/lib/telegram-tokens-indexes';
import { randomBytes } from 'crypto';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// Token expires in 5 minutes
const TOKEN_EXPIRY_MS = 5 * 60 * 1000;

export async function POST() {
  const session = await auth();
  if (!session?.user?.id) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    // Ensure indexes exist (idempotent, only runs once per process)
    await ensureTelegramTokenIndexes();
    
    // Generate a secure random token
    const token = randomBytes(32).toString('hex');
    
    const client = await clientPromise;
    const db = client.db(process.env.MONGODB_DB_NAME || 'pm-wallet-tracker');
    const tokensCollection = db.collection('telegramConnectTokens');
    
    // Store token with userId and expiration
    const expiresAt = new Date(Date.now() + TOKEN_EXPIRY_MS);
    
    await tokensCollection.insertOne({
      token,
      userId: session.user.id,
      expiresAt,
      createdAt: new Date(),
      used: false,
    });
    
    // Note: TTL index on expiresAt will auto-delete expired tokens
    // Still clean up used tokens manually (TTL only handles expiration, not 'used' flag)
    tokensCollection.deleteMany({ used: true }).catch(() => {});
    
    console.log('[api/telegram/connect-token] Generated token for userId:', session.user.id);
    
    return Response.json({ 
      token,
      expiresIn: TOKEN_EXPIRY_MS / 1000, // seconds
    });
  } catch (error: any) {
    console.error('[api/telegram/connect-token] Error:', error);
    return Response.json({ error: 'Internal server error' }, { status: 500 });
  }
}

