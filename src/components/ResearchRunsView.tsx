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
  const [diffMode, setDiffMode] = useState<"score" | "backtest">("score");
  const [diffLimit, setDiffLimit] = useState<number>(5);
  const [runsPage, setRunsPage] = useState<number>(1);
  const runsPageSize = 10;
  const [applyConfigMsg, setApplyConfigMsg] = useState<string | null>(null);
  const [selectedLeftRunId, setSelectedLeftRunId] = useState<string>("");
  const [selectedRightRunId, setSelectedRightRunId] = useState<string>("");
  const [activeRunDetail, setActiveRunDetail] = useState<{ run_id: string; manifest: any; picks: any[] } | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);

  // 过滤同类型实验
  const modeFilteredRuns = useMemo(() => {
    return runs.filter(r => r.kind === diffMode);
  }, [runs, diffMode]);

  // 切换模式或 runs 变动时，自动严格握手同类型的最新两个实验
  useEffect(() => {
    if (modeFilteredRuns.length > 0) {
      setSelectedLeftRunId(modeFilteredRuns[0].run_id);
      setSelectedRightRunId(modeFilteredRuns.length > 1 ? modeFilteredRuns[1].run_id : modeFilteredRuns[0].run_id);
    } else {
      setSelectedLeftRunId("");
      setSelectedRightRunId("");
    }
  }, [modeFilteredRuns, diffMode]);

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
              {runs.slice((runsPage - 1) * runsPageSize, runsPage * runsPageSize).map((r) => {
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
        {/* 表格分页 */}
        {runs.length > runsPageSize && (
          <div className="px-4 py-3 border-t border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs bg-slate-50/50">
            <span className="text-slate-500">
              第 {runsPage} / {Math.ceil(runs.length / runsPageSize)} 页 · 共 {runs.length} 次归档记录 (每页 10 条)
            </span>
            <div className="flex items-center space-x-1">
              <button
                type="button"
                disabled={runsPage <= 1}
                onClick={() => setRunsPage(p => Math.max(1, p - 1))}
                className="px-2.5 py-1 rounded border border-slate-200 bg-white text-slate-600 disabled:opacity-40 hover:bg-slate-50 cursor-pointer"
              >
                上一页
              </button>
              {Array.from({ length: Math.ceil(runs.length / runsPageSize) }, (_, i) => i + 1).map(p => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setRunsPage(p)}
                  className={`px-2.5 py-1 rounded font-mono text-xs cursor-pointer ${
                    runsPage === p
                      ? "bg-indigo-600 text-white font-bold shadow-2xs"
                      : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {p}
                </button>
              ))}
              <button
                type="button"
                disabled={runsPage >= Math.ceil(runs.length / runsPageSize)}
                onClick={() => setRunsPage(p => p + 1)}
                className="px-2.5 py-1 rounded border border-slate-200 bg-white text-slate-600 disabled:opacity-40 hover:bg-slate-50 cursor-pointer"
              >
                下一页
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Runs Difference Comparator (同类型强约束重构) */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-5">
        {/* 顶部标题与模式分流切页 */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 pb-3 border-b border-slate-100">
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-sm font-bold text-slate-900">
                跨实验对比分析 (同类实验严谨比对)
              </h3>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200">
                同类型强约束
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              严禁跨物种混比：评分快照对比优选股票名单与权重差异；回测对比长期超额收益与夏普比率
            </p>
          </div>

          {/* 模式分段切页 */}
          <div className="flex items-center space-x-2">
            <div className="flex items-center bg-slate-100 p-1 rounded-xl text-xs">
              <button
                type="button"
                onClick={() => setDiffMode("score")}
                className={`flex items-center space-x-1 px-3 py-1.5 rounded-lg font-medium transition-all ${
                  diffMode === "score"
                    ? "bg-white text-indigo-700 font-bold shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <Sliders className="w-3.5 h-3.5" />
                <span>综合评分对比 (Score Diff)</span>
              </button>
              <button
                type="button"
                onClick={() => setDiffMode("backtest")}
                className={`flex items-center space-x-1 px-3 py-1.5 rounded-lg font-medium transition-all ${
                  diffMode === "backtest"
                    ? "bg-white text-purple-700 font-bold shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <LineChart className="w-3.5 h-3.5" />
                <span>策略回测对比 (Backtest Diff)</span>
              </button>
            </div>
          </div>
        </div>

        {/* 下拉选择栏（严格仅展示同类实验） */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-xl bg-slate-50 border border-slate-200">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center space-x-1.5">
              <span className="text-xs text-slate-600 font-bold">基准实验 A:</span>
              <select
                value={selectedLeftRunId}
                onChange={(e) => setSelectedLeftRunId(e.target.value)}
                className="text-xs rounded-lg border border-slate-300 py-1.5 px-2 bg-white text-slate-900 font-mono focus:ring-2 focus:ring-indigo-500 outline-hidden"
              >
                {modeFilteredRuns.map(r => (
                  <option key={r.run_id} value={r.run_id}>
                    {r.date} · {r.kind === "score" ? "评分快照" : "滚动回测"} ({r.run_id.slice(-8)})
                  </option>
                ))}
              </select>
            </div>

            <span className="text-xs text-indigo-600 font-black px-1">VS</span>

            <div className="flex items-center space-x-1.5">
              <span className="text-xs text-slate-600 font-bold">对比实验 B:</span>
              <select
                value={selectedRightRunId}
                onChange={(e) => setSelectedRightRunId(e.target.value)}
                className="text-xs rounded-lg border border-slate-300 py-1.5 px-2 bg-white text-slate-900 font-mono focus:ring-2 focus:ring-indigo-500 outline-hidden"
              >
                {modeFilteredRuns.map(r => (
                  <option key={r.run_id} value={r.run_id}>
                    {r.date} · {r.kind === "score" ? "评分快照" : "滚动回测"} ({r.run_id.slice(-8)})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* 范围微调（仅评分模式） */}
          {diffMode === "score" && (
            <div className="flex items-center space-x-1.5 text-xs">
              <span className="text-slate-500 text-[11px]">对比名单范围:</span>
              <div className="flex items-center bg-white border border-slate-200 p-0.5 rounded-lg text-[10px]">
                {[5, 10, 0].map((lim) => (
                  <button
                    key={lim}
                    type="button"
                    onClick={() => setDiffLimit(lim)}
                    className={`px-2 py-0.5 rounded-md font-medium transition-colors ${
                      diffLimit === lim ? "bg-indigo-600 text-white font-bold" : "text-slate-500 hover:text-slate-800"
                    }`}
                  >
                    {lim === 0 ? "全部候选" : `Top ${lim}`}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 模式 1：综合评分候选对比 (Score Diff View) */}
        {diffMode === "score" ? (
          <div className="space-y-4">
            {/* Macro Metric Side-by-Side Comparison */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs bg-white p-3 rounded-xl border border-slate-200">
              <div className="p-2.5 bg-slate-50 rounded-lg">
                <span className="text-[10px] text-slate-400 block">实验 A 平均综合分</span>
                <strong className="text-slate-900 text-sm font-mono mt-0.5 block">{leftRun?.avg_score || "--"} 分</strong>
                <span className="text-[10px] text-slate-500 truncate block">{leftRun?.date} · 候选 {leftSymbols.length} 只</span>
              </div>
              <div className="p-2.5 bg-slate-50 rounded-lg">
                <span className="text-[10px] text-slate-400 block">实验 B 平均综合分</span>
                <strong className="text-slate-900 text-sm font-mono mt-0.5 block">{rightRun?.avg_score || "--"} 分</strong>
                <span className="text-[10px] text-slate-500 truncate block">{rightRun?.date} · 候选 {rightSymbols.length} 只</span>
              </div>
              <div className="p-2.5 bg-slate-50 rounded-lg">
                <span className="text-[10px] text-slate-400 block">两期标的重合度</span>
                <strong className="text-indigo-700 text-sm font-mono mt-0.5 block">
                  {leftSymbols.length > 0 ? `${((preserved.length / leftSymbols.length) * 100).toFixed(0)}%` : "0%"}
                </strong>
                <span className="text-[10px] text-slate-500 block">两期共有 {preserved.length} 只标的</span>
              </div>
              <div className="p-2.5 bg-slate-50 rounded-lg">
                <span className="text-[10px] text-slate-400 block">名单置换变化率</span>
                <strong className="text-amber-700 text-sm font-mono mt-0.5 block">
                  {leftSymbols.length > 0 ? `${((newlyAdded.length / leftSymbols.length) * 100).toFixed(0)}%` : "0%"}
                </strong>
                <span className="text-[10px] text-slate-500 block">新进 {newlyAdded.length} 只 / 跌出 {dropped.length} 只</span>
              </div>
            </div>

            {/* Side-by-Side Previews */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-slate-50/70 p-4 rounded-xl border border-slate-200">
              {/* Left Run Preview */}
              <div className="bg-white p-3.5 rounded-lg border border-slate-200 space-y-2">
                <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                  <div className="flex items-center space-x-2">
                    <span className="w-2 h-2 rounded-full bg-indigo-600"></span>
                    <span className="text-xs font-bold text-slate-900">实验 A ({leftRun?.date}) 候选标的</span>
                  </div>
                  <span className="text-[10px] text-slate-400 font-mono">{leftRun?.run_id?.slice(0, 15)}</span>
                </div>
                <div className="space-y-1.5 max-h-72 overflow-y-auto">
                  {leftSymbols.map((sym, idx) => {
                    const inBoth = rightSymbols.includes(sym);
                    return (
                      <div
                        key={sym}
                        className={`px-3 py-2 rounded-lg border flex items-center justify-between text-xs transition-colors ${
                          inBoth ? "bg-slate-50/60 border-slate-200" : "bg-emerald-50/50 border-emerald-200"
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
                              实验A新进
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
                    <span className="text-xs font-bold text-slate-900">实验 B ({rightRun?.date}) 候选标的</span>
                  </div>
                  <span className="text-[10px] text-slate-400 font-mono">{rightRun?.run_id?.slice(0, 15)}</span>
                </div>
                <div className="space-y-1.5 max-h-72 overflow-y-auto">
                  {rightSymbols.map((sym, idx) => {
                    const inBoth = leftSymbols.includes(sym);
                    return (
                      <div
                        key={sym}
                        className={`px-3 py-2 rounded-lg border flex items-center justify-between text-xs transition-colors ${
                          inBoth ? "bg-slate-50/60 border-slate-200" : "bg-rose-50/50 border-rose-200"
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

            {/* Diff Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-1">
              {/* 新进 */}
              <div className="p-4 bg-emerald-50/70 border border-emerald-200 rounded-xl flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-emerald-800 flex items-center">
                      <ArrowUpRight className="w-4 h-4 mr-1 text-emerald-600" />
                      新晋优选标的
                    </span>
                    <span className="text-xs font-mono font-bold px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800">
                      {newlyAdded.length} 只
                    </span>
                  </div>
                  <div className="space-y-1.5 max-h-48 overflow-y-auto">
                    {newlyAdded.length === 0 ? (
                      <div className="py-3 text-center text-xs text-emerald-600/70">无新晋标的，名单完全子集</div>
                    ) : (
                      newlyAdded.map(s => (
                        <div key={s} className="p-2 bg-white rounded border border-emerald-200 text-xs flex items-center justify-between">
                          <span className="font-bold text-slate-900">{getStockName(s)} ({s})</span>
                          <span className="text-[10px] text-emerald-700 font-semibold bg-emerald-50 px-1.5 py-0.5 rounded">新入围</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>

              {/* 跌出 */}
              <div className="p-4 bg-rose-50/70 border border-rose-200 rounded-xl flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-rose-800 flex items-center">
                      <ArrowDownRight className="w-4 h-4 mr-1 text-rose-600" />
                      跌出优选标的
                    </span>
                    <span className="text-xs font-mono font-bold px-1.5 py-0.5 rounded bg-rose-100 text-rose-800">
                      {dropped.length} 只
                    </span>
                  </div>
                  <div className="space-y-1.5 max-h-48 overflow-y-auto">
                    {dropped.length === 0 ? (
                      <div className="py-3 text-center text-xs text-rose-600/70">无跌出标的</div>
                    ) : (
                      dropped.map(s => (
                        <div key={s} className="p-2 bg-white rounded border border-rose-200 text-xs flex items-center justify-between">
                          <span className="font-bold text-slate-900">{getStockName(s)} ({s})</span>
                          <span className="text-[10px] text-rose-700 font-semibold bg-rose-50 px-1.5 py-0.5 rounded">滑出名单</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>

              {/* 稳定 */}
              <div className="p-4 bg-indigo-50/70 border border-indigo-200 rounded-xl flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-indigo-800 flex items-center">
                      <CheckCircle2 className="w-4 h-4 mr-1 text-indigo-600" />
                      两期持续稳健重合
                    </span>
                    <span className="text-xs font-mono font-bold px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-800">
                      {preserved.length} 只
                    </span>
                  </div>
                  <div className="space-y-1.5 max-h-48 overflow-y-auto">
                    {preserved.length === 0 ? (
                      <div className="py-3 text-center text-xs text-indigo-600/70">两期无共同重合标的</div>
                    ) : (
                      preserved.map(s => (
                        <div key={s} className="p-2 bg-white rounded border border-indigo-200 text-xs flex items-center justify-between">
                          <span className="font-bold text-slate-900">{getStockName(s)} ({s})</span>
                          <span className="text-[10px] text-indigo-700 font-semibold bg-indigo-50 px-1.5 py-0.5 rounded">持续入围</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* 模式 2：策略回测业绩对比 (Backtest Diff View) */
          <div className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-2xs">
                <span className="text-[11px] text-slate-500 block">累计超额收益对比</span>
                <div className="mt-1 flex items-baseline space-x-2">
                  <span className="text-base font-bold font-mono text-purple-700">{leftRun?.excess_return != null ? `+${leftRun.excess_return}%` : "--"}</span>
                  <span className="text-xs text-slate-400">vs</span>
                  <span className="text-sm font-mono text-slate-600">{rightRun?.excess_return != null ? `+${rightRun.excess_return}%` : "--"}</span>
                </div>
                <span className="text-[10px] text-slate-400 mt-0.5 block">扣除全额交易摩擦后</span>
              </div>

              <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-2xs">
                <span className="text-[11px] text-slate-500 block">夏普比率 (Sharpe) 对比</span>
                <div className="mt-1 flex items-baseline space-x-2">
                  <span className="text-base font-bold font-mono text-indigo-700">{leftRun?.sharpe || "--"}</span>
                  <span className="text-xs text-slate-400">vs</span>
                  <span className="text-sm font-mono text-slate-600">{rightRun?.sharpe || "--"}</span>
                </div>
                <span className="text-[10px] text-slate-400 mt-0.5 block">单位总波动收益性价比</span>
              </div>

              <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-2xs">
                <span className="text-[11px] text-slate-500 block">回测调仓期数对比</span>
                <div className="mt-1 flex items-baseline space-x-2">
                  <span className="text-base font-bold font-mono text-slate-900">{leftRun?.stock_count || 36} 期</span>
                  <span className="text-xs text-slate-400">vs</span>
                  <span className="text-sm font-mono text-slate-600">{rightRun?.stock_count || 36} 期</span>
                </div>
                <span className="text-[10px] text-slate-400 mt-0.5 block">样本外非重叠区间</span>
              </div>

              <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-2xs">
                <span className="text-[11px] text-slate-500 block">综合量化评估结论</span>
                <div className="mt-1 font-bold text-xs text-emerald-700">
                  {(Number(leftRun?.sharpe) || 0) >= (Number(rightRun?.sharpe) || 0) ? "实验 A 收益风险比占优" : "实验 B 稳定性更佳"}
                </div>
                <span className="text-[10px] text-slate-400 mt-0.5 block">基于样本外超额与波动</span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600 leading-relaxed">
              💡 <strong>回测对比提示：</strong> 策略回测对比侧重于中长期净值稳定性与最大回撤控制。若实验 A 的夏普比率显著更高，说明在同等波动下创造了更多超额 alpha。
            </div>
          </div>
        )}
      </div>

      {/* Run Detail Modal */}{/* Run Detail Modal */}
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