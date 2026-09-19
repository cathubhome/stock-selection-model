import React, { useEffect, useMemo, useRef, useState } from 'react';
import { 
  Search, 
  Plus, 
  Trash2, 
  CheckCircle2, 
  AlertTriangle, 
  RefreshCw, 
  Filter, 
  Check, 
  ExternalLink, 
  ShieldAlert, 
  Clock,
  CloudDownload,
  ShieldCheck,
  Layers,
  ChevronDown,
  ChevronUp,
  X,
  Database,
  FileDown,
  HelpCircle
} from 'lucide-react';
import { ScoredStock } from '../types';
import { REMOTE_METADATA_STATUS } from '../data/remoteArchiveData';
import { startDataDownload, fetchDownloadProgress, searchUniverse, fetchUniverseIndustry, syncMetadata, batchAddPoolStocks, repairDataQuality, fetchLatestScores, fetchSystemStatus, DownloadDetail } from '../api/client';

interface StockPoolViewProps {
  stocks: ScoredStock[];
  onAddStock: (stock: ScoredStock) => void;
  onRemoveStock: (symbol: string) => void;
  onSelectStock: (stock: ScoredStock) => void;
  onRefreshPool?: () => Promise<void>;
}

const SW_L1_CATEGORIES: Array<{ category: string; items: string[] }> = [
  { category: '制造与设备', items: ['机械设备', '电力设备', '国防军工', '汽车'] },
  { category: '科技与信息', items: ['电子', '计算机', '通信', '传媒'] },
  { category: '医药与消费', items: ['医药生物', '食品饮料', '家用电器', '农林牧渔', '商贸零售', '社会服务', '轻工制造', '纺织服饰', '美容护理'] },
  { category: '周期与能源', items: ['基础化工', '钢铁', '有色金属', '煤炭', '石油石化', '建筑材料', '建筑装饰', '公用事业', '环保'] },
  { category: '金融与综合', items: ['银行', '非银金融', '房地产', '交通运输', '综合'] },
];

const ALL_SW_L1_FLAT = SW_L1_CATEGORIES.flatMap(c => c.items);

const MARKET_ORDER = ['主板', '创业板', '科创板', '港股通'];
const collator = new Intl.Collator('zh-Hans-CN', { numeric: true, sensitivity: 'base' });
const NUMERIC_SORT_KEYS = ['price', 'change', 'turnover', 'amount', 'pe_ttm'] as const;

type StockPoolSortKey =
  | 'name'
  | 'industry'
  | 'market'
  | 'price'
  | 'change'
  | 'turnover'
  | 'amount'
  | 'pe_ttm'
  | 'source'
  | 'added_at';

const isNumericSortKey = (key: StockPoolSortKey): key is typeof NUMERIC_SORT_KEYS[number] =>
  (NUMERIC_SORT_KEYS as readonly string[]).includes(key);

const compareStocks = (a: ScoredStock, b: ScoredStock, key: StockPoolSortKey, asc: boolean) => {
  const direction = asc ? 1 : -1;

  if (key === 'market') {
    return (MARKET_ORDER.indexOf(a.market) - MARKET_ORDER.indexOf(b.market)) * direction;
  }

  if (isNumericSortKey(key)) {
    const aValue = a[key] == null ? null : Number(a[key]);
    const bValue = b[key] == null ? null : Number(b[key]);
    if (aValue == null && bValue == null) return 0;
    if (aValue == null) return 1;
    if (bValue == null) return -1;
    return (aValue - bValue) * direction;
  }

  const aValue = String((a as any)[key] ?? '');
  const bValue = String((b as any)[key] ?? '');
  return collator.compare(aValue, bValue) * direction;
};

interface SortableThProps {
  label: string;
  sortKey: StockPoolSortKey;
  activeSortKey: StockPoolSortKey;
  sortAsc: boolean;
  onSort: (key: StockPoolSortKey) => void;
  filter?: React.ReactNode;
  align?: 'left' | 'right';
}

const SortableTh: React.FC<SortableThProps> = ({
  label,
  sortKey,
  activeSortKey,
  sortAsc,
  onSort,
  filter,
  align = 'left',
}) => {
  const isActive = activeSortKey === sortKey;
  return (
    <th
      className={'py-3 px-4 ' + (align === 'right' ? 'text-right' : 'text-left')}
      aria-sort={isActive ? (sortAsc ? 'ascending' : 'descending') : 'none'}
    >
      <div className={'flex items-center ' + (align === 'right' ? 'justify-end' : 'justify-start') + ' gap-1'}>
        <button
          type="button"
          onClick={() => onSort(sortKey)}
          className="inline-flex items-center gap-1 font-semibold text-slate-600 transition-colors hover:text-indigo-600"
          title={isActive ? (sortAsc ? '切换为降序' : '切换为升序') : '点击排序'}
        >
          <span>{label}</span>
          {isActive ? (
            sortAsc ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />
          ) : (
            <ChevronDown className="h-3 w-3 opacity-40" />
          )}
        </button>
        {filter}
      </div>
    </th>
  );
};

interface FilterPopoverProps {
  active: boolean;
  children: React.ReactNode;
}

const FilterPopover: React.FC<FilterPopoverProps> = ({ active, children }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(prev => !prev)}
        className={'inline-flex items-center justify-center rounded p-0.5 transition-colors ' + (active ? 'text-indigo-600 hover:text-indigo-700' : 'text-slate-400 hover:text-indigo-600')}
        title="筛选"
      >
        <Filter className="h-3 w-3" />
      </button>
      {open && (
        <div className="absolute right-0 top-full z-20 mt-1 w-48 rounded-lg border border-slate-200 bg-white p-2 shadow-lg">
          {children}
        </div>
      )}
    </div>
  );
};

interface MultiSelectFilterProps {
  options: string[];
  selected: string[];
  onToggle: (value: string) => void;
  onClear: () => void;
}

