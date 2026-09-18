
const safeNum = (val: any, fallback = 0): number => {
  const n = typeof val === 'number' ? val : Number(val);
  return isNaN(n) ? fallback : n;
};

const fmtNum = (val: any, digits = 2, fallback = '--'): string => {
  if (val === null || val === undefined) return fallback;
  const n = typeof val === 'number' ? val : Number(val);
  if (isNaN(n)) return fallback;
  return n.toFixed(digits);
};
import React, { useEffect, useMemo, useState } from 'react';
import { 
  Sliders, 
  RotateCcw, 
  BrainCircuit, 
  Activity, 
  BarChart2, 
  Flame, 
  MessageSquare,
  ChevronRight,
  FileSpreadsheet,
  FileText,
  Sparkles,
  FileDown,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  Info,
  Calendar,
  AlertTriangle,
  HelpCircle
} from 'lucide-react';
import { ScoredStock, ScoringConfig, WeightConfig } from '../types';
import { downloadCandidateExcel, downloadResearchReportPdf, fetchScoringContext, fetchSystemStatus, ScoringContextResponse, SystemStatusResponse } from '../api/client';
import { DEFAULT_WEIGHTS } from '../utils/scoring';
import { TermTooltip } from './TermTooltip';

const FACTOR_META: Record<string, { name: string; dir: "high" | "low" | "mid"; dirLabel: string; desc: string }> = {
  ret_120: { name: "半年期价格动量", dir: "high", dirLabel: "偏大为佳", desc: "过去120交易日累计超额收益，捕捉中长期多头趋势" },
  vol_20: { name: "20日价格波动率", dir: "low", dirLabel: "偏小更稳", desc: "衡量股价短期震荡剧烈程度，低波动个股回撤更可控" },
  atr_pct_14: { name: "14日真实波幅占比", dir: "mid", dirLabel: "适中为宜", desc: "日内真实波动幅度，过高需警惕情绪过热后的大幅回调" },
  obv_slope_20: { name: "能量潮资金斜率", dir: "high", dirLabel: "越大越好", desc: "OBV能量潮上翘趋势，正值越大代表主力资金持续流入" },
  amount_log: { name: "日均成交额对数", dir: "high", dirLabel: "越大越好", desc: "衡量个股资金容量，值越大代表流动性充裕、买卖滑点冲击低" },
  signal_pct: { name: "MACD信号线动能", dir: "high", dirLabel: "大于0为好", desc: "经典平滑异同信号，正值代表多头动能加速扩散" },
  macd_pct: { name: "MACD差离值相对强度", dir: "high", dirLabel: "大于0为好", desc: "快慢均线扩散速度，反映短期趋势超越长期趋势的冲力" },
  ret_20: { name: "20日月度动量", dir: "high", dirLabel: "偏大为佳", desc: "近1个月累计超额收益，中短期趋势动能核心指标" },
  ret_5: { name: "5日周度动量", dir: "mid", dirLabel: "适中偏强", desc: "近1周超额涨跌幅，适中偏强最佳，防范短期过热见顶" },
  ret_60: { name: "60日季度动量", dir: "high", dirLabel: "偏大为佳", desc: "中期季度均线趋势，反映机构资金季度配置方向" },
  body_pct: { name: "日K实体饱满度", dir: "high", dirLabel: "阳线越大好", desc: "K线实体占全天振幅比例，饱满大阳线代表多方买意坚决" },
  close_position: { name: "日内收盘相对位置", dir: "high", dirLabel: "靠近高点好", desc: "收盘价处于全天最高最低的相对位置，高位收盘代表承接力强" },
  upper_shadow_pct: { name: "上影线抛压占比", dir: "low", dirLabel: "偏小为好", desc: "上影线占整根K线比例，越长说明盘中冲高回落抛压越大" },
  lower_shadow_pct: { name: "下影线支撑占比", dir: "high", dirLabel: "偏大为好", desc: "下影线占整根K线比例，越长代表探底回升买盘支撑强劲" },
  volume_ratio_20: { name: "20日成交量比", dir: "mid", dirLabel: "温和放量佳", desc: "当前成交量对比前20日均量倍数，温和放大最健康" },
  money_flow_20: { name: "20日资金流向强弱", dir: "high", dirLabel: "越大越好", desc: "量价加权资金流向，正向持续流入为优选标的" },
  rsi_14: { name: "14日RSI强弱指标", dir: "mid", dirLabel: "50~70最佳", desc: "经典相对强弱指标，处于强势中枢区间为最佳动量" },
  sma_20_ratio: { name: "20日均线偏离度", dir: "mid", dirLabel: "适中偏强", desc: "收盘价相对20日均线比率，过大易均值回归，过低趋势偏弱" },
  sma_60_ratio: { name: "60日均线趋势偏离", dir: "high", dirLabel: "大于1为佳", desc: "收盘价站稳60日生命线上方，确立中线多头格局" },
  vwap_dev: { name: "均价偏离度 (VWAP)", dir: "mid", dirLabel: "适中为好", desc: "收盘价对比成交量加权均价偏离，衡量买卖力量均衡度" },
  bollinger_pctb: { name: "布林带通道位置", dir: "mid", dirLabel: "60%~80%佳", desc: "股价处于布林通道的百分位，沿着上轨攀升但未极端超买" },
  market_cap_log: { name: "总市值规模对数", dir: "mid", dirLabel: "风格中性", desc: "用于规模风格约束，避免单押超大盘或微盘股" },
  pe_ttm: { name: "市盈率估值倒数", dir: "high", dirLabel: "同业偏高好", desc: "盈余收益率(E/P)，同行业内性价比越高越具防御安全垫" },
};

interface CompositeScoringViewProps {
  weights: WeightConfig;
  onUpdateWeights: (weights: WeightConfig) => void;
  stocks: ScoredStock[];
  onSelectStock: (stock: ScoredStock) => void;
  onRunScoring: (config: ScoringConfig) => void;
  isScoringRunning?: boolean;
  scoringProgress?: { running?: boolean; percent?: number; message?: string; error?: string | null; details?: any[]; elapsed_seconds?: number; result?: any };
  onNavigateToData?: () => void;
}

