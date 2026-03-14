import { NextRequest, NextResponse } from 'next/server';
import YahooFinance from 'yahoo-finance2';

export const revalidate = 3600; // Cache route response for 1 hour

const yahooFinance = new YahooFinance();

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
}

function calculateInvestmentScore(stock: StockData): { score: number; breakdown: ScoreBreakdown } {
  let score = 50;
  const breakdown: ScoreBreakdown = {
    baseScore: 50,
    peRatio: { contribution: 0, reason: 'Not available' },
    pbRatio: { contribution: 0, reason: 'Not available' },
    psRatio: { contribution: 0, reason: 'Not available' },
    priceChange: { value: stock.priceChangePercent, contribution: 0, reason: 'No significant change' },
    volume: { contribution: 0, reason: 'Not available' },
    roe: { contribution: 0, reason: 'Not available' },
    roa: { contribution: 0, reason: 'Not available' },
    debtToEquity: { contribution: 0, reason: 'Not available' },
    currentRatio: { contribution: 0, reason: 'Not available' },
    dividendYield: { contribution: 0, reason: 'Not available' },
    profitMargin: { contribution: 0, reason: 'Not available' },
    revenueGrowth: { contribution: 0, reason: 'Not available' },
    earningsGrowth: { contribution: 0, reason: 'Not available' },
    beta: { contribution: 0, reason: 'Not available' },
    fiftyTwoWeekChange: { contribution: 0, reason: 'Not available' },
    newsSentiment: { contribution: 0, reason: 'Neutral' },
    socialSentiment: { contribution: 0, reason: 'Neutral' },
    totalScore: 50,
  };

  if (stock.peRatio !== undefined && stock.peRatio > 0) {
    breakdown.peRatio.value = stock.peRatio;
    if (stock.peRatio < 10) { breakdown.peRatio.contribution = 15; breakdown.peRatio.reason = 'Excellent (P/E < 10)'; score += 15; }
    else if (stock.peRatio < 15) { breakdown.peRatio.contribution = 10; breakdown.peRatio.reason = 'Good (P/E < 15)'; score += 10; }
    else if (stock.peRatio < 20) { breakdown.peRatio.contribution = 5; breakdown.peRatio.reason = 'Fair (P/E < 20)'; score += 5; }
    else if (stock.peRatio > 50) { breakdown.peRatio.contribution = -20; breakdown.peRatio.reason = 'Poor (P/E > 50)'; score -= 20; }
    else if (stock.peRatio > 30) { breakdown.peRatio.contribution = -10; breakdown.peRatio.reason = 'High (P/E > 30)'; score -= 10; }
    else { breakdown.peRatio.reason = 'Moderate (P/E 20-30)'; }
  } else {
    breakdown.peRatio.reason = 'Not available (company may have negative earnings or data unavailable)';
  }

  if (stock.pbRatio !== undefined) {
    breakdown.pbRatio.value = stock.pbRatio;
    if (stock.pbRatio < 1) { breakdown.pbRatio.contribution = 10; breakdown.pbRatio.reason = 'Excellent (P/B < 1)'; score += 10; }
    else if (stock.pbRatio < 1.5) { breakdown.pbRatio.contribution = 5; breakdown.pbRatio.reason = 'Good (P/B < 1.5)'; score += 5; }
    else if (stock.pbRatio > 5) { breakdown.pbRatio.contribution = -10; breakdown.pbRatio.reason = 'Poor (P/B > 5)'; score -= 10; }
    else if (stock.pbRatio > 3) { breakdown.pbRatio.contribution = -5; breakdown.pbRatio.reason = 'High (P/B > 3)'; score -= 5; }
    else { breakdown.pbRatio.reason = 'Moderate (P/B 1.5-3)'; }
  }

  if (stock.psRatio !== undefined) {
    breakdown.psRatio.value = stock.psRatio;
    if (stock.psRatio < 1) { breakdown.psRatio.contribution = 10; breakdown.psRatio.reason = 'Excellent (P/S < 1)'; score += 10; }
    else if (stock.psRatio < 2) { breakdown.psRatio.contribution = 5; breakdown.psRatio.reason = 'Good (P/S < 2)'; score += 5; }
    else if (stock.psRatio > 10) { breakdown.psRatio.contribution = -10; breakdown.psRatio.reason = 'Poor (P/S > 10)'; score -= 10; }
    else if (stock.psRatio > 5) { breakdown.psRatio.contribution = -5; breakdown.psRatio.reason = 'High (P/S > 5)'; score -= 5; }
    else { breakdown.psRatio.reason = 'Moderate (P/S 2-5)'; }
  }

  if (stock.priceChangePercent > 10) { breakdown.priceChange.contribution = 10; breakdown.priceChange.reason = 'Strong growth (>10%)'; score += 10; }
  else if (stock.priceChangePercent > 5) { breakdown.priceChange.contribution = 5; breakdown.priceChange.reason = 'Positive growth (5-10%)'; score += 5; }
  else if (stock.priceChangePercent < -10) { breakdown.priceChange.contribution = -10; breakdown.priceChange.reason = 'Significant decline (<-10%)'; score -= 10; }
  else if (stock.priceChangePercent < -5) { breakdown.priceChange.contribution = -5; breakdown.priceChange.reason = 'Negative trend (-5% to -10%)'; score -= 5; }
  else { breakdown.priceChange.reason = 'Stable (-5% to 5%)'; }

  if (stock.volume && stock.marketCap) {
    const volumeRatio = stock.volume / stock.marketCap;
    breakdown.volume.value = volumeRatio;
    if (volumeRatio > 0.1) { breakdown.volume.contribution = 5; breakdown.volume.reason = 'High trading activity (>10% of market cap)'; score += 5; }
    else if (volumeRatio < 0.01) { breakdown.volume.contribution = -5; breakdown.volume.reason = 'Low trading activity (<1% of market cap)'; score -= 5; }
    else { breakdown.volume.reason = 'Normal trading activity (1-10% of market cap)'; }
  }

  if (stock.roe !== undefined) {
    breakdown.roe.value = stock.roe;
    if (stock.roe > 20) { breakdown.roe.contribution = 8; breakdown.roe.reason = 'Excellent ROE (>20%)'; score += 8; }
    else if (stock.roe > 15) { breakdown.roe.contribution = 5; breakdown.roe.reason = 'Good ROE (15-20%)'; score += 5; }
    else if (stock.roe > 10) { breakdown.roe.contribution = 2; breakdown.roe.reason = 'Fair ROE (10-15%)'; score += 2; }
    else if (stock.roe < 0) { breakdown.roe.contribution = -5; breakdown.roe.reason = 'Negative ROE'; score -= 5; }
    else { breakdown.roe.reason = 'Low ROE (<10%)'; }
  }

  if (stock.roa !== undefined) {
    breakdown.roa.value = stock.roa;
    if (stock.roa > 10) { breakdown.roa.contribution = 5; breakdown.roa.reason = 'Excellent ROA (>10%)'; score += 5; }
    else if (stock.roa > 5) { breakdown.roa.contribution = 3; breakdown.roa.reason = 'Good ROA (5-10%)'; score += 3; }
    else if (stock.roa < 0) { breakdown.roa.contribution = -3; breakdown.roa.reason = 'Negative ROA'; score -= 3; }
    else { breakdown.roa.reason = 'Low ROA (<5%)'; }
  }

  if (stock.debtToEquity !== undefined) {
    breakdown.debtToEquity.value = stock.debtToEquity;
    if (stock.debtToEquity < 0.5) { breakdown.debtToEquity.contribution = 5; breakdown.debtToEquity.reason = 'Low debt (<0.5)'; score += 5; }
    else if (stock.debtToEquity < 1) { breakdown.debtToEquity.contribution = 3; breakdown.debtToEquity.reason = 'Moderate debt (0.5-1)'; score += 3; }
    else if (stock.debtToEquity > 2) { breakdown.debtToEquity.contribution = -5; breakdown.debtToEquity.reason = 'High debt (>2)'; score -= 5; }
    else { breakdown.debtToEquity.reason = 'Elevated debt (1-2)'; }
  }

  if (stock.currentRatio !== undefined) {
    breakdown.currentRatio.value = stock.currentRatio;
    if (stock.currentRatio > 2) { breakdown.currentRatio.contribution = 3; breakdown.currentRatio.reason = 'Strong liquidity (>2)'; score += 3; }
    else if (stock.currentRatio > 1.5) { breakdown.currentRatio.contribution = 2; breakdown.currentRatio.reason = 'Good liquidity (1.5-2)'; score += 2; }
    else if (stock.currentRatio < 1) { breakdown.currentRatio.contribution = -5; breakdown.currentRatio.reason = 'Poor liquidity (<1)'; score -= 5; }
    else { breakdown.currentRatio.reason = 'Adequate liquidity (1-1.5)'; }
  }

  if (stock.dividendYield !== undefined && stock.dividendYield > 0) {
    breakdown.dividendYield.value = stock.dividendYield;
    if (stock.dividendYield > 4) { breakdown.dividendYield.contribution = 4; breakdown.dividendYield.reason = 'High dividend yield (>4%)'; score += 4; }
    else if (stock.dividendYield > 2) { breakdown.dividendYield.contribution = 2; breakdown.dividendYield.reason = 'Good dividend yield (2-4%)'; score += 2; }
    else { breakdown.dividendYield.reason = 'Low dividend yield (<2%)'; }
  }

  if (stock.profitMargin !== undefined) {
    breakdown.profitMargin.value = stock.profitMargin;
    if (stock.profitMargin > 20) { breakdown.profitMargin.contribution = 8; breakdown.profitMargin.reason = 'Excellent margin (>20%)'; score += 8; }
    else if (stock.profitMargin > 10) { breakdown.profitMargin.contribution = 5; breakdown.profitMargin.reason = 'Good margin (10-20%)'; score += 5; }
    else if (stock.profitMargin > 5) { breakdown.profitMargin.contribution = 2; breakdown.profitMargin.reason = 'Fair margin (5-10%)'; score += 2; }
    else if (stock.profitMargin < 0) { breakdown.profitMargin.contribution = -8; breakdown.profitMargin.reason = 'Negative margin'; score -= 8; }
    else { breakdown.profitMargin.reason = 'Low margin (<5%)'; }
  }

  if (stock.revenueGrowth !== undefined) {
    breakdown.revenueGrowth.value = stock.revenueGrowth;
    if (stock.revenueGrowth > 20) { breakdown.revenueGrowth.contribution = 8; breakdown.revenueGrowth.reason = 'Strong growth (>20%)'; score += 8; }
    else if (stock.revenueGrowth > 10) { breakdown.revenueGrowth.contribution = 5; breakdown.revenueGrowth.reason = 'Good growth (10-20%)'; score += 5; }
    else if (stock.revenueGrowth > 5) { breakdown.revenueGrowth.contribution = 2; breakdown.revenueGrowth.reason = 'Moderate growth (5-10%)'; score += 2; }
    else if (stock.revenueGrowth < -10) { breakdown.revenueGrowth.contribution = -8; breakdown.revenueGrowth.reason = 'Declining revenue (<-10%)'; score -= 8; }
    else if (stock.revenueGrowth < 0) { breakdown.revenueGrowth.contribution = -3; breakdown.revenueGrowth.reason = 'Negative growth'; score -= 3; }
    else { breakdown.revenueGrowth.reason = 'Slow growth (<5%)'; }
  }

  if (stock.earningsGrowth !== undefined) {
    breakdown.earningsGrowth.value = stock.earningsGrowth;
    if (stock.earningsGrowth > 25) { breakdown.earningsGrowth.contribution = 8; breakdown.earningsGrowth.reason = 'Strong earnings growth (>25%)'; score += 8; }
    else if (stock.earningsGrowth > 15) { breakdown.earningsGrowth.contribution = 5; breakdown.earningsGrowth.reason = 'Good earnings growth (15-25%)'; score += 5; }
    else if (stock.earningsGrowth > 5) { breakdown.earningsGrowth.contribution = 2; breakdown.earningsGrowth.reason = 'Moderate earnings growth (5-15%)'; score += 2; }
    else if (stock.earningsGrowth < -20) { breakdown.earningsGrowth.contribution = -10; breakdown.earningsGrowth.reason = 'Declining earnings (<-20%)'; score -= 10; }
    else if (stock.earningsGrowth < 0) { breakdown.earningsGrowth.contribution = -5; breakdown.earningsGrowth.reason = 'Negative earnings growth'; score -= 5; }
    else { breakdown.earningsGrowth.reason = 'Slow earnings growth (<5%)'; }
  }

  if (stock.beta !== undefined) {
    breakdown.beta.value = stock.beta;
    if (stock.beta >= 0.8 && stock.beta <= 1.2) { breakdown.beta.contribution = 3; breakdown.beta.reason = 'Stable volatility (0.8-1.2)'; score += 3; }
    else if (stock.beta > 1.5) { breakdown.beta.contribution = -3; breakdown.beta.reason = 'High volatility (>1.5)'; score -= 3; }
    else if (stock.beta < 0.5) { breakdown.beta.contribution = 2; breakdown.beta.reason = 'Low volatility (<0.5)'; score += 2; }
    else { breakdown.beta.reason = 'Moderate volatility'; }
  }

  if (stock.fiftyTwoWeekChange !== undefined) {
    breakdown.fiftyTwoWeekChange.value = stock.fiftyTwoWeekChange;
    if (stock.fiftyTwoWeekChange > 50) { breakdown.fiftyTwoWeekChange.contribution = 8; breakdown.fiftyTwoWeekChange.reason = 'Strong 52-week performance (>50%)'; score += 8; }
    else if (stock.fiftyTwoWeekChange > 20) { breakdown.fiftyTwoWeekChange.contribution = 5; breakdown.fiftyTwoWeekChange.reason = 'Good 52-week performance (20-50%)'; score += 5; }
    else if (stock.fiftyTwoWeekChange < -30) { breakdown.fiftyTwoWeekChange.contribution = -8; breakdown.fiftyTwoWeekChange.reason = 'Poor 52-week performance (<-30%)'; score -= 8; }
    else if (stock.fiftyTwoWeekChange < -10) { breakdown.fiftyTwoWeekChange.contribution = -3; breakdown.fiftyTwoWeekChange.reason = 'Negative 52-week performance (-10% to -30%)'; score -= 3; }
    else { breakdown.fiftyTwoWeekChange.reason = 'Moderate 52-week performance'; }
  }

  breakdown.newsSentiment.contribution = 0;
  breakdown.newsSentiment.reason = 'Neutral (requires news API integration)';
  breakdown.socialSentiment.contribution = 0;
  breakdown.socialSentiment.reason = 'Neutral (requires social API integration)';

  const finalScore = Math.max(0, Math.min(100, Math.round(score)));
  breakdown.totalScore = finalScore;

  return { score: finalScore, breakdown };
}

