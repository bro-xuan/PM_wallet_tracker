import { stmt } from '@/lib/db';
import { isAddress } from '@/lib/util';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(req: Request) {
  const form = await req.formData();
  const file = form.get('file') as File | null;
  if (!file) return new Response('file required', { status: 400 });
  const text = await file.text();
  const addrs = text.split(/[\r\n,;\s]+/).map(s => s.trim()).filter(Boolean).filter(isAddress);
  for (const a of addrs) stmt.insertWallet.run(a);
  return new Response(JSON.stringify({ added: addrs }), { headers: { 'content-type': 'application/json' }});
}
