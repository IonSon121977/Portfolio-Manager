'use client';

import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

export default function StockDetailPage() {
  const params = useParams();
  const router = useRouter();
  const symbol = decodeURIComponent(params.symbol as string);
  const [stock, setStock] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/stocks?symbols=${symbol}`)
      .then(r => r.json())
      .then(data => {
        setStock(data.stocks?.[0] || null);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [symbol]);

  if (loading) return (
    <div style={{ fontFamily: 'Arial, sans-serif', padding: 40, maxWidth: 800, margin: '0 auto' }}>
      <p>Loading {symbol}...</p>
    </div>
  );

  if (!stock) return (
    <div style={{ fontFamily: 'Arial, sans-serif', padding: 40, maxWidth: 800, margin: '0 auto' }}>
      <button onClick={() => router.push('/stocks')} style={{ marginBottom: 24, padding: '8px 16px', cursor: 'pointer' }}>← Back</button>
      <p>No data found for {symbol}</p>
    </div>
  );

  const bd = stock.scoreBreakdown;

  return (
    <div style={{ fontFamily: 'Arial, sans-serif', padding: 40, maxWidth: 900, margin: '0 auto' }}>
      <button
        onClick={() => router.push('/stocks')}
        style={{ marginBottom: 24, padding: '8px 16px', background: '#1976d2', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 14 }}
      >
        ← Back to Stocks
      </button>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 16, marginBottom: 8 }}>
        <h1 style={{ margin: 0, fontSize: 28 }}>{stock.symbol}</h1>
        <span style={{ color: '#666', fontSize: 18 }}>{stock.name}</span>
      </div>

      <div style={{ display: 'flex', gap: 24, marginBottom: 32, flexWrap: 'wrap' }}>
        <div style={{ background: '#f5f5f5', borderRadius: 8, padding: '16px 24px' }}>
          <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>Current Price</div>
          <div style={{ fontSize: 24, fontWeight: 700 }}>${stock.currentPrice?.toFixed(2)}</div>
        </div>
        <div style={{ background: '#f5f5f5', borderRadius: 8, padding: '16px 24px' }}>
          <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>Day Change</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: stock.priceChangePercent >= 0 ? '#2e7d32' : '#c62828' }}>
            {stock.priceChangePercent >= 0 ? '+' : ''}{stock.priceChangePercent?.toFixed(2)}%
          </div>
        </div>
        <div style={{ background: '#e3f2fd', borderRadius: 8, padding: '16px 24px' }}>
          <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>Investment Score</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: '#1976d2' }}>{stock.investmentScore}</div>
        </div>
      </div>

      {bd && (
        <>
          <h2 style={{ fontSize: 18, marginBottom: 16 }}>Score Breakdown</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
            {[
              { label: 'P/E Ratio', data: bd.peRatio },
              { label: 'P/B Ratio', data: bd.pbRatio },
              { label: 'P/S Ratio', data: bd.psRatio },
              { label: 'Price Change', data: bd.priceChange },
              { label: 'Volume', data: bd.volume },
              { label: 'ROE', data: bd.roe },
              { label: 'ROA', data: bd.roa },
              { label: 'Debt/Equity', data: bd.debtToEquity },
              { label: 'Current Ratio', data: bd.currentRatio },
              { label: 'Dividend Yield', data: bd.dividendYield },
              { label: 'Profit Margin', data: bd.profitMargin },
              { label: 'Revenue Growth', data: bd.revenueGrowth },
              { label: 'Earnings Growth', data: bd.earningsGrowth },
              { label: 'Beta', data: bd.beta },
              { label: '52W Change', data: bd.fiftyTwoWeekChange },
            ].map(({ label, data }) => data && (
              <div key={label} style={{
                padding: 12, background: '#fafafa', borderRadius: 8,
                borderLeft: `4px solid ${data.contribution > 0 ? '#2e7d32' : data.contribution < 0 ? '#c62828' : '#ccc'}`
              }}>
                <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>
                  {label}{data.value !== undefined ? ` (${typeof data.value === 'number' ? data.value.toFixed(2) : data.value})` : ''}
                </div>
                <div style={{ fontSize: 20, fontWeight: 700, color: data.contribution > 0 ? '#2e7d32' : data.contribution < 0 ? '#c62828' : '#666' }}>
                  {data.contribution > 0 ? '+' : ''}{data.contribution}
                </div>
                <div style={{ fontSize: 11, color: '#888', fontStyle: 'italic' }}>{data.reason}</div>
              </div>
            ))}
            <div style={{ padding: 12, background: '#e3f2fd', borderRadius: 8, borderLeft: '4px solid #1976d2', gridColumn: '1 / -1' }}>
              <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>Total Score</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#1976d2' }}>{bd.totalScore}</div>
              <div style={{ fontSize: 11, color: '#888', fontStyle: 'italic' }}>Final investment score (0-100)</div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
