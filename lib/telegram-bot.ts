// Telegram Bot handler for whale alerts
import TelegramBot from 'node-telegram-bot-api';
import clientPromise from './mongodb';

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const BOT_USERNAME = process.env.TELEGRAM_BOT_USERNAME || 'PM_Intel_bot';

if (!BOT_TOKEN) {
  console.warn('[telegram-bot] TELEGRAM_BOT_TOKEN not set. Telegram features will be disabled.');
}

// Initialize bot (using polling for now, can switch to webhook later)
let bot: TelegramBot | null = null;

if (BOT_TOKEN) {
  try {
    // Use polling for development (simpler than webhook setup)
    // In production, you can switch to webhook by setting polling: false and using webhook endpoint
    const usePolling = process.env.TELEGRAM_USE_POLLING === 'true' || process.env.NODE_ENV === 'development';
    bot = new TelegramBot(BOT_TOKEN, { polling: usePolling });
    
    if (usePolling) {
      console.log(`[telegram-bot] Bot started with polling mode`);
    } else {
      console.log(`[telegram-bot] Bot started (webhook mode - use /api/telegram/webhook)`);
    }
  } catch (error: any) {
    console.error('[telegram-bot] Failed to initialize bot:', error.message);
    bot = null;
  }
  
  // Set up command handlers (only if bot was successfully created)
  // Use global flag to prevent duplicate handler registration in Next.js HMR
  const globalAny = globalThis as any;
  if (bot && !globalAny.__TELEGRAM_BOT_HANDLERS_SET__) {
    globalAny.__TELEGRAM_BOT_HANDLERS_SET__ = true;
    
    // Log all messages for debugging (set up first)
    bot.on('message', (msg) => {
      console.log('[telegram-bot] 📨 Received message:', {
        chatId: msg.chat.id,
        text: msg.text,
        from: msg.from?.username || msg.from?.id,
      });
    });
    
    // Handle /start command with token verification
    bot.onText(/\/start(?: (.+))?/, async (msg, match) => {
      console.log('[telegram-bot] 🚀 Received /start command', { 
        chatId: msg.chat.id, 
        token: match?.[1] ? match[1].substring(0, 10) + '...' : null,
        from: msg.from?.username || msg.from?.id,
      });
      
      const chatId = msg.chat.id;
      const username = msg.from?.username || null;
      const token = match?.[1]; // Extract token from /start <token>
      
      if (!token) {
        console.log('[telegram-bot] ⚠️ /start without token');
        await bot?.sendMessage(chatId, 
          'Welcome to PM Intel Bot! 🐋\n\n' +
          'To connect your account, please use the connection link from the website.'
        );
        return;
      }
      
      console.log(`[telegram-bot] 🔗 Processing connection with token, chatId: ${chatId}`);
      
      try {
        // Verify token in MongoDB
        const client = await clientPromise;
        const db = client.db(process.env.MONGODB_DB_NAME || 'pm-wallet-tracker');
        const tokensCollection = db.collection('telegramConnectTokens');
        
        // Find token and verify it's valid
        const tokenDoc = await tokensCollection.findOne({
          token: token,
          used: false,
          expiresAt: { $gt: new Date() }, // Not expired
        });
        
        if (!tokenDoc) {
          console.log('[telegram-bot] ❌ Invalid or expired token');
          await bot?.sendMessage(
            chatId,
            '❌ Invalid or expired connection link.\n\n' +
            'Please go back to the website and click "Connect Telegram" again to get a new link.'
          );
          return;
        }
        
        const userId = tokenDoc.userId;
        console.log(`[telegram-bot] ✅ Token verified for userId: ${userId}, chatId: ${chatId}`);
        
        // Mark token as used
        await tokensCollection.updateOne(
          { token: token },
          { $set: { used: true, usedAt: new Date() } }
        );
        
        // Store connection in MongoDB
        const telegramAccountsCollection = db.collection('telegramAccounts');
        
        // Upsert connection
        const result = await telegramAccountsCollection.updateOne(
          { userId: userId },
          {
            $set: {
              userId: userId,
              chatId: String(chatId),
              username: username,
              linkedAt: new Date(),
              isActive: true,
            },
          },
          { upsert: true }
        );
        
        console.log(`[telegram-bot] 💾 Connection saved to MongoDB:`, {
          matched: result.matchedCount,
          modified: result.modifiedCount,
          upserted: result.upsertedCount,
        });
        
        await bot.sendMessage(
          chatId,
          '✅ Connected!\n\n' +
          'You will now receive whale trade alerts based on your filter settings.\n\n' +
          'You can manage your alerts and filters on the website.'
        );
        
        console.log(`[telegram-bot] ✅ User ${userId} connected with chatId ${chatId}`);
      } catch (error: any) {
        console.error('[telegram-bot] ❌ Error connecting user:', error);
        try {
          await bot?.sendMessage(
            chatId,
            '❌ Error connecting your account. Please try again or contact support.'
          );
        } catch (sendError) {
          console.error('[telegram-bot] Failed to send error message:', sendError);
        }
      }
    });
    
    // Handle /help command
    bot.onText(/\/help/, async (msg) => {
      const chatId = msg.chat.id;
      await bot?.sendMessage(
        chatId,
        '🐋 PM Intel Bot Commands:\n\n' +
        '/start <userId> - Connect your account\n' +
        '/help - Show this help message\n\n' +
        'Manage your alerts and filters on the website.'
      );
    });
    
    // Handle errors
    bot.on('error', (error) => {
      console.error('[telegram-bot] ❌ Bot error:', error);
    });
    
    bot.on('polling_error', (error: any) => {
      console.error('[telegram-bot] ❌ Polling error:', error);
      // 409 conflict is normal when multiple instances try to poll
      if (error.message?.includes('409') || error.code === 'ETELEGRAM') {
        console.log('[telegram-bot] ⚠️  409 conflict (multiple instances - this is normal in development)');
      }
    });
    
    console.log(`[telegram-bot] ✅ Bot initialized and handlers registered: @${BOT_USERNAME}`);
  } else if (bot) {
    console.log('[telegram-bot] ♻️  Handlers already registered (HMR reload)');
  }
} else {
  console.warn('[telegram-bot] Bot not initialized - missing TELEGRAM_BOT_TOKEN');
}

// Export function to send notifications
export async function sendTelegramNotification(
  chatId: string,
  message: string
): Promise<boolean> {
  if (!bot) {
    console.error('[telegram-bot] Bot not initialized');
    return false;
  }
  
  try {
    await bot.sendMessage(chatId, message, { parse_mode: 'HTML' });
    return true;
  } catch (error: any) {
    console.error(`[telegram-bot] Error sending message to ${chatId}:`, error.message);
    // If user blocked bot or chatId is invalid, mark as inactive
    if (error.response?.statusCode === 403 || error.response?.statusCode === 400) {
      const client = await clientPromise;
      const db = client.db(process.env.MONGODB_DB_NAME || 'pm-wallet-tracker');
      const telegramAccountsCollection = db.collection('telegramAccounts');
      await telegramAccountsCollection.updateOne(
        { chatId: String(chatId) },
        { $set: { isActive: false } }
      );
    }
    return false;
  }
}

// Export bot instance for webhook handler
export { bot };
export const BOT_USERNAME_EXPORT = BOT_USERNAME;

