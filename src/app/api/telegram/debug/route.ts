// GET /api/telegram/debug - Debug endpoint to check bot status
import { getTelegramBot } from '@/lib/telegram-bot';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  const bot = getTelegramBot();
  const usePolling = process.env.NODE_ENV === 'development' && process.env.TELEGRAM_USE_POLLING === 'true';
  
  return Response.json({
    botInitialized: bot !== null,
    botTokenSet: !!process.env.TELEGRAM_BOT_TOKEN,
    pollingEnabled: usePolling,
    webhookMode: !usePolling,
    nodeEnv: process.env.NODE_ENV,
    recommendation: usePolling 
      ? 'Using polling (development mode). In production, use webhook mode.'
      : 'Using webhook mode (recommended for production).',
  });
}

