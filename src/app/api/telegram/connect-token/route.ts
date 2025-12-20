// POST /api/telegram/connect-token - Generate a one-time token for Telegram connection
import { auth } from '@/lib/auth';
import clientPromise from '@/lib/mongodb';
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
    
    // Clean up expired tokens (best effort, don't block on this)
    tokensCollection.deleteMany({ 
      $or: [
        { expiresAt: { $lt: new Date() } },
        { used: true }
      ]
    }).catch(() => {});
    
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

