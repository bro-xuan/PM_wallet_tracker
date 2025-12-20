// POST /api/telegram/webhook - Receive updates from Telegram
// This is the primary entry point for Telegram updates in production (webhook mode)
// In development with polling, this endpoint is not used, but still works if called
import { getTelegramBot } from '@/lib/telegram-bot';
import { NextRequest } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  // Lazy initialization: bot is created when webhook is called (production)
  const bot = getTelegramBot();
  
  if (!bot) {
    return Response.json({ error: 'Telegram bot not initialized' }, { status: 503 });
  }

  try {
    const update = await req.json();
    
    // Process the update (this will trigger handlers set up in setupHandlers)
    await bot.processUpdate(update);
    
    return Response.json({ ok: true });
  } catch (error: any) {
    console.error('[api/telegram/webhook] Error processing update:', error);
    return Response.json({ error: 'Error processing update' }, { status: 500 });
  }
}

