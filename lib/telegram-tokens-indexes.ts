/**
 * Ensures indexes exist on telegramConnectTokens collection.
 * 
 * Creates:
 * - Unique index on 'token' field (prevents duplicate tokens)
 * - TTL index on 'expiresAt' field (auto-deletes expired tokens)
 * 
 * This keeps the collection small and efficient.
 */
import clientPromise from './mongodb';

let indexesEnsured = false;

export async function ensureTelegramTokenIndexes() {
  // Only run once per process (idempotent)
  if (indexesEnsured) {
    return;
  }

  try {
    const client = await clientPromise;
    const db = client.db(process.env.MONGODB_DB_NAME || 'pm-wallet-tracker');
    const tokensCollection = db.collection('telegramConnectTokens');

    // Create unique index on token field
    try {
      await tokensCollection.createIndex(
        { token: 1 },
        { 
          unique: true,
          name: 'token_unique_idx'
        }
      );
      console.log('[telegram-tokens-indexes] ✅ Created unique index on token field');
    } catch (error: any) {
      // Index might already exist, which is fine
      if (error.code === 85 || error.codeName === 'IndexOptionsConflict') {
        // Index already exists with different options - try to drop and recreate
        try {
          await tokensCollection.dropIndex('token_unique_idx');
          await tokensCollection.createIndex(
            { token: 1 },
            { 
              unique: true,
              name: 'token_unique_idx'
            }
          );
          console.log('[telegram-tokens-indexes] ✅ Recreated unique index on token field');
        } catch (e: any) {
          if (e.code !== 27 && e.codeName !== 'IndexNotFound') {
            console.warn('[telegram-tokens-indexes] ⚠️  Could not recreate token index:', e.message);
          }
        }
      } else if (error.code !== 86 && error.codeName !== 'IndexKeySpecsConflict') {
        // Index already exists with same options, which is fine
        console.log('[telegram-tokens-indexes] ℹ️  Token unique index already exists');
      } else {
        console.warn('[telegram-tokens-indexes] ⚠️  Could not create token unique index:', error.message);
      }
    }

    // Create TTL index on expiresAt field (auto-deletes expired documents)
    try {
      await tokensCollection.createIndex(
        { expiresAt: 1 },
        { 
          expireAfterSeconds: 0, // Delete immediately when expiresAt is reached
          name: 'expiresAt_ttl_idx'
        }
      );
      console.log('[telegram-tokens-indexes] ✅ Created TTL index on expiresAt field');
    } catch (error: any) {
      // Index might already exist, which is fine
      if (error.code === 85 || error.codeName === 'IndexOptionsConflict') {
        // Index already exists with different options - try to drop and recreate
        try {
          await tokensCollection.dropIndex('expiresAt_ttl_idx');
          await tokensCollection.createIndex(
            { expiresAt: 1 },
            { 
              expireAfterSeconds: 0,
              name: 'expiresAt_ttl_idx'
            }
          );
          console.log('[telegram-tokens-indexes] ✅ Recreated TTL index on expiresAt field');
        } catch (e: any) {
          if (e.code !== 27 && e.codeName !== 'IndexNotFound') {
            console.warn('[telegram-tokens-indexes] ⚠️  Could not recreate TTL index:', e.message);
          }
        }
      } else if (error.code !== 86 && error.codeName !== 'IndexKeySpecsConflict') {
        // Index already exists with same options, which is fine
        console.log('[telegram-tokens-indexes] ℹ️  TTL index already exists');
      } else {
        console.warn('[telegram-tokens-indexes] ⚠️  Could not create TTL index:', error.message);
      }
    }

    indexesEnsured = true;
  } catch (error: any) {
    console.error('[telegram-tokens-indexes] ❌ Error ensuring indexes:', error);
    // Don't throw - allow the application to continue even if index creation fails
  }
}