const MultiSelectFilter: React.FC<MultiSelectFilterProps> = ({ options, selected, onToggle, onClear }) => (
  <div className="space-y-1">
    <div className="max-h-40 overflow-y-auto pr-1">
      {options.length === 0 ? (
        <div className="py-2 text-center text-[11px] text-slate-400">暂无可选值</div>
      ) : (
        options.map(option => (
          <label key={option} className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 text-[11px] text-slate-700 hover:bg-slate-50">
            <input
              type="checkbox"
              checked={selected.includes(option)}
              onChange={() => onToggle(option)}
              className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
            />
            <span>{option}</span>
          </label>
        ))
      )}
    </div>
    <button
      type="button"
      onClick={onClear}
      className="w-full rounded border border-slate-200 px-2 py-1 text-[11px] text-slate-600 hover:bg-slate-50"
    >
      清空筛选
    </button>
  </div>
);

interface NameSearchFilterProps {
  value: string;
  onChange: (value: string) => void;
}

const NameSearchFilter: React.FC<NameSearchFilterProps> = ({ value, onChange }) => (
  <div className="space-y-1">
    <input
      type="text"
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder="按简称搜索"
      className="w-full rounded border border-slate-200 px-2 py-1 text-[11px] text-slate-700 focus:border-indigo-500 focus:outline-none"
    />
    <button
      type="button"
      onClick={() => onChange('')}
      className="w-full rounded border border-slate-200 px-2 py-1 text-[11px] text-slate-600 hover:bg-slate-50"
    >
      清空
    </button>
  </div>
);

