const fs = require('fs');

// 1. 更新 StockPoolView.tsx
let spContent = fs.readFileSync('src/components/StockPoolView.tsx', 'utf8');

// 引入 ChevronUp
if (!spContent.includes('ChevronUp')) {
  spContent = spContent.replace("ChevronDown,", "ChevronDown,\n  ChevronUp,");
}

// 加入 showLogDrawer 状态与 pipelineStats
if (!spContent.includes('showLogDrawer')) {
  const targetState = "const activityLogRef = useRef<HTMLDivElement>(null);";
  spContent = spContent.replace(targetState, "const [showLogDrawer, setShowLogDrawer] = useState(false);");
  
  const targetHook = "useEffect(() => {\n    refreshMarketData();\n  }, []);";
  const newStats = `useEffect(() => {
    refreshMarketData();
  }, []);

  const pipelineStats = useMemo(() => {
    const updatedStocks = downloadDetails.filter(d => d.ok === true && (d.rows || 0) > 0).length;
    const latestStocks = downloadDetails.filter(d => d.ok === true && (d.rows || 0) === 0).length;
    const failedStocks = downloadDetails.filter(d => d.ok === false).length;
    const totalRows = downloadDetails.reduce((sum, d) => sum + (d.rows || 0), 0);
    const lastItem = downloadDetails[downloadDetails.length - 1] || null;
    return { updatedStocks, latestStocks, failedStocks, totalRows, lastItem };
  }, [downloadDetails]);`;
  spContent = spContent.replace(targetHook, newStats);
}

// 替换整个旧的行情更新明细区域
const oldStart = "{(isDownloading || downloadDetails.length > 0 || downloadError) && (";
const oldEnd = "      {/* Data Quality Diagnosis Banner */}";

const startIdx = spContent.indexOf(oldStart);
const endIdx = spContent.indexOf(oldEnd);

