'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

type Trade = {
  txhash: string;
  wallet: string;
  side: 'BUY'|'SELL';
  size: number;
  price: number;
  notional: number;
  outcome?: string;
  title?: string;
  slug?: string;
  timestamp: number;
};

function fmt(n: number){ return n.toFixed(2); }
const marketUrl = (slug?: string) => slug ? `https://polymarket.com/market/${slug}` : '#';
const walletProfileUrl = (addr: string) => `https://polymarket.com/profile/${addr}`;
const shortAddr = (addr: string) => addr.length <= 8 ? addr : `${addr.slice(0,4)}…${addr.slice(-4)}`;
const BASE_TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Berlin',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Australia/Sydney',
];

export default function Home() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [wallets, setWallets] = useState<string[]>([]);
  const [addressInput, setAddressInput] = useState('');
  const [walletFilter, setWalletFilter] = useState('');
  const [notionalPreset, setNotionalPreset] = useState('');
  const [sideFilter, setSideFilter] = useState('');
  const [priceFilter, setPriceFilter] = useState('');
  const [timeZone, setTimeZone] = useState('UTC');
  const [labels, setLabels] = useState<Record<string, string>>({});
  const walletsRef = useRef<Set<string>>(new Set());

  const walletsSet = useMemo(() => new Set(wallets.map(w => w.toLowerCase())), [wallets]);
  const timeZoneOptions = useMemo(() => {
    const guess = typeof Intl !== 'undefined'
      ? Intl.DateTimeFormat().resolvedOptions().timeZone
      : 'UTC';
    const opts = [...BASE_TIMEZONES];
    if (guess && !opts.includes(guess)) {
      opts.splice(1, 0, guess);
    }
    return opts;
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const storedTz = localStorage.getItem('timeZone');
      if (storedTz) {
        setTimeZone(storedTz);
      } else {
        const guess = Intl.DateTimeFormat().resolvedOptions().timeZone;
        if (guess) setTimeZone(guess);
      }
    } catch {}
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const raw = localStorage.getItem('walletLabels');
      if (raw) setLabels(JSON.parse(raw));
    } catch {}
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      localStorage.setItem('walletLabels', JSON.stringify(labels));
    } catch {}
  }, [labels]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      localStorage.setItem('timeZone', timeZone);
    } catch {}
  }, [timeZone]);

  useEffect(() => {
    walletsRef.current = walletsSet;
    if (walletsSet.size === 0) {
      setTrades([]);
    } else {
      setTrades(prev => prev.filter(t => walletsSet.has(t.wallet.toLowerCase())));
    }
  }, [walletsSet]);

  const tsFormatter = useMemo(() => new Intl.DateTimeFormat('en-US', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }), [timeZone]);

  const formatTime = useCallback((seconds: number) => {
    const parts = tsFormatter.formatToParts(new Date(seconds * 1000));
    const map: Record<string, string> = {};
    for (const part of parts) {
      if (part.type === 'literal') continue;
      map[part.type] = part.value;
    }
    const date = `${map.year}-${map.month}-${map.day}`;
    const time = `${map.hour}:${map.minute}:${map.second}`;
    return `${date} ${time}`;
  }, [tsFormatter]);

  const syncWalletsAndTrades = useCallback(async () => {
    const [t, w] = await Promise.all([
      fetch('/api/trades/recent?limit=200', { cache: 'no-store' }).then(r=>r.json()),
      fetch('/api/wallets', { cache: 'no-store' }).then(r=>r.json())
    ]);
    const addresses: string[] = w.addresses || [];
    const allowed = new Set(addresses.map(a => a.toLowerCase()));
    setWallets(addresses);
    setTrades(Array.isArray(t.trades)
      ? t.trades.filter((trade: Trade) => allowed.has(trade.wallet.toLowerCase()))
      : []
    );
  }, []);

  // initial data
  useEffect(() => {
    syncWalletsAndTrades();
  }, [syncWalletsAndTrades]);

  // live stream
  useEffect(() => {
    const es = new EventSource('/api/stream');
    const onTrade = (ev: MessageEvent) => {
      const t = JSON.parse(ev.data) as Trade;
      if (!walletsRef.current.has(t.wallet.toLowerCase())) return;
      setTrades(prev => [t, ...prev]);
    };
    es.addEventListener('trade', onTrade);
    return () => {
      es.removeEventListener('trade', onTrade);
      es.close();
    };
  }, []);

  async function addWallets() {
    const addrs = addressInput.split(/[\s,;]+/).map(s=>s.trim()).filter(Boolean);
    if (addrs.length === 0) return;
    await fetch('/api/wallets', {
      method: 'POST',
      cache: 'no-store',
      headers: { 'content-type':'application/json' },
      body: JSON.stringify({ addresses: addrs })
    });
    setAddressInput('');
    await syncWalletsAndTrades();
  }

  async function removeWallet(addr: string) {
    const addrKey = addr.toLowerCase();
    setWallets(prev => prev.filter(w => w.toLowerCase() !== addrKey));
    setLabels(prev => {
      const copy = { ...prev };
      delete copy[addrKey];
      return copy;
    });
    setTrades(prev => prev.filter(t => t.wallet.toLowerCase() !== addrKey));
    try {
      const resp = await fetch(`/api/wallets/${encodeURIComponent(addr)}`, { method: 'DELETE', cache: 'no-store' });
      if (!resp.ok) throw new Error('Failed to delete wallet');
      await syncWalletsAndTrades();
    } catch (err) {
      console.error('removeWallet failed', err);
      await syncWalletsAndTrades();
    }
  }

  async function onUpload(e: React.ChangeEvent<HTMLFormElement>){
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    await fetch('/api/wallets/upload', { method:'POST', body: fd });
    e.currentTarget.reset();
    await syncWalletsAndTrades();
  }

  const filtered = useMemo(() => {
    const walletQuery = walletFilter.trim().toLowerCase();
    const minNotional = Number(notionalPreset || 0);
    return trades.filter(t => {
      if (!walletsSet.has(t.wallet.toLowerCase())) return false;
      if (minNotional > 0 && t.notional < minNotional) return false;
      if (sideFilter && t.side !== sideFilter) return false;
      if (priceFilter) {
        const p = t.price;
        if (priceFilter === 'extreme') {
          if (!((p >= 0 && p < 0.05) || (p > 0.95 && p <= 1))) return false;
        } else if (priceFilter === 'middle') {
          if (!(p >= 0.05 && p <= 0.95)) return false;
        }
      }
      if (walletQuery) {
        const label = labels[t.wallet.toLowerCase()] || '';
        const hay = `${label} ${t.wallet}`.toLowerCase();
        if (!hay.includes(walletQuery)) return false;
      }
      return true;
    });
  }, [trades, walletFilter, notionalPreset, sideFilter, priceFilter, walletsSet, labels]);

  function editLabel(addr: string) {
    const current = labels[addr.toLowerCase()] || '';
    const next = window.prompt('Label for wallet', current);
    if (next === null) return;
    const trimmed = next.trim();
    setLabels(prev => {
      const copy = { ...prev };
      const key = addr.toLowerCase();
      if (!trimmed) {
        delete copy[key];
      } else {
        copy[key] = trimmed;
      }
      return copy;
    });
  }

  return (
    <>
      <header>
        <h1>Polymarket Wallet Tracker <span className="muted">· live</span></h1>
        <div className="settings">
          <label htmlFor="timezone">Time zone</label>
          <select
            id="timezone"
            value={timeZone}
            onChange={e => setTimeZone(e.target.value)}
          >
            {timeZoneOptions.map(tz => (
              <option key={tz} value={tz}>{tz}</option>
            ))}
          </select>
        </div>
      </header>
      <main>
        <section className="card">
          <h3>Watch wallets</h3>
          <p className="muted">Add 0x addresses (proxy wallets). Upload a .txt/.csv or paste below.</p>

          <form className="row file-row" onSubmit={onUpload}>
            <input type="file" name="file" accept=".txt,.csv"/>
            <button type="submit">Upload file</button>
          </form>

          <div className="row">
            <input
              value={addressInput}
              onChange={e=>setAddressInput(e.target.value)}
              placeholder="0xabc..., 0xdef..."
              style={{ flex:1 }}
            />
            <button onClick={addWallets}>Add</button>
          </div>

          <h4 style={{marginTop:18}}>Current wallets</h4>
          <ul style={{listStyle:'none', paddingLeft:0, margin:0}}>
            {wallets.map(a => (
              <li key={a} className="row">
                <div style={{flex:1}}>
                  <div className="mono addr">
                    {labels[a.toLowerCase()] || shortAddr(a)}
                  </div>
                </div>
                <button type="button" onClick={()=>editLabel(a)}>Label</button>
                <button type="button" onClick={()=>removeWallet(a)}>Remove</button>
              </li>
            ))}
          </ul>
        </section>

        <section className="card">
          <div className="row" style={{justifyContent:'space-between'}}>
            <div>
              <strong>Live trades</strong>
              <span className="muted"> · newest first</span>
            </div>
            <div className="row filters">
              <input
                placeholder="Filter by wallet or label"
                value={walletFilter}
                onChange={e=>setWalletFilter(e.target.value)}
              />
              <select
                value={notionalPreset}
                onChange={e=>setNotionalPreset(e.target.value)}
                style={{width:160}}
              >
                <option value="">All notionals</option>
                <option value="500">&gt; 500</option>
                <option value="1000">&gt; 1,000</option>
                <option value="3000">&gt; 3,000</option>
                <option value="5000">&gt; 5,000</option>
                <option value="10000">&gt; 10,000</option>
              </select>
              <select
                value={sideFilter}
                onChange={e=>setSideFilter(e.target.value)}
                style={{width:120}}
              >
                <option value="">All sides</option>
                <option value="BUY">Buy only</option>
                <option value="SELL">Sell only</option>
              </select>
              <select
                value={priceFilter}
                onChange={e=>setPriceFilter(e.target.value)}
                style={{width:180}}
              >
                <option value="">All prices</option>
                <option value="extreme">0-5% &amp; 95%-100%</option>
                <option value="middle">5-95%</option>
              </select>
              <span className="tag">{filtered.length}</span>
            </div>
          </div>

          <div style={{overflow:'auto', maxHeight:'calc(100vh - 260px)', marginTop:12}}>
            <table>
              <thead>
                <tr>
                  <th className="nowrap">Time</th>
                  <th>Wallet</th>
                  <th>Market</th>
                  <th>Outcome</th>
                  <th>Side</th>
                  <th className="nowrap">Size</th>
                  <th className="nowrap">Price</th>
                  <th className="nowrap">Notional</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(t => (
                  <tr key={t.txhash}>
                    <td className="nowrap">{formatTime(t.timestamp)}</td>
                    <td className="mono addr">
                      <a
                        href={walletProfileUrl(t.wallet)}
                        target="_blank"
                        rel="noopener"
                      >
                        {labels[t.wallet.toLowerCase()] || shortAddr(t.wallet)}
                      </a>
                    </td>
                    <td>
                      {t.slug
                        ? <a href={marketUrl(t.slug)} target="_blank" rel="noopener">{t.title || ''}</a>
                        : (t.title || '')}
                    </td>
                    <td>{t.outcome || ''}</td>
                    <td className={t.side === 'BUY' ? 'buy' : 'sell'}>{t.side}</td>
                    <td>{fmt(t.size)}</td>
                    <td>{fmt(t.price)}</td>
                    <td>{fmt(t.notional)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </>
  );
}
