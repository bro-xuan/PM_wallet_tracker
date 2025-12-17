// GET /api/telegram/debug - Debug endpoint to check bot status
import { bot } from '@/lib/telegram-bot';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  return Response.json({
    botInitialized: bot !== null,
    botTokenSet: !!process.env.TELEGRAM_BOT_TOKEN,
    pollingEnabled: process.env.TELEGRAM_USE_POLLING === 'true' || process.env.NODE_ENV === 'development',
    nodeEnv: process.env.NODE_ENV,
  });
}