async function fetchStockData(symbol: string): Promise<StockData | null> {
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const quote: any = await yahooFinance.quote(symbol);

    if (!quote || typeof quote.regularMarketPrice !== 'number') {
      return null;
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const quoteSummary: any = await yahooFinance.quoteSummary(symbol, {
      modules: ['summaryProfile', 'defaultKeyStatistics', 'financialData', 'summaryDetail', 'incomeStatementHistory', 'balanceSheetHistory']
    }).catch(() => null);

    const currentPrice: number = quote.regularMarketPrice;
    const previousClose: number = quote.regularMarketPreviousClose ?? currentPrice;
    const priceChangePercent = previousClose
      ? ((currentPrice - previousClose) / previousClose) * 100
      : 0;

    const defaultKeyStatistics = quoteSummary?.defaultKeyStatistics;
    const summaryProfile = quoteSummary?.summaryProfile;
    const financialData = quoteSummary?.financialData;
    const summaryDetail = quoteSummary?.summaryDetail;
    const incomeStatementHistory = quoteSummary?.incomeStatementHistory;

    const peRatio = defaultKeyStatistics?.trailingPE ?? defaultKeyStatistics?.forwardPE;
    const pbRatio = defaultKeyStatistics?.priceToBook;
    const psRatio = defaultKeyStatistics?.priceToSalesTrailing12Months;
    const volume = quote.regularMarketVolume;
    const marketCap = defaultKeyStatistics?.marketCap;
    const beta = defaultKeyStatistics?.beta;

    const roe = financialData?.returnOnEquity ? financialData.returnOnEquity * 100 : undefined;
    const roa = financialData?.returnOnAssets ? financialData.returnOnAssets * 100 : undefined;
    const profitMargin = financialData?.profitMargins ? financialData.profitMargins * 100 : undefined;
    const debtToEquity = defaultKeyStatistics?.debtToEquity;
    const currentRatio = financialData?.currentRatio;
    const dividendYield = summaryDetail?.dividendYield ? summaryDetail.dividendYield * 100 : undefined;

    let revenueGrowth: number | undefined;
    let earningsGrowth: number | undefined;
    if (incomeStatementHistory?.incomeStatementHistory?.length >= 2) {
      const statements = incomeStatementHistory.incomeStatementHistory;
      const currentRevenue = statements[0]?.totalRevenue?.raw;
      const previousRevenue = statements[1]?.totalRevenue?.raw;
      const currentEarnings = statements[0]?.netIncome?.raw;
      const previousEarnings = statements[1]?.netIncome?.raw;
      if (currentRevenue && previousRevenue && previousRevenue > 0)
        revenueGrowth = ((currentRevenue - previousRevenue) / previousRevenue) * 100;
      if (currentEarnings && previousEarnings && previousEarnings !== 0)
        earningsGrowth = ((currentEarnings - previousEarnings) / Math.abs(previousEarnings)) * 100;
    }

    const fiftyTwoWeekHigh = summaryDetail?.fiftyTwoWeekHigh;
    let fiftyTwoWeekChange: number | undefined;
    if (fiftyTwoWeekHigh && fiftyTwoWeekHigh > 0)
      fiftyTwoWeekChange = ((currentPrice - fiftyTwoWeekHigh) / fiftyTwoWeekHigh) * 100;

    const stockName = summaryProfile?.longName || quote.longName || quote.shortName || symbol;

    return {
      symbol: quote.symbol || symbol,
      name: stockName,
      currentPrice,
      priceChangePercent: parseFloat(priceChangePercent.toFixed(2)),
      peRatio: (typeof peRatio === 'number' && peRatio > 0) ? parseFloat(peRatio.toFixed(2)) : undefined,
      pbRatio: (typeof pbRatio === 'number' && pbRatio > 0) ? parseFloat(pbRatio.toFixed(2)) : undefined,
      psRatio: (typeof psRatio === 'number' && psRatio > 0) ? parseFloat(psRatio.toFixed(2)) : undefined,
      volume: typeof volume === 'number' ? Math.floor(volume) : undefined,
      marketCap: typeof marketCap === 'number' ? Math.floor(marketCap) : undefined,
      roe: typeof roe === 'number' ? parseFloat(roe.toFixed(2)) : undefined,
      roa: typeof roa === 'number' ? parseFloat(roa.toFixed(2)) : undefined,
      debtToEquity: (typeof debtToEquity === 'number' && debtToEquity >= 0) ? parseFloat(debtToEquity.toFixed(2)) : undefined,
      currentRatio: (typeof currentRatio === 'number' && currentRatio > 0) ? parseFloat(currentRatio.toFixed(2)) : undefined,
      dividendYield: (typeof dividendYield === 'number' && dividendYield >= 0) ? parseFloat(dividendYield.toFixed(2)) : undefined,
      profitMargin: typeof profitMargin === 'number' ? parseFloat(profitMargin.toFixed(2)) : undefined,
      revenueGrowth: typeof revenueGrowth === 'number' ? parseFloat(revenueGrowth.toFixed(2)) : undefined,
      earningsGrowth: typeof earningsGrowth === 'number' ? parseFloat(earningsGrowth.toFixed(2)) : undefined,
      beta: typeof beta === 'number' ? parseFloat(beta.toFixed(2)) : undefined,
      fiftyTwoWeekChange: typeof fiftyTwoWeekChange === 'number' ? parseFloat(fiftyTwoWeekChange.toFixed(2)) : undefined,
    };
  } catch (error) {
    console.error(`Error fetching data for ${symbol}:`, error);
    return null;
  }
}

