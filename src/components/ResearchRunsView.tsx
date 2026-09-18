import React, { useState, useMemo } from 'react';
import { 
  History, 
  ArrowRight, 
  GitCommit, 
  Calendar, 
  CheckCircle2, 
  Sliders, 
  LineChart, 
  Layers,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Sparkles,
  Tag,
  Clock
} from 'lucide-react';
import { ArchiveRun, ScoredStock } from '../types';
import { fetchRunDetail } from '../api/client';
import { Eye, X } from 'lucide-react';
import { ARCHIVE_RESEARCH_RUNS, RAW_REMOTE_STOCKS } from '../data/remoteArchiveData';

// Comprehensive fallback dictionary for quick symbol-to-name lookups
const KNOWN_STOCK_NAMES: Record<string, { name: string; industry: string }> = {
  '605277': { name: '新亚电子', industry: '线缆部件及其他' },
  '002882': { name: '金龙羽', industry: '电线电缆制造' },
  '002837': { name: '英维克', industry: '温控节能设备' },
  '688152': { name: '麒麟信安', industry: '国产操作系统' },
  '000938': { name: '紫光股份', industry: 'ICT基础设施与服务' },
  '002272': { name: '川润股份', industry: '润滑与流体控制' },
  '300727': { name: '润禾材料', industry: '有机硅精细化工' },
  '601118': { name: '海南橡胶', industry: '天然橡胶种植加工' },
  '688379': { name: '华光新材', industry: '先进焊接功能材料' },
  '688667': { name: '菱电电控', industry: '汽车动力电子控制' },
  '300476': { name: '胜宏科技', industry: '高精密度印制电路板' },
  '600172': { name: '黄河旋风', industry: '超硬材料及制品' },
  '300285': { name: '国瓷材料', industry: '电子陶瓷高端功能材料' },
  '002407': { name: '多氟多', industry: '无机氟化锂新材料' },
  '688598': { name: '金博股份', industry: '碳基复合材料' },
  '002083': { name: '孚日股份', industry: '家纺出口及新材料' },
};

interface ResearchRunsViewProps {
  runs?: ArchiveRun[];
  stocks?: ScoredStock[];
  onNavigate?: (step: any) => void;
}