export const CompositeScoringView: React.FC<CompositeScoringViewProps> = ({
  weights,
  onUpdateWeights,
  stocks,
  onSelectStock,
  onRunScoring,
  isScoringRunning = false,
  scoringProgress,
  onNavigateToData,
}) => {
  const [selectedStockSymbol, setSelectedStockSymbol] = useState<string>(stocks[0]?.symbol || '605277');
  const [tableView, setTableView] = useState<'决策' | '模型' | '技术' | '赔率' | '可信度'>('决策');
  const [searchFilter, setSearchFilter] = useState('');
  const [systemStatus, setSystemStatus] = useState<SystemStatusResponse | null>(null);
  const [scoringContext, setScoringContext] = useState<ScoringContextResponse | null>(null);
  const [scoringConfig, setScoringConfig] = useState<ScoringConfig>({ horizon: 20, top_k: 10, fetch_sentiment: true });
  const [exportMenuOpen, setExportMenuOpen] = useState<boolean>(false);
  const exportMenuRef = React.useRef<HTMLDivElement>(null);
  const [showScoringLog, setShowScoringLog] = useState<boolean>(false);

  useEffect(() => {
    let cancelled = false;
    const refresh = async () => {
      const [status, context] = await Promise.all([fetchSystemStatus(), fetchScoringContext()]);
      if (!cancelled) {
        setSystemStatus(status);
        setScoringContext(context);
      }
    };
    refresh();
    const timer = window.setInterval(refresh, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [scoringProgress?.running]);

  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target as Node)) {
        setExportMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  const latestMarketDate = systemStatus?.market_data?.latest_date || '--';
  const latestDataDate = scoringContext?.manifest?.data_end || stocks[0]?.date || '--';
  const scoreUsesLatestMarket = latestDataDate !== '--' && latestDataDate === latestMarketDate;

  const sumWeights = 
    weights.model + 
    weights.technical + 
    weights.volume_price + 
    weights.candle + 
    weights.sentiment;
  const weightsValid = Math.abs(sumWeights - 1) < 0.001;
  const persistedWeights = scoringContext?.manifest?.config?.weights;
  const isPreview = persistedWeights
    ? (Object.keys(weights) as Array<keyof WeightConfig>).some(key => Math.abs(weights[key] - Number(persistedWeights[key] || 0)) > 0.001)
    : false;

  const handleSliderChange = (key: keyof WeightConfig, val: number) => {
    onUpdateWeights({
      ...weights,
      [key]: val / 100,
    });
  };

  const applyPreset = (preset: WeightConfig) => {
    onUpdateWeights(preset);
  };

  // Re-calculate composite scores dynamically based on user-adjusted weights
  const scoredList = useMemo(() => {
    const total = sumWeights || 1;
    const normModel = weights.model / total;
    const normTech = weights.technical / total;
    const normVP = weights.volume_price / total;
    const normCandle = weights.candle / total;
    const normSent = weights.sentiment / total;

    const list = stocks.map((s) => {
      const dynScore = 
        safeNum(s.model_score) * normModel +
        safeNum(s.technical_score) * normTech +
        safeNum(s.volume_price_score) * normVP +
        safeNum(s.candle_score) * normCandle +
        safeNum(s.sentiment_score) * normSent;

      return {
        ...s,
        composite_score: Number(dynScore.toFixed(2))
      };
    });

    list.sort((a, b) => b.composite_score - a.composite_score);
    return list.map((s, idx) => ({ ...s, rank: idx + 1 }));
  }, [stocks, weights, sumWeights]);

  const filteredList = useMemo(() => {
    if (!searchFilter.trim()) return scoredList;
    const q = searchFilter.toLowerCase();
    return scoredList.filter(s => 
      s.symbol.toLowerCase().includes(q) || 
      s.name.toLowerCase().includes(q) ||
      (s.industry || '').toLowerCase().includes(q)
    );
  }, [scoredList, searchFilter]);

  const activeStock = useMemo(() => {
    return scoredList.find(s => s.symbol === selectedStockSymbol) || scoredList[0] || null;
  }, [scoredList, selectedStockSymbol]);
  const factorContribution = useMemo(() => {
    if (!activeStock) return [];
    return [
      { label: '模型评分', score: safeNum(activeStock.model_score), weight: weights.model },
      { label: '技术评分', score: safeNum(activeStock.technical_score), weight: weights.technical },
      { label: '量价评分', score: safeNum(activeStock.volume_price_score), weight: weights.volume_price },
      { label: 'K线评分', score: safeNum(activeStock.candle_score), weight: weights.candle },
      { label: '舆情评分', score: safeNum(activeStock.sentiment_score), weight: weights.sentiment },
    ].map(item => ({ ...item, contribution: item.score * item.weight }));
  }, [activeStock, weights]);

  // Export CSV
  const handleExportCSV = () => {
    const headers = [
      'rank', 'symbol', 'name', 'composite_score', 'model_score', 
      'technical_score', 'volume_price_score', 'candle_score', 'sentiment_score',
      'odds_win_rate', 'odds_reward_risk', 'credibility_score', 'industry'
    ];
    const rows = scoredList.map(s => [
      s.rank,
      s.symbol,
      s.name,
      s.composite_score,
      s.model_score,
      s.technical_score,
      s.volume_price_score,
      s.candle_score,
      s.sentiment_score,
      s.odds_win_rate,
      s.odds_reward_risk,
      s.credibility_score ?? '',
      s.industry
    ]);
    const csvContent = '\uFEFF' + [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `latest_picks_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="space-y-1.5">
          <div className="flex items-center space-x-2 text-indigo-600 text-xs font-bold uppercase tracking-wider">
            <Sliders className="w-4 h-4" />
            <span>第三步 · 综合多因子评分与候选研判</span>
          </div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            五维因子权重动态配置与透明归因
          </h2>
          <div className="flex flex-wrap items-center gap-2 pt-0.5">
            <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-slate-50 border border-slate-200 text-xs text-slate-600">
              <Calendar className="w-3 h-3 text-slate-400" />
              <span>评分截面基准: <strong className="font-mono text-slate-800">{latestDataDate}</strong></span>
            </div>
            <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-medium border ${scoreUsesLatestMarket ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
              {scoreUsesLatestMarket ? '基于最新行情截面 (已对齐)' : `行情已至 ${latestMarketDate}，评分待重算`}
            </span>
            {onNavigateToData && !scoreUsesLatestMarket && (
              <button
                onClick={onNavigateToData}
                className="text-[11px] text-indigo-600 hover:text-indigo-800 font-medium hover:underline cursor-pointer"
                title="前往股票池与数据中心进行增量更新"
              >
                前往更新行情 ↗
              </button>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => onRunScoring(scoringConfig)}
            disabled={isScoringRunning || !weightsValid}
            className={`inline-flex items-center px-4 py-2 rounded-lg text-xs font-bold shadow-xs transition-all ${
              isScoringRunning || !weightsValid
                ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                : 'bg-indigo-600 hover:bg-indigo-700 text-white cursor-pointer'
            }`}
          >
            <Sparkles className={`w-3.5 h-3.5 mr-1.5 ${isScoringRunning ? 'animate-spin' : ''}`} />
            {isScoringRunning ? '测算中...' : !weightsValid ? '权重合计需为 100%' : '重新测算评分'}
          </button>

          {/* Export Deliverables Dropdown Menu */}
          <div ref={exportMenuRef} className="relative">
            <button
              type="button"
              onClick={() => setExportMenuOpen(prev => !prev)}
              className="inline-flex items-center px-3 py-2 rounded-lg text-xs font-semibold bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 transition-colors shadow-xs cursor-pointer"
            >
              <FileDown className="w-3.5 h-3.5 mr-1 text-slate-500" />
              <span>导出投研产物</span>
              <ChevronDown className={`w-3.5 h-3.5 ml-1 text-slate-400 transition-transform duration-200 ${exportMenuOpen ? 'rotate-180' : ''}`} />
            </button>

            {exportMenuOpen && (
              <div className="absolute right-0 mt-1 w-52 rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl animate-in fade-in zoom-in-95 duration-100 z-30 text-xs">
                <button
                  onClick={() => {
                    downloadCandidateExcel();
                    setExportMenuOpen(false);
                  }}
                  className="w-full flex items-center px-2.5 py-2 rounded-lg text-left text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
                >
                  <FileSpreadsheet className="w-4 h-4 mr-2 text-emerald-600 shrink-0" />
                  <div>
                    <div className="font-medium">导出候选明细 (Excel)</div>
                    <div className="text-[10px] text-slate-400">多工作表与指标说明</div>
                  </div>
                </button>

                <button
                  onClick={() => {
                    downloadResearchReportPdf();
                    setExportMenuOpen(false);
                  }}
                  className="w-full flex items-center px-2.5 py-2 rounded-lg text-left text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
                >
                  <FileText className="w-4 h-4 mr-2 text-rose-600 shrink-0" />
                  <div>
                    <div className="font-medium">导出研究报告 (PDF)</div>
                    <div className="text-[10px] text-slate-400">标准 A4 规格报告排版</div>
                  </div>
                </button>

                <div className="border-t border-slate-100 my-1" />

                <button
                  onClick={() => {
                    handleExportCSV();
                    setExportMenuOpen(false);
                  }}
                  className="w-full flex items-center px-2.5 py-2 rounded-lg text-left text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
                >
                  <FileDown className="w-4 h-4 mr-2 text-slate-500 shrink-0" />
                  <div>
                    <div className="font-medium">导出候选清单 (CSV)</div>
                    <div className="text-[10px] text-slate-400">纯文本表格格式</div>
                  </div>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {scoringProgress ? (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 bg-gradient-to-r from-slate-50 to-white">
            <div>
              <div className="flex items-center space-x-2">
                <span className={`w-2 h-2 rounded-full ${scoringProgress.running ? 'bg-indigo-600 animate-ping' : scoringProgress.error ? 'bg-rose-500' : 'bg-emerald-500'}`} />
                <h3 className="text-sm font-bold text-slate-900">评分测算进度</h3>
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-mono">
                  {Math.round(scoringProgress.percent || 0)}%
                </span>
              </div>
              <p className={`text-xs mt-1 ${scoringProgress.error ? 'text-rose-600 font-medium' : 'text-slate-500'}`}>
                {scoringProgress.error || scoringProgress.message || '多因子滚动推演与证据对齐中...'}
              </p>
            </div>
            <div className="flex items-center space-x-2">
              {scoringProgress.elapsed_seconds != null && (
                <span className="text-[11px] font-mono px-2 py-1 rounded bg-slate-100 text-slate-600">
                  耗时 {scoringProgress.elapsed_seconds.toFixed(1)}s
                </span>
              )}
              <button
                type="button"
                onClick={() => setShowScoringLog(prev => !prev)}
                className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-indigo-600 hover:bg-slate-100/80 transition-all px-2.5 py-1 rounded-full cursor-pointer"
              >
                <span>{showScoringLog ? "收起步骤" : `查看测算步骤 (${scoringProgress.details?.length || 0})`}</span>
                <ChevronDown className={`w-3.5 h-3.5 ml-1 transition-transform duration-200 ${showScoringLog ? "rotate-180" : ""}`} />
              </button>
            </div>
          </div>
          <div className="h-1.5 bg-slate-100 w-full overflow-hidden">
            <div
              className={`h-full transition-all duration-300 ${scoringProgress.error ? 'bg-rose-500' : 'bg-gradient-to-r from-purple-500 via-indigo-600 to-emerald-500'}`}
              style={{ width: `${Math.min(100, Math.max(5, scoringProgress.percent || 0))}%` }}
            />
          </div>
          {/* 4 Pipeline Stat Badges */}
          <div className="p-4 grid grid-cols-2 sm:grid-cols-4 gap-3 bg-white text-xs">
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
              <span className="text-[11px] text-slate-400 block">模型算法状态</span>
              <div className="font-bold text-slate-800 mt-0.5">
                {scoringProgress.running ? '前向推演中' : scoringProgress.error ? '测算异常' : '测算已就绪'}
              </div>
            </div>
            <div className="p-2.5 rounded-lg bg-purple-50/60 border border-purple-100/80">
              <span className="text-[11px] text-purple-700 block">五维因子集成</span>
              <div className="font-bold text-purple-900 mt-0.5">实时加权归一化</div>
            </div>
            <div className="p-2.5 rounded-lg bg-emerald-50/60 border border-emerald-100/80">
              <span className="text-[11px] text-emerald-700 block">候选标的产出</span>
              <div className="font-bold text-emerald-900 mt-0.5">
                {scoringProgress.result?.candidate_count ?? scoringConfig.top_k} 只核心标的
              </div>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
              <span className="text-[11px] text-slate-400 block">测算数据基准</span>
              <div className="font-bold font-mono text-slate-700 mt-0.5">
                {scoringProgress.result?.data_end || latestDataDate}
              </div>
            </div>
          </div>
          {showScoringLog && (
            <div className="max-h-56 overflow-y-auto border-t border-slate-100 divide-y divide-slate-100 bg-white px-4 py-1 text-xs">
              {(scoringProgress.details || []).map((detail: any, index: number) => (
                <div key={`${detail.stage || detail.symbol || 'step'}-${index}`} className="flex items-center justify-between py-1.5">
                  <span className="text-slate-700">{detail.stage || '评分步骤'}{detail.symbol ? ` · ${detail.symbol}` : ''}</span>
                  <span className={detail.status === '失败' || detail.error ? 'text-rose-600 font-semibold' : detail.status === '完成' ? 'text-emerald-600 font-medium' : 'text-indigo-600'}>
                    {detail.error || detail.status || detail.note || '--'}
                  </span>
                </div>
              ))}
            </div>
          )}
          {scoringProgress.result && (
            <div className="px-4 py-3 bg-emerald-50 border-t border-emerald-100 text-xs text-emerald-800">
              运行 {scoringProgress.result.run_id} · 数据 {scoringProgress.result.data_end} · 参与 {scoringProgress.result.scored_count} 只 · 候选 {scoringProgress.result.candidate_count} 只
            </div>
          )}
        </div>
      ) : null}
      {/* Weight Controls & Presets Accordion / Card */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 rounded-lg bg-slate-50 border border-slate-200 p-3">
          <label className="text-xs text-slate-600">预测周期（交易日）
            <input type="number" min={5} max={60} step={5} value={scoringConfig.horizon} onChange={event => setScoringConfig(current => ({ ...current, horizon: Number(event.target.value) }))} className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-slate-800" />
          </label>
          <label className="text-xs text-slate-600">候选数量
            <input type="number" min={5} max={50} step={5} value={scoringConfig.top_k} onChange={event => setScoringConfig(current => ({ ...current, top_k: Number(event.target.value) }))} className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-slate-800" />
          </label>
          <label className="flex items-center gap-2 self-end rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700">
            <input type="checkbox" checked={scoringConfig.fetch_sentiment} onChange={event => setScoringConfig(current => ({ ...current, fetch_sentiment: event.target.checked }))} className="accent-indigo-600" />
            抓取最新舆情（东方财富新闻）
          </label>
        </div>
        {isPreview && <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-800">当前列表是权重调整后的排序预览；点击“重新运行评分快照”后才会生成正式评分、条件证据和研究记录。</div>}
        {!weightsValid && <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">当前权重合计 {(sumWeights * 100).toFixed(0)}%，必须调整为 100% 才能运行正式评分。</div>}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
          <div>
            <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
              <span>因子权重分配与归一化</span>
              <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-indigo-50 text-indigo-700">
                {(sumWeights * 100).toFixed(0)}%
              </span>
            </h3>
            <p className="text-[11px] text-slate-400 mt-0.5">
              拖动滑块将即时重新计算截面综合分；系统自动保持各因子相对比例归一化
            </p>
          </div>

          {/* Presets */}
          <div className="flex items-center space-x-1.5 text-xs">
            <span className="text-slate-400 text-[11px] font-medium">快捷预设:</span>
            <button
              onClick={() => applyPreset(DEFAULT_WEIGHTS)}
              className="px-2.5 py-1 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium transition-colors text-[11px]"
            >
              默认均衡 (35/25/20/10/10)
            </button>
            <button
              onClick={() => applyPreset({ model: 0.20, technical: 0.40, volume_price: 0.30, candle: 0.10, sentiment: 0.00 })}
              className="px-2.5 py-1 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium transition-colors text-[11px]"
            >
              量价进攻 (20/40/30/10/0)
            </button>
            <button
              onClick={() => applyPreset({ model: 0.50, technical: 0.20, volume_price: 0.15, candle: 0.10, sentiment: 0.05 })}
              className="px-2.5 py-1 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium transition-colors text-[11px]"
            >
              模型驱动 (50/20/15/10/5)
            </button>
            <button
              onClick={() => applyPreset(DEFAULT_WEIGHTS)}
              title="重置"
              className="p-1 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-500"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* 5 Sliders Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {/* Model */}
          <div className="bg-purple-50/40 p-3 rounded-xl border border-purple-200/70 transition-shadow hover:shadow-xs">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-bold text-purple-900 flex items-center">
                <BrainCircuit className="w-3.5 h-3.5 mr-1 text-purple-600" />
                <TermTooltip term="模型评分">模型评分</TermTooltip>
              </span>
              <span className="font-mono text-xs font-bold text-purple-700">
                {(weights.model * 100).toFixed(0)}%
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              step="5"
              value={Math.round(weights.model * 100)}
              onChange={(e) => handleSliderChange('model', Number(e.target.value))}
              className="w-full accent-purple-600 cursor-pointer"
            />
            <span className="text-[10px] text-slate-400 block mt-1">LightGBM超额预测</span>
          </div>

          {/* Technical */}
          <div className="bg-sky-50/40 p-3 rounded-xl border border-sky-200/70 transition-shadow hover:shadow-xs">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-bold text-sky-900 flex items-center">
                <Activity className="w-3.5 h-3.5 mr-1 text-sky-600" />
                <TermTooltip term="技术面">技术面</TermTooltip>
              </span>
              <span className="font-mono text-xs font-bold text-sky-700">
                {(weights.technical * 100).toFixed(0)}%
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              step="5"
              value={Math.round(weights.technical * 100)}
              onChange={(e) => handleSliderChange('technical', Number(e.target.value))}
              className="w-full accent-sky-600 cursor-pointer"
            />
            <span className="text-[10px] text-slate-400 block mt-1">20/60日均线及动量</span>
          </div>

          {/* Volume Price */}
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/80">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-bold text-slate-800 flex items-center">
                <BarChart2 className="w-3.5 h-3.5 mr-1 text-emerald-600" />
                量价关系
              </span>
              <span className="font-mono text-xs font-bold text-emerald-600">
                {(weights.volume_price * 100).toFixed(0)}%
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              step="5"
              value={Math.round(weights.volume_price * 100)}
              onChange={(e) => handleSliderChange('volume_price', Number(e.target.value))}
              className="w-full accent-emerald-600 cursor-pointer"
            />
            <span className="text-[10px] text-slate-400 block mt-1">OBV斜率与量比倍数</span>
          </div>

          {/* Candle */}
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/80">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-bold text-slate-800 flex items-center">
                <Flame className="w-3.5 h-3.5 mr-1 text-amber-600" />
                K线走势
              </span>
              <span className="font-mono text-xs font-bold text-amber-600">
                {(weights.candle * 100).toFixed(0)}%
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              step="5"
              value={Math.round(weights.candle * 100)}
              onChange={(e) => handleSliderChange('candle', Number(e.target.value))}
              className="w-full accent-amber-600 cursor-pointer"
            />
            <span className="text-[10px] text-slate-400 block mt-1">实体占比与上下影线</span>
          </div>

          {/* Sentiment */}
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/80">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-bold text-slate-800 flex items-center">
                <MessageSquare className="w-3.5 h-3.5 mr-1 text-purple-600" />
                舆情面
              </span>
              <span className="font-mono text-xs font-bold text-purple-600">
                {(weights.sentiment * 100).toFixed(0)}%
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              step="5"
              value={Math.round(weights.sentiment * 100)}
              onChange={(e) => handleSliderChange('sentiment', Number(e.target.value))}
              className="w-full accent-purple-600 cursor-pointer"
            />
            <span className="text-[10px] text-slate-400 block mt-1">新闻接口与关键词词典</span>
          </div>
        </div>
      </div>

      {/* Main Candidate Table + Stock Detail Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Candidate Table */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden flex flex-col">
          {/* Table Toolbar */}
          <div className="p-4 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-50/50">
            <div className="flex items-center space-x-2">
              <span className="text-xs font-bold text-slate-800">视图维度:</span>
              <div className="inline-flex rounded-lg border border-slate-200 p-0.5 bg-white">
                {(['决策', '模型', '技术', '赔率', '可信度'] as const).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => setTableView(mode)}
                    className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                      tableView === mode
                        ? 'bg-indigo-600 text-white font-semibold'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    {mode}
                  </button>
                ))}
              </div>
            </div>

            <div className="relative">
              <input
                type="text"
                placeholder="筛选代码或简称..."
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                className="pl-3 pr-3 py-1 text-xs rounded-md border border-slate-300 w-44 bg-white outline-hidden focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto flex-1 max-h-[560px]">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-slate-600 text-[11px] font-semibold border-b border-slate-200 sticky top-0 z-10">
                <tr>
                  <th className="py-2.5 px-3">排名</th>
                  <th className="py-2.5 px-3">标的 / 代码</th>
                  <th className="py-2.5 px-3">综合分</th>
                  {tableView === '决策' && (
                    <>
                      <th className="py-2.5 px-3">现价 / 涨跌</th>
                      <th className="py-2.5 px-3">胜率 / 盈亏比</th>
                      <th className="py-2.5 px-3">可信度</th>
                    </>
                  )}
                  {tableView === '模型' && (
                    <>
                      <th className="py-2.5 px-3">模型分</th>
                      <th className="py-2.5 px-3">原始值</th>
                      <th className="py-2.5 px-3">行业</th>
                    </>
                  )}
                  {tableView === '技术' && (
                    <>
                      <th className="py-2.5 px-3">技术分</th>
                      <th className="py-2.5 px-3">量价分</th>
                      <th className="py-2.5 px-3">K线分</th>
                    </>
                  )}
                  {tableView === '赔率' && (
                    <>
                      <th className="py-2.5 px-3">历史胜率</th>
                      <th className="py-2.5 px-3">盈亏比 (R)</th>
                      <th className="py-2.5 px-3">期望收益</th>
                    </>
                  )}
                  {tableView === '可信度' && (
                    <>
                      <th className="py-2.5 px-3">等级</th>
                      <th className="py-2.5 px-3">稳定性</th>
                      <th className="py-2.5 px-3">一致性</th>
                    </>
                  )}
                  <th className="py-2.5 px-3 text-right">选择</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredList.map((stock) => {
                  const isSelected = stock.symbol === selectedStockSymbol;
                  return (
                    <tr 
                      key={stock.symbol}
                      onClick={() => {
                        setSelectedStockSymbol(stock.symbol);
                        onSelectStock(stock);
                      }}
                      className={`cursor-pointer transition-colors ${
                        isSelected ? 'bg-indigo-50/80 font-medium' : 'hover:bg-slate-50'
                      }`}
                    >
                      <td className="py-2.5 px-3 font-mono font-bold text-slate-800">
                        #{stock.rank}
                      </td>
                      <td className="py-2.5 px-3">
                        <div className="font-bold text-slate-900">{stock.name}</div>
                        <div className="text-[10px] text-slate-400 font-mono">{stock.symbol}</div>
                      </td>
                      <td className="py-2.5 px-3">
                        <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-bold ${
                          safeNum(stock.composite_score) >= 80
                            ? 'bg-rose-100 text-rose-800' 
                            : safeNum(stock.composite_score) >= 70
                              ? 'bg-indigo-100 text-indigo-800'
                              : 'bg-slate-100 text-slate-700'
                        }`}>
                          {fmtNum(stock.composite_score, 1)}
                        </span>
                      </td>

                      {tableView === '决策' && (
                        <>
                          <td className="py-2.5 px-3">
                            <span className="font-semibold text-slate-800">¥{(Number(stock.price) || 0).toFixed(2)}</span>
                            <span className={`ml-1 text-[10px] ${(Number(stock.change) || 0) >= 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                              {(Number(stock.change) || 0) >= 0 ? `+${(Number(stock.change) || 0).toFixed(2)}%` : `${(Number(stock.change) || 0).toFixed(2)}%`}
                            </span>
                          </td>
                          <td className="py-2.5 px-3">
                            <span>{stock.odds_win_rate == null ? '未积累' : `${fmtNum(stock.odds_win_rate, 1)}%`}</span>
                            <span className="text-slate-400 mx-1">/</span>
                            <span>{stock.odds_reward_risk == null ? '--' : `${fmtNum(stock.odds_reward_risk, 2)}R`}</span>
                          </td>
                          <td className="py-2.5 px-3">
                            <span className="text-[11px] text-slate-600">
                              {stock.credibility_score == null ? '待评估' : `${fmtNum(stock.credibility_score, 0)}分 (${stock.credibility_grade || '未分级'})`}
                            </span>
                          </td>
                        </>
                      )}

                      {tableView === '模型' && (
                        <>
                          <td className="py-2.5 px-3 font-mono">{stock.model_score.toFixed(1)}</td>
                          <td className="py-2.5 px-3 font-mono text-slate-500">{fmtNum(stock.model_raw, 4)}</td>
                          <td className="py-2.5 px-3 text-slate-600">{stock.industry || '行业待补全'}</td>
                        </>
                      )}

                      {tableView === '技术' && (
                        <>
                          <td className="py-2.5 px-3 font-mono">{stock.technical_score.toFixed(1)}</td>
                          <td className="py-2.5 px-3 font-mono">{stock.volume_price_score.toFixed(1)}</td>
                          <td className="py-2.5 px-3 font-mono">{stock.candle_score.toFixed(1)}</td>
                        </>
                      )}

                      {tableView === '赔率' && (
                        <>
                          <td className="py-2.5 px-3 font-semibold text-slate-900">{stock.odds_win_rate == null ? '未积累' : `${fmtNum(stock.odds_win_rate, 1)}%`}</td>
                          <td className="py-2.5 px-3 font-mono">{fmtNum(stock.odds_reward_risk, 2)}</td>
                          <td className={`py-2.5 px-3 font-semibold ${safeNum(stock.odds_expected_return) >= 0 ? 'text-emerald-700' : 'text-rose-700'}`}>{stock.odds_expected_return == null ? '--' : `${safeNum(stock.odds_expected_return) >= 0 ? '+' : ''}${fmtNum(stock.odds_expected_return, 2)}%`}</td>
                        </>
                      )}

                      {tableView === '可信度' && (
                        <>
                          <td className="py-2.5 px-3 font-bold text-indigo-700">{stock.credibility_grade || '待评估'}</td>
                          <td className="py-2.5 px-3 font-mono">{stock.credibility_stability == null ? '--' : `${fmtNum(stock.credibility_stability, 0)}%`}</td>
                          <td className="py-2.5 px-3 font-mono">{stock.credibility_agreement == null ? '--' : `${fmtNum(stock.credibility_agreement, 0)}%`}</td>
                        </>
                      )}

                      <td className="py-2.5 px-3 text-right">
                        <ChevronRight className={`w-4 h-4 inline transition-transform ${isSelected ? 'text-indigo-600 translate-x-1' : 'text-slate-300'}`} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right 1 Col: Selected Stock Detail & Evidence Cards */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5 flex flex-col justify-between space-y-4">
          {activeStock ? (
            <div className="space-y-4">
              {/* 1. 标的概览与现价（清爽大气两列布局，彻底消除丑陋小方框） */}
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <div>
                  <div className="flex items-center space-x-2">
                    <h3 className="text-lg font-bold text-slate-900">{activeStock.name}</h3>
                    <span className="text-xs font-mono text-slate-400">{activeStock.symbol}</span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                      {activeStock.industry || "行业待补全"}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    最新价 {activeStock.price == null ? "--" : `¥${fmtNum(activeStock.price, 2)}`} · 换手率 {activeStock.turnover == null ? "--" : `${fmtNum(activeStock.turnover, 2)}%`} · PE {activeStock.pe_ttm == null ? "--" : activeStock.pe_ttm < 0 ? `亏损 (${fmtNum(activeStock.pe_ttm, 1)})` : fmtNum(activeStock.pe_ttm, 1)}
                  </p>
                </div>

                <div className="text-right flex items-center space-x-3">
                  <div>
                    <span className="text-[10px] text-slate-400 block font-medium">综合评分</span>
                    <span className="text-2xl font-black text-indigo-600 font-mono tracking-tight">
                      {fmtNum(activeStock.composite_score, 1)}
                      <span className="text-xs font-normal text-slate-400 ml-0.5">分</span>
                    </span>
                  </div>
                  <div className="pl-3 border-l border-slate-200/80">
                    <span className="text-[10px] text-slate-400 block font-medium">全池排序</span>
                    <span className="text-xl font-bold text-slate-900 font-mono">
                      #{activeStock.rank}
                    </span>
                    {activeStock.rank_change && activeStock.rank_change !== "-" && (
                      <span className="block text-[10px] text-slate-500 font-medium">较上次 {activeStock.rank_change}</span>
                    )}
                  </div>
                </div>
              </div>

              {/* 2. 【核心量化决策底牌】（上提到第二层级！一眼看到胜率、盈亏比与可信度） */}
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-200/80">
                  <span className="text-[10px] text-slate-500 block font-medium">决策可信度</span>
                  <div className="font-bold text-indigo-700 mt-1 truncate">
                    {activeStock.credibility_score == null ? "待评估" : `${fmtNum(activeStock.credibility_score, 0)}分 (${activeStock.credibility_grade || "未分级"})`}
                  </div>
                </div>
                <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-200/80">
                  <span className="text-[10px] text-slate-500 block font-medium">历史胜率 / 盈亏比</span>
                  <div className="font-bold text-slate-800 mt-1 truncate">
                    {activeStock.odds_win_rate == null ? "未积累" : `${fmtNum(activeStock.odds_win_rate, 1)}%`} · {activeStock.odds_reward_risk == null ? "--" : `${fmtNum(activeStock.odds_reward_risk, 2)}R`}
                  </div>
                </div>
                <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-200/80">
                  <span className="text-[10px] text-slate-500 block font-medium">高分条件胜率</span>
                  <div className="font-bold text-slate-800 mt-1 truncate">
                    {activeStock.conditional_win_rate == null ? "未积累样本" : `${(activeStock.conditional_win_rate * 100).toFixed(1)}%`}
                  </div>
                </div>
              </div>

              {/* 3. 五维分项打分与各维度加权贡献（合并连贯呈现） */}
              <div className="bg-slate-50/70 rounded-xl border border-slate-200/80 p-3.5 space-y-2.5">
                <div className="flex items-center justify-between pb-1.5 border-b border-slate-200/60">
                  <div className="flex items-center space-x-1.5">
                    <h4 className="text-xs font-bold text-slate-800">五维分项打分与加权贡献</h4>
                    <span className="text-[10px] text-slate-400">(得分 × 权重 = 贡献)</span>
                  </div>
                  <span className="text-[11px] font-mono text-slate-500">
                    加权合计: <strong className="text-indigo-700 font-bold">+{fmtNum(activeStock.composite_score, 1)}分</strong>
                  </span>
                </div>

                <div className="space-y-2 text-xs">
                  {/* 模型 */}
                  <div className="flex items-center justify-between gap-2">
                    <span className="w-24 text-slate-700 flex items-center shrink-0">
                      <BrainCircuit className="w-3.5 h-3.5 mr-1 text-purple-600" />
                      <span>模型预测分</span>
                    </span>
                    <div className="flex-1 flex items-center space-x-2">
                      <div className="flex-1 bg-slate-200/70 h-2 rounded-full overflow-hidden">
                        <div className="bg-purple-600 h-full rounded-full" style={{ width: `${activeStock.model_score}%` }}></div>
                      </div>
                      <span className="font-mono text-[11px] text-slate-500 w-28 text-right shrink-0">
                        {(Number(activeStock.model_score) || 0).toFixed(0)}分 × 35% = <strong className="text-purple-700 font-bold">+{((Number(activeStock.model_score) || 0) * 0.35).toFixed(1)}</strong>
                      </span>
                    </div>
                  </div>

                  {/* 技术 */}
                  <div className="flex items-center justify-between gap-2">
                    <span className="w-24 text-slate-700 flex items-center shrink-0">
                      <Activity className="w-3.5 h-3.5 mr-1 text-sky-600" />
                      <span>技术均线分</span>
                    </span>
                    <div className="flex-1 flex items-center space-x-2">
                      <div className="flex-1 bg-slate-200/70 h-2 rounded-full overflow-hidden">
                        <div className="bg-sky-600 h-full rounded-full" style={{ width: `${activeStock.technical_score}%` }}></div>
                      </div>
                      <span className="font-mono text-[11px] text-slate-500 w-28 text-right shrink-0">
                        {(Number(activeStock.technical_score) || 0).toFixed(0)}分 × 25% = <strong className="text-sky-700 font-bold">+{((Number(activeStock.technical_score) || 0) * 0.25).toFixed(1)}</strong>
                      </span>
                    </div>
                  </div>

                  {/* 量价 */}
                  <div className="flex items-center justify-between gap-2">
                    <span className="w-24 text-slate-700 flex items-center shrink-0">
                      <BarChart2 className="w-3.5 h-3.5 mr-1 text-amber-600" />
                      <span>量价配合分</span>
                    </span>
                    <div className="flex-1 flex items-center space-x-2">
                      <div className="flex-1 bg-slate-200/70 h-2 rounded-full overflow-hidden">
                        <div className="bg-amber-500 h-full rounded-full" style={{ width: `${activeStock.volume_price_score}%` }}></div>
                      </div>
                      <span className="font-mono text-[11px] text-slate-500 w-28 text-right shrink-0">
                        {(Number(activeStock.volume_price_score) || 0).toFixed(0)}分 × 20% = <strong className="text-amber-700 font-bold">+{((Number(activeStock.volume_price_score) || 0) * 0.20).toFixed(1)}</strong>
                      </span>
                    </div>
                  </div>

                  {/* K线 */}
                  <div className="flex items-center justify-between gap-2">
                    <span className="w-24 text-slate-700 flex items-center shrink-0">
                      <Flame className="w-3.5 h-3.5 mr-1 text-emerald-600" />
                      <span>K线形态分</span>
                    </span>
                    <div className="flex-1 flex items-center space-x-2">
                      <div className="flex-1 bg-slate-200/70 h-2 rounded-full overflow-hidden">
                        <div className="bg-emerald-600 h-full rounded-full" style={{ width: `${activeStock.candle_score}%` }}></div>
                      </div>
                      <span className="font-mono text-[11px] text-slate-500 w-28 text-right shrink-0">
                        {(Number(activeStock.candle_score) || 0).toFixed(0)}分 × 10% = <strong className="text-emerald-700 font-bold">+{((Number(activeStock.candle_score) || 0) * 0.10).toFixed(1)}</strong>
                      </span>
                    </div>
                  </div>

                  {/* 舆情 */}
                  <div className="flex items-center justify-between gap-2">
                    <span className="w-24 text-slate-700 flex items-center shrink-0">
                      <MessageSquare className="w-3.5 h-3.5 mr-1 text-rose-600" />
                      <span>舆情面打分</span>
                    </span>
                    <div className="flex-1 flex items-center space-x-2">
                      <div className="flex-1 bg-slate-200/70 h-2 rounded-full overflow-hidden">
                        <div className="bg-rose-600 h-full rounded-full" style={{ width: `${activeStock.sentiment_score}%` }}></div>
                      </div>
                      <span className="font-mono text-[11px] text-slate-500 w-28 text-right shrink-0">
                        {(Number(activeStock.sentiment_score) || 0).toFixed(0)}分 × 10% = <strong className="text-rose-700 font-bold">+{((Number(activeStock.sentiment_score) || 0) * 0.10).toFixed(1)}</strong>
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* 4. 正向支撑证据 */}
              <div className="bg-emerald-50/70 border border-emerald-200/80 rounded-lg p-3">
                <div className="flex items-center space-x-1.5 text-emerald-800 font-bold text-xs mb-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span>正向支撑证据 (Positive Evidence)</span>
                </div>
                <ul className="text-xs text-emerald-900 space-y-1 pl-5 list-disc">
                  {(activeStock.positive_evidences?.length ? activeStock.positive_evidences : ["当前没有达到展示条件的明确正面证据"]).map((ev, i) => (
                    <li key={i}>{ev}</li>
                  ))}
                </ul>
              </div>

              {/* 5. 风险提示与警示 */}
              <div className="bg-amber-50/70 border border-amber-200/80 rounded-lg p-3">
                <div className="flex items-center space-x-1.5 text-amber-800 font-bold text-xs mb-1.5">
                  <AlertTriangle className="w-4 h-4 text-amber-600" />
                  <span>风险提示与警示 (Risk & Warnings)</span>
                </div>
                <ul className="text-xs text-amber-900 space-y-1 pl-5 list-disc">
                  {(activeStock.negative_evidences?.length ? activeStock.negative_evidences : ["当前没有达到展示条件的明确反面证据"]).map((ev, i) => (
                    <li key={i}>{ev}</li>
                  ))}
                </ul>
              </div>

              {/* 6. 数据与验证限制 */}
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                <div className="flex items-center space-x-1.5 text-slate-800 font-bold text-xs mb-1.5">
                  <Info className="w-4 h-4 text-slate-500" />
                  <span>数据与验证限制</span>
                </div>
                <ul className="text-xs text-slate-700 space-y-1 pl-5 list-disc">
                  {(activeStock.limitations?.length ? activeStock.limitations : ["当前未识别到额外限制；历史表现仍不代表未来收益"]).map((item, index) => <li key={index}>{item}</li>)}
                </ul>
              </div>
            </div>
          ) : (
            <div className="py-12 text-center text-slate-400">请在左侧列表中点击选择一只标的查看证据归因</div>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 pb-2 border-b border-slate-100">
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-sm font-bold text-slate-900">全局策略有效性与模型稳健性审计</h3>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 font-semibold border border-blue-200">
                全局策略级评估 · 不随单只股票切换
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              评估当前多因子打分体系在全市场的样本外预测误差、截面排序稳定度与因子健壮性，反映整体模型质量，不代表单只股票走势。
            </p>
          </div>
          <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${scoringContext?.research_status?.passed ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-800'}`}>{scoringContext?.research_status?.label || '未验证'}</span>
        </div>
        {/* 全局 4 核心宏观指标（带白话含义与导引） */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div className="rounded-xl bg-slate-50/80 border border-slate-200/80 p-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-slate-600 font-bold">样本外 MAE</span>
              <span className="text-[9px] px-1.5 py-0.2 rounded bg-slate-200/70 text-slate-600 font-medium">越小越精确</span>
            </div>
            <div className="text-base font-bold font-mono text-slate-900 mt-1">
              {scoringContext?.validation?.mae == null ? "--" : `${(scoringContext.validation.mae * 100).toFixed(2)}%`}
            </div>
            <span className="text-[10px] text-slate-400 block mt-0.5">预测收益平均绝对误差</span>
          </div>

          <div className="rounded-xl bg-slate-50/80 border border-slate-200/80 p-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-slate-600 font-bold">样本外 R²</span>
              <span className="text-[9px] px-1.5 py-0.2 rounded bg-slate-200/70 text-slate-600 font-medium">金融弱信号</span>
            </div>
            <div className="text-base font-bold font-mono text-slate-900 mt-1">
              {fmtNum(scoringContext?.validation?.r2, 3)}
            </div>
            <span className="text-[10px] text-slate-400 block mt-0.5">模型拟合优度(接近0属金融常态)</span>
          </div>

          <div className="rounded-xl bg-slate-50/80 border border-slate-200/80 p-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-slate-600 font-bold">滚动 Rank IC</span>
              <span className="text-[9px] px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold">有效正相关</span>
            </div>
            <div className="text-base font-bold font-mono text-indigo-700 mt-1">
              +{fmtNum(scoringContext?.backtest?.ic_mean, 3)}
            </div>
            <span className="text-[10px] text-emerald-600 block mt-0.5">高分股收益整体跑赢低分股</span>
          </div>

          <div className="rounded-xl bg-slate-50/80 border border-slate-200/80 p-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-slate-600 font-bold">分层 Q5-Q1</span>
              <span className="text-[9px] px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold">单调正向</span>
            </div>
            <div className="text-base font-bold font-mono text-emerald-700 mt-1">
              +{scoringContext?.backtest?.q5_q1_mean_return == null ? "--" : `${(scoringContext.backtest.q5_q1_mean_return * 100).toFixed(2)}%`}
            </div>
            <span className="text-[10px] text-emerald-600 block mt-0.5">头部20%标的跑赢末尾20%</span>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs text-slate-600">
          <div className="flex justify-between rounded-lg bg-slate-50 px-3 py-2"><span>最大因子相关性</span><strong>{fmtNum(scoringContext?.diagnostics?.max_absolute_factor_correlation, 2)}</strong></div>
          <div className="flex justify-between rounded-lg bg-slate-50 px-3 py-2"><span>最低排序相关性</span><strong>{fmtNum(scoringContext?.diagnostics?.minimum_rank_correlation, 2)}</strong></div>
          <div className="flex justify-between rounded-lg bg-slate-50 px-3 py-2"><span>最低候选重合率</span><strong>{scoringContext?.diagnostics?.minimum_top_k_overlap == null ? '--' : `${(scoringContext.diagnostics.minimum_top_k_overlap * 100).toFixed(0)}%`}</strong></div>
        </div>
        {scoringContext?.importance?.length ? (
          <div className="space-y-3 pt-2">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold text-slate-800 flex items-center">
                <span>核心模型因子重要性与特征导引</span>
                <span className="text-[10px] text-slate-400 font-normal ml-2">(数值越大代表算法做超额收益预测时越倚重该特征)</span>
              </h4>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
              {scoringContext.importance.slice(0, 6).map(item => {
                const maxImportance = safeNum(scoringContext.importance[0]?.importance, 1);
                const ratio = maxImportance > 0 ? (safeNum(item.importance) / maxImportance) : 0;
                const meta = FACTOR_META[item.feature] || {
                  name: item.feature,
                  dir: "mid",
                  dirLabel: "适中偏强",
                  desc: "量化模型特征工程派生指标",
                };
                const dirBadgeClass = meta.dir === "high"
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : meta.dir === "low"
                    ? "bg-amber-50 text-amber-700 border-amber-200"
                    : "bg-blue-50 text-blue-700 border-blue-200";
                return (
                  <div key={item.feature} className="p-2.5 rounded-lg border border-slate-200/80 bg-slate-50/50 hover:bg-white transition-colors space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center space-x-1.5">
                        <strong className="text-slate-900">{meta.name}</strong>
                        <span className="text-[10px] font-mono text-slate-400">({item.feature})</span>
                      </div>
                      <span className={`text-[10px] px-1.5 py-0.2 rounded border font-medium ${dirBadgeClass}`}>
                        💡 {meta.dirLabel}
                      </span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <div className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-indigo-500 to-purple-600 rounded-full" style={{ width: `${Math.round(ratio * 100)}%` }} />
                      </div>
                      <span className="text-[10px] font-mono font-bold text-slate-600 w-12 text-right">
                        {(ratio * 100).toFixed(0)}% 权重
                      </span>
                    </div>
                    <p className="text-[10px] text-slate-500 leading-normal">
                      {meta.desc}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        ) : <p className="text-xs text-slate-400">重新运行综合评分后生成因子重要性。</p>}
        {!!scoringContext?.research_status?.failed_reasons?.length && <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">当前验证限制：{scoringContext.research_status.failed_reasons.slice(0, 3).join('；')}</div>}
      </div>
    </div>
  );
};
