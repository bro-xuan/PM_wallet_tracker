// Telegram Bot handler for whale alerts
import TelegramBot from 'node-telegram-bot-api';
import clientPromise from './mongodb';

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const BOT_USERNAME = process.env.TELEGRAM_BOT_USERNAME || 'PM_Intel_bot';

// Lazy initialization: bot is only created when needed
// This prevents issues in serverless environments where module loading happens multiple times
let bot: TelegramBot | null = null;
let handlersInitialized = false;

// Determine if we should use polling (only in development, never in production)
const shouldUsePolling = () => {
  // Only use polling if explicitly enabled AND in development
  // In production, always use webhooks (no polling)
  return process.env.NODE_ENV === 'development' && process.env.TELEGRAM_USE_POLLING === 'true';
};

// Initialize bot instance (lazy, only when needed)
function getBot(): TelegramBot | null {
  if (!BOT_TOKEN) {
    if (!handlersInitialized) {
      console.warn('[telegram-bot] TELEGRAM_BOT_TOKEN not set. Telegram features will be disabled.');
    }
    return null;
  }

  // If bot already exists, return it
  if (bot) {
    return bot;
  }

  // Create bot instance (without polling in production - webhook only)
  try {
    const usePolling = shouldUsePolling();
    bot = new TelegramBot(BOT_TOKEN, { polling: usePolling });
    
    if (usePolling) {
      console.log(`[telegram-bot] Bot initialized with polling mode (development only)`);
    } else {
      console.log(`[telegram-bot] Bot initialized (webhook mode - use /api/telegram/webhook)`);
    }
  } catch (error: any) {
    console.error('[telegram-bot] Failed to initialize bot:', error.message);
    bot = null;
    return null;
  }

  // Set up handlers only once
  if (!handlersInitialized) {
    setupHandlers();
    handlersInitialized = true;
  }

  return bot;
}

// Set up bot command handlers
function setupHandlers() {
  const botInstance = bot;
  if (!botInstance) return;

  // Log all messages for debugging (set up first)
  botInstance.on('message', (msg) => {
    console.log('[telegram-bot] 📨 Received message:', {
      chatId: msg.chat.id,
      text: msg.text,
      from: msg.from?.username || msg.from?.id,
    });
  });
  
  // Handle /start command with token verification
  botInstance.onText(/\/start(?: (.+))?/, async (msg, match) => {
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
    botInstance.onText(/\/help/, async (msg) => {
      const chatId = msg.chat.id;
      await botInstance?.sendMessage(
        chatId,
        '🐋 PM Intel Bot Commands:\n\n' +
        '/start <token> - Connect your account\n' +
        '/help - Show this help message\n\n' +
        'Manage your alerts and filters on the website.'
      );
    });
    
    // Handle errors
    botInstance.on('error', (error) => {
      console.error('[telegram-bot] ❌ Bot error:', error);
    });
    
    botInstance.on('polling_error', (error: any) => {
      console.error('[telegram-bot] ❌ Polling error:', error);
      // 409 conflict is normal when multiple instances try to poll (dev only)
      if (error.message?.includes('409') || error.code === 'ETELEGRAM') {
        console.log('[telegram-bot] ⚠️  409 conflict (multiple instances - this is normal in development)');
      }
    });
    
    console.log(`[telegram-bot] ✅ Handlers registered: @${BOT_USERNAME}`);
}

// Initialize bot on module load only in development (with polling)
// In production, bot is initialized lazily when webhook handler is called
if (shouldUsePolling()) {
  getBot();
}

// Export function to send notifications
export async function sendTelegramNotification(
  chatId: string,
  message: string
): Promise<boolean> {
  const botInstance = getBot();
  if (!botInstance) {
    console.error('[telegram-bot] Bot not initialized');
    return false;
  }
  
  try {
    await botInstance.sendMessage(chatId, message, { parse_mode: 'HTML' });
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

// Export bot getter for webhook handler
export { getBot as getTelegramBot };
export const BOT_USERNAME_EXPORT = BOT_USERNAME;

// For backward compatibility, export bot (but prefer getBot in new code)
export { bot };