if (startIdx !== -1 && endIdx !== -1) {
  const newHud = `{(isDownloading || downloadDetails.length > 0 || downloadError) && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          {/* Header */}
          <div className="px-5 py-3.5 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 bg-gradient-to-r from-slate-50 to-white">
            <div>
              <div className="flex items-center space-x-2">
                <span className={`w-2 h-2 rounded-full ${isDownloading ? 'bg-indigo-600 animate-ping' : downloadError ? 'bg-rose-500' : 'bg-emerald-500'}`} />
                <h3 className="text-sm font-bold text-slate-900">行情更新进度</h3>
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-mono">
                  {downloadProgress}%
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                {downloadMessage || '正在按需增量拉取最新交易日行情 Bar 并对齐入库'}
              </p>
            </div>
            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={() => setShowLogDrawer(prev => !prev)}
                className="inline-flex items-center text-xs font-medium text-slate-600 hover:text-indigo-600 transition-colors px-2.5 py-1 rounded border border-slate-200 bg-white hover:bg-slate-50 cursor-pointer"
              >
                <span>{showLogDrawer ? '收起底层日志' : `查看底层明细日志 (${downloadDetails.length})`}</span>
                {showLogDrawer ? <ChevronUp className="w-3.5 h-3.5 ml-1" /> : <ChevronDown className="w-3.5 h-3.5 ml-1" />}
              </button>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="h-1.5 bg-slate-100 w-full overflow-hidden">
            <div
              className={`h-full transition-all duration-300 ${downloadError ? 'bg-rose-500' : 'bg-gradient-to-r from-indigo-500 via-indigo-600 to-emerald-500'}`}
              style={{ width: `${Math.min(100, Math.max(5, downloadProgress))}%` }}
            />
          </div>

          {/* Compact 4-Card HUD */}
          <div className="p-4 grid grid-cols-2 sm:grid-cols-4 gap-3 bg-white">
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
              <span className="text-[11px] text-slate-500 block">处理总标的</span>
              <div className="text-base font-bold font-mono text-slate-900 mt-0.5">
                {downloadDetails.length} <span className="text-xs text-slate-400 font-normal">/ {stocks.length} 只</span>
              </div>
              <span className="text-[10px] text-slate-400">覆盖股票池</span>
            </div>

            <div className="p-3 rounded-lg bg-emerald-50/60 border border-emerald-100/80">
              <span className="text-[11px] text-emerald-700 block">成功增量补齐</span>
              <div className="text-base font-bold font-mono text-emerald-800 mt-0.5">
                {pipelineStats.updatedStocks} <span className="text-xs text-emerald-600 font-normal">只标的</span>
              </div>
              <span className="text-[10px] text-emerald-600">新增 {pipelineStats.totalRows} 行数据</span>
            </div>

            <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
              <span className="text-[11px] text-slate-500 block">已是最新免更新</span>
              <div className="text-base font-bold font-mono text-slate-700 mt-0.5">
                {pipelineStats.latestStocks} <span className="text-xs text-slate-400 font-normal">只标的</span>
              </div>
              <span className="text-[10px] text-slate-400">本地已对齐最近收盘</span>
            </div>

            <div className={`p-3 rounded-lg border ${pipelineStats.failedStocks > 0 ? 'bg-rose-50 border-rose-200' : 'bg-slate-50 border-slate-100'}`}>
              <span className={`text-[11px] block ${pipelineStats.failedStocks > 0 ? 'text-rose-700 font-semibold' : 'text-slate-500'}`}>失败与异常</span>
              <div className={`text-base font-bold font-mono mt-0.5 ${pipelineStats.failedStocks > 0 ? 'text-rose-700' : 'text-slate-700'}`}>
                {pipelineStats.failedStocks} <span className="text-xs font-normal">只</span>
              </div>
              <span className="text-[10px] text-slate-400">{pipelineStats.failedStocks > 0 ? '需检查网络或代码' : '无网络或解析故障'}</span>
            </div>
          </div>

          {/* Active Focus Chip */}
          {pipelineStats.lastItem && (
            <div className="px-4 py-2.5 bg-slate-50/70 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2 text-xs">
              <div className="flex items-center space-x-2">
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700">最新同步标的</span>
                <span className="font-bold text-slate-800">{pipelineStats.lastItem.name || pipelineStats.lastItem.symbol}</span>
                <span className="font-mono text-slate-400">({pipelineStats.lastItem.symbol})</span>
                <span className="text-slate-500 text-[11px]">{pipelineStats.lastItem.note || '增量更新完成'}</span>
              </div>
              {pipelineStats.lastItem.rows != null && (
                <span className="text-[11px] font-mono text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                  +{pipelineStats.lastItem.rows} 交易日 K线
                </span>
              )}
            </div>
          )}

          {/* Collapsible Detailed Log Drawer (Default Closed) */}
          {showLogDrawer && (
            <div className="max-h-60 overflow-y-auto border-t border-slate-100 divide-y divide-slate-100 bg-white text-xs">
              {downloadDetails.map((detail) => (
                <div key={detail.symbol} className="px-4 py-2 flex items-center justify-between hover:bg-slate-50/80 transition-colors">
                  <div className="flex items-center space-x-2">
                    <span className="font-mono font-semibold text-slate-800">{detail.symbol}</span>
                    <span className="font-medium text-slate-700">{detail.name || '--'}</span>
                    <span className="text-[11px] text-slate-400 font-mono">{detail.start && detail.end ? `${detail.start} ~ ${detail.end}` : ''}</span>
                  </div>
                  <div className="flex items-center space-x-2 text-right">
                    <span className={`text-[11px] font-medium ${detail.ok === false ? 'text-rose-600' : 'text-slate-500'}`}>
                      {detail.error || detail.note || (detail.ok ? '成功' : '处理中')}
                    </span>
                    {detail.rows != null && detail.rows > 0 && (
                      <span className="font-mono text-emerald-600 text-[11px]">+{detail.rows}行</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}\n\n      `;
  spContent = spContent.slice(0, startIdx) + newHud + spContent.slice(endIdx);
  fs.writeFileSync('src/components/StockPoolView.tsx', spContent, 'utf8');
  console.log('StockPoolView.tsx updated successfully!');
} else {
  console.error('Could not find start or end index:', startIdx, endIdx);
}

// 2. 更新 Navbar.tsx（移除“恢复默认”按钮）
let nbContent = fs.readFileSync('src/components/Navbar.tsx', 'utf8');
nbContent = nbContent.replace(/onResetToDefault: () => void;\r?\n/g, '');
nbContent = nbContent.replace(/onResetToDefault,\r?\n/g, '');
const btnRegex = /<button\s+onClick=\{onResetToDefault\}[\s\S]*?<\/button>/g;
nbContent = nbContent.replace(btnRegex, '');
fs.writeFileSync('src/components/Navbar.tsx', nbContent, 'utf8');
console.log('Navbar.tsx updated successfully!');

// 3. 更新 App.tsx（移除 Navbar 的 onResetToDefault）
let appContent = fs.readFileSync('src/App.tsx', 'utf8');
appContent = appContent.replace(/onResetToDefault=\{handleResetToDefault\}\r?\n/g, '');
fs.writeFileSync('src/App.tsx', appContent, 'utf8');
console.log('App.tsx updated successfully!');
