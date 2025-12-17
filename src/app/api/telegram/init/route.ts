// GET /api/telegram/init - Initialize bot (ensures it's loaded)
// This endpoint forces the bot module to be imported and initialized
import '@/lib/telegram-bot';
import { bot } from '@/lib/telegram-bot';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  return Response.json({
    botInitialized: bot !== null,
    message: bot 
      ? 'Bot is initialized and ready to receive messages'
      : 'Bot failed to initialize - check TELEGRAM_BOT_TOKEN',
  });
}

