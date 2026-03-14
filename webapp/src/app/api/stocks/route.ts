export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

import { NextResponse } from 'next/server';

const FUNDAMENTALS_URL = 'https://raw.githubusercontent.com/IonSon121977/Portfolio-Manager/main/docs/data/fundamentals.json';
const SNAPSHOT_URL     = 'https://raw.githubusercontent.com/IonSon121977/Portfolio-Manager/main/docs/data/snapshot.json';

interface StockData {
  symbol: string;
  name: string;
  currentPrice: number;
  priceChangePercent: number;
  peRatio?: number;
  pbRatio?: number;
  psRatio?: number;
  volume?: number;
  marketCap?: number;
  roe?: number;
  roa?: number;
  debtToEquity?: number;
  currentRatio?: number;
  dividendYield?: number;
  profitMargin?: number;
  revenueGrowth?: number;
  earningsGrowth?: number;
  beta?: number;
  fiftyTwoWeekChange?: number;
}

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

interface StockWithScore extends StockData {
  investmentScore: number;
  scoreBreakdown: ScoreBreakdown;
  shares?: number;
  valueEur?: number;
  lastUpdated?: string;
}

function calculateInvestmentScore(stock: StockData): { score: number; breakdown: ScoreBreakdown } {
  let score = 50;
  const breakdown: ScoreBreakdown = {
    baseScore: 50,
    peRatio:       { contribution: 0, reason: 'Not available' },
    pbRatio:       { contribution: 0, reason: 'Not available' },
    psRatio:       { contribution: 0, reason: 'Not available' },
    priceChange:   { value: stock.priceChangePercent, contribution: 0, reason: 'No significant change' },
    volume:        { contribution: 0, reason: 'Not available' },
    roe:           { contribution: 0, reason: 'Not available' },
    roa:           { contribution: 0, reason: 'Not available' },
    debtToEquity:  { contribution: 0, reason: 'Not available' },
    currentRatio:  { contribution: 0, reason: 'Not available' },
    dividendYield: { contribution: 0, reason: 'Not available' },
    profitMargin:  { contribution: 0, reason: 'Not available' },
    revenueGrowth: { contribution: 0, reason: 'Not available' },
    earningsGrowth:{ contribution: 0, reason: 'Not available' },
    beta:          { contribution: 0, reason: 'Not available' },
    fiftyTwoWeekChange: { contribution: 0, reason: 'Not available' },
    newsSentiment: { contribution: 0, reason: 'Neutral' },
    socialSentiment:{ contribution: 0, reason: 'Neutral' },
    totalScore: 50,
  };

  if (stock.peRatio !== undefined && stock.peRatio > 0) {
    breakdown.peRatio.value = stock.peRatio;
    if (stock.peRatio < 10)      { breakdown.peRatio.contribution = 15;  breakdown.peRatio.reason = 'Excellent (P/E < 10)';   score += 15; }
    else if (stock.peRatio < 15) { breakdown.peRatio.contribution = 10;  breakdown.peRatio.reason = 'Good (P/E < 15)';        score += 10; }
    else if (stock.peRatio < 20) { breakdown.peRatio.contribution = 5;   breakdown.peRatio.reason = 'Fair (P/E < 20)';        score += 5;  }
    else if (stock.peRatio > 50) { breakdown.peRatio.contribution = -20; breakdown.peRatio.reason = 'Poor (P/E > 50)';        score -= 20; }
    else if (stock.peRatio > 30) { breakdown.peRatio.contribution = -10; breakdown.peRatio.reason = 'High (P/E > 30)';        score -= 10; }
    else                         { breakdown.peRatio.reason = 'Moderate (P/E 20-30)'; }
  }

  if (stock.pbRatio !== undefined) {
    breakdown.pbRatio.value = stock.pbRatio;
    if (stock.pbRatio < 1)      { breakdown.pbRatio.contribution = 10;  breakdown.pbRatio.reason = 'Excellent (P/B < 1)';   score += 10; }
    else if (stock.pbRatio < 1.5){ breakdown.pbRatio.contribution = 5;   breakdown.pbRatio.reason = 'Good (P/B < 1.5)';      score += 5;  }
    else if (stock.pbRatio > 5) { breakdown.pbRatio.contribution = -10; breakdown.pbRatio.reason = 'Poor (P/B > 5)';        score -= 10; }
    else if (stock.pbRatio > 3) { breakdown.pbRatio.contribution = -5;  breakdown.pbRatio.reason = 'High (P/B > 3)';        score -= 5;  }
    else                        { breakdown.pbRatio.reason = 'Moderate (P/B 1.5-3)'; }
  }

  if (stock.psRatio !== undefined) {
    breakdown.psRatio.value = stock.psRatio;
    if (stock.psRatio < 1)      { breakdown.psRatio.contribution = 10;  breakdown.psRatio.reason = 'Excellent (P/S < 1)';   score += 10; }
    else if (stock.psRatio < 2) { breakdown.psRatio.contribution = 5;   breakdown.psRatio.reason = 'Good (P/S < 2)';        score += 5;  }
    else if (stock.psRatio > 10){ breakdown.psRatio.contribution = -10; breakdown.psRatio.reason = 'Poor (P/S > 10)';       score -= 10; }
    else if (stock.psRatio > 5) { breakdown.psRatio.contribution = -5;  breakdown.psRatio.reason = 'High (P/S > 5)';        score -= 5;  }
    else                        { breakdown.psRatio.reason = 'Moderate (P/S 2-5)'; }
  }

  if (stock.priceChangePercent > 10)       { breakdown.priceChange.contribution = 10;  breakdown.priceChange.reason = 'Strong growth (>10%)';           score += 10; }
  else if (stock.priceChangePercent > 5)   { breakdown.priceChange.contribution = 5;   breakdown.priceChange.reason = 'Positive growth (5-10%)';         score += 5;  }
  else if (stock.priceChangePercent < -10) { breakdown.priceChange.contribution = -10; breakdown.priceChange.reason = 'Significant decline (<-10%)';     score -= 10; }
  else if (stock.priceChangePercent < -5)  { breakdown.priceChange.contribution = -5;  breakdown.priceChange.reason = 'Negative trend (-5% to -10%)';    score -= 5;  }
  else                                     { breakdown.priceChange.reason = 'Stable (-5% to 5%)'; }

  if (stock.roe !== undefined) {
    breakdown.roe.value = stock.roe;
    if (stock.roe > 20)      { breakdown.roe.contribution = 8;  breakdown.roe.reason = 'Excellent ROE (>20%)';  score += 8; }
    else if (stock.roe > 15) { breakdown.roe.contribution = 5;  breakdown.roe.reason = 'Good ROE (15-20%)';     score += 5; }
    else if (stock.roe > 10) { breakdown.roe.contribution = 2;  breakdown.roe.reason = 'Fair ROE (10-15%)';     score += 2; }
    else if (stock.roe < 0)  { breakdown.roe.contribution = -5; breakdown.roe.reason = 'Negative ROE';          score -= 5; }
    else                     { breakdown.roe.reason = 'Low ROE (<10%)'; }
  }

  if (stock.roa !== undefined) {
    breakdown.roa.value = stock.roa;
    if (stock.roa > 10)      { breakdown.roa.contribution = 5;  breakdown.roa.reason = 'Excellent ROA (>10%)';  score += 5; }
    else if (stock.roa > 5)  { breakdown.roa.contribution = 3;  breakdown.roa.reason = 'Good ROA (5-10%)';      score += 3; }
    else if (stock.roa < 0)  { breakdown.roa.contribution = -3; breakdown.roa.reason = 'Negative ROA';          score -= 3; }
    else                     { breakdown.roa.reason = 'Low ROA (<5%)'; }
  }

  if (stock.debtToEquity !== undefined) {
    breakdown.debtToEquity.value = stock.debtToEquity;
    if (stock.debtToEquity < 0.5)      { breakdown.debtToEquity.contribution = 5;  breakdown.debtToEquity.reason = 'Low debt (<0.5)';       score += 5; }
    else if (stock.debtToEquity < 1)   { breakdown.debtToEquity.contribution = 3;  breakdown.debtToEquity.reason = 'Moderate debt (0.5-1)'; score += 3; }
    else if (stock.debtToEquity > 2)   { breakdown.debtToEquity.contribution = -5; breakdown.debtToEquity.reason = 'High debt (>2)';         score -= 5; }
    else                               { breakdown.debtToEquity.reason = 'Elevated debt (1-2)'; }
  }

  if (stock.currentRatio !== undefined) {
    breakdown.currentRatio.value = stock.currentRatio;
    if (stock.currentRatio > 2)        { breakdown.currentRatio.contribution = 3;  breakdown.currentRatio.reason = 'Strong liquidity (>2)';      score += 3; }
    else if (stock.currentRatio > 1.5) { breakdown.currentRatio.contribution = 2;  breakdown.currentRatio.reason = 'Good liquidity (1.5-2)';     score += 2; }
    else if (stock.currentRatio < 1)   { breakdown.currentRatio.contribution = -5; breakdown.currentRatio.reason = 'Poor liquidity (<1)';        score -= 5; }
    else                               { breakdown.currentRatio.reason = 'Adequate liquidity (1-1.5)'; }
  }

  if (stock.dividendYield !== undefined && stock.dividendYield > 0) {
    breakdown.dividendYield.value = stock.dividendYield;
    if (stock.dividendYield > 4)      { breakdown.dividendYield.contribution = 4; breakdown.dividendYield.reason = 'High dividend yield (>4%)';  score += 4; }
    else if (stock.dividendYield > 2) { breakdown.dividendYield.contribution = 2; breakdown.dividendYield.reason = 'Good dividend yield (2-4%)'; score += 2; }
    else                              { breakdown.dividendYield.reason = 'Low dividend yield (<2%)'; }
  }

  if (stock.profitMargin !== undefined) {
    breakdown.profitMargin.value = stock.profitMargin;
    if (stock.profitMargin > 20)      { breakdown.profitMargin.contribution = 8;  breakdown.profitMargin.reason = 'Excellent margin (>20%)'; score += 8; }
    else if (stock.profitMargin > 10) { breakdown.profitMargin.contribution = 5;  breakdown.profitMargin.reason = 'Good margin (10-20%)';    score += 5; }
    else if (stock.profitMargin > 5)  { breakdown.profitMargin.contribution = 2;  breakdown.profitMargin.reason = 'Fair margin (5-10%)';     score += 2; }
    else if (stock.profitMargin < 0)  { breakdown.profitMargin.contribution = -8; breakdown.profitMargin.reason = 'Negative margin';         score -= 8; }
    else                              { breakdown.profitMargin.reason = 'Low margin (<5%)'; }
  }

  if (stock.revenueGrowth !== undefined) {
    breakdown.revenueGrowth.value = stock.revenueGrowth;
    if (stock.revenueGrowth > 20)       { breakdown.revenueGrowth.contribution = 8;  breakdown.revenueGrowth.reason = 'Strong growth (>20%)';      score += 8; }
    else if (stock.revenueGrowth > 10)  { breakdown.revenueGrowth.contribution = 5;  breakdown.revenueGrowth.reason = 'Good growth (10-20%)';      score += 5; }
    else if (stock.revenueGrowth > 5)   { breakdown.revenueGrowth.contribution = 2;  breakdown.revenueGrowth.reason = 'Moderate growth (5-10%)';   score += 2; }
    else if (stock.revenueGrowth < -10) { breakdown.revenueGrowth.contribution = -8; breakdown.revenueGrowth.reason = 'Declining revenue (<-10%)'; score -= 8; }
    else if (stock.revenueGrowth < 0)   { breakdown.revenueGrowth.contribution = -3; breakdown.revenueGrowth.reason = 'Negative growth';           score -= 3; }
    else                                { breakdown.revenueGrowth.reason = 'Slow growth (<5%)'; }
  }

  if (stock.earningsGrowth !== undefined) {
    breakdown.earningsGrowth.value = stock.earningsGrowth;
    if (stock.earningsGrowth > 25)       { breakdown.earningsGrowth.contribution = 8;  breakdown.earningsGrowth.reason = 'Strong earnings growth (>25%)';    score += 8;  }
    else if (stock.earningsGrowth > 15)  { breakdown.earningsGrowth.contribution = 5;  breakdown.earningsGrowth.reason = 'Good earnings growth (15-25%)';    score += 5;  }
    else if (stock.earningsGrowth > 5)   { breakdown.earningsGrowth.contribution = 2;  breakdown.earningsGrowth.reason = 'Moderate earnings growth (5-15%)'; score += 2;  }
    else if (stock.earningsGrowth < -20) { breakdown.earningsGrowth.contribution = -10; breakdown.earningsGrowth.reason = 'Declining earnings (<-20%)';      score -= 10; }
    else if (stock.earningsGrowth < 0)   { breakdown.earningsGrowth.contribution = -5; breakdown.earningsGrowth.reason = 'Negative earnings growth';         score -= 5;  }
    else                                 { breakdown.earningsGrowth.reason = 'Slow earnings growth (<5%)'; }
  }

  if (stock.beta !== undefined) {
    breakdown.beta.value = stock.beta;
    if (stock.beta >= 0.8 && stock.beta <= 1.2) { breakdown.beta.contribution = 3;  breakdown.beta.reason = 'Stable volatility (0.8-1.2)'; score += 3; }
    else if (stock.beta > 1.5)                  { breakdown.beta.contribution = -3; breakdown.beta.reason = 'High volatility (>1.5)';       score -= 3; }
    else if (stock.beta < 0.5)                  { breakdown.beta.contribution = 2;  breakdown.beta.reason = 'Low volatility (<0.5)';        score += 2; }
    else                                        { breakdown.beta.reason = 'Moderate volatility'; }
  }

  if (stock.fiftyTwoWeekChange !== undefined) {
    breakdown.fiftyTwoWeekChange.value = stock.fiftyTwoWeekChange;
    if (stock.fiftyTwoWeekChange > 50)       { breakdown.fiftyTwoWeekChange.contribution = 8;  breakdown.fiftyTwoWeekChange.reason = 'Strong 52-week performance (>50%)';           score += 8; }
    else if (stock.fiftyTwoWeekChange > 20)  { breakdown.fiftyTwoWeekChange.contribution = 5;  breakdown.fiftyTwoWeekChange.reason = 'Good 52-week performance (20-50%)';           score += 5; }
    else if (stock.fiftyTwoWeekChange < -30) { breakdown.fiftyTwoWeekChange.contribution = -8; breakdown.fiftyTwoWeekChange.reason = 'Poor 52-week performance (<-30%)';            score -= 8; }
    else if (stock.fiftyTwoWeekChange < -10) { breakdown.fiftyTwoWeekChange.contribution = -3; breakdown.fiftyTwoWeekChange.reason = 'Negative 52-week performance (-10% to -30%)'; score -= 3; }
    else                                     { breakdown.fiftyTwoWeekChange.reason = 'Moderate 52-week performance'; }
  }

  breakdown.newsSentiment.contribution  = 0;
  breakdown.newsSentiment.reason        = 'Neutral';
  breakdown.socialSentiment.contribution= 0;
  breakdown.socialSentiment.reason      = 'Neutral';

  const finalScore = Math.max(0, Math.min(100, Math.round(score)));
  breakdown.totalScore = finalScore;
  return { score: finalScore, breakdown };
}

