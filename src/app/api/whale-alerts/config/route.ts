// GET/PUT /api/whale-alerts/config - Get/Update whale alert configuration
import { auth } from '@/lib/auth';
import clientPromise from '@/lib/mongodb';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// Default configuration
const DEFAULT_CONFIG = {
  minNotionalUsd: 10000,
  minPrice: 0.05,
  maxPrice: 0.95,
  sides: ['BUY', 'SELL'],
  enabled: false,
};

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const client = await clientPromise;
    const db = client.db(process.env.MONGODB_DB_NAME || 'pm-wallet-tracker');
    const configCollection = db.collection('whaleAlertConfigs');
    
    const config = await configCollection.findOne({ userId: session.user.id });
    
    if (!config) {
      // Return default config if none exists
      return Response.json(DEFAULT_CONFIG);
    }
    
    return Response.json({
      minNotionalUsd: config.minNotionalUsd ?? DEFAULT_CONFIG.minNotionalUsd,
      minPrice: config.minPrice ?? DEFAULT_CONFIG.minPrice,
      maxPrice: config.maxPrice ?? DEFAULT_CONFIG.maxPrice,
      sides: config.sides ?? DEFAULT_CONFIG.sides,
      enabled: config.enabled ?? DEFAULT_CONFIG.enabled,
    });
  } catch (error: any) {
    console.error('[api/whale-alerts/config] GET Error:', error);
    return Response.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function PUT(req: Request) {
  const session = await auth();
  if (!session?.user?.id) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const body = await req.json();
    const { minNotionalUsd, minPrice, maxPrice, sides, enabled } = body;
    
    // Validate inputs
    if (minNotionalUsd !== undefined && (typeof minNotionalUsd !== 'number' || minNotionalUsd < 0)) {
      return Response.json({ error: 'Invalid minNotionalUsd' }, { status: 400 });
    }
    if (minPrice !== undefined && (typeof minPrice !== 'number' || minPrice < 0 || minPrice > 1)) {
      return Response.json({ error: 'Invalid minPrice (must be 0-1)' }, { status: 400 });
    }
    if (maxPrice !== undefined && (typeof maxPrice !== 'number' || maxPrice < 0 || maxPrice > 1)) {
      return Response.json({ error: 'Invalid maxPrice (must be 0-1)' }, { status: 400 });
    }
    if (minPrice !== undefined && maxPrice !== undefined && minPrice >= maxPrice) {
      return Response.json({ error: 'minPrice must be less than maxPrice' }, { status: 400 });
    }
    if (sides !== undefined && (!Array.isArray(sides) || !sides.every((s: string) => ['BUY', 'SELL'].includes(s)))) {
      return Response.json({ error: 'Invalid sides (must be array of "BUY" and/or "SELL")' }, { status: 400 });
    }
    if (enabled !== undefined && typeof enabled !== 'boolean') {
      return Response.json({ error: 'Invalid enabled (must be boolean)' }, { status: 400 });
    }
    
    const client = await clientPromise;
    const db = client.db(process.env.MONGODB_DB_NAME || 'pm-wallet-tracker');
    const configCollection = db.collection('whaleAlertConfigs');
    
    const updateData: any = {
      updatedAt: new Date(),
    };
    
    if (minNotionalUsd !== undefined) updateData.minNotionalUsd = minNotionalUsd;
    if (minPrice !== undefined) updateData.minPrice = minPrice;
    if (maxPrice !== undefined) updateData.maxPrice = maxPrice;
    if (sides !== undefined) updateData.sides = sides;
    if (enabled !== undefined) updateData.enabled = enabled;
    
    const result = await configCollection.updateOne(
      { userId: session.user.id },
      {
        $set: updateData,
        $setOnInsert: {
          userId: session.user.id,
          createdAt: new Date(),
          ...DEFAULT_CONFIG,
        },
      },
      { upsert: true }
    );
    
    return Response.json({ success: true, updated: result.modifiedCount > 0 || result.upsertedCount > 0 });
  } catch (error: any) {
    console.error('[api/whale-alerts/config] PUT Error:', error);
    return Response.json({ error: 'Internal server error' }, { status: 500 });
  }
}

