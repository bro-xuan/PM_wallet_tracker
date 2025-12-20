// Telegram Bot handler for whale alerts
import TelegramBot from 'node-telegram-bot-api';
import clientPromise from './mongodb';

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const BOT_USERNAME = process.env.TELEGRAM_BOT_USERNAME || 'PM_Intel_bot';

// Lazy initialization: bot is only created when needed
// This prevents issues in serverless environments where module loading happens multiple times
// Use global variable in development to persist across HMR reloads
const globalAny = globalThis as typeof globalThis & {
  _telegramBot?: TelegramBot | null;
  _telegramBotHandlersInitialized?: boolean;
};

// In development, use global to persist across HMR reloads
// In production, use module-level variable (serverless-friendly)
// Note: We don't export this directly - use getBotInstance() instead
let _botModule: TelegramBot | null = null;
let _handlersInitializedModule = false;

// Get bot instance (from global in dev, module in prod)
function getBotInstance(): TelegramBot | null {
  if (process.env.NODE_ENV === 'development') {
    return globalAny._telegramBot ?? null;
  }
  return _botModule;
}

// Set bot instance (to global in dev, module in prod)
function setBotInstance(instance: TelegramBot | null) {
  if (process.env.NODE_ENV === 'development') {
    globalAny._telegramBot = instance;
  } else {
    _botModule = instance;
  }
}

// Get handlers initialized flag
function getHandlersInitialized(): boolean {
  if (process.env.NODE_ENV === 'development') {
    return globalAny._telegramBotHandlersInitialized ?? false;
  }
  return _handlersInitializedModule;
}

// Set handlers initialized flag
function setHandlersInitialized(value: boolean) {
  if (process.env.NODE_ENV === 'development') {
    globalAny._telegramBotHandlersInitialized = value;
  } else {
    _handlersInitializedModule = value;
  }
}

// Determine if we should use polling (only in development, never in production)
const shouldUsePolling = () => {
  // Only use polling if explicitly enabled AND in development
  // In production, always use webhooks (no polling)
  return process.env.NODE_ENV === 'development' && process.env.TELEGRAM_USE_POLLING === 'true';
};

// Initialize bot instance (lazy, only when needed)
function getBot(): TelegramBot | null {
  if (!BOT_TOKEN) {
    if (!getHandlersInitialized()) {
      console.warn('[telegram-bot] TELEGRAM_BOT_TOKEN not set. Telegram features will be disabled.');
    }
    return null;
  }

  // If bot already exists (check global in dev, module in prod), return it
  const existingBot = getBotInstance();
  if (existingBot) {
    return existingBot;
  }

  // Create bot instance (without polling in production - webhook only)
  try {
    const usePolling = shouldUsePolling();
    const newBot = new TelegramBot(BOT_TOKEN, { polling: usePolling });
    setBotInstance(newBot);
    
    if (usePolling) {
      console.log(`[telegram-bot] Bot initialized with polling mode (development only)`);
    } else {
      console.log(`[telegram-bot] Bot initialized (webhook mode - use /api/telegram/webhook)`);
    }
  } catch (error: any) {
    console.error('[telegram-bot] Failed to initialize bot:', error.message);
    setBotInstance(null);
    return null;
  }

  // Set up handlers only once
  if (!getHandlersInitialized()) {
    setupHandlers();
    setHandlersInitialized(true);
  }

  return getBotInstance();
}

// Set up bot command handlers
function setupHandlers() {
  const botInstance = getBotInstance();
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
        await botInstance?.sendMessage(chatId, 
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
          await botInstance?.sendMessage(
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
        
        await botInstance.sendMessage(
          chatId,
          '✅ Connected!\n\n' +
          'You will now receive whale trade alerts based on your filter settings.\n\n' +
          'You can manage your alerts and filters on the website.'
        );
        
        console.log(`[telegram-bot] ✅ User ${userId} connected with chatId ${chatId}`);
      } catch (error: any) {
        console.error('[telegram-bot] ❌ Error connecting user:', error);
        try {
          await botInstance?.sendMessage(
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
      // 409 conflict means another instance is polling - stop this instance
      if (error.message?.includes('409') || error.code === 'ETELEGRAM') {
        console.warn('[telegram-bot] ⚠️  409 Conflict: Another bot instance is polling. Stopping this instance to prevent conflicts.');
        console.warn('[telegram-bot] 💡 Solution: Only one instance should poll. Check for duplicate imports or restart the dev server.');
        
        // Stop polling on this instance to prevent conflicts
        try {
          botInstance.stopPolling();
          setBotInstance(null); // Clear the instance so it can be recreated if needed
        } catch (stopError) {
          // Ignore errors when stopping
        }
        return;
      }
      
      console.error('[telegram-bot] ❌ Polling error:', error);
    });
    
    console.log(`[telegram-bot] ✅ Handlers registered: @${BOT_USERNAME}`);
}

// Initialize bot on module load only in development (with polling)
// In production, bot is initialized lazily when webhook handler is called
// Use global check to prevent multiple initializations in HMR
if (shouldUsePolling()) {
  // Only initialize if not already initialized (prevents HMR duplicates)
  if (!getBotInstance()) {
    getBot();
  } else {
    console.log('[telegram-bot] ♻️  Bot already initialized (HMR reload detected)');
  }
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

// For backward compatibility, export bot getter
// Note: This is a getter function that returns the current bot instance
// In development, returns the global instance; in production, the module instance
export function getBotExport() {
  return getBotInstance();
}

