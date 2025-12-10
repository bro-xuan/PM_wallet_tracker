import { stmt } from '@/lib/db';
import { isAddress } from '@/lib/util';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function DELETE(req: Request) {
  const url = new URL(req.url);
  const segments = url.pathname.split('/').filter(Boolean);
  const raw = decodeURIComponent(segments[segments.length - 1] || '');
  const a = raw.trim();
  stmt.deleteWallet.run(a);
  stmt.deleteCursor.run(a);
  stmt.deleteTradesByWallet.run(a);
  const invalid = !isAddress(a);
  return Response.json({ removed: a, invalidFormat: invalid });
}

