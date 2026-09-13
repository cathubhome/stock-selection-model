import { ScoredStock, WeightConfig, BacktestMetrics, BacktestCurvePoint, BacktestPeriod, ArchiveRun } from '../types';

const API_BASE = '/api';

export interface SystemStatusResponse {
  status: string;
  version: string;
  timestamp: string;
  pool_count: number;
  raw_bar_files: number;
  metadata_status: any;
  market_sentiment: any;
  latest_score_run: any;
}

export interface LatestScoresResponse {
  stocks: ScoredStock[];
  manifest: any;
  count: number;
  updated_at?: string;
}

export interface LatestBacktestResponse {
  metrics: BacktestMetrics;
  curve: BacktestCurvePoint[];
  periods: BacktestPeriod[];
}

export interface TaskProgressResponse {
  running: boolean;
  current?: number;
  total?: number;
  percent: number;
  symbol?: string;
  message: string;
  error?: string | null;
}

export async function fetchSystemStatus(): Promise<SystemStatusResponse | null> {
  try {
    const res = await fetch(API_BASE + '/status');
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchStockPool(): Promise<ScoredStock[] | null> {
  try {
    const res = await fetch(API_BASE + '/pool');
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function addPoolStocks(symbols: string[], source = 'Web界面添加'): Promise<boolean> {
  try {
    const res = await fetch(API_BASE + '/pool', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbols, source }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function removePoolStock(symbol: string): Promise<boolean> {
  try {
    const res = await fetch(API_BASE + '/pool/' + encodeURIComponent(symbol), {
      method: 'DELETE',
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function searchUniverse(q: string, limit = 20): Promise<any[]> {
  try {
    const res = await fetch(API_BASE + '/universe/search?q=' + encodeURIComponent(q) + '&limit=' + limit);
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

export async function startDataDownload(): Promise<{ ok: boolean; task_id?: string; symbols_count?: number }> {
  const res = await fetch(API_BASE + '/data/download', { method: 'POST' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '下载启动失败' }));
    throw new Error(err.detail || '下载启动失败');
  }
  return await res.json();
}

export async function fetchDownloadProgress(taskId: string): Promise<TaskProgressResponse> {
  const res = await fetch(API_BASE + '/data/download-progress?task_id=' + encodeURIComponent(taskId));
  if (!res.ok) {
    return { running: false, percent: 100, message: '无法获取任务进度' };
  }
  return await res.json();
}

export async function syncMetadata(): Promise<any> {
  const res = await fetch(API_BASE + '/data/sync-metadata', { method: 'POST' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '元数据同步失败' }));
    throw new Error(err.detail || '元数据同步失败');
  }
  return await res.json();
}

export async function fetchLatestScores(): Promise<LatestScoresResponse | null> {
  try {
    const res = await fetch(API_BASE + '/scores/latest');
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function runScoring(params: {
  horizon: number;
  top_k: number;
  weights: WeightConfig;
  fetch_sentiment?: boolean;
}): Promise<any> {
  const res = await fetch(API_BASE + '/scores/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '模型评分运行失败' }));
    throw new Error(err.detail || '模型评分运行失败');
  }
  return await res.json();
}

export async function fetchLatestBacktest(): Promise<LatestBacktestResponse | null> {
  try {
    const res = await fetch(API_BASE + '/backtest/latest');
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function runBacktest(params: {
  horizon: number;
  top_k: number;
  weights?: WeightConfig;
  transaction_cost_bps: number;
  benchmark: string;
}): Promise<LatestBacktestResponse> {
  const res = await fetch(API_BASE + '/backtest/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '回测执行失败' }));
    throw new Error(err.detail || '回测执行失败');
  }
  return await res.json();
}

export async function fetchResearchRuns(): Promise<ArchiveRun[]> {
  try {
    const res = await fetch(API_BASE + '/runs');
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}
