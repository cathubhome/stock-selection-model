export interface StockBasic {
  symbol: string;
  name: string;
  pinyin: string;
  industry: string;
  market: '主板' | '创业板' | '科创板' | 'ETF' | '港股通';
  source?: string;
  added_at?: string;
}

export interface MarketQuote {
  symbol: string;
  name: string;
  price: number;
  change: number; // percentage, e.g. 2.45
  turnover: number; // percentage, e.g. 4.2
  volume_ratio: number; // e.g. 1.35
  volume: number; // in lots or shares
  amount: number; // in CNY
  pe_ttm: number;
  pb: number;
  high_52w: number;
  low_52w: number;
}

export interface FactorMetrics {
  ret_5: number;
  ret_20: number;
  ret_60: number;
  ret_120: number;
  vol_20: number;
  sma_20_ratio: number;
  sma_60_ratio: number;
  volume_ratio_20: number;
  obv_slope_20: number;
  money_flow_20: number;
  body_pct: number;
  close_position: number;
  upper_shadow_pct: number;
  lower_shadow_pct: number;
}

export interface ScoredStock extends StockBasic, MarketQuote {
  model_raw: number;
  model_score: number; // 0 - 100
  technical_score: number; // 0 - 100
  volume_price_score: number; // 0 - 100
  candle_score: number; // 0 - 100
  sentiment_score: number; // 0 - 100
  sentiment_source: string;
  news_count: number;
  composite_score: number; // 0 - 100
  rank: number;
  odds_reward_risk: number; // e.g. 2.4
  odds_win_rate: number; // percentage, e.g. 64.5
  odds_expected_return: number; // percentage, e.g. 8.2
  diagnostic_status: 'excellent' | 'good' | 'warning';
  diagnostic_message: string;
  trading_days: number;
  credibility_score?: number;
  credibility_grade?: string;
  credibility_strategy?: number;
  credibility_conditional?: number;
  credibility_stability?: number;
  credibility_agreement?: number;
  positive_evidences?: string[];
  negative_evidences?: string[];
}

export interface WeightConfig {
  model: number;
  technical: number;
  volume_price: number;
  candle: number;
  sentiment: number;
}

export interface BacktestPeriod {
  period_index: number;
  date: string;
  rebalance_date: string;
  holding_symbols: string[];
  holding_names: string[];
  period_return: number; // strategy period return
  benchmark_return: number; // csi 300 period return
  excess_return: number;
  cost_deducted: number;
  net_return: number;
}

export interface BacktestMetrics {
  periods: number;
  cumulative_return: number;
  annualized_return: number;
  max_drawdown: number;
  sharpe: number;
  win_rate: number;
  benchmark_return: number;
  excess_return: number;
  calmar_ratio: number;
  volatility: number;
}

export interface BacktestCurvePoint {
  date: string;
  strategy_nav: number; // normalized to 1.0 at start
  benchmark_nav: number; // normalized to 1.0 at start
  drawdown: number;
}

export interface BacktestConfig {
  horizon: number; // holding period in trading days: 5, 10, 20, 60
  top_k: number; // number of stocks selected: 5, 10, 15, 20
  transaction_cost_bps: number; // basis points, e.g. 15 bps (0.15%)
  benchmark: string;
}

export interface ArchiveRun {
  run_id: string;
  date: string;
  created_at: string;
  kind: 'score' | 'backtest';
  stock_count: number;
  top_symbols: string[];
  avg_score: number;
  excess_return?: number;
  sharpe?: number;
}

export type ResearchStep = '研究看板' | '股票池与数据' | '综合评分' | '历史回测' | '研究记录';

