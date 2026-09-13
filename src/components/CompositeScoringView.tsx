
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
import React, { useState, useMemo } from 'react';
import { 
  Sliders, 
  RotateCcw, 
  BrainCircuit, 
  Activity, 
  BarChart2, 
  Flame, 
  MessageSquare,
  Sparkles,
  Award,
  ChevronRight,
  ShieldCheck,
  FileSpreadsheet,
  Play,
  CheckCircle2,
  TrendingUp,
  Info,
  Calendar,
  RefreshCw,
  Clock,
  AlertTriangle
} from 'lucide-react';
import { ScoredStock, WeightConfig } from '../types';
import { downloadCandidateExcel, downloadResearchReportPdf } from '../api/client';
import { FileText, Download } from 'lucide-react';
import { DEFAULT_WEIGHTS } from '../utils/scoring';

interface CompositeScoringViewProps {
  weights: WeightConfig;
  onUpdateWeights: (weights: WeightConfig) => void;
  stocks: ScoredStock[];
  onSelectStock: (stock: ScoredStock) => void;
  onRunScoring: () => void;
  isScoringRunning?: boolean;
  onNavigateToData?: () => void;
}

export const CompositeScoringView: React.FC<CompositeScoringViewProps> = ({
  weights,
  onUpdateWeights,
  stocks,
  onSelectStock,
  onRunScoring,
  isScoringRunning = false,
  onNavigateToData,
}) => {
  const [selectedStockSymbol, setSelectedStockSymbol] = useState<string>(stocks[0]?.symbol || '605277');
  const [tableView, setTableView] = useState<'决策' | '模型' | '技术' | '赔率' | '可信度'>('决策');
  const [searchFilter, setSearchFilter] = useState('');

  const sumWeights = 
    weights.model + 
    weights.technical + 
    weights.volume_price + 
    weights.candle + 
    weights.sentiment;

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
    const normModel = weights.model / sumWeights;
    const normTech = weights.technical / sumWeights;
    const normVP = weights.volume_price / sumWeights;
    const normCandle = weights.candle / sumWeights;
    const normSent = weights.sentiment / sumWeights;

    const list = stocks.map((s) => {
      const dynScore = 
        s.model_score * normModel +
        s.technical_score * normTech +
        s.volume_price_score * normVP +
        s.candle_score * normCandle +
        s.sentiment_score * normSent;

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
      s.industry.toLowerCase().includes(q)
    );
  }, [scoredList, searchFilter]);

  const activeStock = useMemo(() => {
    return scoredList.find(s => s.symbol === selectedStockSymbol) || scoredList[0] || null;
  }, [scoredList, selectedStockSymbol]);

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
      s.credibility_score || 40,
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
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-indigo-600 text-xs font-bold uppercase tracking-wider mb-1">
            <Sliders className="w-4 h-4" />
            <span>第三步 · 综合多因子评分与候选研判</span>
          </div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            五维因子权重动态配置与透明归因
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            模型(35%) + 技术(25%) + 量价(20%) + K线(10%) + 舆情(10%)，实时归一化计算，自动更新截面排位
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {/* Micro Data Provenance Badge */}
          <div className="inline-flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-600">
            <Calendar className="w-3.5 h-3.5 text-slate-400" />
            <span>评分截面: <strong className="font-mono text-slate-800">2026-09-04</strong></span>
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-50 text-amber-700 border border-amber-200" title="本地数据最新交易日为 2026-09-04">
              距今 9 天
            </span>
            {onNavigateToData && (
              <button
                onClick={onNavigateToData}
                className="text-[11px] text-indigo-600 hover:text-indigo-800 font-medium hover:underline ml-0.5 cursor-pointer"
                title="前往股票池与数据中心进行增量更新"
              >
                去更新 ↗
              </button>
            )}
          </div>

          <button
            onClick={onRunScoring}
            disabled={isScoringRunning}
            className={`inline-flex items-center px-4 py-2 rounded-xl text-xs font-bold shadow-xs transition-all ${
              isScoringRunning
                ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                : 'bg-indigo-600 hover:bg-indigo-700 text-white cursor-pointer'
            }`}
          >
            <Play className={`w-3.5 h-3.5 mr-1.5 fill-current ${isScoringRunning ? 'animate-pulse' : ''}`} />
            {isScoringRunning ? '正在重新测算评分...' : '重新运行评分快照'}
          </button>

          <button
            onClick={downloadCandidateExcel}
            className="inline-flex items-center px-3.5 py-2 rounded-xl text-xs font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-300 transition-colors shadow-xs cursor-pointer"
            title="导出多工作表Excel（含候选明细及量化指标字典说明）"
          >
            <FileSpreadsheet className="w-3.5 h-3.5 mr-1 text-emerald-600" />
            导出候选明细 (Excel)
          </button>

          <button
            onClick={downloadResearchReportPdf}
            className="inline-flex items-center px-3.5 py-2 rounded-xl text-xs font-semibold bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-300 transition-colors shadow-xs cursor-pointer"
            title="导出A4规格完整量化投研报告PDF"
          >
            <FileText className="w-3.5 h-3.5 mr-1 text-rose-600" />
            导出研究报告 (PDF)
          </button>

          <button
            onClick={handleExportCSV}
            className="inline-flex items-center px-3.5 py-2 rounded-xl text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 transition-colors shadow-xs cursor-pointer"
          >
            <FileSpreadsheet className="w-3.5 h-3.5 mr-1 text-slate-500" />
            导出候选 (CSV)
          </button>
        </div>
      </div>

      {/* Weight Controls & Presets Accordion / Card */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs space-y-4">
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
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/80">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-bold text-slate-800 flex items-center">
                <BrainCircuit className="w-3.5 h-3.5 mr-1 text-indigo-600" />
                模型评分
              </span>
              <span className="font-mono text-xs font-bold text-indigo-600">
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
              className="w-full accent-indigo-600 cursor-pointer"
            />
            <span className="text-[10px] text-slate-400 block mt-1">LightGBM超额预测</span>
          </div>

          {/* Technical */}
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/80">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-bold text-slate-800 flex items-center">
                <Activity className="w-3.5 h-3.5 mr-1 text-blue-600" />
                技术面
              </span>
              <span className="font-mono text-xs font-bold text-blue-600">
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
              className="w-full accent-blue-600 cursor-pointer"
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
                          stock.composite_score >= 80 
                            ? 'bg-rose-100 text-rose-800' 
                            : stock.composite_score >= 70
                              ? 'bg-indigo-100 text-indigo-800'
                              : 'bg-slate-100 text-slate-700'
                        }`}>
                          {stock.composite_score.toFixed(1)}
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
                            <span>{stock.odds_win_rate}%</span>
                            <span className="text-slate-400 mx-1">/</span>
                            <span>{stock.odds_reward_risk}R</span>
                          </td>
                          <td className="py-2.5 px-3">
                            <span className="text-[11px] text-slate-600">
                              {stock.credibility_score?.toFixed(0) || '40'}分 ({stock.credibility_grade || '中'})
                            </span>
                          </td>
                        </>
                      )}

                      {tableView === '模型' && (
                        <>
                          <td className="py-2.5 px-3 font-mono">{stock.model_score.toFixed(1)}</td>
                          <td className="py-2.5 px-3 font-mono text-slate-500">{stock.model_raw.toFixed(4)}</td>
                          <td className="py-2.5 px-3 text-slate-600">{stock.industry}</td>
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
                          <td className="py-2.5 px-3 font-semibold text-slate-900">{stock.odds_win_rate}%</td>
                          <td className="py-2.5 px-3 font-mono">{stock.odds_reward_risk}</td>
                          <td className="py-2.5 px-3 text-emerald-700 font-semibold">+{stock.odds_expected_return}%</td>
                        </>
                      )}

                      {tableView === '可信度' && (
                        <>
                          <td className="py-2.5 px-3 font-bold text-indigo-700">{stock.credibility_grade || '中'}</td>
                          <td className="py-2.5 px-3 font-mono">{stock.credibility_stability?.toFixed(0) || '80'}%</td>
                          <td className="py-2.5 px-3 font-mono">{stock.credibility_agreement?.toFixed(0) || '75'}%</td>
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
              {/* Header Info */}
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <div>
                  <div className="flex items-center space-x-2">
                    <h3 className="text-lg font-bold text-slate-900">{activeStock.name}</h3>
                    <span className="text-xs font-mono text-slate-400">{activeStock.symbol}</span>
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-600">
                      {activeStock.industry}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5">
                    最新价 ¥{(Number(activeStock.price) || 0).toFixed(2)} · 换手率 {(Number(activeStock.turnover) || 0).toFixed(2)}% · PE {activeStock.pe_ttm != null ? Number(activeStock.pe_ttm).toFixed(1) : '--'}
                  </p>
                </div>

                <div className="text-right">
                  <span className="text-[11px] text-slate-400 block">综合排名</span>
                  <span className="text-xl font-extrabold text-indigo-600 font-mono">
                    #{activeStock.rank}
                  </span>
                </div>
              </div>

              {/* 5-Factor Score Breakdown */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-slate-700">五维分项打分</h4>
                <div className="space-y-1.5 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500 flex items-center">
                      <BrainCircuit className="w-3.5 h-3.5 mr-1 text-indigo-500" />
                      模型预测分
                    </span>
                    <div className="flex items-center space-x-2">
                      <div className="w-24 bg-slate-100 h-1.5 rounded-full overflow-hidden">
                        <div className="bg-indigo-600 h-full" style={{ width: `${activeStock.model_score}%` }}></div>
                      </div>
                      <span className="font-mono font-bold text-slate-800 w-8 text-right">{(Number(activeStock.model_score) || 0).toFixed(0)}</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-slate-500 flex items-center">
                      <Activity className="w-3.5 h-3.5 mr-1 text-blue-500" />
                      技术均线分
                    </span>
                    <div className="flex items-center space-x-2">
                      <div className="w-24 bg-slate-100 h-1.5 rounded-full overflow-hidden">
                        <div className="bg-blue-600 h-full" style={{ width: `${activeStock.technical_score}%` }}></div>
                      </div>
                      <span className="font-mono font-bold text-slate-800 w-8 text-right">{(Number(activeStock.technical_score) || 0).toFixed(0)}</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-slate-500 flex items-center">
                      <BarChart2 className="w-3.5 h-3.5 mr-1 text-emerald-500" />
                      量价配合分
                    </span>
                    <div className="flex items-center space-x-2">
                      <div className="w-24 bg-slate-100 h-1.5 rounded-full overflow-hidden">
                        <div className="bg-emerald-600 h-full" style={{ width: `${activeStock.volume_price_score}%` }}></div>
                      </div>
                      <span className="font-mono font-bold text-slate-800 w-8 text-right">{(Number(activeStock.volume_price_score) || 0).toFixed(0)}</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-slate-500 flex items-center">
                      <Flame className="w-3.5 h-3.5 mr-1 text-amber-500" />
                      K线形态分
                    </span>
                    <div className="flex items-center space-x-2">
                      <div className="w-24 bg-slate-100 h-1.5 rounded-full overflow-hidden">
                        <div className="bg-amber-500 h-full" style={{ width: `${activeStock.candle_score}%` }}></div>
                      </div>
                      <span className="font-mono font-bold text-slate-800 w-8 text-right">{(Number(activeStock.candle_score) || 0).toFixed(0)}</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-slate-500 flex items-center">
                      <MessageSquare className="w-3.5 h-3.5 mr-1 text-purple-500" />
                      舆情词典分
                    </span>
                    <div className="flex items-center space-x-2">
                      <div className="w-24 bg-slate-100 h-1.5 rounded-full overflow-hidden">
                        <div className="bg-purple-600 h-full" style={{ width: `${activeStock.sentiment_score}%` }}></div>
                      </div>
                      <span className="font-mono font-bold text-slate-800 w-8 text-right">{(Number(activeStock.sentiment_score) || 0).toFixed(0)}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Positive Evidence */}
              <div className="bg-emerald-50/70 border border-emerald-200/80 rounded-lg p-3">
                <div className="flex items-center space-x-1.5 text-emerald-800 font-bold text-xs mb-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span>正向支撑证据 (Positive Evidence)</span>
                </div>
                <ul className="text-xs text-emerald-900 space-y-1 pl-5 list-disc">
                  {activeStock.positive_evidences?.map((ev, i) => (
                    <li key={i}>{ev}</li>
                  )) || <li>指标运行良好，无负面异动</li>}
                </ul>
              </div>

              {/* Negative Evidence / Warning */}
              <div className="bg-amber-50/70 border border-amber-200/80 rounded-lg p-3">
                <div className="flex items-center space-x-1.5 text-amber-800 font-bold text-xs mb-1.5">
                  <AlertTriangle className="w-4 h-4 text-amber-600" />
                  <span>风险提示与警示 (Risk & Warnings)</span>
                </div>
                <ul className="text-xs text-amber-900 space-y-1 pl-5 list-disc">
                  {activeStock.negative_evidences?.map((ev, i) => (
                    <li key={i}>{ev}</li>
                  )) || <li>未检出重大财务或违规风险信号</li>}
                </ul>
              </div>

              {/* Odds & Credibility Quick Card */}
              <div className="grid grid-cols-2 gap-2 pt-2 text-xs">
                <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                  <span className="text-[11px] text-slate-500 block">历史胜率 / 盈亏比</span>
                  <div className="font-bold text-slate-800 mt-0.5">
                    {activeStock.odds_win_rate}% · {activeStock.odds_reward_risk}R
                  </div>
                </div>
                <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                  <span className="text-[11px] text-slate-500 block">决策可信度评估</span>
                  <div className="font-bold text-indigo-700 mt-0.5">
                    {activeStock.credibility_score?.toFixed(0) || '40'}分 ({activeStock.credibility_grade || '中'})
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="py-12 text-center text-slate-400">请在左侧列表中点击选择一只标的查看证据归因</div>
          )}
        </div>
      </div>
    </div>
  );
};
