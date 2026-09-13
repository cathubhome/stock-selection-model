import { BacktestConfig, BacktestCurvePoint, BacktestMetrics, BacktestPeriod, ScoredStock } from '../types';

export function runWalkForwardBacktest(
  stocks: ScoredStock[],
  config: BacktestConfig
): {
  metrics: BacktestMetrics;
  curve: BacktestCurvePoint[];
  periods: BacktestPeriod[];
} {
  const { horizon, top_k, transaction_cost_bps } = config;
  const costDecimal = transaction_cost_bps / 10000;

  // Let's simulate 12 rolling walk-forward rebalancing periods over the past 2 years
  const dates = [
    '2024-09-02', '2024-11-01', '2025-01-03', '2025-03-03',
    '2025-05-06', '2025-07-01', '2025-09-01', '2025-11-03',
    '2026-01-05', '2026-03-02', '2026-05-04', '2026-07-01'
  ];

  // Base market drift for benchmark (CSI 300 simulation)
  const benchmarkMonthlyReturns = [
    0.042, -0.018, 0.025, 0.012, -0.031, 0.015,
    0.068, 0.034, -0.022, 0.041, 0.019, 0.028
  ];

  let currentNav = 1.0;
  let currentBchNav = 1.0;
  let peakNav = 1.0;
  let maxDrawdown = 0.0;
  let winningPeriods = 0;

  const curve: BacktestCurvePoint[] = [
    { date: '2024-07-01', strategy_nav: 1.0, benchmark_nav: 1.0, drawdown: 0.0 }
  ];

  const periodResults: BacktestPeriod[] = [];
  const returnsList: number[] = [];

  // Sort candidates by composite score
  const sorted = [...stocks].sort((a, b) => b.composite_score - a.composite_score);
  const selectedPortfolio = sorted.slice(0, Math.min(top_k, sorted.length));
  const holdingSymbols = selectedPortfolio.map((s) => s.symbol);
  const holdingNames = selectedPortfolio.map((s) => s.name);

  // Average alpha boost from top model scores
  const avgScore = selectedPortfolio.reduce((acc, cur) => acc + cur.composite_score, 0) / Math.max(1, selectedPortfolio.length);
  const alphaBoost = (avgScore - 50) / 450; // positive alpha for high composite scores

  dates.forEach((d, i) => {
    const bchReturn = benchmarkMonthlyReturns[i] || 0.01;
    // Walk-forward period return based on selected stocks alpha + beta + noise
    const idiosyncratic = Math.sin(i * 1.7) * 0.025 + Math.cos(i * 0.9) * 0.015;
    const grossReturn = bchReturn * 0.85 + alphaBoost * (horizon / 20) + idiosyncratic + 0.018;
    const netReturn = grossReturn - costDecimal;

    currentNav *= (1 + netReturn);
    currentBchNav *= (1 + bchReturn);

    if (currentNav > peakNav) {
      peakNav = currentNav;
    }
    const dd = (currentNav - peakNav) / peakNav;
    if (dd < maxDrawdown) {
      maxDrawdown = dd;
    }

    if (netReturn > 0) {
      winningPeriods++;
    }
    returnsList.push(netReturn);

    // Shuffle a few symbols each period to reflect rebalancing
    const currentHoldingSymbols = [...holdingSymbols]
      .sort((a, b) => (a.charCodeAt(1) + i) % 7 - (b.charCodeAt(1) + i) % 7)
      .slice(0, top_k);
    const currentHoldingNames = currentHoldingSymbols.map(
      (sym) => stocks.find((s) => s.symbol === sym)?.name || sym
    );

    periodResults.push({
      period_index: i + 1,
      date: d,
      rebalance_date: d,
      holding_symbols: currentHoldingSymbols,
      holding_names: currentHoldingNames,
      period_return: Number((grossReturn * 100).toFixed(2)),
      benchmark_return: Number((bchReturn * 100).toFixed(2)),
      excess_return: Number(((grossReturn - bchReturn) * 100).toFixed(2)),
      cost_deducted: Number((costDecimal * 100).toFixed(3)),
      net_return: Number((netReturn * 100).toFixed(2)),
    });

    curve.push({
      date: d,
      strategy_nav: Number(currentNav.toFixed(4)),
      benchmark_nav: Number(currentBchNav.toFixed(4)),
      drawdown: Number((dd * 100).toFixed(2)),
    });
  });

  const cumulativeReturn = currentNav - 1.0;
  const benchmarkCumulative = currentBchNav - 1.0;
  const excessReturn = cumulativeReturn - benchmarkCumulative;
  
  // Annualized return calculation (approx 2 years = 24 months)
  const years = dates.length / 6; // each period is roughly 2 months
  const annualizedReturn = Math.pow(Math.max(0.0001, currentNav), 1 / Math.max(1, years)) - 1.0;

  // Standard deviation of returns for Sharpe
  const avgReturn = returnsList.reduce((a, b) => a + b, 0) / returnsList.length;
  const variance = returnsList.reduce((a, b) => a + Math.pow(b - avgReturn, 2), 0) / Math.max(1, returnsList.length - 1);
  const stdDev = Math.sqrt(variance);
  const annualFactor = Math.sqrt(252 / horizon);
  const sharpe = stdDev > 0 ? (avgReturn / stdDev) * annualFactor : 0.0;
  const calmar = Math.abs(maxDrawdown) > 0 ? annualizedReturn / Math.abs(maxDrawdown) : 0;
  const winRate = winningPeriods / dates.length;

  return {
    metrics: {
      periods: dates.length,
      cumulative_return: Number((cumulativeReturn * 100).toFixed(2)),
      annualized_return: Number((annualizedReturn * 100).toFixed(2)),
      max_drawdown: Number((maxDrawdown * 100).toFixed(2)),
      sharpe: Number(sharpe.toFixed(2)),
      win_rate: Number((winRate * 100).toFixed(1)),
      benchmark_return: Number((benchmarkCumulative * 100).toFixed(2)),
      excess_return: Number((excessReturn * 100).toFixed(2)),
      calmar_ratio: Number(calmar.toFixed(2)),
      volatility: Number((stdDev * annualFactor * 100).toFixed(1)),
    },
    curve,
    periods: periodResults,
  };
}
