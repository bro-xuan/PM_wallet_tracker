import { isAddress } from '@/lib/util';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const POLYMARKET_DATA_API = 'https://data-api.polymarket.com';

function formatCurrency(value: number): string {
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
    // Fetch all three endpoints in parallel
    const [valueResp, tradedResp, closedPositionsResp] = await Promise.all([
      fetch(`${POLYMARKET_DATA_API}/value?user=${address}`),
      fetch(`${POLYMARKET_DATA_API}/traded?user=${address}`),
      fetch(`${POLYMARKET_DATA_API}/closed-positions?user=${address}&limit=1000&offset=0`)
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
      predictionsCount = typeof tradedData.traded === 'number' ? tradedData.traded : 0;
    }

    // Calculate Biggest Win from closed positions
    if (closedPositionsResp.ok) {
      const closedPositions = await closedPositionsResp.json();
      
      if (Array.isArray(closedPositions) && closedPositions.length > 0) {
        // Group by (conditionId, asset) composite key
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
        // If all are <= 0, biggestWin remains 0
      }
    }

    return new Response(JSON.stringify({
      address,
      positionsValue,
      positionsValueFormatted: formatCurrency(positionsValue),
      biggestWin,
      biggestWinFormatted: formatCurrency(biggestWin),
      predictionsCount
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
