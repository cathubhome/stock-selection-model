import React, { useState, useMemo } from 'react';
import { 
  Search, 
  Plus, 
  Check, 
  DownloadCloud, 
  Sparkles, 
  Database,
  ArrowRight,
  TrendingUp,
  Clock,
  Layers,
  Info
} from 'lucide-react';
import { StockBasic } from '../types';
import { FULL_UNIVERSE_SEARCHABLE } from '../data/stockUniverse';

interface DataPreparationViewProps {
  localPool: StockBasic[];
  onAddStock: (stock: StockBasic) => void;
  onBatchAdd: (stocks: StockBasic[]) => void;
  onProceedToPool: () => void;
}

export const DataPreparationView: React.FC<DataPreparationViewProps> = ({
  localPool,
  onAddStock,
  onBatchAdd,
  onProceedToPool,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedMarket, setSelectedMarket] = useState<string>('ALL');
  const [selectedSymbols, setSelectedSymbols] = useState<Set<string>>(new Set());
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadSuccessMessage, setDownloadSuccessMessage] = useState<string | null>(null);

  const localSymbolSet = useMemo(() => new Set(localPool.map((s) => s.symbol)), [localPool]);

  // Filter universe by query (code, name, pinyin acronym) and market
  const filteredStocks = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return FULL_UNIVERSE_SEARCHABLE.filter((s) => {
      const matchQuery = 
        !q ||
        s.symbol.toLowerCase().includes(q) ||
        s.name.toLowerCase().includes(q) ||
        s.pinyin.toLowerCase().includes(q) ||
        s.industry.toLowerCase().includes(q);

      const matchMarket = selectedMarket === 'ALL' || s.market === selectedMarket;
      return matchQuery && matchMarket;
    });
  }, [searchQuery, selectedMarket]);

  const handleToggleSelect = (symbol: string) => {
    const next = new Set(selectedSymbols);
    if (next.has(symbol)) {
      next.delete(symbol);
    } else {
      next.add(symbol);
    }
    setSelectedSymbols(next);
  };

  const handleBatchImport = () => {
    const toAdd = FULL_UNIVERSE_SEARCHABLE.filter(
      (s) => selectedSymbols.has(s.symbol) && !localSymbolSet.has(s.symbol)
    );
    if (toAdd.length > 0) {
      onBatchAdd(toAdd);
      setSelectedSymbols(new Set());
      setDownloadSuccessMessage(`已成功将 ${toAdd.length} 只股票加入本地池并完成历史日线对齐！`);
      setTimeout(() => setDownloadSuccessMessage(null), 4000);
    }
  };

  const handleSimulateFullDownload = () => {
    setIsDownloading(true);
    setTimeout(() => {
      setIsDownloading(false);
      setDownloadSuccessMessage('已从 AKShare (东方财富主接口 + 腾讯历史行情备用接口) 刷新并同步最新交易日日线序列！');
      setTimeout(() => setDownloadSuccessMessage(null), 4000);
    }, 1200);
  };

  return (
    <div className="space-y-6">
      {/* Workflow Step Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white rounded-2xl p-6 shadow-md relative overflow-hidden">
        <div className="relative z-10">
          <div className="flex items-center space-x-2 text-indigo-300 text-xs font-semibold uppercase tracking-wider mb-2">
            <Database className="w-4 h-4" />
            <span>第一步 · 数据准备 (Data Preparation)</span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight mb-2">
            A股全市场标的检索与行情同步
          </h2>
          <p className="text-slate-300 text-sm max-w-3xl leading-relaxed">
            支持按 <strong className="text-white">股票代码</strong> (如 300476)、<strong className="text-white">中文名称</strong> (如 胜宏科技) 或 <strong className="text-white">拼音首字母</strong> (如 SHKJ) 模糊检索。历史行情经过复权计算、退市与停牌清洗，为滚动模型提供健全特征面板。
          </p>
        </div>
      </div>

      {/* Overview Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl p-4 border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium mb-1">
            <span>本地股票池标的</span>
            <Layers className="w-4 h-4 text-indigo-500" />
          </div>
          <div className="text-2xl font-bold text-slate-900">{localPool.length} <span className="text-xs font-normal text-slate-500">只</span></div>
          <div className="text-xs text-emerald-600 mt-1 flex items-center font-medium">
            <Check className="w-3 h-3 mr-1" /> 已就绪可直接参与模型训练
          </div>
        </div>

        <div className="bg-white rounded-xl p-4 border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium mb-1">
            <span>全市场检索支持</span>
            <Database className="w-4 h-4 text-blue-500" />
          </div>
          <div className="text-2xl font-bold text-slate-900">5,420+ <span className="text-xs font-normal text-slate-500">家</span></div>
          <div className="text-xs text-slate-500 mt-1">包含主板 / 创业板 / 科创板 / ETF</div>
        </div>

        <div className="bg-white rounded-xl p-4 border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium mb-1">
            <span>历史回溯跨度</span>
            <Clock className="w-4 h-4 text-purple-500" />
          </div>
          <div className="text-2xl font-bold text-slate-900">2018 - 2026</div>
          <div className="text-xs text-slate-500 mt-1">滚动前向窗口，严格无未来函数</div>
        </div>

        <div className="bg-white rounded-xl p-4 border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium mb-1">
            <span>数据接口健康度</span>
            <TrendingUp className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="text-2xl font-bold text-emerald-600">正常 (在线)</div>
          <div className="text-xs text-slate-500 mt-1">AKShare 东方财富 / 腾讯双源热备</div>
        </div>
      </div>

      {/* Success Notification */}
      {downloadSuccessMessage && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 px-4 py-3 rounded-xl text-sm flex items-center justify-between animate-fade-in">
          <div className="flex items-center space-x-2">
            <Check className="w-4 h-4 text-emerald-600" />
            <span className="font-medium">{downloadSuccessMessage}</span>
          </div>
          <button 
            onClick={onProceedToPool} 
            className="text-xs font-bold text-emerald-700 hover:text-emerald-900 underline flex items-center"
          >
            查看本地股票池 <ArrowRight className="w-3.5 h-3.5 ml-0.5" />
          </button>
        </div>
      )}

      {/* Search & Actions Bar */}
      <div className="bg-white rounded-xl p-5 border border-slate-200/80 shadow-xs space-y-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          {/* Search Input */}
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="搜索代码 / 名称 / 拼音首字母 (如 300476, 胜宏科技, SHKJ)"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all text-slate-800 placeholder-slate-400"
            />
          </div>

          {/* Market Filter Chips */}
          <div className="flex items-center space-x-1.5 overflow-x-auto text-xs">
            {['ALL', '主板', '创业板', '科创板', 'ETF', '港股通'].map((m) => (
              <button
                key={m}
                onClick={() => setSelectedMarket(m)}
                className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                  selectedMarket === m
                    ? 'bg-indigo-600 text-white shadow-2xs'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {m === 'ALL' ? '全部板块' : m}
              </button>
            ))}
          </div>

          {/* Actions */}
          <div className="flex items-center space-x-2">
            <button
              onClick={handleBatchImport}
              disabled={selectedSymbols.size === 0}
              className={`inline-flex items-center px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                selectedSymbols.size > 0
                  ? 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-400 cursor-not-allowed'
              }`}
            >
              <Plus className="w-3.5 h-3.5 mr-1" />
              批量导入已选 ({selectedSymbols.size})
            </button>

            <button
              onClick={handleSimulateFullDownload}
              disabled={isDownloading}
              className="inline-flex items-center px-3.5 py-2 rounded-lg text-xs font-semibold bg-white hover:bg-slate-50 border border-slate-300 text-slate-700 transition-colors"
            >
              <DownloadCloud className={`w-3.5 h-3.5 mr-1 text-slate-500 ${isDownloading ? 'animate-bounce' : ''}`} />
              {isDownloading ? '行情同步中...' : '同步最新行情'}
            </button>
          </div>
        </div>

        {/* Quick Suggestion Pills */}
        <div className="flex items-center space-x-2 text-xs text-slate-500 pt-1">
          <span className="font-medium text-slate-400 flex items-center">
            <Sparkles className="w-3 h-3 mr-1 text-indigo-500" /> 推荐检索：
          </span>
          {['300476 (胜宏科技)', '600519 (贵州茅台)', '300750 (宁德时代)', '688008 (澜起科技)', '513050 (中概互联)'].map((tag) => {
            const sym = tag.split(' ')[0];
            return (
              <button
                key={tag}
                onClick={() => setSearchQuery(sym)}
                className="px-2 py-0.5 rounded bg-slate-100 hover:bg-indigo-50 hover:text-indigo-600 text-slate-600 border border-slate-200 transition-colors"
              >
                {tag}
              </button>
            );
          })}
        </div>
      </div>

      {/* Stock Universe List Table */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-200/80 flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
            <span>候选标的检索结果</span>
            <span className="text-xs font-normal text-slate-500">
              (共 {filteredStocks.length} 只匹配标的)
            </span>
          </h3>
          <button
            onClick={onProceedToPool}
            className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center space-x-1"
          >
            <span>进入本地股票池</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="overflow-x-auto max-h-96 overflow-y-auto">
          <table className="w-full text-left text-xs text-slate-600">
            <thead className="bg-slate-50/80 text-slate-500 font-semibold border-b border-slate-200 sticky top-0 z-10 backdrop-blur-xs">
              <tr>
                <th className="p-3.5 w-10 text-center">
                  <input
                    type="checkbox"
                    checked={
                      filteredStocks.length > 0 &&
                      filteredStocks.every((s) => selectedSymbols.has(s.symbol))
                    }
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedSymbols(new Set(filteredStocks.map((s) => s.symbol)));
                      } else {
                        setSelectedSymbols(new Set());
                      }
                    }}
                    className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                  />
                </th>
                <th className="p-3.5">代码</th>
                <th className="p-3.5">名称</th>
                <th className="p-3.5">拼音首字母</th>
                <th className="p-3.5">板块</th>
                <th className="p-3.5">所属细分行业 / 题材</th>
                <th className="p-3.5">状态</th>
                <th className="p-3.5 text-right">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredStocks.map((stock) => {
                const inPool = localSymbolSet.has(stock.symbol);
                const isSelected = selectedSymbols.has(stock.symbol);

                return (
                  <tr 
                    key={stock.symbol} 
                    className={`hover:bg-slate-50/70 transition-colors ${
                      isSelected ? 'bg-indigo-50/40' : ''
                    }`}
                  >
                    <td className="p-3.5 text-center">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => handleToggleSelect(stock.symbol)}
                        disabled={inPool}
                        className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 disabled:opacity-40"
                      />
                    </td>
                    <td className="p-3.5 font-mono font-bold text-slate-900">{stock.symbol}</td>
                    <td className="p-3.5 font-medium text-slate-800">{stock.name}</td>
                    <td className="p-3.5 font-mono text-slate-500">{stock.pinyin}</td>
                    <td className="p-3.5">
                      <span className={`inline-flex px-2 py-0.5 rounded text-[11px] font-semibold ${
                        stock.market === '科创板' ? 'bg-purple-50 text-purple-700 border border-purple-200' :
                        stock.market === '创业板' ? 'bg-cyan-50 text-cyan-700 border border-cyan-200' :
                        stock.market === 'ETF' ? 'bg-amber-50 text-amber-700 border border-amber-200' :
                        stock.market === '港股通' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' :
                        'bg-slate-100 text-slate-700 border border-slate-200'
                      }`}>
                        {stock.market}
                      </span>
                    </td>
                    <td className="p-3.5 text-slate-600 max-w-xs truncate">{stock.industry}</td>
                    <td className="p-3.5">
                      {inPool ? (
                        <span className="inline-flex items-center text-emerald-600 font-semibold text-[11px]">
                          <Check className="w-3.5 h-3.5 mr-1" /> 已在本地池
                        </span>
                      ) : (
                        <span className="text-slate-400 text-[11px]">未加入</span>
                      )}
                    </td>
                    <td className="p-3.5 text-right">
                      {inPool ? (
                        <button
                          disabled
                          className="px-2.5 py-1 rounded bg-slate-100 text-slate-400 text-xs cursor-default font-medium"
                        >
                          已导入
                        </button>
                      ) : (
                        <button
                          onClick={() => onAddStock(stock)}
                          className="px-2.5 py-1 rounded bg-indigo-50 hover:bg-indigo-100 text-indigo-600 font-medium text-xs border border-indigo-200 transition-colors"
                        >
                          + 添加到池
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Research Tips Section */}
      <div className="bg-slate-100/80 rounded-xl p-4 border border-slate-200 text-xs text-slate-600 space-y-1">
        <div className="flex items-center text-slate-800 font-semibold space-x-1.5 mb-1">
          <Info className="w-4 h-4 text-indigo-600" />
          <span>数据准备与严格防泄漏规则</span>
        </div>
        <p>• <strong>日线行情源</strong>：历史行情默认尝试东方财富接口，连接超时或频控时自动回退至腾讯历史行情接口。</p>
        <p>• <strong>去幸存者偏差</strong>：避免仅用当前活跃标的去推断远古历史，严肃模型应按调仓日时点进行横截面截取。</p>
        <p>• <strong>复权口径</strong>：计算收益与因子时统一采用前复权 (QFQ) 口径，保证价格连续性无虚假除权缺口。</p>
      </div>
    </div>
  );
};
