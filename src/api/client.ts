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

export interface GovernanceCheckItem {
  level: string;
  name: string;
  current: string;
  threshold: string;
  passed: boolean;
  desc: string;
}

export interface GovernanceStatusResponse {
  passed: boolean;
  label: string;
  failed_reasons: string[];
  warnings: string[];
  checks: GovernanceCheckItem[];
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

export async function batchAddPoolStocks(text: string, source = '批量粘贴导入'): Promise<{ ok: boolean; added: number; total: number } | null> {
  try {
    const res = await fetch(API_BASE + '/pool/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, source }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: '批量添加失败' }));
      throw new Error(err.detail || '批量添加失败');
    }
    return await res.json();
  } catch (err: any) {
    throw err;
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

export async function startDataDownload(payload: { scope?: 'pool' | 'top_amount'; top_n?: number; mode?: 'incremental' | 'full'; start_date?: string; end_date?: string } = {}): Promise<{ ok: boolean; task_id?: string; symbols_count?: number }> {
  const res = await fetch(API_BASE + '/data/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
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

export async function repairDataQuality(): Promise<any> {
  const res = await fetch(API_BASE + '/data/repair-quality', { method: 'POST' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '数据质量修复失败' }));
    throw new Error(err.detail || '数据质量修复失败');
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

export async function runScoring(payload: {
  horizon?: number;
  top_k?: number;
  weights?: WeightConfig;
  fetch_sentiment?: boolean;
}): Promise<LatestScoresResponse | null> {
  const res = await fetch(API_BASE + '/scores/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '评分计算失败' }));
    throw new Error(err.detail || '评分计算失败');
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

export async function runBacktest(payload: {
  horizon?: number;
  top_k?: number;
  transaction_cost_bps?: number;
  benchmark?: string;
  weights?: WeightConfig;
}): Promise<LatestBacktestResponse | null> {
  const res = await fetch(API_BASE + '/backtest/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '回测运行失败' }));
    throw new Error(err.detail || '回测运行失败');
  }
  return await res.json();
}
export async function fetchResearchLinkage(): Promise<any | null> {
  try {
    const res = await fetch(API_BASE + '/research/linkage');
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export async function fetchStockHistory(symbol: string, days = 120): Promise<any | null> {
  try {
    const res = await fetch(API_BASE + '/stock/' + encodeURIComponent(symbol) + '/history?days=' + days);
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export async function fetchGovernanceStatus(): Promise<GovernanceStatusResponse | null> {
  try {
    const res = await fetch(API_BASE + '/governance/status');
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
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

export async function fetchRunDetail(runId: string): Promise<any> {
  try {
    const res = await fetch(API_BASE + '/runs/' + encodeURIComponent(runId));
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// Direct File Downloads
export function downloadFile(url: string, filename: string) {
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

export function downloadCandidateExcel() {
  const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');
  downloadFile(`${API_BASE}/export/excel`, `candidate_picks_${today}.xlsx`);
}

export function downloadResearchReportPdf() {
  const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');
  downloadFile(`${API_BASE}/export/pdf`, `research_report_${today}.pdf`);
}

export function downloadBacktestCsv() {
  const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');
  downloadFile(`${API_BASE}/export/backtest-csv`, `backtest_periods_${today}.csv`);
}
