import { isAddress } from '@/lib/util';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const POLYMARKET_DATA_API = 'https://data-api.polymarket.com';

async function fetchAllClosedPositions(address: string): Promise<any[]> {
  const allPositions: any[] = [];
  let offset = 0;
  const limit = 50;

  while (true) {
    const resp = await fetch(
      `${POLYMARKET_DATA_API}/closed-positions?user=${address}&limit=${limit}&offset=${offset}&sortBy=TIMESTAMP&sortDirection=ASC`
    );

    if (!resp.ok) break;

    const pageData = await resp.json();
    if (!Array.isArray(pageData) || pageData.length === 0) break;

    allPositions.push(...pageData);

    // If we got fewer than limit results, we've reached the last page
    if (pageData.length < limit) break;

    offset += limit;
  }

  return allPositions;
}

async function fetchAllOpenPositions(address: string): Promise<any[]> {
  const allPositions: any[] = [];
  let offset = 0;
  const limit = 500;

  while (true) {
    const resp = await fetch(
      `${POLYMARKET_DATA_API}/positions?user=${address}&sizeThreshold=0&limit=${limit}&offset=${offset}`
    );

    if (!resp.ok) break;

    const pageData = await resp.json();
    if (!Array.isArray(pageData) || pageData.length === 0) break;

    allPositions.push(...pageData);

    // If we got fewer than limit results, we've reached the last page
    if (pageData.length < limit) break;

    offset += limit;
  }

  return allPositions;
}

