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
  change: number;
  turnover: number;
  volume_ratio: number;
  volume: number;
  amount: number;
  pe_ttm?: number;
  pb?: number;
  high_52w?: number;
  low_52w?: number;
}

export interface ScoredStock extends StockBasic, MarketQuote {
  date?: string;
  model_raw: number;
  model_score: number;
  technical_score: number;
  volume_price_score: number;
  candle_score: number;
  sentiment_score: number;
  sentiment_source?: string;
  news_count?: number;
  composite_score: number;
  rank: number;
  rank_change?: string;
  odds_sample_count?: number | null;
  odds_reward_risk: number;
  odds_win_rate: number;
  odds_expected_return: number;
  diagnostic_status: 'excellent' | 'good' | 'warning' | 'danger';
  diagnostic_message: string;
  trading_days: number;
  credibility_score?: number;
  credibility_grade?: string;
  credibility_stability?: number;
  credibility_agreement?: number;
  conditional_sample_count?: number | null;
  conditional_win_rate?: number | null;
  conditional_win_rate_low?: number | null;
  conditional_win_rate_high?: number | null;
  conditional_expected_return?: number | null;
  conditional_return_low?: number | null;
  conditional_return_high?: number | null;
  limitations?: string[];
  data_complete?: boolean;
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

export interface ScoringConfig {
  horizon: number;
  top_k: number;
  fetch_sentiment: boolean;
}

export interface BacktestConfig {
  horizon: number;
  top_k: number;
  transaction_cost_bps: number;
  benchmark: string;
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
  ic_mean?: number;
  ic_confidence_low?: number;
  ic_confidence_high?: number;
  q5_q1_mean_return?: number;
}

export interface BacktestCurvePoint {
  date: string;
  strategy_nav: number;
  benchmark_nav: number;
  drawdown: number;
}

export interface BacktestPeriod {
  period_index: number;
  date: string;
  rebalance_date: string;
  holding_symbols: string[];
  holding_names?: string[];
  portfolio_return?: number;
  period_return?: number;
  benchmark_return: number;
  excess_return: number;
  cost_deducted?: number;
  turnover?: number;
}

export interface ArchiveRun {
  run_id: string;
  date: string;
  created_at: string;
  kind: 'score' | 'backtest' | string;
  stock_count: number;
  top_symbols: string[];
  avg_score: number;
  excess_return?: number;
  sharpe?: number;
}

export type ResearchStep = '研究看板' | '股票池与数据' | '综合评分' | '历史回测' | '研究记录';