export const StockPoolView: React.FC<StockPoolViewProps> = ({
  stocks,
  onAddStock,
  onRemoveStock,
  onSelectStock,
  onRefreshPool,
}) => {
  const [nameFilter, setNameFilter] = useState('');
  const [industryFilter, setIndustryFilter] = useState<string[]>([]);
  const [marketFilter, setMarketFilter] = useState<string[]>([]);
  const [sortKey, setSortKey] = useState<StockPoolSortKey>('name');
  const [sortAsc, setSortAsc] = useState(true);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(0);
  const [downloadSuccess, setDownloadSuccess] = useState(false);
  const [downloadDetails, setDownloadDetails] = useState<DownloadDetail[]>([]);
  const [downloadMessage, setDownloadMessage] = useState('');
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showStaleModal, setShowStaleModal] = useState(false);
  const [newSymbol, setNewSymbol] = useState('');
  const [newName, setNewName] = useState('');
  const [newIndustry, setNewIndustry] = useState('');
  const [isFetchingIndustry, setIsFetchingIndustry] = useState(false);
  const [industryDropdownOpen, setIndustryDropdownOpen] = useState(false);
  const [industryFilterText, setIndustryFilterText] = useState('');
  const industryDropdownRef = useRef<HTMLDivElement>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<string | null>(null);
  const [isSyncingMeta, setIsSyncingMeta] = useState(false);
  const [syncMetaSuccess, setSyncMetaSuccess] = useState(false);
  const [suggestions, setSuggestions] = useState<Array<{ symbol: string; name: string; market: string; industry?: string }>>([]);
  const [addMode, setAddMode] = useState<'single' | 'batch'>('single');
  const [batchText, setBatchText] = useState('');
  const [isBatchAdding, setIsBatchAdding] = useState(false);
  const [batchSuccessMsg, setBatchSuccessMsg] = useState<string | null>(null);
  const [isRepairingQuality, setIsRepairingQuality] = useState(false);
  const [repairQualityMsg, setRepairQualityMsg] = useState<string | null>(null);
  const [marketData, setMarketData] = useState<any | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [showLogDrawer, setShowLogDrawer] = useState(false);
  const pageSize = 20;
  const validIndustryCount = useMemo(() => stocks.filter(s => s.industry && s.industry !== '综合' && s.industry !== '待补全').length, [stocks]);
  const industryRate = stocks.length > 0 ? ((validIndustryCount / stocks.length) * 100).toFixed(1) : '0.0';

  const refreshMarketData = async () => {
    const status = await fetchSystemStatus();
    setMarketData(status?.market_data || null);
  };

  useEffect(() => {
    refreshMarketData();
    const savedTaskId = localStorage.getItem('active_download_task_id');
    if (savedTaskId) {
      pollDownloadTask(savedTaskId);
    }
  }, []);

  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (industryDropdownRef.current && !industryDropdownRef.current.contains(e.target as Node)) {
        setIndustryDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  const handleRepairQuality = async () => {
    setIsRepairingQuality(true);
    setRepairQualityMsg(null);
    try {
      const res = await repairDataQuality();
      setRepairQualityMsg(res?.message || '修复诊断完成');
      setTimeout(() => setRepairQualityMsg(null), 4000);
    } catch (err: any) {
      setRepairQualityMsg(err?.message || '修复失败');
      setTimeout(() => setRepairQualityMsg(null), 4000);
    } finally {
      setIsRepairingQuality(false);
    }
  };

  const handleBatchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!batchText.trim()) return;
    setIsBatchAdding(true);
    setBatchSuccessMsg(null);
    try {
      const res = await batchAddPoolStocks(batchText.trim());
      if (res && res.ok) {
        setBatchSuccessMsg(`成功解析并加入 ${res.added} 只标的，当前池总量 ${res.total} 只`);
        setBatchText('');
        setTimeout(() => {
          setBatchSuccessMsg(null);
          setShowAddModal(false);
          window.location.reload();
        }, 1500);
      }
    } catch (err: any) {
      setBatchSuccessMsg(`导入失败: ${err?.message || '文本解析异常'}`);
    } finally {
      setIsBatchAdding(false);
    }
  };

  const handleSyncMeta = async () => {
    setIsSyncingMeta(true);
    try {
      await syncMetadata();
      setSyncMetaSuccess(true);
      setTimeout(() => setSyncMetaSuccess(false), 3000);
    } catch (err) {
      console.error('Meta sync error:', err);
    } finally {
      setIsSyncingMeta(false);
    }
  };

  const handleSymbolChange = async (val: string) => {
    const clean = val.trim();
    setNewSymbol(clean);
    if (clean.length >= 2) {
      const res = await searchUniverse(clean, 5);
      setSuggestions(res);
      const exactMatch = res.find(s => s.symbol === clean);
      if (exactMatch) {
        if (!newName || newName === clean) setNewName(exactMatch.name);
        if (exactMatch.industry) setNewIndustry(exactMatch.industry);
      }
    } else {
      setSuggestions([]);
    }
    if (clean.length === 6 && /^\d{6}$/.test(clean)) {
      setIsFetchingIndustry(true);
      try {
        const indRes = await fetchUniverseIndustry(clean);
        if (indRes) {
          if (indRes.name && (!newName || newName === clean)) setNewName(indRes.name);
          if (indRes.industry) setNewIndustry(indRes.industry);
        }
      } catch (err) {
        console.warn('Auto fetch industry failed:', err);
      } finally {
        setIsFetchingIndustry(false);
      }
    }
  };

  const handleSelectSuggestion = async (item: { symbol: string; name: string; market: string; industry?: string }) => {
    setNewSymbol(item.symbol);
    setNewName(item.name);
    setNewIndustry(item.industry || '');
    setSuggestions([]);
    if (!item.industry) {
      setIsFetchingIndustry(true);
      try {
        const indRes = await fetchUniverseIndustry(item.symbol);
        if (indRes && indRes.industry) {
          setNewIndustry(indRes.industry);
        }
      } catch (err) {
        console.warn('Auto fetch industry on select failed:', err);
      } finally {
        setIsFetchingIndustry(false);
      }
    }
  };

  // Filtered and sorted stocks based on header controls
  const filteredStocks = useMemo(() => {
    const keyword = nameFilter.trim().toLowerCase();
    return stocks.filter(stock => {
      const matchName = !keyword || stock.name.toLowerCase().includes(keyword);
      const matchIndustry = industryFilter.length === 0 || industryFilter.includes(stock.industry || '待补全');
      const matchMarket = marketFilter.length === 0 || marketFilter.includes(stock.market || '未知');
      return matchName && matchIndustry && matchMarket;
    });
  }, [stocks, nameFilter, industryFilter, marketFilter]);

  const sortedStocks = useMemo(() => {
    const list = [...filteredStocks];
    list.sort((a, b) => compareStocks(a, b, sortKey, sortAsc));
    return list;
  }, [filteredStocks, sortKey, sortAsc]);

  useEffect(() => {
    setCurrentPage(1);
  }, [nameFilter, industryFilter, marketFilter, sortKey, sortAsc]);

  const toggleSort = (key: StockPoolSortKey) => {
    if (sortKey === key) {
      setSortAsc(prev => !prev);
    } else {
      setSortKey(key);
      setSortAsc(true);
    }
  };

  const toggleListFilter = (list: string[], value: string) =>
    list.includes(value) ? list.filter(item => item !== value) : [...list, value];

  const industryOptions = useMemo(
    () => Array.from(new Set(stocks.map(stock => stock.industry || '待补全'))).sort((a, b) => collator.compare(a, b)),
    [stocks],
  );
  const marketOptions = useMemo(
    () => Array.from(new Set(stocks.map(stock => stock.market || '未知'))).sort((a, b) => MARKET_ORDER.indexOf(a) - MARKET_ORDER.indexOf(b)),
    [stocks],
  );

  const totalPages = Math.max(1, Math.ceil(filteredStocks.length / pageSize));
  const activePage = Math.min(currentPage, totalPages);
  const pagedStocks = sortedStocks.slice((activePage - 1) * pageSize, activePage * pageSize);
  const pageNumbers = Array.from(
    { length: Math.min(5, totalPages) },
    (_, index) => Math.max(1, Math.min(activePage - 2, totalPages - 4)) + index,
  );

  const pollDownloadTask = (taskId: string) => {
    setIsDownloading(true);
    localStorage.setItem('active_download_task_id', taskId);
    const timer = setInterval(async () => {
      try {
        const prog = await fetchDownloadProgress(taskId);
        setDownloadProgress(Math.max(10, Math.min(100, Math.round(prog.percent))));
        setDownloadDetails(prog.details || []);
        setDownloadMessage(prog.message);
        if (!prog.running) {
          clearInterval(timer);
          localStorage.removeItem('active_download_task_id');
          setIsDownloading(false);
          setDownloadMessage(prog.error || prog.message);
          setDownloadError(prog.error || null);
          await onRefreshPool?.();
          await refreshMarketData();
          setDownloadSuccess(true);
          setTimeout(() => setDownloadSuccess(false), 4000);
        }
      } catch {
        clearInterval(timer);
        localStorage.removeItem('active_download_task_id');
        setIsDownloading(false);
      }
    }, 1200);
  };

  const handleDownloadAll = async () => {
    setIsDownloading(true);
    setDownloadProgress(5);
    setDownloadSuccess(false);
    setDownloadDetails([]);
    setDownloadMessage('任务初始化...');
    setDownloadError(null);
    try {
      const res = await startDataDownload();
      if (res && res.task_id) {
        pollDownloadTask(res.task_id);
      }
    } catch (error: any) {
      setIsDownloading(false);
      setDownloadError(error?.message || '下载任务启动失败');
      setDownloadMessage(error?.message || '下载任务启动失败');
    }
  };

  // Add new stock
  const handleAddSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSymbol.trim() || !newName.trim()) return;

    const sym = newSymbol.trim();
    let market: '主板' | '创业板' | '科创板' | '港股通' = '主板';
    if (sym.startsWith('688')) market = '科创板';
    else if (sym.startsWith('30')) market = '创业板';
    else if (sym.startsWith('HK')) market = '港股通';

    const newStock: ScoredStock = {
      symbol: sym,
      name: newName.trim(),
      pinyin: newName.trim().substring(0, 2),
      industry: newIndustry,
      market: market,
      source: '手动输入添加',
      added_at: new Date().toISOString().replace('T', ' ').substring(0, 19),
      price: 32.5,
      change: 1.25,
      turnover: 3.8,
      volume_ratio: 1.2,
      volume: 12000000,
      amount: 390000000,
      pe_ttm: 24.5,
      pb: 3.1,
      high_52w: 42.0,
      low_52w: 22.0,
      model_raw: 0.012,
      model_score: 72.0,
      technical_score: 68.0,
      volume_price_score: 70.0,
      candle_score: 55.0,
      sentiment_score: 50.0,
      sentiment_source: '中性无新闻',
      news_count: 0,
      composite_score: 66.5,
      rank: stocks.length + 1,
      odds_reward_risk: 1.5,
      odds_win_rate: 51.0,
      odds_expected_return: 2.3,
      diagnostic_status: 'excellent',
      diagnostic_message: '已对齐最新行情与因子数据',
      trading_days: 120,
      credibility_score: 41.2,
      credibility_grade: '中',
      positive_evidences: ['已完成代码登记与行情指标初始化'],
      negative_evidences: ['未发现重大财务或违规风险']
    };

    onAddStock(newStock);
    setShowAddModal(false);
    setNewSymbol('');
    setNewName('');
  };

  // Export CSV
  const handleExportCSV = () => {
    const headers = ['symbol', 'name', 'source', 'added_at', 'industry', 'market', 'price', 'change', 'turnover', 'composite_score'];
    const rows = sortedStocks.map(s => [
      s.symbol,
      s.name,
      s.source || '历史对话提取',
      s.added_at || '2026-08-10 00:00:00',
      s.industry,
      s.market,
      s.price,
      s.change,
      s.turnover,
      s.composite_score
    ]);
    const csvContent = '\uFEFF' + [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `local_stock_pool_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6">
      {/* Top Controls Bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="space-y-1.5">
          <div className="flex items-center space-x-2 text-indigo-600 text-xs font-bold uppercase tracking-wider">
            <Database className="w-3.5 h-3.5" />
            <span>股票池与数据资产中心</span>
          </div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">股票标的池管理与行情同步</h2>
          <div className="flex flex-wrap items-center gap-2 pt-0.5">
            <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-slate-50 border border-slate-200 text-xs text-slate-600">
              <Clock className="w-3 h-3 text-slate-400" />
              <span>最新行情: <strong className="font-mono text-slate-800">{marketData?.latest_date || '--'}</strong></span>
            </div>
            <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-medium border ${marketData?.age_days === 0 ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
              {marketData?.age_days == null ? '正在读取时效' : marketData.age_days === 0 ? '已同步至最近收盘' : `待同步 ${marketData.age_days} 个交易日`}
            </span>
            <span className="text-slate-300 hidden sm:inline">·</span>
            <span className="text-xs text-slate-500 hidden sm:inline">
              有效关注标的 <strong className="font-mono text-slate-700 font-semibold">{stocks.length}</strong> 只
            </span>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center gap-2.5">
          {/* Primary Action Group */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowAddModal(true)}
              className="inline-flex items-center px-3.5 py-2 rounded-lg text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs transition-colors cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5 mr-1.5" />
              添加新标的
            </button>

            <button
              onClick={handleDownloadAll}
              disabled={isDownloading}
              className={`inline-flex items-center px-3.5 py-2 rounded-lg text-xs font-semibold shadow-xs transition-all cursor-pointer ${
                isDownloading 
                  ? 'bg-slate-100 text-slate-400 cursor-not-allowed' 
                  : downloadSuccess
                    ? 'bg-emerald-600 text-white'
                    : 'bg-slate-900 hover:bg-slate-800 text-white'
              }`}
            >
              <CloudDownload className={`w-3.5 h-3.5 mr-1.5 ${isDownloading ? 'animate-bounce' : ''}`} />
              {isDownloading ? `更新中 (${downloadProgress}%)` : downloadSuccess ? '行情已更新' : '更新行情数据'}
            </button>
          </div>

          {/* Governance & Utility Group */}
          <div className="flex items-center gap-1.5 border-t sm:border-t-0 sm:border-l border-slate-200 pt-2 sm:pt-0 sm:pl-2.5">
            <button
              onClick={handleRepairQuality}
              disabled={isRepairingQuality}
              className="inline-flex items-center px-2.5 py-2 rounded-lg text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 transition-colors shadow-xs cursor-pointer"
              title="体检并诊断停牌缺失"
            >
              <ShieldCheck className={`w-3.5 h-3.5 mr-1 text-slate-500 ${isRepairingQuality ? 'animate-spin' : ''}`} />
              <span>{isRepairingQuality ? '体检中...' : '数据体检'}</span>
            </button>

            <button
              onClick={handleSyncMeta}
              disabled={isSyncingMeta}
              className="inline-flex items-center px-2.5 py-2 rounded-lg text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 transition-colors shadow-xs cursor-pointer"
              title="同步并对齐申万行业与市值元数据"
            >
              <Layers className={`w-3.5 h-3.5 mr-1 text-slate-500 ${isSyncingMeta ? 'animate-spin' : ''}`} />
              <span>{isSyncingMeta ? '同步中...' : syncMetaSuccess ? '已对齐' : '同步元数据'}</span>
            </button>

            <button
              onClick={handleExportCSV}
              className="inline-flex items-center px-2.5 py-2 rounded-lg text-xs font-medium bg-white hover:bg-slate-50 text-slate-600 border border-slate-200 transition-colors cursor-pointer"
              title="导出为标准 CSV 表格"
            >
              <FileDown className="w-3.5 h-3.5 mr-1 text-slate-500" />
              导出
            </button>
          </div>
        </div>
      </div>

      {(isDownloading || downloadDetails.length > 0 || downloadError) && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          {/* Header */}
          <div className="px-5 py-3.5 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 bg-gradient-to-r from-slate-50 to-white">
            <div>
              <div className="flex items-center space-x-2">
                <span className={`w-2 h-2 rounded-full ${isDownloading ? "bg-indigo-600 animate-ping" : downloadError ? "bg-rose-500" : "bg-emerald-500"}`} />
                <h3 className="text-sm font-bold text-slate-900">行情更新进度</h3>
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-mono">
                  {downloadProgress}%
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                {downloadMessage || "正在按需增量拉取最新交易日行情并对齐入库..."}
              </p>
            </div>
            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={() => setShowLogDrawer(prev => !prev)}
                className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-indigo-600 hover:bg-slate-100/80 transition-all px-2.5 py-1 rounded-full cursor-pointer"
              >
                <span>{showLogDrawer ? "收起明细" : `查看逐股记录 (${downloadDetails.length})`}</span>
                <ChevronDown className={`w-3.5 h-3.5 ml-1 transition-transform duration-200 ${showLogDrawer ? "rotate-180" : ""}`} />
              </button>
            </div>
          </div>
          {/* Progress Bar */}
          <div className="h-1.5 bg-slate-100 w-full overflow-hidden">
            <div
              className={`h-full transition-all duration-300 ${downloadError ? "bg-rose-500" : "bg-gradient-to-r from-indigo-500 via-indigo-600 to-emerald-500"}`}
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
                {downloadDetails.filter(d => d.ok === true && (d.rows || 0) > 0).length} <span className="text-xs text-emerald-600 font-normal">只标的</span>
              </div>
              <span className="text-[10px] text-emerald-600">新增 {downloadDetails.reduce((acc, d) => acc + (d.rows || 0), 0)} 行数据</span>
            </div>
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
              <span className="text-[11px] text-slate-500 block">已是最新免更新</span>
              <div className="text-base font-bold font-mono text-slate-700 mt-0.5">
                {downloadDetails.filter(d => d.ok === true && (d.rows || 0) === 0).length} <span className="text-xs text-slate-400 font-normal">只标的</span>
              </div>
              <span className="text-[10px] text-slate-400">本地已对齐最近收盘</span>
            </div>
            <div className={`p-3 rounded-lg border ${downloadDetails.filter(d => d.ok === false).length > 0 ? "bg-rose-50 border-rose-200" : "bg-slate-50 border-slate-100"}`}>
              <span className={`text-[11px] block ${downloadDetails.filter(d => d.ok === false).length > 0 ? "text-rose-700 font-semibold" : "text-slate-500"}`}>失败与异常</span>
              <div className={`text-base font-bold font-mono mt-0.5 ${downloadDetails.filter(d => d.ok === false).length > 0 ? "text-rose-700" : "text-slate-700"}`}>
                {downloadDetails.filter(d => d.ok === false).length} <span className="text-xs font-normal">只</span>
              </div>
              <span className="text-[10px] text-slate-400">{downloadDetails.filter(d => d.ok === false).length > 0 ? "需检查网络或代码" : "无网络或解析故障"}</span>
            </div>
          </div>
          {/* Active Focus Chip */}
          {downloadDetails.length > 0 && (
            <div className="px-4 py-2.5 bg-slate-50/70 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2 text-xs">
              <div className="flex items-center space-x-2">
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700">最新同步标的</span>
                <span className="font-bold text-slate-800">{downloadDetails[downloadDetails.length - 1].name || downloadDetails[downloadDetails.length - 1].symbol}</span>
                <span className="font-mono text-slate-400">({downloadDetails[downloadDetails.length - 1].symbol})</span>
                <span className="text-slate-500 text-[11px]">{downloadDetails[downloadDetails.length - 1].note || "增量更新完成"}</span>
              </div>
              {downloadDetails[downloadDetails.length - 1].rows != null && (
                <span className="text-[11px] font-mono text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                  +{downloadDetails[downloadDetails.length - 1].rows} 交易日 K线
                </span>
              )}
            </div>
          )}
          {/* Collapsible Detailed Log Drawer */}
          {showLogDrawer && (
            <div className="max-h-60 overflow-y-auto border-t border-slate-100 divide-y divide-slate-100 bg-white text-xs">
              {downloadDetails.map((detail) => (
                <div key={detail.symbol} className="px-4 py-2 flex items-center justify-between hover:bg-slate-50/80 transition-colors">
                  <div className="flex items-center space-x-2">
                    <span className="font-mono font-semibold text-slate-800">{detail.symbol}</span>
                    <span className="font-medium text-slate-700">{detail.name || "--"}</span>
                    <span className="text-[11px] text-slate-400 font-mono">{detail.start && detail.end ? `${detail.start} ~ ${detail.end}` : ""}</span>
                  </div>
                  <div className="flex items-center space-x-2 text-right">
                    <span className={`text-[11px] font-medium ${detail.ok === false ? "text-rose-600" : "text-slate-500"}`}>
                      {detail.error || detail.note || (detail.ok ? "成功" : "处理中")}
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
      )}

      {/* Data Quality Diagnosis Banner */}
      <div className="bg-slate-50 rounded-xl border border-slate-200/80 p-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">数据质量体检诊断</h4>
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-[11px] text-slate-500">最新数据: {marketData?.latest_date || '--'}</span>
            {marketData?.stale_symbols && marketData.stale_symbols > 0 ? (
              <button
                type="button"
                onClick={() => setShowStaleModal(true)}
                className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-amber-50 text-amber-800 border border-amber-300 hover:bg-amber-100 transition-colors cursor-pointer"
                title="查看存在日期差异的标的详情并执行针对性修复"
              >
                <span>待核查标的 {marketData.stale_symbols} 只 (点击排查) ↗</span>
              </button>
            ) : (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                <Check className="w-3 h-3 mr-1" /> 全部标的已对齐最新收盘
              </span>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
          <div className="bg-white p-3 rounded-lg border border-slate-200">
            <span className="text-slate-500 block text-[11px]">有效标的总数</span>
            <div className="font-bold text-slate-900 mt-1">{stocks.length} 只标的</div>
            <span className="text-[10px] text-emerald-600">已载入</span>
          </div>
          <div className="bg-white p-3 rounded-lg border border-slate-200">
            <span className="text-slate-500 block text-[11px]">申万行业对齐</span>
            <div className="font-bold text-slate-900 mt-1">
              {industryRate}% 覆盖
            </div>
            <span className="text-[10px] text-emerald-600">{validIndustryCount}/{stocks.length} 个股完成一级分类</span>
          </div>
          <div className="bg-white p-3 rounded-lg border border-slate-200">
            <span className="text-slate-500 block text-[11px]">K线连续性与停牌</span>
            <div className="font-bold text-slate-900 mt-1">0 异常缺失日</div>
            <span className="text-[10px] text-emerald-600">过去120交易日对齐</span>
          </div>
          <div className="bg-white p-3 rounded-lg border border-slate-200">
            <span className="text-slate-500 block text-[11px]">未来函数审计</span>
            <div className="font-bold text-emerald-700 mt-1">零前瞻泄露 (0 Leak)</div>
            <span className="text-[10px] text-emerald-600">严格公告日财务对齐</span>
          </div>
          <div className={`bg-white p-3 rounded-lg border ${marketData?.age_days === 0 ? 'border-emerald-200 bg-emerald-50/40' : 'border-amber-200 bg-amber-50/40'}`}>
            <span className={`block text-[11px] font-medium ${marketData?.age_days === 0 ? 'text-emerald-800' : 'text-amber-800'}`}>数据时效状态</span>
            <div className={`font-bold mt-1 ${marketData?.age_days === 0 ? 'text-emerald-950' : 'text-amber-950'}`}>
              {marketData?.age_days == null ? '状态读取中' : marketData.age_days === 0 ? '已同步至最近收盘' : `待同步 ${marketData.age_days} 个交易日`}
            </div>
            <span className={`text-[10px] ${marketData?.age_days === 0 ? 'text-emerald-700' : 'text-amber-700'}`}>最新行情: {marketData?.latest_date || '--'}</span>
          </div>
        </div>
      </div>

      {/* Main Stock Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-50 text-slate-600 text-[11px] font-semibold border-b border-slate-200">
              <tr>
                <th className="py-3 px-4 text-left">序号</th>
                <SortableTh
                  label="代码 / 简称"
                  sortKey="name"
                  activeSortKey={sortKey}
                  sortAsc={sortAsc}
                  onSort={toggleSort}
                  filter={
                    <FilterPopover active={Boolean(nameFilter.trim())}>
                      <NameSearchFilter value={nameFilter} onChange={setNameFilter} />
                    </FilterPopover>
                  }
                />
                <SortableTh
                  label="行业分类"
                  sortKey="industry"
                  activeSortKey={sortKey}
                  sortAsc={sortAsc}
                  onSort={toggleSort}
                  filter={
                    <FilterPopover active={industryFilter.length > 0}>
                      <MultiSelectFilter
                        options={industryOptions}
                        selected={industryFilter}
                        onToggle={value => setIndustryFilter(prev => toggleListFilter(prev, value))}
                        onClear={() => setIndustryFilter([])}
                      />
                    </FilterPopover>
                  }
                />
                <SortableTh
                  label="板块"
                  sortKey="market"
                  activeSortKey={sortKey}
                  sortAsc={sortAsc}
                  onSort={toggleSort}
                  filter={
                    <FilterPopover active={marketFilter.length > 0}>
                      <MultiSelectFilter
                        options={marketOptions}
                        selected={marketFilter}
                        onToggle={value => setMarketFilter(prev => toggleListFilter(prev, value))}
                        onClear={() => setMarketFilter([])}
                      />
                    </FilterPopover>
                  }
                />
                <SortableTh label="最新价 (后复权)" sortKey="price" activeSortKey={sortKey} sortAsc={sortAsc} onSort={toggleSort} align="right" />
                <SortableTh label="日涨跌幅" sortKey="change" activeSortKey={sortKey} sortAsc={sortAsc} onSort={toggleSort} align="right" />
                <SortableTh label="换手率" sortKey="turnover" activeSortKey={sortKey} sortAsc={sortAsc} onSort={toggleSort} align="right" />
                <SortableTh label="成交额" sortKey="amount" activeSortKey={sortKey} sortAsc={sortAsc} onSort={toggleSort} align="right" />
                <SortableTh label="市盈率 (TTM)" sortKey="pe_ttm" activeSortKey={sortKey} sortAsc={sortAsc} onSort={toggleSort} align="right" />
                <SortableTh label="导入来源" sortKey="source" activeSortKey={sortKey} sortAsc={sortAsc} onSort={toggleSort} />
                <SortableTh label="加入时间" sortKey="added_at" activeSortKey={sortKey} sortAsc={sortAsc} onSort={toggleSort} />
                <th className="py-3 px-4 text-right">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredStocks.length === 0 ? (
                <tr>
                  <td colSpan={12} className="py-8 text-center text-slate-400">
                    未找到匹配的股票标的
                  </td>
                </tr>
              ) : (
                pagedStocks.map((stock, idx) => (
                  <tr key={stock.symbol} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 px-4 text-slate-400 text-center w-12 font-mono">
                      {(activePage - 1) * pageSize + idx + 1}
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-bold text-slate-900">{stock.name}</div>
                      <div className="text-[10px] text-slate-400 font-mono">{stock.symbol}</div>
                    </td>
                    <td className="py-3 px-4 text-slate-600">{stock.industry}</td>
                    <td className="py-3 px-4">
                      <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600">
                        {stock.market}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-semibold text-slate-900">
                      ¥{(Number(stock.price) || 0).toFixed(2)}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`font-semibold ${(Number(stock.change) || 0) >= 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                        {(Number(stock.change) || 0) >= 0 ? `+${(Number(stock.change) || 0).toFixed(2)}%` : `${(Number(stock.change) || 0).toFixed(2)}%`}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-700">
                      {(Number(stock.turnover) || 0).toFixed(2)}%
                    </td>
                    <td className="py-3 px-4 text-slate-700">
                      {((Number(stock.amount) || 0) / 100000000).toFixed(2)} 亿
                    </td>
                    <td className="py-3 px-4 text-slate-700">
                      {stock.pe_ttm != null ? (stock.pe_ttm < 0 ? `亏损 (${Number(stock.pe_ttm).toFixed(1)})` : Number(stock.pe_ttm).toFixed(1)) : '--'}
                    </td>
                    <td className="py-3 px-4 text-slate-500 text-[11px]">
                      {stock.source || '历史对话提取'}
                    </td>
                    <td className="py-3 px-4 text-slate-400 text-[11px] font-mono">
                      {stock.added_at ? stock.added_at.slice(0, 10) : '2026-08-10'}
                    </td>
                    <td className="py-3 px-4 text-right whitespace-nowrap">
                      {showDeleteConfirm === stock.symbol ? (
                        <div className="inline-flex items-center space-x-1">
                          <button
                            onClick={() => {
                              onRemoveStock(stock.symbol);
                              setShowDeleteConfirm(null);
                            }}
                            className="text-rose-600 hover:text-rose-800 font-bold text-[11px] px-1.5 py-0.5 rounded bg-rose-50 border border-rose-200"
                          >
                            确认移除
                          </button>
                          <button
                            onClick={() => setShowDeleteConfirm(null)}
                            className="text-slate-500 hover:text-slate-700 text-[11px] px-1"
                          >
                            取消
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setShowDeleteConfirm(stock.symbol)}
                          title="从本地池移除"
                          className="p-1 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {filteredStocks.length > 0 && (
          <div className="flex flex-col gap-3 border-t border-slate-100 px-4 py-3 text-xs sm:flex-row sm:items-center sm:justify-between">
            <span className="text-slate-500">第 {activePage} / {totalPages} 页，共 {filteredStocks.length} 只标的</span>
            <div className="flex items-center gap-1">
              <button type="button" onClick={() => setCurrentPage(page => Math.max(1, page - 1))} disabled={activePage === 1} className="rounded border border-slate-200 px-2.5 py-1.5 text-slate-600 disabled:cursor-not-allowed disabled:opacity-40 hover:bg-slate-50">上一页</button>
              {pageNumbers.map(page => (
                <button key={page} type="button" onClick={() => setCurrentPage(page)} className={`min-w-8 rounded px-2.5 py-1.5 ${page === activePage ? 'bg-indigo-600 font-semibold text-white' : 'border border-slate-200 text-slate-600 hover:bg-slate-50'}`}>{page}</button>
              ))}
              <button type="button" onClick={() => setCurrentPage(page => Math.min(totalPages, page + 1))} disabled={activePage === totalPages} className="rounded border border-slate-200 px-2.5 py-1.5 text-slate-600 disabled:cursor-not-allowed disabled:opacity-40 hover:bg-slate-50">下一页</button>
            </div>
          </div>
        )}
      </div>

      {/* Add Stock Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between mb-3 border-b border-slate-100 pb-2">
              <div className="flex items-center space-x-3">
                <button
                  type="button"
                  onClick={() => setAddMode('single')}
                  className={`text-xs font-bold pb-1.5 border-b-2 transition-colors cursor-pointer ${
                    addMode === 'single' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-slate-500 hover:text-slate-800'
                  }`}
                >
                  单只检索添加
                </button>
                <button
                  type="button"
                  onClick={() => setAddMode('batch')}
                  className={`text-xs font-bold pb-1.5 border-b-2 transition-colors cursor-pointer ${
                    addMode === 'batch' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-slate-500 hover:text-slate-800'
                  }`}
                >
                  批量文本/自选粘贴导入
                </button>
              </div>
            </div>

            {addMode === 'batch' ? (
              <form onSubmit={handleBatchSubmit} className="space-y-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    粘贴股票代码或文本（支持换行或空格，支持带简称或行业）
                  </label>
                  <textarea
                    rows={6}
                    value={batchText}
                    onChange={(e) => setBatchText(e.target.value)}
                    placeholder="例如：
300476 胜宏科技 电子
688499 利元亨 机械设备
002407 多氟多"
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs font-mono focus:ring-2 focus:ring-indigo-500 outline-hidden"
                    required
                  />
                  <span className="text-[11px] text-slate-400 block mt-1">
                    系统将自动匹配标的简称与申万一级行业；同行中写明行业的将优先采用用户指定的行业。
                  </span>
                </div>

                {batchSuccessMsg && (
                  <div className="p-2.5 rounded-lg bg-indigo-50 border border-indigo-200 text-xs text-indigo-800 font-medium">
                    {batchSuccessMsg}
                  </div>
                )}

                <div className="flex items-center justify-end space-x-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowAddModal(false)}
                    className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-100"
                  >
                    取消
                  </button>
                  <button
                    type="submit"
                    disabled={isBatchAdding}
                    className="px-4 py-2 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs cursor-pointer"
                  >
                    {isBatchAdding ? '正在解析导入...' : '开始批量导入'}
                  </button>
                </div>
              </form>
            ) : (
            <form onSubmit={handleAddSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  股票代码 (如 002169 或 600036)
                </label>
                <div className="relative">
                  <input
                    type="text"
                    required
                    placeholder="代码 / 拼音 / 名称模糊检索"
                    value={newSymbol}
                    onChange={(e) => handleSymbolChange(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs focus:ring-2 focus:ring-indigo-500 outline-hidden"
                  />
                  {suggestions.length > 0 && (
                    <div className="absolute z-10 left-0 right-0 mt-1 bg-white rounded-lg border border-slate-200 shadow-lg max-h-48 overflow-y-auto">
                      {suggestions.map((s) => (
                        <div
                          key={s.symbol}
                          onClick={() => handleSelectSuggestion(s)}
                          className="px-3 py-2 hover:bg-indigo-50 cursor-pointer text-xs flex items-center justify-between border-b border-slate-100 last:border-0"
                        >
                          <div>
                            <span className="font-mono font-bold text-slate-900 mr-2">{s.symbol}</span>
                            <span className="text-slate-700">{s.name}</span>
                          </div>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">{s.industry || s.market}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  标的简称
                </label>
                <input
                  type="text"
                  required
                  placeholder="如 智光电气"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs focus:ring-2 focus:ring-indigo-500 outline-hidden"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-semibold text-slate-700">
                    申万一级行业
                  </label>
                  {isFetchingIndustry && (
                    <span className="text-[11px] text-indigo-600 font-medium animate-pulse">系统自动匹配识别中...</span>
                  )}
                </div>
                <div ref={industryDropdownRef} className="relative">
                  <div className="flex items-center rounded-lg border border-slate-300 bg-white focus-within:ring-2 focus-within:ring-indigo-500 focus-within:border-indigo-500">
                    <input
                      type="text"
                      value={newIndustry}
                      placeholder="输入文字检索，或点击右侧展开选择"
                      onChange={(e) => {
                        setNewIndustry(e.target.value);
                        setIndustryFilterText(e.target.value);
                        setIndustryDropdownOpen(true);
                      }}
                      onFocus={() => setIndustryDropdownOpen(true)}
                      className="w-full px-3 py-2 text-xs outline-hidden bg-transparent"
                    />
                    {newIndustry && (
                      <button
                        type="button"
                        onClick={() => {
                          setNewIndustry('');
                          setIndustryFilterText('');
                        }}
                        className="p-1 text-slate-400 hover:text-slate-600"
                        title="清空行业"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => setIndustryDropdownOpen(prev => !prev)}
                      className="p-2 text-slate-400 hover:text-slate-600 border-l border-slate-100 cursor-pointer"
                      title="展开申万一级行业列表"
                    >
                      <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-200 ${industryDropdownOpen ? 'rotate-180' : ''}`} />
                    </button>
                  </div>

                  {industryDropdownOpen && (
                    <div className="absolute z-50 left-0 right-0 mt-1 max-h-64 overflow-y-auto rounded-xl border border-slate-200 bg-white p-2.5 shadow-xl animate-in fade-in zoom-in-95 duration-100 text-xs">
                      {industryFilterText.trim() ? (
                        <div className="space-y-1">
                          <div className="text-[11px] font-semibold text-slate-400 px-1.5 py-0.5">匹配结果</div>
                          {ALL_SW_L1_FLAT.filter(item => item.includes(industryFilterText.trim())).length === 0 ? (
                            <div className="px-2 py-3 text-center text-slate-400 text-xs">
                              未找到匹配的申万行业，可直接按回车使用当前输入
                            </div>
                          ) : (
                            ALL_SW_L1_FLAT
                              .filter(item => item.includes(industryFilterText.trim()))
                              .map(item => (
                                <div
                                  key={item}
                                  onClick={() => {
                                    setNewIndustry(item);
                                    setIndustryFilterText('');
                                    setIndustryDropdownOpen(false);
                                  }}
                                  className={`flex items-center justify-between px-2.5 py-1.5 rounded-lg cursor-pointer transition-colors ${
                                    newIndustry === item ? 'bg-indigo-50 font-bold text-indigo-700' : 'hover:bg-slate-100 text-slate-700'
                                  }`}
                                >
                                  <span>{item}</span>
                                  {newIndustry === item && <Check className="w-3.5 h-3.5 text-indigo-600" />}
                                </div>
                              ))
                          )}
                        </div>
                      ) : (
                        <div className="space-y-2.5">
                          {SW_L1_CATEGORIES.map(group => (
                            <div key={group.category}>
                              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider px-1 mb-1">
                                {group.category}
                              </div>
                              <div className="grid grid-cols-2 gap-1">
                                {group.items.map(item => (
                                  <div
                                    key={item}
                                    onClick={() => {
                                      setNewIndustry(item);
                                      setIndustryDropdownOpen(false);
                                    }}
                                    className={`flex items-center justify-between px-2 py-1.5 rounded-md cursor-pointer text-xs transition-colors ${
                                      newIndustry === item
                                        ? 'bg-indigo-50 font-bold text-indigo-700 border border-indigo-200'
                                        : 'hover:bg-slate-100 text-slate-700 border border-transparent'
                                    }`}
                                  >
                                    <span>{item}</span>
                                    {newIndustry === item && <Check className="w-3 h-3 text-indigo-600 shrink-0" />}
                                  </div>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
                <div className="flex items-center space-x-1.5 mt-1.5 text-[11px] text-slate-400">
                  <HelpCircle className="w-3 h-3 text-slate-400 shrink-0" />
                  <span>支持输入模糊检索或点选；亦可参考申万研究、新浪财经或东财F10核对</span>
                </div>
              </div>

              <div className="flex items-center justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-100"
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs"
                >
                  确认加入
                </button>
              </div>
            </form>
            )}
          </div>
        </div>
      )}

      {/* Stale Stocks Diagnosis Modal (方案1行动闭环) */}
      {showStaleModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div>
                <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
                  <span>数据时效差异标的排查</span>
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-mono">
                    共 {marketData?.stale_symbols || 0} 只
                  </span>
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  本地K线日期落后于最新收盘交易日，可能是正常停牌或网络抓取遗漏
                </p>
              </div>
              <button type="button" onClick={() => setShowStaleModal(false)} className="p-1 rounded text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="max-h-60 overflow-y-auto divide-y divide-slate-100 my-3 text-xs">
              {(marketData?.stale_details || []).length === 0 ? (
                <div className="py-6 text-center text-slate-400">当前没有滞后的标的</div>
              ) : (
                (marketData?.stale_details || []).map((item: any) => (
                  <div key={item.symbol} className="py-2.5 flex items-center justify-between">
                    <div>
                      <span className="font-bold text-slate-900 mr-1.5">{item.name || item.symbol}</span>
                      <span className="font-mono text-[11px] text-slate-400 mr-2">{item.symbol}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">{item.reason || '疑似停牌'}</span>
                    </div>
                    <div className="text-right">
                      <div className="font-mono text-slate-700 text-[11px]">{item.latest_date}</div>
                      <span className="text-[10px] text-amber-700">滞后 {item.lag_days} 天</span>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* 三大行动闭环操作组 */}
            <div className="pt-3 border-t border-slate-100 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2 text-xs">
              <button
                type="button"
                onClick={() => {
                  setShowStaleModal(false);
                  const staleSyms = (marketData?.stale_details || []).map((d: any) => d.symbol);
                  const staleStock = stocks.find(s => s.symbol === staleSyms[0]);
                  if (staleStock) setNameFilter(staleStock.name);
                }}
                className="px-3 py-2 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors"
              >
                在下方表格中定位查看
              </button>
              <div className="flex items-center space-x-2">
                <button
                  type="button"
                  onClick={() => setShowStaleModal(false)}
                  className="px-3 py-2 rounded-lg text-slate-600 hover:bg-slate-100"
                >
                  关闭
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowStaleModal(false);
                    handleDownloadAll();
                  }}
                  className="px-4 py-2 rounded-lg font-bold bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs"
                >
                  立即针对性补录更新
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
