'use client';

import React, { useEffect, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import jsPDF from 'jspdf';
import 'jspdf-autotable';
import { PRODUCT_NAME, PRODUCT_VERSION } from '../../lib/version';
import './stocks.css';

interface ScoreBreakdown {
  baseScore: number;
  peRatio: { value?: number; contribution: number; reason: string };
  pbRatio: { value?: number; contribution: number; reason: string };
  psRatio: { value?: number; contribution: number; reason: string };
  priceChange: { value: number; contribution: number; reason: string };
  volume: { value?: number; contribution: number; reason: string };
  roe: { value?: number; contribution: number; reason: string };
  roa: { value?: number; contribution: number; reason: string };
  debtToEquity: { value?: number; contribution: number; reason: string };
  currentRatio: { value?: number; contribution: number; reason: string };
  dividendYield: { value?: number; contribution: number; reason: string };
  profitMargin: { value?: number; contribution: number; reason: string };
  revenueGrowth: { value?: number; contribution: number; reason: string };
  earningsGrowth: { value?: number; contribution: number; reason: string };
  beta: { value?: number; contribution: number; reason: string };
  fiftyTwoWeekChange: { value?: number; contribution: number; reason: string };
  newsSentiment: { contribution: number; reason: string };
  socialSentiment: { contribution: number; reason: string };
  totalScore: number;
}

interface Stock {
  symbol: string;
  name: string;
  investmentScore: number;
  currentPrice: number;
  priceChangePercent: number;
  scoreBreakdown?: ScoreBreakdown;
}

type SortField = 'symbol' | 'name' | 'investmentScore' | 'currentPrice' | 'priceChangePercent';
type SortDirection = 'asc' | 'desc';

export default function StocksClient() {
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortField, setSortField] = useState<SortField>('investmentScore');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [showInfoBox, setShowInfoBox] = useState(false);
  const router = useRouter();
  
  // Filters
  const [minScore, setMinScore] = useState<number | ''>('');
  const [maxScore, setMaxScore] = useState<number | ''>('');
  const [minPrice, setMinPrice] = useState<number | ''>('');
  const [maxPrice, setMaxPrice] = useState<number | ''>('');
  const [minChange, setMinChange] = useState<number | ''>('');
  const [maxChange, setMaxChange] = useState<number | ''>('');

  useEffect(() => {
    fetchStocks();
  }, []);

  const fetchStocks = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/stocks');
      if (!response.ok) throw new Error('Failed to fetch stocks');
      const data = await response.json();
      setStocks(data.stocks || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  // Filter and search stocks
  const filteredStocks = useMemo(() => {
    return stocks.filter(stock => {
      // Search filter
      const matchesSearch = 
        stock.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
        stock.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        stock.investmentScore.toString().includes(searchTerm) ||
        stock.currentPrice.toString().includes(searchTerm) ||
        stock.priceChangePercent.toString().includes(searchTerm);

      // Score filter
      const matchesScore = 
        (minScore === '' || stock.investmentScore >= minScore) &&
        (maxScore === '' || stock.investmentScore <= maxScore);

      // Price filter
      const matchesPrice = 
        (minPrice === '' || stock.currentPrice >= minPrice) &&
        (maxPrice === '' || stock.currentPrice <= maxPrice);

      // Change filter
      const matchesChange = 
        (minChange === '' || stock.priceChangePercent >= minChange) &&
        (maxChange === '' || stock.priceChangePercent <= maxChange);

      return matchesSearch && matchesScore && matchesPrice && matchesChange;
    });
  }, [stocks, searchTerm, minScore, maxScore, minPrice, maxPrice, minChange, maxChange]);

  // Sort stocks
  const sortedStocks = useMemo(() => {
    const sorted = [...filteredStocks].sort((a, b) => {
      let aVal: number | string;
      let bVal: number | string;

      switch (sortField) {
        case 'symbol':
        case 'name':
          aVal = a[sortField].toLowerCase();
          bVal = b[sortField].toLowerCase();
          break;
        default:
          aVal = a[sortField];
          bVal = b[sortField];
      }

      if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });

    return sorted;
  }, [filteredStocks, sortField, sortDirection]);

  // Paginate stocks
  const paginatedStocks = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    return sortedStocks.slice(startIndex, startIndex + itemsPerPage);
  }, [sortedStocks, currentPage, itemsPerPage]);

  const totalPages = Math.ceil(sortedStocks.length / itemsPerPage);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
    setCurrentPage(1);
  };

  const getSortIcon = (field: SortField) => {
    if (sortField !== field) return '↕️';
    return sortDirection === 'asc' ? '↑' : '↓';
  };

  const toggleRowExpansion = (symbol: string) => {
    setExpandedRows(prev => {
      const newSet = new Set(prev);
      if (newSet.has(symbol)) {
        newSet.delete(symbol);
      } else {
        newSet.add(symbol);
      }
      return newSet;
    });
  };

  const isRowExpanded = (symbol: string) => expandedRows.has(symbol);

  const handleRowKeyDown = (e: React.KeyboardEvent, symbol: string) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      toggleRowExpansion(symbol);
    }
  };

  // Export functions
  const exportToCSV = () => {
    const headers = ['Symbol', 'Name', 'Investment Score', 'Current Price', 'Price Change %'];
    const rows = sortedStocks.map(s => [
      s.symbol,
      s.name,
      s.investmentScore.toString(),
      s.currentPrice.toFixed(2),
      s.priceChangePercent.toFixed(2) + '%'
    ]);

    const csv = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `stocks_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportToJSON = () => {
    const json = JSON.stringify(sortedStocks, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `stocks_${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportToXML = () => {
    let xml = '<?xml version="1.0" encoding="UTF-8"?>\n<stocks>\n';
    sortedStocks.forEach(stock => {
      xml += '  <stock>\n';
      xml += `    <symbol>${escapeXml(stock.symbol)}</symbol>\n`;
      xml += `    <name>${escapeXml(stock.name)}</name>\n`;
      xml += `    <investmentScore>${stock.investmentScore}</investmentScore>\n`;
      xml += `    <currentPrice>${stock.currentPrice.toFixed(2)}</currentPrice>\n`;
      xml += `    <priceChangePercent>${stock.priceChangePercent.toFixed(2)}</priceChangePercent>\n`;
      xml += '  </stock>\n';
    });
    xml += '</stocks>';

    const blob = new Blob([xml], { type: 'application/xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `stocks_${new Date().toISOString().split('T')[0]}.xml`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportToHTML = () => {
    const html = `
<!DOCTYPE html>
<html>
<head>
  <title>Stocks Export</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    th { background-color: #f2f2f2; }
    tr:nth-child(even) { background-color: #f9f9f9; }
  </style>
</head>
<body>
  <h1>Stocks Export - ${new Date().toLocaleDateString()}</h1>
  <table>
    <thead>
      <tr>
        <th>Symbol</th>
        <th>Name</th>
        <th>Investment Score</th>
        <th>Current Price</th>
        <th>Price Change %</th>
      </tr>
    </thead>
    <tbody>
      ${sortedStocks.map(s => `
        <tr>
          <td>${escapeHtml(s.symbol)}</td>
          <td>${escapeHtml(s.name)}</td>
          <td>${s.investmentScore}</td>
          <td>$${s.currentPrice.toFixed(2)}</td>
          <td>${s.priceChangePercent >= 0 ? '+' : ''}${s.priceChangePercent.toFixed(2)}%</td>
        </tr>
      `).join('')}
    </tbody>
  </table>
</body>
</html>`;

    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `stocks_${new Date().toISOString().split('T')[0]}.html`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportToPDF = () => {
    const doc = new jsPDF();
    
    doc.text('Stocks Export', 14, 15);
    doc.text(`Generated: ${new Date().toLocaleDateString()}`, 14, 22);

    (doc as any).autoTable({
      head: [['Symbol', 'Name', 'Score', 'Price', 'Change %']],
      body: sortedStocks.map(s => [
        s.symbol,
        s.name,
        s.investmentScore.toString(),
        `$${s.currentPrice.toFixed(2)}`,
        `${s.priceChangePercent >= 0 ? '+' : ''}${s.priceChangePercent.toFixed(2)}%`
      ]),
      startY: 30,
      styles: { fontSize: 8 },
      headStyles: { fillColor: [66, 139, 202] },
    });

    doc.save(`stocks_${new Date().toISOString().split('T')[0]}.pdf`);
  };

  const escapeXml = (str: string) => {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&apos;');
  };

  const escapeHtml = (str: string) => {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  };

  if (loading) {
    return (
      <div className="container">
        <div className="loading">Loading stocks...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container">
        <div className="error">Error: {error}</div>
        <button onClick={fetchStocks} className="retry-btn">Retry</button>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="page-title-row">
        <h1>Stocks Dashboard</h1>
        <span className="version-tag">{PRODUCT_NAME} v{PRODUCT_VERSION}</span>
      </div>
      
      {/* Information Box */}
      <div className="info-box">
        <button 
          onClick={() => setShowInfoBox(!showInfoBox)}
          className="info-box-toggle"
        >
          <span>{showInfoBox ? '▼' : '▶'}</span>
          <span>How Investment Scores are Calculated</span>
        </button>
        {showInfoBox && (
          <div className="info-box-content">
            <h4>Investment Score Calculation Methodology</h4>
            <p>
              The investment score (0-100) is calculated based on multiple financial metrics and factors. 
              Each component contributes points to the final score:
            </p>
            
            <h5>Valuation Metrics</h5>
            <ul>
              <li><strong>P/E Ratio:</strong> Price-to-Earnings ratio - lower values indicate better value (up to +15 or -20 points)</li>
              <li><strong>P/B Ratio:</strong> Price-to-Book ratio - measures market value relative to book value (up to +10 or -10 points)</li>
              <li><strong>P/S Ratio:</strong> Price-to-Sales ratio - indicates how much investors pay per dollar of sales (up to +10 or -10 points)</li>
            </ul>

            <h5>Performance Metrics</h5>
            <ul>
              <li><strong>Price Change:</strong> Recent performance based on percentage change (up to +10 or -10 points)</li>
              <li><strong>52-Week Change:</strong> Longer-term performance relative to 52-week low (up to +8 or -8 points)</li>
              <li><strong>Volume:</strong> Trading activity relative to market cap (up to +5 or -5 points)</li>
            </ul>

            <h5>Profitability Metrics</h5>
            <ul>
              <li><strong>ROE (Return on Equity):</strong> Measures profitability relative to shareholder equity (up to +8 or -5 points)</li>
              <li><strong>ROA (Return on Assets):</strong> Measures profitability relative to total assets (up to +5 or -3 points)</li>
              <li><strong>Profit Margin:</strong> Percentage of revenue that becomes profit (up to +8 or -8 points)</li>
            </ul>

            <h5>Growth Metrics</h5>
            <ul>
              <li><strong>Revenue Growth:</strong> Year-over-year revenue growth rate (up to +8 or -8 points)</li>
              <li><strong>Earnings Growth:</strong> Year-over-year earnings growth rate (up to +8 or -10 points)</li>
            </ul>

            <h5>Financial Health Metrics</h5>
            <ul>
              <li><strong>Debt-to-Equity:</strong> Measures financial leverage - lower is generally better (up to +5 or -5 points)</li>
              <li><strong>Current Ratio:</strong> Measures short-term liquidity - ability to pay short-term obligations (up to +3 or -5 points)</li>
              <li><strong>Dividend Yield:</strong> Annual dividend payment as percentage of stock price (up to +4 points)</li>
            </ul>

            <h5>Risk Metrics</h5>
            <ul>
              <li><strong>Beta:</strong> Measures stock volatility relative to market (1 = market average) (up to +3 or -3 points)</li>
            </ul>

            <h5>Sentiment Analysis</h5>
            <div className="sentiment-explanation">
              <p>
                <strong>Note:</strong> The news and social sentiment values shown are <strong>simulated</strong> for demonstration purposes. 
                In a production environment, these would be calculated using:
              </p>
              <ul>
                <li><strong>News Sentiment:</strong> Real-time analysis of financial news articles, press releases, and earnings reports using natural language processing (NLP) and sentiment analysis APIs (NewsAPI, Alpha Vantage News, etc.)</li>
                <li><strong>Social Sentiment:</strong> Analysis of social media mentions, discussions, and trends from platforms like Twitter/X, Reddit (r/wallstreetbets, r/stocks), and financial forums using social media APIs combined with sentiment analysis services</li>
              </ul>
              <p>
                Currently, these sentiment contributions are set to <strong>0 (neutral)</strong> as placeholders and do not yet reflect live sentiment analysis or impact the investment score.
              </p>
            </div>

            <h5>Base Score</h5>
            <p>
              All stocks start with a base score of 50 points. The various metrics then add or subtract points based on their values, 
              with the final score clamped between 0 and 100.
            </p>
          </div>
        )}
      </div>
      
      {/* Search and Filters */}
      <div className="controls">
        <div className="search-box">
          <input
            type="text"
            placeholder="Search by symbol, name, score, price, or change..."
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setCurrentPage(1);
            }}
            className="search-input"
          />
        </div>

        <div className="filters">
          <div className="filter-group">
            <label htmlFor="score-min">Investment Score:</label>
            <input
              id="score-min"
              type="number"
              placeholder="Min"
              value={minScore}
              onChange={(e) => {
                setMinScore(e.target.value === '' ? '' : Number(e.target.value));
                setCurrentPage(1);
              }}
              min="0"
              max="100"
              className="filter-input"
            />
            <span>-</span>
            <input
              id="score-max"
              type="number"
              placeholder="Max"
              value={maxScore}
              onChange={(e) => {
                setMaxScore(e.target.value === '' ? '' : Number(e.target.value));
                setCurrentPage(1);
              }}
              min="0"
              max="100"
              className="filter-input"
            />
          </div>

          <div className="filter-group">
            <label htmlFor="price-min">Current Price:</label>
            <input
              id="price-min"
              type="number"
              placeholder="Min"
              value={minPrice}
              onChange={(e) => {
                setMinPrice(e.target.value === '' ? '' : Number(e.target.value));
                setCurrentPage(1);
              }}
              min="0"
              step="0.01"
              className="filter-input"
            />
            <span>-</span>
            <input
              id="price-max"
              type="number"
              placeholder="Max"
              value={maxPrice}
              onChange={(e) => {
                setMaxPrice(e.target.value === '' ? '' : Number(e.target.value));
                setCurrentPage(1);
              }}
              min="0"
              step="0.01"
              className="filter-input"
            />
          </div>

          <div className="filter-group">
            <label htmlFor="change-min">Price Change %:</label>
            <input
              id="change-min"
              type="number"
              placeholder="Min"
              value={minChange}
              onChange={(e) => {
                setMinChange(e.target.value === '' ? '' : Number(e.target.value));
                setCurrentPage(1);
              }}
              step="0.01"
              className="filter-input"
            />
            <span>-</span>
            <input
              id="change-max"
              type="number"
              placeholder="Max"
              value={maxChange}
              onChange={(e) => {
                setMaxChange(e.target.value === '' ? '' : Number(e.target.value));
                setCurrentPage(1);
              }}
              step="0.01"
              className="filter-input"
            />
          </div>
        </div>

        {/* Export buttons */}
        <div className="export-buttons">
          <button onClick={exportToCSV} className="export-btn">Export CSV</button>
          <button onClick={exportToJSON} className="export-btn">Export JSON</button>
          <button onClick={exportToXML} className="export-btn">Export XML</button>
          <button onClick={exportToHTML} className="export-btn">Export HTML</button>
          <button onClick={exportToPDF} className="export-btn">Export PDF</button>
        </div>
      </div>

      {/* Results count */}
      <div className="results-info">
        Showing {paginatedStocks.length} of {sortedStocks.length} stocks
      </div>

      {/* Table */}
      <div className="table-wrapper">
        <table className="stocks-table">
          <thead>
            <tr>
              <th onClick={() => handleSort('symbol')} className="sortable">
                Symbol {getSortIcon('symbol')}
              </th>
              <th onClick={() => handleSort('name')} className="sortable">
                Name {getSortIcon('name')}
              </th>
              <th onClick={() => handleSort('investmentScore')} className="sortable">
                Investment Score {getSortIcon('investmentScore')}
              </th>
              <th onClick={() => handleSort('currentPrice')} className="sortable">
                Current Price {getSortIcon('currentPrice')}
              </th>
              <th onClick={() => handleSort('priceChangePercent')} className="sortable">
                Price Change % {getSortIcon('priceChangePercent')}
              </th>
            </tr>
          </thead>
          <tbody>
            {paginatedStocks.map((stock) => {
              const isExpanded = isRowExpanded(stock.symbol);
              const breakdown = stock.scoreBreakdown;
              
              return (
                <React.Fragment key={stock.symbol}>
                  <tr
                    onClick={() => toggleRowExpansion(stock.symbol)}
                    onKeyDown={(e) => handleRowKeyDown(e, stock.symbol)}
                    className={`table-row-clickable ${isExpanded ? 'expanded' : ''}`}
                    role="button"
                    tabIndex={0}
                    aria-expanded={isExpanded}
                  >
                    <td className="symbol-cell">
                      <span className="expand-icon">{isExpanded ? '▼' : '▶'}</span>
                      {stock.symbol}
                    </td>
                    <td className="name-cell">{stock.name}</td>
                    <td className="score-cell">
                      <span className={`score-badge score-${Math.min(4, Math.floor(stock.investmentScore / 20))}`}>
                        {stock.investmentScore}
                      </span>
                    </td>
                    <td className="price-cell">${stock.currentPrice.toFixed(2)}</td>
                    <td className={`change-cell ${stock.priceChangePercent >= 0 ? 'positive' : 'negative'}`}>
                      {stock.priceChangePercent >= 0 ? '+' : ''}
                      {stock.priceChangePercent.toFixed(2)}%
                    </td>
                  </tr>
                  {isExpanded && breakdown && (
                    <tr key={`${stock.symbol}-details`} className="expanded-row">
                      <td colSpan={5} className="breakdown-cell">
                        <div className="score-breakdown">
                          <div className="breakdown-header">
                            <h3>Investment Score Breakdown</h3>
                            <button
                              className="details-btn"
                              onClick={(e) => {
                                e.stopPropagation();
                                router.push(`/stocks/${encodeURIComponent(stock.symbol)}`);
                              }}
                            >
                              Details
                            </button>
                          </div>
                          <div className="breakdown-grid">
                            <div className="breakdown-item">
                              <div className="breakdown-label">Base Score</div>
                              <div className="breakdown-value neutral">
                                {breakdown.baseScore}
                              </div>
                              <div className="breakdown-reason">Starting point</div>
                            </div>
                            
                            <div className="breakdown-item">
                              <div className="breakdown-label">
                                P/E Ratio
                                {breakdown.peRatio.value !== undefined && ` (${breakdown.peRatio.value.toFixed(2)})`}
                              </div>
                              <div className={`breakdown-value ${breakdown.peRatio.contribution >= 0 ? 'positive' : breakdown.peRatio.contribution < 0 ? 'negative' : 'neutral'}`}>
                                {breakdown.peRatio.contribution > 0 ? '+' : ''}{breakdown.peRatio.contribution}
                              </div>
                              <div className="breakdown-reason">{breakdown.peRatio.reason}</div>
                            </div>
                            
                            <div className="breakdown-item">
                              <div className="breakdown-label">
                                P/B Ratio
                                {breakdown.pbRatio.value !== undefined && ` (${breakdown.pbRatio.value.toFixed(2)})`}
                              </div>
                              <div className={`breakdown-value ${breakdown.pbRatio.contribution >= 0 ? 'positive' : breakdown.pbRatio.contribution < 0 ? 'negative' : 'neutral'}`}>
                                {breakdown.pbRatio.contribution > 0 ? '+' : ''}{breakdown.pbRatio.contribution}
                              </div>
                              <div className="breakdown-reason">{breakdown.pbRatio.reason}</div>
                            </div>
                            
                            <div className="breakdown-item">
                              <div className="breakdown-label">
                                P/S Ratio
                                {breakdown.psRatio.value !== undefined && ` (${breakdown.psRatio.value.toFixed(2)})`}
                              </div>
                              <div className={`breakdown-value ${breakdown.psRatio.contribution >= 0 ? 'positive' : breakdown.psRatio.contribution < 0 ? 'negative' : 'neutral'}`}>
                                {breakdown.psRatio.contribution > 0 ? '+' : ''}{breakdown.psRatio.contribution}
                              </div>
                              <div className="breakdown-reason">{breakdown.psRatio.reason}</div>
                            </div>
                            
                            <div className="breakdown-item">
                              <div className="breakdown-label">
                                Price Change ({breakdown.priceChange.value.toFixed(2)}%)
                              </div>
                              <div className={`breakdown-value ${breakdown.priceChange.contribution >= 0 ? 'positive' : 'negative'}`}>
                                {breakdown.priceChange.contribution > 0 ? '+' : ''}{breakdown.priceChange.contribution}
                              </div>
                              <div className="breakdown-reason">{breakdown.priceChange.reason}</div>
                            </div>
                            
                            {breakdown.volume.value !== undefined && (
                              <div className="breakdown-item">
                                <div className="breakdown-label">
                                  Volume Ratio ({(breakdown.volume.value * 100).toFixed(2)}%)
                                </div>
                                <div className={`breakdown-value ${breakdown.volume.contribution >= 0 ? 'positive' : 'negative'}`}>
                                  {breakdown.volume.contribution > 0 ? '+' : ''}{breakdown.volume.contribution}
                                </div>
                                <div className="breakdown-reason">{breakdown.volume.reason}</div>
                              </div>
                            )}
                            
                            {breakdown.roe.value !== undefined && (
                              <div className="breakdown-item">
                                <div className="breakdown-label">
                                  ROE ({breakdown.roe.value.toFixed(2)}%)
                                </div>
                                <div className={`breakdown-value ${breakdown.roe.contribution >= 0 ? 'positive' : 'negative'}`}>
                                  {breakdown.roe.contribution > 0 ? '+' : ''}{breakdown.roe.contribution}
                                </div>
                                <div className="breakdown-reason">{breakdown.roe.reason}</div>
                              </div>
                            )}
                            
                            {breakdown.roa.value !== undefined && (
                              <div className="breakdown-item">
                                <div className="breakdown-label">
                                  ROA ({breakdown.roa.value.toFixed(2)}%)
                                </div>
                                <div className={`breakdown-value ${breakdown.roa.contribution >= 0 ? 'positive' : 'negative'}`}>
                                  {breakdown.roa.contribution > 0 ? '+' : ''}{breakdown.roa.contribution}
                                </div>
                                <div className="breakdown-reason">{breakdown.roa.reason}</div>
                              </div>
                            )}
                            
                            {breakdown.debtToEquity.value !== undefined && (
                              <div className="breakdown-item">
                                <div className="breakdown-label">
                                  Debt/Equity ({breakdown.debtToEquity.value.toFixed(2)})
                                </div>
                                <div className={`breakdown-value ${breakdown.debtToEquity.contribution >= 0 ? 'positive' : 'negative'}`}>
                                  {breakdown.debtToEquity.contribution > 0 ? '+' : ''}{breakdown.debtToEquity.contribution}
                                </div>
                                <div className="breakdown-reason">{breakdown.debtToEquity.reason}</div>
                              </div>
                            )}
                            
                            {breakdown.currentRatio.value !== undefined && (
                              <div className="breakdown-item">
                                <div className="breakdown-label">
                                  Current Ratio ({breakdown.currentRatio.value.toFixed(2)})
                                </div>
                                <div className={`breakdown-value ${breakdown.currentRatio.contribution >= 0 ? 'positive' : 'negative'}`}>
                                  {breakdown.currentRatio.contribution > 0 ? '+' : ''}{breakdown.currentRatio.contribution}
                                </div>
                                <div className="breakdown-reason">{breakdown.currentRatio.reason}</div>
                              </div>
                            )}
                            
                            {breakdown.dividendYield.value !== undefined && (
                              <div className="breakdown-item">
                                <div className="breakdown-label">
                                  Dividend Yield ({breakdown.dividendYield.value.toFixed(2)}%)
                                </div>
                                <div className={`breakdown-value ${breakdown.dividendYield.contribution >= 0 ? 'positive' : 'neutral'}`}>
                                  {breakdown.dividendYield.contribution > 0 ? '+' : ''}{breakdown.dividendYield.contribution}
                                </div>
                                <div className="breakdown-reason">{breakdown.dividendYield.reason}</div>
                              </div>
                            )}
                            
                            {breakdown.profitMargin.value !== undefined && (
                              <div className="breakdown-item">
                                <div className="breakdown-label">
                                  Profit Margin ({breakdown.profitMargin.value.toFixed(2)}%)
                                </div>
                                <div className={`breakdown-value ${breakdown.profitMargin.contribution >= 0 ? 'positive' : 'negative'}`}>
                                  {breakdown.profitMargin.contribution > 0 ? '+' : ''}{breakdown.profitMargin.contribution}
                                </div>
                                <div className="breakdown-reason">{breakdown.profitMargin.reason}</div>
                              </div>
                            )}
                            
                            {breakdown.revenueGrowth.value !== undefined && (
                              <div className="breakdown-item">
                                <div className="breakdown-label">
                                  Revenue Growth ({breakdown.revenueGrowth.value.toFixed(2)}%)
                                </div>
                                <div className={`breakdown-value ${breakdown.revenueGrowth.contribution >= 0 ? 'positive' : 'negative'}`}>
                                  {breakdown.revenueGrowth.contribution > 0 ? '+' : ''}{breakdown.revenueGrowth.contribution}
                                </div>
                                <div className="breakdown-reason">{breakdown.revenueGrowth.reason}</div>
                              </div>
                            )}
                            
                            {breakdown.earningsGrowth.value !== undefined && (
                              <div className="breakdown-item">
                                <div className="breakdown-label">
                                  Earnings Growth ({breakdown.earningsGrowth.value.toFixed(2)}%)
                                </div>
                                <div className={`breakdown-value ${breakdown.earningsGrowth.contribution >= 0 ? 'positive' : 'negative'}`}>
                                  {breakdown.earningsGrowth.contribution > 0 ? '+' : ''}{breakdown.earningsGrowth.contribution}
                                </div>
                                <div className="breakdown-reason">{breakdown.earningsGrowth.reason}</div>
                              </div>
                            )}
                            
                            {breakdown.beta.value !== undefined && (
                              <div className="breakdown-item">
                                <div className="breakdown-label">
                                  Beta ({breakdown.beta.value.toFixed(2)})
                                </div>
                                <div className={`breakdown-value ${breakdown.beta.contribution >= 0 ? 'positive' : 'negative'}`}>
                                  {breakdown.beta.contribution > 0 ? '+' : ''}{breakdown.beta.contribution}
                                </div>
                                <div className="breakdown-reason">{breakdown.beta.reason}</div>
                              </div>
                            )}
                            
                            {breakdown.fiftyTwoWeekChange.value !== undefined && (
                              <div className="breakdown-item">
                                <div className="breakdown-label">
                                  52-Week Change ({breakdown.fiftyTwoWeekChange.value.toFixed(2)}%)
                                </div>
                                <div className={`breakdown-value ${breakdown.fiftyTwoWeekChange.contribution >= 0 ? 'positive' : 'negative'}`}>
                                  {breakdown.fiftyTwoWeekChange.contribution > 0 ? '+' : ''}{breakdown.fiftyTwoWeekChange.contribution}
                                </div>
                                <div className="breakdown-reason">{breakdown.fiftyTwoWeekChange.reason}</div>
                              </div>
                            )}
                            
                            <div className="breakdown-item">
                              <div className="breakdown-label">News Sentiment</div>
                              <div className={`breakdown-value ${breakdown.newsSentiment.contribution >= 0 ? 'positive' : 'negative'}`}>
                                {breakdown.newsSentiment.contribution > 0 ? '+' : ''}{breakdown.newsSentiment.contribution.toFixed(1)}
                              </div>
                              <div className="breakdown-reason">{breakdown.newsSentiment.reason}</div>
                            </div>
                            
                            <div className="breakdown-item">
                              <div className="breakdown-label">Social Sentiment</div>
                              <div className={`breakdown-value ${breakdown.socialSentiment.contribution >= 0 ? 'positive' : 'negative'}`}>
                                {breakdown.socialSentiment.contribution > 0 ? '+' : ''}{breakdown.socialSentiment.contribution.toFixed(1)}
                              </div>
                              <div className="breakdown-reason">{breakdown.socialSentiment.reason}</div>
                            </div>
                            
                            <div className="breakdown-item total">
                              <div className="breakdown-label">Total Score</div>
                              <div className="breakdown-value total-score">
                                {breakdown.totalScore}
                              </div>
                              <div className="breakdown-reason">Final investment score</div>
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="pagination">
        <div className="pagination-controls">
          <button
            onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
            disabled={currentPage === 1}
            className="page-btn"
          >
            Previous
          </button>
          <span className="page-info">
            Page {currentPage} of {totalPages || 1}
          </span>
          <button
            onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
            disabled={currentPage >= totalPages}
            className="page-btn"
          >
            Next
          </button>
        </div>
        <div className="items-per-page">
          <label>Items per page:</label>
          <select
            value={itemsPerPage}
            onChange={(e) => {
              setItemsPerPage(Number(e.target.value));
              setCurrentPage(1);
            }}
            className="items-select"
          >
            <option value={5}>5</option>
            <option value={10}>10</option>
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
        </div>
      </div>
    </div>
  );
}
