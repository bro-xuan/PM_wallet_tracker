import db, { stmt } from '@/lib/db';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(req: Request) {
  const url = new URL(req.url);
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '200', 10), 1000);
  const offset = Math.max(parseInt(url.searchParams.get('offset') || '0', 10), 0);
  const min = Number(url.searchParams.get('minNotional') || '0');

  const rows = (offset > 0 
    ? stmt.listRecentPaginated.all(limit, offset)
    : stmt.listRecent.all(limit)
  ).map((r: any) => ({
    txhash: r.txhash,
    wallet: r.proxyWallet,
    side: r.side,
    size: r.size,
    price: r.price,
    notional: Number(r.size) * Number(r.price),
    outcome: r.outcome,
    title: r.title,
    slug: r.slug,
    timestamp: r.timestamp,
  }));

  const filtered = min > 0 ? rows.filter(r => r.notional >= min) : rows;
  const total = (stmt.countTrades.get() as any).count;
  
  return new Response(JSON.stringify({ 
    trades: filtered,
    total,
    limit,
    offset 
  }), {
    headers: { 'content-type': 'application/json' }
  });
}
