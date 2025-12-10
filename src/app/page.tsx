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
  const [activeTab, setActiveTab] = useState<'monitoring' | 'stats'>('monitoring');
  const [trades, setTrades] = useState<Trade[]>([]);
  const [wallets, setWallets] = useState<string[]>([]);
  const [addressInput, setAddressInput] = useState('');
  const [walletFilter, setWalletFilter] = useState('');
  const [notionalPreset, setNotionalPreset] = useState('');
  const [sideFilter, setSideFilter] = useState('');
  const [priceFilter, setPriceFilter] = useState('');
  const [timeZone, setTimeZone] = useState('UTC');
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [currentPage, setCurrentPage] = useState(0);
  const [pageSize, setPageSize] = useState(200);
  const [totalTrades, setTotalTrades] = useState(0);
  const walletsRef = useRef<Set<string>>(new Set());
  const tableContainerRef = useRef<HTMLDivElement>(null);
  
  // Trader Stats state
  const [traderAddress, setTraderAddress] = useState('');
  const [traderStats, setTraderStats] = useState<any>(null);
  const [loadingStats, setLoadingStats] = useState(false);
  const [statsError, setStatsError] = useState<string | null>(null);

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
    const offset = currentPage * pageSize;
    const [t, w] = await Promise.all([
      fetch(`/api/trades/recent?limit=${pageSize}&offset=${offset}`, { cache: 'no-store' }).then(r=>r.json()),
      fetch('/api/wallets', { cache: 'no-store' }).then(r=>r.json())
    ]);
    const addresses: string[] = w.addresses || [];
    const allowed = new Set(addresses.map(a => a.toLowerCase()));
    setWallets(addresses);
    setTotalTrades(t.total || 0);
    setTrades(Array.isArray(t.trades)
      ? t.trades.filter((trade: Trade) => allowed.has(trade.wallet.toLowerCase()))
      : []
    );
  }, [currentPage, pageSize]);

  // initial data
  useEffect(() => {
    syncWalletsAndTrades();
  }, [syncWalletsAndTrades]);

  // scroll to top when page changes
  useEffect(() => {
    if (tableContainerRef.current) {
      tableContainerRef.current.scrollTop = 0;
    }
  }, [currentPage]);

  // reset to page 0 when page size changes
  useEffect(() => {
    setCurrentPage(0);
  }, [pageSize]);

  // live stream (only on first page)
  useEffect(() => {
    if (currentPage !== 0) return; // Disable live stream when viewing older pages
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
  }, [currentPage]);

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
    const seen = new Set<string>();
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
      const uniqueKey = `${t.txhash}-${t.wallet}-${t.timestamp}`;
      if (seen.has(uniqueKey)) return false;
      seen.add(uniqueKey);
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

  async function fetchTraderStats(addr: string) {
    if (!addr || addr.trim().length === 0) return;
    setLoadingStats(true);
    setStatsError(null);
    try {
      const resp = await fetch(`/api/trader/stats?address=${encodeURIComponent(addr)}`, { cache: 'no-store' });
      const data = await resp.json();
      if (!resp.ok) {
        setStatsError(data.error || 'Failed to fetch trader stats');
        setTraderStats(null);
      } else {
        setTraderStats(data);
      }
    } catch (err: any) {
      console.error('Failed to fetch trader stats', err);
      setStatsError(err.message || 'Failed to fetch trader stats');
      setTraderStats(null);
    } finally {
      setLoadingStats(false);
    }
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
      <div style={{padding:'0 20px', borderBottom:'1px solid var(--line)', display:'flex', gap:0}}>
        <button
          type="button"
          onClick={()=>setActiveTab('monitoring')}
          style={{
            padding:'12px 24px',
            border:'none',
            borderBottom:activeTab === 'monitoring' ? '2px solid #4b6bff' : '2px solid transparent',
            background:'transparent',
            color:activeTab === 'monitoring' ? 'var(--ink)' : 'var(--muted)',
            cursor:'pointer',
            fontSize:14,
            fontWeight:activeTab === 'monitoring' ? 600 : 400
          }}
        >
          Live Monitoring
        </button>
        <button
          type="button"
          onClick={()=>setActiveTab('stats')}
          style={{
            padding:'12px 24px',
            border:'none',
            borderBottom:activeTab === 'stats' ? '2px solid #4b6bff' : '2px solid transparent',
            background:'transparent',
            color:activeTab === 'stats' ? 'var(--ink)' : 'var(--muted)',
            cursor:'pointer',
            fontSize:14,
            fontWeight:activeTab === 'stats' ? 600 : 400
          }}
        >
          Trader Stats
        </button>
      </div>
      <main>
        {activeTab === 'monitoring' ? (
          <>
        <section className="card" style={{display:'flex', flexDirection:'column', height:'100%'}}>
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
          <ul style={{listStyle:'none', paddingLeft:0, margin:0, flex:1, overflowY:'auto', minHeight:0}}>
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

          <div ref={tableContainerRef} style={{overflow:'auto', height:'60vh', minHeight:'400px', marginTop:12}}>
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
                  <tr key={`${t.txhash}-${t.wallet}-${t.timestamp}`}>
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

          <div style={{display:'flex', justifyContent:'flex-end', alignItems:'center', gap:12, marginTop:16, flexWrap:'wrap'}}>
            <span style={{fontSize:14, color:'var(--ink)'}}>
              Results: {(currentPage * pageSize) + 1} - {Math.min((currentPage + 1) * pageSize, totalTrades)} of {totalTrades}
            </span>
            <div style={{display:'flex', gap:4, alignItems:'center'}}>
              {(() => {
                const totalPages = Math.ceil(totalTrades / pageSize);
                const current = currentPage + 1;
                const pages: (number | string)[] = [];
                
                if (totalPages <= 7) {
                  for (let i = 1; i <= totalPages; i++) pages.push(i);
                } else {
                  pages.push(1);
                  if (current > 3) pages.push('...');
                  for (let i = Math.max(2, current - 1); i <= Math.min(totalPages - 1, current + 1); i++) {
                    pages.push(i);
                  }
                  if (current < totalPages - 2) pages.push('...');
                  pages.push(totalPages);
                }
                
                return (
                  <>
                    <button
                      type="button"
                      onClick={()=>setCurrentPage(prev=>Math.max(0, prev-1))}
                      disabled={currentPage === 0}
                      style={{
                        padding:'6px 10px',
                        minWidth:36,
                        height:36,
                        borderRadius:6,
                        border:'1px solid #2a375d',
                        background:currentPage === 0 ? '#0e152a' : '#152042',
                        color:'var(--ink)',
                        cursor:currentPage === 0 ? 'not-allowed' : 'pointer',
                        opacity:currentPage === 0 ? 0.5 : 1
                      }}
                    >
                      &lt;
                    </button>
                    {pages.map((p, idx) => {
                      if (p === '...') {
                        return (
                          <span key={`ellipsis-${idx}`} style={{padding:'0 4px', color:'var(--muted)'}}>...</span>
                        );
                      }
                      const pageNum = p as number;
                      const isActive = pageNum === current;
                      return (
                        <button
                          key={pageNum}
                          type="button"
                          onClick={()=>setCurrentPage(pageNum - 1)}
                          style={{
                            padding:'6px 10px',
                            minWidth:36,
                            height:36,
                            borderRadius:6,
                            border:'1px solid #2a375d',
                            background:isActive ? '#1e3a8a' : '#152042',
                            color:isActive ? '#fff' : 'var(--ink)',
                            cursor:'pointer'
                          }}
                        >
                          {pageNum}
                        </button>
                      );
                    })}
                    <button
                      type="button"
                      onClick={()=>setCurrentPage(prev=>Math.min(Math.ceil(totalTrades / pageSize) - 1, prev+1))}
                      disabled={(currentPage + 1) * pageSize >= totalTrades}
                      style={{
                        padding:'6px 10px',
                        minWidth:36,
                        height:36,
                        borderRadius:6,
                        border:'1px solid #2a375d',
                        background:(currentPage + 1) * pageSize >= totalTrades ? '#0e152a' : '#152042',
                        color:'var(--ink)',
                        cursor:(currentPage + 1) * pageSize >= totalTrades ? 'not-allowed' : 'pointer',
                        opacity:(currentPage + 1) * pageSize >= totalTrades ? 0.5 : 1
                      }}
                    >
                      &gt;
                    </button>
                  </>
                );
              })()}
              <select
                value={pageSize}
                onChange={e=>setPageSize(Number(e.target.value))}
                style={{
                  padding:'6px 10px',
                  height:36,
                  borderRadius:6,
                  border:'1px solid #2a375d',
                  background:'#152042',
                  color:'var(--ink)',
                  cursor:'pointer'
                }}
              >
                <option value={50}>50</option>
                <option value={100}>100</option>
                <option value={200}>200</option>
                <option value={500}>500</option>
              </select>
            </div>
          </div>
        </section>
          </>
        ) : (
          <section className="card">
            <h3>Trader Stats</h3>
            <p className="muted">Enter a wallet address to view PnL and win rate statistics.</p>
            
            <div className="row" style={{marginTop:16}}>
              <input
                value={traderAddress}
                onChange={e=>setTraderAddress(e.target.value)}
                placeholder="0x..."
                style={{ flex:1 }}
                onKeyDown={e=>{if(e.key==='Enter') fetchTraderStats(traderAddress)}}
              />
              <button onClick={()=>fetchTraderStats(traderAddress)} disabled={loadingStats}>
                {loadingStats ? 'Loading...' : 'Get Stats'}
              </button>
            </div>

            {traderStats && (
              <div style={{marginTop:24}}>
                <section className="card" style={{padding:24}}>
                  <div style={{display:'flex', alignItems:'center', gap:16, marginBottom:24}}>
                    <div style={{
                      width:64,
                      height:64,
                      borderRadius:'50%',
                      background:'linear-gradient(135deg, #ff6b9d 0%, #c44569 50%, #f8b500 100%)',
                      flexShrink:0
                    }} />
                    <div style={{flex:1}}>
                      <h2 
                        style={{margin:0, fontSize:24, fontWeight:600, cursor:'pointer'}}
                        title={traderAddress}
                        onClick={()=>{navigator.clipboard.writeText(traderAddress)}}
                      >
                        {shortAddr(traderAddress)}
                      </h2>
                      <p style={{margin:4, fontSize:14, color:'var(--muted)', fontFamily:'ui-monospace'}}>
                        {traderAddress}
                      </p>
                    </div>
                  </div>

                  <div style={{display:'flex', gap:24, paddingTop:24, borderTop:'1px solid var(--line)'}}>
                    <div style={{flex:1}}>
                      <div style={{fontSize:12, color:'var(--muted)', marginBottom:8}}>Positions Value</div>
                      <div style={{fontSize:28, fontWeight:600}}>
                        {traderStats.positionsValueFormatted || '$0'}
                      </div>
                    </div>
                    <div style={{width:1, background:'var(--line)'}} />
                    <div style={{flex:1}}>
                      <div style={{fontSize:12, color:'var(--muted)', marginBottom:8}}>Biggest Win</div>
                      <div style={{fontSize:28, fontWeight:600}}>
                        {traderStats.biggestWinFormatted || '$0'}
                      </div>
                    </div>
                    <div style={{width:1, background:'var(--line)'}} />
                    <div style={{flex:1}}>
                      <div style={{fontSize:12, color:'var(--muted)', marginBottom:8}}>Predictions</div>
                      <div style={{fontSize:28, fontWeight:600}}>
                        {traderStats.predictionsCount || 0}
                      </div>
                    </div>
                  </div>
                </section>
              </div>
            )}

            {loadingStats && (
              <div style={{marginTop:24, padding:16, textAlign:'center', color:'var(--muted)'}}>
                Loading trader stats...
              </div>
            )}

            {statsError && (
              <div style={{marginTop:24, padding:16, background:'var(--bg)', borderRadius:8, textAlign:'center', color:'var(--bad)'}}>
                Error: {statsError}
              </div>
            )}
          </section>
        )}
      </main>
    </>
  );
}