function formatCurrency(value: number): string {
  if (value === 0) {
    return '$0';
  }
  if (value >= 1000000) {
    return `$${(value / 1000000).toFixed(1)}M`;
  } else if (value >= 1000) {
    return `$${(value / 1000).toFixed(1)}k`;
  } else {
    return `$${value.toFixed(2)}`;
  }
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const address = url.searchParams.get('address') || '';
  
  if (!address || !isAddress(address)) {
    return new Response(JSON.stringify({ error: 'Valid wallet address required' }), { 
      status: 400,
      headers: { 'content-type': 'application/json' }
    });
  }

  try {
    // Fetch value and traded endpoints first
    const [valueResp, tradedResp] = await Promise.all([
      fetch(`${POLYMARKET_DATA_API}/value?user=${address}`),
      fetch(`${POLYMARKET_DATA_API}/traded?user=${address}`)
    ]);

    // Handle errors gracefully
    let positionsValue = 0;
    let predictionsCount = 0;
    let biggestWin = 0;

    if (valueResp.ok) {
      const valueData = await valueResp.json();
      // Response is an array: [{ "user": "0x...", "value": 123.45 }]
      if (Array.isArray(valueData) && valueData.length > 0) {
        const firstItem = valueData[0];
        if (typeof firstItem.value === 'number') {
          positionsValue = firstItem.value;
        } else if (typeof firstItem.value === 'string') {
          positionsValue = parseFloat(firstItem.value) || 0;
        }
      }
    }

    if (tradedResp.ok) {
      const tradedData = await tradedResp.json();
      // Handle different possible response structures
      let rawTraded: any;
      if (typeof tradedData === 'number') {
        rawTraded = tradedData;
      } else if (typeof tradedData.traded === 'number' || typeof tradedData.traded === 'string') {
        rawTraded = tradedData.traded;
      } else if (typeof tradedData.data?.traded === 'number' || typeof tradedData.data?.traded === 'string') {
        rawTraded = tradedData.data.traded;
      }
      predictionsCount = typeof rawTraded === 'number' ? rawTraded : (typeof rawTraded === 'string' ? parseInt(rawTraded, 10) || 0 : 0);
    }

    // Fetch all closed and open positions with pagination
    const [closedPositions, openPositions] = await Promise.all([
      fetchAllClosedPositions(address),
      fetchAllOpenPositions(address)
    ]);

    // Calculate totalClosedRealized: sum of all realizedPnl from closed positions
    let totalClosedRealized = 0;
    for (const position of closedPositions) {
      const realizedPnl = typeof position.realizedPnl === 'number' ? position.realizedPnl : 0;
      totalClosedRealized += realizedPnl;
    }

    // Calculate totalOpenPnl: sum of (cashPnl + realizedPnl) for each open position
    let totalOpenPnl = 0;
    for (const position of openPositions) {
      const cashPnl = typeof position.cashPnl === 'number' ? position.cashPnl : 0;
      const realizedPnl = typeof position.realizedPnl === 'number' ? position.realizedPnl : 0;
      totalOpenPnl += (cashPnl + realizedPnl);
    }

    // Total all-time trading PnL
    const allTimePnl = totalClosedRealized + totalOpenPnl;

    // Calculate Biggest Win and PnL chart data from closed positions
    let pnlChartData: { all: Array<{ time: string; value: number }>, d1: Array<{ time: string; value: number }>, w1: Array<{ time: string; value: number }>, m1: Array<{ time: string; value: number }> } = {
      all: [],
      d1: [],
      w1: [],
      m1: []
    };

    if (closedPositions.length > 0) {

        // Group by (conditionId, asset) composite key for Biggest Win
        const groupedPnL: Record<string, number> = {};
        
        for (const position of closedPositions) {
          if (typeof position.conditionId === 'string' && typeof position.asset === 'string') {
            const key = `${position.conditionId}:${position.asset}`;
            const realizedPnl = typeof position.realizedPnl === 'number' ? position.realizedPnl : 0;
            
            if (!groupedPnL[key]) {
              groupedPnL[key] = 0;
            }
            groupedPnL[key] += realizedPnl;
          }
        }
        
        // Find the maximum positive netRealizedPnl
        const allNetPnLs = Object.values(groupedPnL);
        const positivePnLs = allNetPnLs.filter(pnl => pnl > 0);
        
        if (positivePnLs.length > 0) {
          biggestWin = Math.max(...positivePnLs);
        }

        // Build cumulative PnL series for different time windows
        const now = Math.floor(Date.now() / 1000);
        const oneDayAgo = now - 24 * 60 * 60;
        const oneWeekAgo = now - 7 * 24 * 60 * 60;
        const oneMonthAgo = now - 30 * 24 * 60 * 60;

        // Filter and sort positions by timestamp
        const validPositions = closedPositions
          .filter((p: any) => typeof p.timestamp === 'number' && typeof p.realizedPnl === 'number')
          .sort((a: any, b: any) => a.timestamp - b.timestamp);

        // Helper function to build cumulative series
        function buildCumulativeSeries(positions: any[]): Array<{ time: string; value: number }> {
          let cumPnl = 0;
          return positions.map((p: any) => {
            cumPnl += p.realizedPnl;
            return {
              time: new Date(p.timestamp * 1000).toISOString(),
              value: cumPnl
            };
          });
        }

        // Build ALL series (all positions)
        pnlChartData.all = buildCumulativeSeries(validPositions);

        // Build 1D series
        const d1Positions = validPositions.filter((p: any) => p.timestamp >= oneDayAgo);
        pnlChartData.d1 = buildCumulativeSeries(d1Positions);

        // Build 1W series
        const w1Positions = validPositions.filter((p: any) => p.timestamp >= oneWeekAgo);
        pnlChartData.w1 = buildCumulativeSeries(w1Positions);

        // Build 1M series
        const m1Positions = validPositions.filter((p: any) => p.timestamp >= oneMonthAgo);
        pnlChartData.m1 = buildCumulativeSeries(m1Positions);
    }

    // Format all-time PnL with thousands separators and 2 decimals
    const allTimePnlFormatted = allTimePnl.toLocaleString('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });

    return new Response(JSON.stringify({
      address,
      positionsValue,
      positionsValueFormatted: formatCurrency(positionsValue),
      biggestWin,
      biggestWinFormatted: formatCurrency(biggestWin),
      predictionsCount,
      allTimePnl,
      allTimePnlFormatted,
      pnlChartData
    }), {
      headers: { 'content-type': 'application/json' }
    });
  } catch (error: any) {
    return new Response(JSON.stringify({ 
      error: error.message || 'Failed to fetch trader stats' 
    }), { 
      status: 500,
      headers: { 'content-type': 'application/json' }
    });
  }
}
