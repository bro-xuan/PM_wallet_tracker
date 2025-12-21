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
      excludeCategories: config.excludeCategories ?? [],
      categoryFilter: config.categoryFilter ?? [],
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
    let body;
    try {
      body = await req.json();
    } catch (parseError: any) {
      console.error('[api/whale-alerts/config] JSON parse error:', parseError);
      return Response.json({ error: 'Invalid JSON in request body' }, { status: 400 });
    }
    
    const { minNotionalUsd, minPrice, maxPrice, sides, excludeCategories, categoryFilter, enabled } = body;
    
    console.log('[api/whale-alerts/config] PUT request:', {
      userId: session.user.id,
      body: { minNotionalUsd, minPrice, maxPrice, sides, excludeCategories, categoryFilter, enabled },
    });
    
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
    if (excludeCategories !== undefined) {
      if (!Array.isArray(excludeCategories)) {
        return Response.json({ error: 'Invalid excludeCategories (must be array)' }, { status: 400 });
      }
      // Allow empty array, but if not empty, all items must be non-empty strings
      if (excludeCategories.length > 0 && !excludeCategories.every((c: any) => typeof c === 'string' && c.length > 0)) {
        return Response.json({ error: 'Invalid excludeCategories (must be array of non-empty strings)' }, { status: 400 });
      }
    }
    if (categoryFilter !== undefined) {
      if (!Array.isArray(categoryFilter)) {
        return Response.json({ error: 'Invalid categoryFilter (must be array)' }, { status: 400 });
      }
      // Allow empty array, but if not empty, all items must be non-empty strings
      if (categoryFilter.length > 0 && !categoryFilter.every((c: any) => typeof c === 'string' && c.length > 0)) {
        return Response.json({ error: 'Invalid categoryFilter (must be array of non-empty strings)' }, { status: 400 });
      }
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
    if (excludeCategories !== undefined) updateData.excludeCategories = excludeCategories;
    if (categoryFilter !== undefined) updateData.categoryFilter = categoryFilter;
    if (enabled !== undefined) updateData.enabled = enabled;
    
    console.log('[api/whale-alerts/config] Update data:', JSON.stringify(updateData, null, 2));
    
    // Build $setOnInsert with defaults, but exclude fields that are in updateData
    const setOnInsert: any = {
      userId: session.user.id,
      createdAt: new Date(),
    };
    
    // Only add default values for fields that aren't being updated
    if (minNotionalUsd === undefined) setOnInsert.minNotionalUsd = DEFAULT_CONFIG.minNotionalUsd;
    if (minPrice === undefined) setOnInsert.minPrice = DEFAULT_CONFIG.minPrice;
    if (maxPrice === undefined) setOnInsert.maxPrice = DEFAULT_CONFIG.maxPrice;
    if (sides === undefined) setOnInsert.sides = DEFAULT_CONFIG.sides;
    if (excludeCategories === undefined) setOnInsert.excludeCategories = [];
    if (categoryFilter === undefined) setOnInsert.categoryFilter = [];
    if (enabled === undefined) setOnInsert.enabled = DEFAULT_CONFIG.enabled;
    
    console.log('[api/whale-alerts/config] SetOnInsert data:', JSON.stringify(setOnInsert, null, 2));
    console.log('[api/whale-alerts/config] About to update MongoDB...');
    
    const result = await configCollection.updateOne(
      { userId: session.user.id },
      {
        $set: updateData,
        $setOnInsert: setOnInsert,
      },
      { upsert: true }
    );
    
    console.log('[api/whale-alerts/config] Update result:', {
      matched: result.matchedCount,
      modified: result.modifiedCount,
      upserted: result.upsertedCount,
    });
    
    // Signal worker to reload filters immediately
    // Only if settings were actually updated (not just created)
    if (result.modifiedCount > 0 || result.upsertedCount > 0) {
      const filterReloadCollection = db.collection('filterReloadSignals');
      await filterReloadCollection.updateOne(
        { _id: 'global' },
        { 
          $set: { 
            requestedAt: new Date(),
            requestedBy: session.user.id
          } 
        },
        { upsert: true }
      );
      console.log('[api/whale-alerts/config] Filter reload signal set');
    }
    
    return Response.json({ success: true, updated: result.modifiedCount > 0 || result.upsertedCount > 0 });
    
  } catch (error: any) {
    console.error('[api/whale-alerts/config] PUT Error:', error);
    console.error('[api/whale-alerts/config] PUT Error stack:', error?.stack);
    return Response.json({ 
      error: 'Internal server error',
      details: process.env.NODE_ENV === 'development' ? error?.message : undefined
    }, { status: 500 });
  }
}