// Your portfolio holdings
const PORTFOLIO_STOCKS = [
  // Stocks with positions
  'MSFT',
  'ENR.DE',
  'VH2.DE',
  'MILDEF.ST',
  'GOOG',
  'AIR.PA',
  'HO.PA',
  // Watchlist
  'BTC-USD',
  'GC=F',
  'SI=F',
  'NVDA',
  'AMZN',
  'AAPL',
  'LLY',
  'GBF.DE',
  'BA.L',
  'BESI.AS',
  'ASM.AS',
  'CAT',
  'IBE.MC',
  'SNDK',
  'SMHN.DE',
  // ETFs
  'SPYY.DE',
  'EUNK.DE',
  'QDVE.DE',
  'IS3N.DE',
];

const CONCURRENCY_LIMIT = 3;

async function withConcurrencyLimit<T>(tasks: (() => Promise<T>)[], limit: number): Promise<(T | undefined)[]> {
  const results: (T | undefined)[] = new Array(tasks.length);
  let index = 0;
  async function worker() {
    while (index < tasks.length) {
      const i = index++;
      try { results[i] = await tasks[i](); }
      catch (error) { console.error(`Task ${i} failed:`, error); }
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, tasks.length) }, worker));
  return results;
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const symbolsParam = searchParams.get('symbols');
    const symbols = symbolsParam
      ? symbolsParam.split(',').map(s => s.trim().toUpperCase()).filter(Boolean)
      : PORTFOLIO_STOCKS;

    const tasks = symbols.map(symbol => () => fetchStockData(symbol));
    const stockResults = await withConcurrencyLimit(tasks, CONCURRENCY_LIMIT);

    const stocksWithScores: StockWithScore[] = stockResults
      .filter((stock): stock is StockData => stock != null)
      .map(stock => {
        const { score, breakdown } = calculateInvestmentScore(stock);
        return { ...stock, investmentScore: score, scoreBreakdown: breakdown };
      })
      .sort((a, b) => b.investmentScore - a.investmentScore);

    return NextResponse.json({ stocks: stocksWithScores });
  } catch (error) {
    console.error('Error fetching stocks:', error);
    return NextResponse.json({ error: 'Failed to fetch stocks' }, { status: 500 });
  }
}