export const ResearchRunsView: React.FC<ResearchRunsViewProps> = ({
  runs = [],
  stocks = [],
  onNavigate,
}) => {
  const [diffLimit, setDiffLimit] = useState<number>(5);
  const [applyConfigMsg, setApplyConfigMsg] = useState<string | null>(null);
  const [selectedLeftRunId, setSelectedLeftRunId] = useState<string>(runs[0]?.run_id || '');
  const [activeRunDetail, setActiveRunDetail] = useState<{ run_id: string; manifest: any; picks: any[] } | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);

  const handleApplyRunConfig = (manifest: any) => {
    if (!manifest?.config) return;
    try {
      if (manifest.config.weights) {
        localStorage.setItem("a_share_stock_model_weights_v2", JSON.stringify(manifest.config.weights));
      }
      setApplyConfigMsg("已将该实验参数 (周期、TopK及权重) 载入本地配置！");
      setTimeout(() => {
        setApplyConfigMsg(null);
        if (onNavigate) onNavigate("综合评分");
      }, 1200);
    } catch (e) {
      console.error(e);
    }
  };

  const handleOpenDetail = async (runId: string) => {
    setIsLoadingDetail(true);
    try {
      const res = await fetchRunDetail(runId);
      if (res) setActiveRunDetail(res);
    } catch (err) {
      console.error('Failed to fetch run detail:', err);
    } finally {
      setIsLoadingDetail(false);
    }
  };
  const [selectedRightRunId, setSelectedRightRunId] = useState<string>(runs[1]?.run_id || runs[0]?.run_id || "");
  const [diffKind, setDiffKind] = useState<"all" | "score" | "backtest">("score");

  // 异步数据载入后自动握手选中最新两期实验
  React.useEffect(() => {
    if (runs.length > 0) {
      const scoreRuns = runs.filter(r => r.kind === "score");
      const defaultPool = scoreRuns.length >= 2 ? scoreRuns : runs;
      if (!selectedLeftRunId || !runs.some(r => r.run_id === selectedLeftRunId)) {
        setSelectedLeftRunId(defaultPool[0].run_id);
      }
      if (!selectedRightRunId || !runs.some(r => r.run_id === selectedRightRunId)) {
        setSelectedRightRunId(defaultPool.length > 1 ? defaultPool[1].run_id : defaultPool[0].run_id);
      }
    }
  }, [runs]);

  // Fast lookup map for symbol -> { name, industry }
  const stockMetaMap = useMemo(() => {
    const map: Record<string, { name: string; industry: string }> = {};

    // 1. Fill known static dictionary
    Object.entries(KNOWN_STOCK_NAMES).forEach(([sym, val]) => {
      map[sym] = val;
    });

    // 2. Fill from raw remote stocks
    (RAW_REMOTE_STOCKS as any[]).forEach(s => {
      if (s.symbol && s.name) {
        map[s.symbol] = { name: s.name, industry: s.industry || '综合板块' };
      }
    });

    // 3. Override with any runtime stocks in state
    stocks.forEach(s => {
      if (s.symbol && s.name) {
        map[s.symbol] = { name: s.name, industry: s.industry || '综合板块' };
      }
    });

    return map;
  }, [stocks]);

  const getStockName = (symbol: string): string => {
    return stockMetaMap[symbol]?.name || symbol;
  };

  const getStockIndustry = (symbol: string): string => {
    return stockMetaMap[symbol]?.industry || 'A股标的';
  };

  const leftRun = runs.find(r => r.run_id === selectedLeftRunId) || runs[0];
  const rightRun = runs.find(r => r.run_id === selectedRightRunId) || runs[2] || runs[0];

  // Compare candidates between Left and Right with dynamic limit
  const leftSymbols = (leftRun?.top_symbols || []).slice(0, diffLimit === 0 ? undefined : diffLimit);
  const rightSymbols = (rightRun?.top_symbols || []).slice(0, diffLimit === 0 ? undefined : diffLimit);

  const leftAvg = leftRun?.avg_score || (leftRun?.excess_return != null ? `+${leftRun.excess_return}%` : "--");
  const rightAvg = rightRun?.avg_score || (rightRun?.excess_return != null ? `+${rightRun.excess_return}%` : "--");

  const newlyAdded = leftSymbols.filter(s => !rightSymbols.includes(s));
  const dropped = rightSymbols.filter(s => !leftSymbols.includes(s));
  const preserved = leftSymbols.filter(s => rightSymbols.includes(s));

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-indigo-600 text-xs font-bold uppercase tracking-wider mb-1">
            <History className="w-4 h-4" />
            <span>第五步 · 实验与研究运行记录 (Research Runs & Artifacts)</span>
          </div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            历史评分快照追溯与跨版本候选差异比对
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            每次评分与回测均自动存档完整模型指纹、特征数据与参数配置，清晰展示股票名称、代码及进出变动
          </p>
        </div>
      </div>

      {/* Runs Timeline / Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
            <span>归档实验列表</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-mono">
              共 {runs.length} 次记录
            </span>
          </h3>
          <span className="text-xs text-slate-400">数据源: data/archive/</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-50 text-slate-600 text-[11px] font-semibold border-b border-slate-200">
              <tr>
                <th className="py-2.5 px-4">运行编号 (Run ID)</th>
                <th className="py-2.5 px-4">类型</th>
                <th className="py-2.5 px-4">截面日期</th>
                <th className="py-2.5 px-4">归档时间</th>
                <th className="py-2.5 px-4">标的数量</th>
                <th className="py-2.5 px-4">核心候选标的 (股票名称 / 代码)</th>
                <th className="py-2.5 px-4">平均得分 / 表现</th>
                <th className="py-2.5 px-4 text-right">状态</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
              {runs.map((r) => {
                const isScore = r.kind === 'score';
                return (
                  <tr key={r.run_id} className="hover:bg-slate-50 transition-colors">
                    <td className="py-2.5 px-4 font-bold text-slate-900">
                      {r.run_id}
                    </td>
                    <td className="py-2.5 px-4">
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-sans font-semibold ${
                        isScore ? 'bg-indigo-50 text-indigo-700 border border-indigo-200' : 'bg-purple-50 text-purple-700 border border-purple-200'
                      }`}>
                        {isScore ? <Sliders className="w-3 h-3 mr-1" /> : <LineChart className="w-3 h-3 mr-1" />}
                        {isScore ? '综合评分' : '前向回测'}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 text-slate-600">{r.date}</td>
                    <td className="py-2.5 px-4 text-slate-400">{r.created_at}</td>
                    <td className="py-2.5 px-4 font-sans">{r.stock_count} 只</td>
                    <td className="py-2.5 px-4 text-slate-800 font-sans">
                      <div className="flex flex-wrap gap-1.5 py-0.5">
                        {r.top_symbols.map((sym) => (
                          <span
                            key={sym}
                            className="inline-flex items-center px-2 py-0.5 rounded-md bg-slate-100/90 text-slate-800 text-[11px] border border-slate-200/80 hover:bg-indigo-50 hover:text-indigo-700 hover:border-indigo-200 transition-colors"
                            title={`行业: ${getStockIndustry(sym)}`}
                          >
                            <span className="font-semibold text-slate-900 mr-1">{getStockName(sym)}</span>
                            <span className="text-[10px] text-slate-400 font-mono">({sym})</span>
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-2.5 px-4">
                      {isScore ? (
                        <span className="text-slate-900 font-semibold font-sans">{r.avg_score} 分</span>
                      ) : (
                        <span className="text-rose-600 font-semibold font-sans">超额 +{r.excess_return}% · 夏普 {r.sharpe}</span>
                      )}
                    </td>
                    <td className="py-2.5 px-4 text-right whitespace-nowrap">
                      <div className="flex items-center justify-end space-x-2">
                        <span className="inline-flex items-center text-emerald-600 text-[10px] font-sans font-medium">
                          <CheckCircle2 className="w-3 h-3 mr-1" /> 已归档
                        </span>
                        <button
                          onClick={() => handleOpenDetail(r.run_id)}
                          className="inline-flex items-center px-2 py-1 rounded bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-[11px] font-sans font-medium transition-colors cursor-pointer"
                        >
                          <Eye className="w-3 h-3 mr-1" />
                          详情
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Runs Difference Comparator */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-5">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 pb-3 border-b border-slate-100">
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-sm font-bold text-slate-900">
                跨实验候选标的与量化效能对比
              </h3>
              <div className="flex items-center space-x-1 bg-slate-100 p-0.5 rounded-lg text-[10px]">
                {[5, 10, 0].map((lim) => (
                  <button
                    key={lim}
                    type="button"
                    onClick={() => setDiffLimit(lim)}
                    className={`px-2 py-0.5 rounded-md font-medium transition-colors ${
                      diffLimit === lim ? "bg-white text-indigo-700 shadow-2xs font-bold" : "text-slate-500 hover:text-slate-800"
                    }`}
                  >
                    {lim === 0 ? "全部候选" : `Top ${lim}`}
                  </button>
                ))}
              </div>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              横向对比两个独立实验的参数配置、综合收益表现、重合率及选股流动性
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center space-x-1.5">
                <span className="text-xs text-slate-600 font-bold">实验 A (最新基准):</span>
                <select
                  value={selectedLeftRunId}
                  onChange={(e) => setSelectedLeftRunId(e.target.value)}
                  className="text-xs rounded-lg border border-slate-300 py-1.5 px-2 bg-white text-slate-900 font-mono focus:ring-2 focus:ring-indigo-500 outline-hidden"
                >
                  {runs.map(r => (
                    <option key={r.run_id} value={r.run_id}>
                      {r.date} · {r.kind === "score" ? "综合评分" : "前向回测"} ({r.run_id.slice(-8)})
                    </option>
                  ))}
                </select>
              </div>

              <span className="text-xs text-indigo-600 font-black px-1">VS</span>

              <div className="flex items-center space-x-1.5">
                <span className="text-xs text-slate-600 font-bold">实验 B (对比样本):</span>
                <select
                  value={selectedRightRunId}
                  onChange={(e) => setSelectedRightRunId(e.target.value)}
                  className="text-xs rounded-lg border border-slate-300 py-1.5 px-2 bg-white text-slate-900 font-mono focus:ring-2 focus:ring-indigo-500 outline-hidden"
                >
                  {runs.map(r => (
                    <option key={r.run_id} value={r.run_id}>
                      {r.date} · {r.kind === "score" ? "综合评分" : "前向回测"} ({r.run_id.slice(-8)})
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Macro Metric Side-by-Side Comparison */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs bg-white p-3 rounded-xl border border-slate-200">
          <div className="p-2 bg-slate-50 rounded-lg">
            <span className="text-[10px] text-slate-400 block">实验 A 截面表现</span>
            <strong className="text-slate-900 text-sm font-mono mt-0.5 block">{leftAvg}</strong>
            <span className="text-[10px] text-slate-500 truncate block">{leftRun?.date} · {leftRun?.kind === "score" ? "综合评分" : "前向回测"}</span>
          </div>
          <div className="p-2 bg-slate-50 rounded-lg">
            <span className="text-[10px] text-slate-400 block">实验 B 截面表现</span>
            <strong className="text-slate-900 text-sm font-mono mt-0.5 block">{rightAvg}</strong>
            <span className="text-[10px] text-slate-500 truncate block">{rightRun?.date} · {rightRun?.kind === "score" ? "综合评分" : "前向回测"}</span>
          </div>
          <div className="p-2 bg-slate-50 rounded-lg">
            <span className="text-[10px] text-slate-400 block">标的重合度</span>
            <strong className="text-indigo-700 text-sm font-mono mt-0.5 block">
              {leftSymbols.length > 0 ? `${((preserved.length / leftSymbols.length) * 100).toFixed(0)}%` : "0%"}
            </strong>
            <span className="text-[10px] text-slate-500 block">两期共有 {preserved.length} 只标的</span>
          </div>
          <div className="p-2 bg-slate-50 rounded-lg">
            <span className="text-[10px] text-slate-400 block">名单置换比例</span>
            <strong className="text-amber-700 text-sm font-mono mt-0.5 block">
              {leftSymbols.length > 0 ? `${((newlyAdded.length / leftSymbols.length) * 100).toFixed(0)}%` : "0%"}
            </strong>
            <span className="text-[10px] text-slate-500 block">新进 {newlyAdded.length} 只 / 跌出 {dropped.length} 只</span>
          </div>
        </div>

        {/* Side-by-Side Top 5 Previews */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-slate-50/70 p-4 rounded-xl border border-slate-200">
          {/* Left Run Preview */}
          <div className="bg-white p-3.5 rounded-lg border border-slate-200 space-y-2">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <div className="flex items-center space-x-2">
                <span className="w-2 h-2 rounded-full bg-indigo-600"></span>
                <span className="text-xs font-bold text-slate-900">实验 A ({leftRun.date}) Top 5 标的</span>
              </div>
              <span className="text-[10px] text-slate-400 font-mono">{leftRun.run_id.slice(0, 15)}</span>
            </div>
            <div className="space-y-1.5">
              {leftSymbols.map((sym, idx) => {
                const inBoth = rightSymbols.includes(sym);
                return (
                  <div 
                    key={sym} 
                    className={`px-3 py-2 rounded-lg border flex items-center justify-between text-xs transition-colors ${
                      inBoth 
                        ? 'bg-slate-50/60 border-slate-200' 
                        : 'bg-emerald-50/50 border-emerald-200'
                    }`}
                  >
                    <div className="flex items-center space-x-2.5">
                      <span className="font-mono font-bold text-slate-400 w-4 text-center">#{idx + 1}</span>
                      <div>
                        <div className="font-bold text-slate-900">{getStockName(sym)}</div>
                        <div className="text-[10px] text-slate-400 font-mono">{sym} · {getStockIndustry(sym)}</div>
                      </div>
                    </div>
                    <div>
                      {inBoth ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-50 text-indigo-700">
                          两期均在
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800">
                          实验A特有
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Run Preview */}
          <div className="bg-white p-3.5 rounded-lg border border-slate-200 space-y-2">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <div className="flex items-center space-x-2">
                <span className="w-2 h-2 rounded-full bg-slate-500"></span>
                <span className="text-xs font-bold text-slate-900">实验 B ({rightRun.date}) Top 5 标的</span>
              </div>
              <span className="text-[10px] text-slate-400 font-mono">{rightRun.run_id.slice(0, 15)}</span>
            </div>
            <div className="space-y-1.5">
              {rightSymbols.map((sym, idx) => {
                const inBoth = leftSymbols.includes(sym);
                return (
                  <div 
                    key={sym} 
                    className={`px-3 py-2 rounded-lg border flex items-center justify-between text-xs transition-colors ${
                      inBoth 
                        ? 'bg-slate-50/60 border-slate-200' 
                        : 'bg-rose-50/50 border-rose-200'
                    }`}
                  >
                    <div className="flex items-center space-x-2.5">
                      <span className="font-mono font-bold text-slate-400 w-4 text-center">#{idx + 1}</span>
                      <div>
                        <div className="font-bold text-slate-900">{getStockName(sym)}</div>
                        <div className="text-[10px] text-slate-400 font-mono">{sym} · {getStockIndustry(sym)}</div>
                      </div>
                    </div>
                    <div>
                      {inBoth ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-50 text-indigo-700">
                          两期均在
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-100 text-rose-800">
                          实验B特有
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Diff Result Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-1">
          {/* Newly Entered */}
          <div className="p-4 bg-emerald-50/70 border border-emerald-200 rounded-xl flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2.5">
                <div className="flex items-center space-x-1.5 text-emerald-800 font-bold text-xs">
                  <ArrowUpRight className="w-4 h-4 text-emerald-600" />
                  <span>新晋入选标的 (Newly Entered in A)</span>
                </div>
                <span className="text-xs font-mono font-bold px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800">
                  {newlyAdded.length} 只
                </span>
              </div>
              <p className="text-[11px] text-emerald-700 mb-3">
                在实验 A 中入选前列，但在实验 B 中未进入 Top 5
              </p>

              {newlyAdded.length > 0 ? (
                <div className="space-y-2">
                  {newlyAdded.map(s => (
                    <div key={s} className="p-2.5 bg-white rounded-lg border border-emerald-200 text-xs shadow-2xs flex items-center justify-between">
                      <div>
                        <div className="font-bold text-slate-900 flex items-center space-x-1.5">
                          <span>{getStockName(s)}</span>
                          <span className="font-mono text-[10px] text-slate-400 font-normal">({s})</span>
                        </div>
                        <div className="text-[10px] text-slate-500 mt-0.5">
                          {getStockIndustry(s)}
                        </div>
                      </div>
                      <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                        新晋前列
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-4 text-center text-xs text-emerald-600/80 bg-white/50 rounded-lg border border-emerald-100">
                  无新晋标的，两期前优名单完全重合或子集
                </div>
              )}
            </div>
          </div>

          {/* Dropped Out */}
          <div className="p-4 bg-rose-50/70 border border-rose-200 rounded-xl flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2.5">
                <div className="flex items-center space-x-1.5 text-rose-800 font-bold text-xs">
                  <ArrowDownRight className="w-4 h-4 text-rose-600" />
                  <span>跌出优选标的 (Dropped Out from B)</span>
                </div>
                <span className="text-xs font-mono font-bold px-1.5 py-0.5 rounded bg-rose-100 text-rose-800">
                  {dropped.length} 只
                </span>
              </div>
              <p className="text-[11px] text-rose-700 mb-3">
                在实验 B 中曾位居前列，但在实验 A 中已滑出 Top 5
              </p>

              {dropped.length > 0 ? (
                <div className="space-y-2">
                  {dropped.map(s => (
                    <div key={s} className="p-2.5 bg-white rounded-lg border border-rose-200 text-xs shadow-2xs flex items-center justify-between">
                      <div>
                        <div className="font-bold text-slate-900 flex items-center space-x-1.5">
                          <span>{getStockName(s)}</span>
                          <span className="font-mono text-[10px] text-slate-400 font-normal">({s})</span>
                        </div>
                        <div className="text-[10px] text-slate-500 mt-0.5">
                          {getStockIndustry(s)}
                        </div>
                      </div>
                      <span className="text-[10px] font-semibold text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                        排名滑落
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-4 text-center text-xs text-rose-600/80 bg-white/50 rounded-lg border border-rose-100">
                  无跌出标的
                </div>
              )}
            </div>
          </div>

          {/* Preserved / Stable */}
          <div className="p-4 bg-indigo-50/70 border border-indigo-200 rounded-xl flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2.5">
                <div className="flex items-center space-x-1.5 text-indigo-800 font-bold text-xs">
                  <CheckCircle2 className="w-4 h-4 text-indigo-600" />
                  <span>持续保持稳定 (Stable Tickers)</span>
                </div>
                <span className="text-xs font-mono font-bold px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-800">
                  {preserved.length} 只
                </span>
              </div>
              <p className="text-[11px] text-indigo-700 mb-3">
                在实验 A 与实验 B 两期均位列 Top 5 的高稳定性核心标的
              </p>

              {preserved.length > 0 ? (
                <div className="space-y-2">
                  {preserved.map(s => (
                    <div key={s} className="p-2.5 bg-white rounded-lg border border-indigo-200 text-xs shadow-2xs flex items-center justify-between">
                      <div>
                        <div className="font-bold text-slate-900 flex items-center space-x-1.5">
                          <span>{getStockName(s)}</span>
                          <span className="font-mono text-[10px] text-slate-400 font-normal">({s})</span>
                        </div>
                        <div className="text-[10px] text-slate-500 mt-0.5">
                          {getStockIndustry(s)}
                        </div>
                      </div>
                      <span className="text-[10px] font-semibold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200">
                        持续优选
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-4 text-center text-xs text-indigo-600/80 bg-white/50 rounded-lg border border-indigo-100">
                  两期实验无共同重合标的
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      {/* Run Detail Modal */}
      {activeRunDetail && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95 duration-150 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <div>
                <h3 className="text-base font-bold text-slate-900">运行快照详情 ({activeRunDetail.run_id})</h3>
                <span className="text-xs text-slate-400 font-mono">
                  创建时间: {activeRunDetail.manifest?.created_at || '历史记录'}
                </span>
              </div>
              <button
                onClick={() => setActiveRunDetail(null)}
                className="w-8 h-8 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 flex items-center justify-center cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                  <span className="text-slate-400 block text-[10px]">运行类型</span>
                  <span className="font-bold text-slate-800">{activeRunDetail.manifest?.kind === 'score' ? '多因子综合评分' : '历史前向回测'}</span>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                  <span className="text-slate-400 block text-[10px]">预测/持有周期</span>
                  <span className="font-bold text-slate-800">{activeRunDetail.manifest?.config?.horizon || 20} 日</span>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                  <span className="text-slate-400 block text-[10px]">持仓/候选数量</span>
                  <span className="font-bold text-slate-800">{activeRunDetail.manifest?.config?.top_k || activeRunDetail.picks?.length || 10} 只</span>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                  <span className="text-slate-400 block text-[10px]">数据指纹</span>
                  <span className="font-mono text-[10px] text-slate-600 truncate block">{activeRunDetail.manifest?.data_fingerprint?.slice(0, 10) || '--'}</span>
                </div>
              </div>

              {activeRunDetail.picks && activeRunDetail.picks.length > 0 && (
                <div>
                  <h4 className="text-xs font-bold text-slate-900 mb-2">核心优选标的快照 (Top Picks)</h4>
                  <div className="border border-slate-200 rounded-xl overflow-hidden">
                    <table className="w-full text-left text-xs text-slate-700">
                      <thead className="bg-slate-50 text-slate-600 text-[11px] font-semibold border-b border-slate-200">
                        <tr>
                          <th className="py-2 px-3">排名</th>
                          <th className="py-2 px-3">代码</th>
                          <th className="py-2 px-3">名称</th>
                          <th className="py-2 px-3">综合评分</th>
                          <th className="py-2 px-3">模型评分</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 font-mono">
                        {activeRunDetail.picks.map((p: any, idx: number) => (
                          <tr key={idx} className="hover:bg-slate-50">
                            <td className="py-1.5 px-3 font-bold text-slate-800 font-sans">{p.rank || idx + 1}</td>
                            <td className="py-1.5 px-3 text-indigo-600">{p.symbol}</td>
                            <td className="py-1.5 px-3 font-sans text-slate-800">{p.name || getStockName(p.symbol)}</td>
                            <td className="py-1.5 px-3 font-bold text-slate-900">{Number(p.composite_score || 0).toFixed(1)}</td>
                            <td className="py-1.5 px-3 text-slate-600">{Number(p.model_score || 0).toFixed(1)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
              <div className="flex items-center justify-between pt-3 border-t border-slate-100">
                <span className="text-xs text-emerald-600 font-medium">
                  {applyConfigMsg || ""}
                </span>
                <div className="flex items-center space-x-2">
                  <button
                    type="button"
                    onClick={() => setActiveRunDetail(null)}
                    className="px-3.5 py-1.5 rounded-lg text-xs text-slate-600 hover:bg-slate-100"
                  >
                    关闭
                  </button>
                  {activeRunDetail.manifest?.config && (
                    <button
                      type="button"
                      onClick={() => handleApplyRunConfig(activeRunDetail.manifest)}
                      className="inline-flex items-center px-4 py-1.5 rounded-lg text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs cursor-pointer"
                    >
                      <Sliders className="w-3.5 h-3.5 mr-1" />
                      一键复现此实验参数并前往评分
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};