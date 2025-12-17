// POST /api/telegram/webhook - Receive updates from Telegram
// This endpoint receives webhook updates from Telegram
import { bot } from '@/lib/telegram-bot';
import { NextRequest } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  if (!bot) {
    return Response.json({ error: 'Telegram bot not initialized' }, { status: 503 });
  }

  try {
    const update = await req.json();
    
    // Process the update
    await bot.processUpdate(update);
    
    return Response.json({ ok: true });
  } catch (error: any) {
    console.error('[api/telegram/webhook] Error processing update:', error);
    return Response.json({ error: 'Error processing update' }, { status: 500 });
  }
}