export async function GET() {
  try {
    // Try fundamentals.json first (richer data), fall back to snapshot.json
    let holdings: any[] = [];
    let updatedAt = '';

    try {
      const res = await fetch(FUNDAMENTALS_URL, { cache: 'no-store' });
      if (res.ok) {
        const data = await res.json();
        holdings  = data.holdings || [];
        updatedAt = data.updated  || '';
        console.log(`Loaded ${holdings.length} holdings from fundamentals.json (${updatedAt})`);
      }
    } catch (e) {
      console.warn('fundamentals.json not available, falling back to snapshot.json');
    }

    // Fallback to snapshot.json if fundamentals not available yet
    if (!holdings.length) {
      const res = await fetch(SNAPSHOT_URL, { cache: 'no-store' });
      if (!res.ok) throw new Error('Both fundamentals.json and snapshot.json unavailable');
      const data = await res.json();
      holdings  = [...(data.stocks || []), ...(data.etfs || [])];
      updatedAt = data.timestamp || '';
      console.log(`Loaded ${holdings.length} holdings from snapshot.json (fallback)`);
    }

    const stocksWithScores: StockWithScore[] = holdings
      .filter((h: any) => !h.error && !h.skip && h.price_eur)
      .map((h: any) => {
        // yfinance returns ratios as decimals — convert to percentages for scoring
        const dYield = h.dividend_yield != null ? h.dividend_yield * 100 : undefined;
        const margin  = h.profit_margin  != null ? h.profit_margin  * 100 : undefined;
        const roe     = h.roe            != null ? h.roe            * 100 : undefined;
        const roa     = h.roa            != null ? h.roa            * 100 : undefined;
        const revGrow = h.revenue_growth != null ? h.revenue_growth * 100 : undefined;
        const epsGrow = h.earnings_growth!= null ? h.earnings_growth* 100 : undefined;

        // 52w change: % from 52w high
        let fiftyTwoWeekChange: number | undefined;
        if (h['52w_high'] && h.price_eur && h['52w_high'] > 0) {
          fiftyTwoWeekChange = ((h.price_eur - h['52w_high']) / h['52w_high']) * 100;
        }

        const stock: StockData = {
          symbol:             h.ticker,
          name:               h.name || h.ticker,
          currentPrice:       h.price_eur    || 0,
          priceChangePercent: h.change_pct   || 0,
          peRatio:            h.pe_ratio     || undefined,
          pbRatio:            h.pb_ratio     || undefined,
          psRatio:            h.ps_ratio     || undefined,
          beta:               h.beta         || undefined,
          marketCap:          h.market_cap   || undefined,
          dividendYield:      dYield,
          profitMargin:       margin,
          roe,
          roa,
          debtToEquity:       h.debt_to_equity || undefined,
          currentRatio:       h.current_ratio  || undefined,
          revenueGrowth:      revGrow,
          earningsGrowth:     epsGrow,
          fiftyTwoWeekChange,
        };

        const { score, breakdown } = calculateInvestmentScore(stock);
        return {
          ...stock,
          investmentScore: score,
          scoreBreakdown:  breakdown,
          shares:          h.shares   || 0,
          valueEur:        h.value_eur|| 0,
          lastUpdated:     updatedAt,
        };
      })
      .sort((a: StockWithScore, b: StockWithScore) => b.investmentScore - a.investmentScore);

    return NextResponse.json({
      stocks:     stocksWithScores,
      updatedAt,
      count:      stocksWithScores.length,
    });

  } catch (error) {
    console.error('Error loading data:', error);
    return NextResponse.json({ stocks: [], error: String(error) }, { status: 500 });
  }
}
