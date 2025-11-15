const DATA_API = process.env.POLYMARKET_DATA_API || 'https://data-api.polymarket.com';
const TAKER_ONLY = (process.env.TAKER_ONLY || 'false').toLowerCase() === 'true';

export type DataTrade = {
  proxyWallet: string;
  side: 'BUY'|'SELL';
  size: number;
  price: number;
  outcome?: string;
  title?: string;
  slug?: string;
  timestamp: number;
  transactionHash: string;
};

export async function fetchTradesForUser(address: string, limit = 50): Promise<DataTrade[]> {
  const params = new URLSearchParams({
    user: address,
    limit: String(limit),
    takerOnly: String(TAKER_ONLY),
  });
  const url = `${DATA_API}/trades?${params.toString()}`;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 10_000);
  const resp = await fetch(url, { signal: ctrl.signal });
  clearTimeout(timer);
  if (!resp.ok) {
    const txt = await resp.text().catch(()=>'');
    throw new Error(`/trades error ${resp.status} ${txt}`);
  }
  const data = await resp.json();
  return Array.isArray(data) ? data as DataTrade[] : [];
}
