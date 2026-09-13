import React, { useState, useMemo } from 'react';
import { 
  Layers, 
  Search, 
  Trash2, 
  AlertTriangle, 
  CheckCircle2, 
  ArrowRight,
  TrendingUp,
  TrendingDown,
  Activity,
  Sliders,
  Filter,
  BarChart2,
  FileCheck
} from 'lucide-react';
import { ScoredStock } from '../types';

interface LocalStockPoolViewProps {
  stocks: ScoredStock[];
  onRemoveStock: (symbol: string) => void;
  onProceedToScoring: () => void;
}

export const LocalStockPoolView: React.FC<LocalStockPoolViewProps> = ({
  stocks,
  onRemoveStock,
  onProceedToScoring,
}) => {
  const [search, setSearch] = useState('');
  const [marketFilter, setMarketFilter] = useState<string>('ALL');
  const [sortBy, setSortBy] = useState<keyof ScoredStock>('composite_score');
  const [sortAsc, setSortAsc] = useState(false);
  const [selectedStockForDetail, setSelectedStockForDetail] = useState<ScoredStock | null>(null);

  // Filter and sort stocks
  const filteredAndSorted = useMemo(() => {
    const q = search.trim().toLowerCase();
    const result = stocks.filter((s) => {
      const matchQuery = 
        !q ||
        s.symbol.toLowerCase().includes(q) ||
        s.name.toLowerCase().includes(q) ||
        s.pinyin.toLowerCase().includes(q) ||
        s.industry.toLowerCase().includes(q);

      const matchMarket = marketFilter === 'ALL' || s.market === marketFilter;
      return matchQuery && matchMarket;
    });

    result.sort((a, b) => {
      const valA = a[sortBy];
      const valB = b[sortBy];

      if (typeof valA === 'number' && typeof valB === 'number') {
        return sortAsc ? valA - valB : valB - valA;
      }
      return sortAsc 
        ? String(valA).localeCompare(String(valB)) 
        : String(valB).localeCompare(String(valA));
    });

    return result;
  }, [stocks, search, marketFilter, sortBy, sortAsc]);

  const toggleSort = (field: keyof ScoredStock) => {
    if (sortBy === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortBy(field);
      setSortAsc(false);
    }
  };

  // Data diagnostics summary
  const diagnosticsSummary = useMemo(() => {
    let excellent = 0;
    let good = 0;
    let warning = 0;

    stocks.forEach((s) => {
      if (s.diagnostic_status === 'warning') warning++;
      else if (s.diagnostic_status === 'good') good++;
      else excellent++;
    });

    return { excellent, good, warning, total: stocks.length };
  }, [stocks]);

  return (
    <div className="space-y-6">
      {/* Step Banner */}
      <div className="bg-gradient-to-r from-indigo-900 via-blue-900 to-slate-900 text-white rounded-2xl p-6 shadow-md">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2 text-indigo-300 text-xs font-semibold uppercase tracking-wider mb-2">
              <Layers className="w-4 h-4" />
              <span>第二步 · 本地股票池 (Local Stock Pool)</span>
            </div>
            <h2 className="text-2xl font-bold tracking-tight mb-2">
              本地标的资产库与数据完整性诊断
            </h2>
            <p className="text-slate-300 text-sm max-w-2xl leading-relaxed">
              当前维护 <strong className="text-white">{stocks.length}</strong> 只本地精选标的。支持实时指标监控、停牌与量价异动核验，确认特征序列完整无误后，即可一键进入多因子综合评分。
            </p>
          </div>

          <button
            onClick={onProceedToScoring}
            className="inline-flex items-center px-5 py-3 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white font-bold text-sm shadow-lg shadow-emerald-500/20 transition-all whitespace-nowrap self-start md:self-center"
          >
            <span>进入综合评分调优</span>
            <ArrowRight className="w-4 h-4 ml-1.5" />
          </button>
        </div>
      </div>

      {/* Diagnostics Alert & Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl p-4 border border-emerald-200/80 shadow-xs flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center text-emerald-600">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs text-slate-500 font-medium">数据完整（优秀）</div>
            <div className="text-xl font-bold text-slate-900">{diagnosticsSummary.excellent} <span className="text-xs font-normal text-slate-500">只标的</span></div>
            <div className="text-[11px] text-emerald-600">240+交易日连续连续序列</div>
          </div>
        </div>

        <div className="bg-white rounded-xl p-4 border border-blue-200/80 shadow-xs flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center text-blue-600">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs text-slate-500 font-medium">前值对齐（良好）</div>
            <div className="text-xl font-bold text-slate-900">{diagnosticsSummary.good} <span className="text-xs font-normal text-slate-500">只标的</span></div>
            <div className="text-[11px] text-blue-600">轻微休市补齐，特征无漂移</div>
          </div>
        </div>

        <div className="bg-white rounded-xl p-4 border border-amber-200/80 shadow-xs flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center text-amber-600">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs text-slate-500 font-medium">风险警示 / 需关注</div>
            <div className="text-xl font-bold text-amber-700">{diagnosticsSummary.warning} <span className="text-xs font-normal text-slate-500">只标的</span></div>
            <div className="text-[11px] text-amber-700">含ST标的或极低流动性样本</div>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white rounded-xl p-4 border border-slate-200/80 shadow-xs flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="筛选本地池代码 / 股票名称 / 拼音..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white text-slate-800"
          />
        </div>

        <div className="flex items-center space-x-2 overflow-x-auto text-xs">
          <span className="text-slate-400 font-medium flex items-center">
            <Filter className="w-3.5 h-3.5 mr-1" /> 板块:
          </span>
          {['ALL', '主板', '创业板', '科创板', 'ETF', '港股通'].map((m) => (
            <button
              key={m}
              onClick={() => setMarketFilter(m)}
              className={`px-2.5 py-1.5 rounded-lg font-medium transition-colors ${
                marketFilter === m
                  ? 'bg-slate-900 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {m === 'ALL' ? '全部' : m}
            </button>
          ))}
        </div>
      </div>

      {/* Local Stocks Data Table */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
          <table className="w-full text-left text-xs text-slate-600">
            <thead className="bg-slate-50/90 text-slate-500 font-semibold border-b border-slate-200 sticky top-0 z-10 backdrop-blur-xs">
              <tr>
                <th 
                  onClick={() => toggleSort('rank')} 
                  className="p-3.5 cursor-pointer hover:text-indigo-600 transition-colors"
                >
                  排序 {sortBy === 'rank' && (sortAsc ? '↑' : '↓')}
                </th>
                <th 
                  onClick={() => toggleSort('symbol')} 
                  className="p-3.5 cursor-pointer hover:text-indigo-600 transition-colors"
                >
                  标的代码 {sortBy === 'symbol' && (sortAsc ? '↑' : '↓')}
                </th>
                <th className="p-3.5">股票名称</th>
                <th className="p-3.5">板块</th>
                <th 
                  onClick={() => toggleSort('price')} 
                  className="p-3.5 text-right cursor-pointer hover:text-indigo-600 transition-colors"
                >
                  最新价 {sortBy === 'price' && (sortAsc ? '↑' : '↓')}
                </th>
                <th 
                  onClick={() => toggleSort('change')} 
                  className="p-3.5 text-right cursor-pointer hover:text-indigo-600 transition-colors"
                >
                  日涨跌幅 {sortBy === 'change' && (sortAsc ? '↑' : '↓')}
                </th>
                <th 
                  onClick={() => toggleSort('turnover')} 
                  className="p-3.5 text-right cursor-pointer hover:text-indigo-600 transition-colors"
                >
                  换手率 {sortBy === 'turnover' && (sortAsc ? '↑' : '↓')}
                </th>
                <th 
                  onClick={() => toggleSort('volume_ratio')} 
                  className="p-3.5 text-right cursor-pointer hover:text-indigo-600 transition-colors"
                >
                  量比 {sortBy === 'volume_ratio' && (sortAsc ? '↑' : '↓')}
                </th>
                <th 
                  onClick={() => toggleSort('model_score')} 
                  className="p-3.5 text-right cursor-pointer hover:text-indigo-600 transition-colors"
                >
                  模型分 (GBDT) {sortBy === 'model_score' && (sortAsc ? '↑' : '↓')}
                </th>
                <th 
                  onClick={() => toggleSort('composite_score')} 
                  className="p-3.5 text-right cursor-pointer hover:text-indigo-600 transition-colors"
                >
                  综合评分 {sortBy === 'composite_score' && (sortAsc ? '↑' : '↓')}
                </th>
                <th className="p-3.5 text-center">数据诊断</th>
                <th className="p-3.5 text-right">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredAndSorted.map((stock) => {
                const isPositive = stock.change >= 0;
                return (
                  <tr 
                    key={stock.symbol}
                    className="hover:bg-slate-50/70 transition-colors group"
                  >
                    <td className="p-3.5 font-bold text-slate-500 text-center w-12">
                      #{stock.rank}
                    </td>
                    <td className="p-3.5 font-mono font-bold text-slate-900">
                      {stock.symbol}
                    </td>
                    <td className="p-3.5">
                      <div className="font-semibold text-slate-800">{stock.name}</div>
                      <div className="text-[11px] text-slate-400">{stock.industry}</div>
                    </td>
                    <td className="p-3.5">
                      <span className={`inline-flex px-2 py-0.5 rounded text-[10px] font-semibold ${
                        stock.market === '科创板' ? 'bg-purple-50 text-purple-700' :
                        stock.market === '创业板' ? 'bg-cyan-50 text-cyan-700' :
                        stock.market === 'ETF' ? 'bg-amber-50 text-amber-700' :
                        stock.market === '港股通' ? 'bg-emerald-50 text-emerald-700' :
                        'bg-slate-100 text-slate-700'
                      }`}>
                        {stock.market}
                      </span>
                    </td>
                    <td className="p-3.5 text-right font-mono font-bold text-slate-900">
                      ¥{stock.price.toFixed(2)}
                    </td>
                    <td className={`p-3.5 text-right font-mono font-bold ${
                      isPositive ? 'text-red-600' : 'text-emerald-600'
                    }`}>
                      <span className="flex items-center justify-end">
                        {isPositive ? (
                          <TrendingUp className="w-3.5 h-3.5 mr-0.5 inline" />
                        ) : (
                          <TrendingDown className="w-3.5 h-3.5 mr-0.5 inline" />
                        )}
                        {isPositive ? `+${stock.change.toFixed(2)}%` : `${stock.change.toFixed(2)}%`}
                      </span>
                    </td>
                    <td className="p-3.5 text-right font-mono text-slate-700">
                      {stock.turnover.toFixed(2)}%
                    </td>
                    <td className="p-3.5 text-right font-mono text-slate-700">
                      {stock.volume_ratio.toFixed(2)}
                    </td>
                    <td className="p-3.5 text-right font-mono font-semibold text-indigo-600">
                      {stock.model_score.toFixed(1)}
                    </td>
                    <td className="p-3.5 text-right">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full font-mono font-bold text-xs bg-indigo-50 text-indigo-700 border border-indigo-200">
                        {stock.composite_score.toFixed(1)}
                      </span>
                    </td>
                    <td className="p-3.5 text-center">
                      <span
                        title={stock.diagnostic_message}
                        className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium ${
                          stock.diagnostic_status === 'excellent'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : stock.diagnostic_status === 'good'
                            ? 'bg-blue-50 text-blue-700 border border-blue-200'
                            : 'bg-amber-50 text-amber-700 border border-amber-200'
                        }`}
                      >
                        {stock.diagnostic_status === 'excellent' ? '完整' : stock.diagnostic_status === 'good' ? '对齐' : '关注'}
                      </span>
                    </td>
                    <td className="p-3.5 text-right">
                      <button
                        onClick={() => onRemoveStock(stock.symbol)}
                        title="从本地股票池移除"
                        className="p-1 rounded text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
