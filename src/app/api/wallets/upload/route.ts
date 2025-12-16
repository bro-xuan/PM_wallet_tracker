import { auth } from '@/lib/auth';
import clientPromise from '@/lib/mongodb';
import { isAddress } from '@/lib/util';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.id) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const form = await req.formData();
  const file = form.get('file') as File | null;
  if (!file) return new Response('file required', { status: 400 });
  const text = await file.text();
  const addrs = text.split(/[\r\n,;\s]+/).map(s => s.trim()).filter(Boolean).filter(isAddress);

  const client = await clientPromise;
  const db = client.db(process.env.MONGODB_DB_NAME || 'pm-wallet-tracker');
  const walletsCollection = db.collection('wallets');
  const now = new Date();

  for (const a of addrs) {
    await walletsCollection.updateOne(
      { userId: session.user.id, address: a.toLowerCase() },
      {
        $set: {
          userId: session.user.id,
          address: a.toLowerCase(),
          isActive: true,
          updatedAt: now,
        },
        $setOnInsert: {
          label: '',
          createdAt: now,
        },
      },
      { upsert: true }
    );
  }

  return new Response(JSON.stringify({ added: addrs }), { headers: { 'content-type': 'application/json' }});
}
