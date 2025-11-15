import db, { stmt } from '@/lib/db';
import { isAddress } from '@/lib/util';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  const addresses = stmt.listWallets.all().map((r: any) => r.address);
  return Response.json({ addresses });
}

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const { addresses } = body || {};
  if (!Array.isArray(addresses) || addresses.length === 0) {
    return new Response(JSON.stringify({ error: 'addresses[] required' }), { status: 400 });
  }
  const added: string[] = [];
  const rejected: string[] = [];
  for (const raw of addresses) {
    const a = String(raw).trim();
    if (!isAddress(a)) { rejected.push(a); continue; }
    stmt.insertWallet.run(a);
    added.push(a);
  }
  return Response.json({ added, rejected });
}
