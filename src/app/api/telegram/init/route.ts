// GET /api/telegram/init - Initialize bot (development only)
// This endpoint is only needed in development with polling mode.
// In production (webhook mode), this endpoint is not needed and should not be called.
// The bot is initialized lazily when the webhook handler receives updates.
import { getTelegramBot } from '@/lib/telegram-bot';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  // In production, warn that this endpoint is not needed
  if (process.env.NODE_ENV === 'production') {
    return Response.json({
      botInitialized: false,
      message: 'This endpoint is not needed in production. Use webhook mode instead.',
      warning: 'In production, the bot is initialized automatically when webhook updates are received.',
    });
  }

  // In development, initialize bot (lazy initialization)
  const bot = getTelegramBot();
  
  return Response.json({
    botInitialized: bot !== null,
    message: bot 
      ? 'Bot is initialized and ready to receive messages (development polling mode)'
      : 'Bot failed to initialize - check TELEGRAM_BOT_TOKEN',
    mode: process.env.TELEGRAM_USE_POLLING === 'true' ? 'polling' : 'webhook',
  });
}

