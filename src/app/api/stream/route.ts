import { NextRequest } from 'next/server';
import { subscribe } from '@/lib/bus';
import '@/lib/poller'; // ensure poller starts in this process

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    start(controller) {
      // immediately send a retry directive
      controller.enqueue(encoder.encode('retry: 2000\n\n'));

      const send = (payload: any) => {
        const msg = `event: trade\ndata: ${JSON.stringify(payload)}\n\n`;
        controller.enqueue(encoder.encode(msg));
      };
      const unsubscribe = subscribe(send);
      const hb = setInterval(() => {
        controller.enqueue(encoder.encode(': ping\n\n'));
      }, 15000);

      // close on client abort
      (req as any).signal?.addEventListener?.('abort', () => {
        clearInterval(hb);
        unsubscribe();
        controller.close();
      });
    },
    cancel() { /* no-op; unsubscribe happens on abort */ }
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no', // for nginx proxies
    },
  });
}
