import React, { useState, useMemo, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { ResearchDashboardView } from './components/ResearchDashboardView';
import { StockPoolView } from './components/StockPoolView';
import { CompositeScoringView } from './components/CompositeScoringView';
import { BacktestView } from './components/BacktestView';
import { ResearchRunsView } from './components/ResearchRunsView';
import { ResearchStep, ScoredStock, WeightConfig, ArchiveRun, ScoringConfig } from './types';
import { RAW_REMOTE_STOCKS, ARCHIVE_RESEARCH_RUNS } from './data/remoteArchiveData';
import { DEFAULT_WEIGHTS } from './utils/scoring';
import { fetchSystemStatus, fetchStockPool, addPoolStocks, removePoolStock, fetchLatestScores, runScoring, fetchScoringProgress, fetchResearchRuns, SystemStatusResponse } from './api/client';

const LOCAL_STORAGE_KEY_POOL = 'a_share_stock_model_pool_v2';
const LOCAL_STORAGE_KEY_WEIGHTS = 'a_share_stock_model_weights_v2';
const LOCAL_STORAGE_KEY_STEP = 'a_share_stock_model_step_v2';

const GithubIcon: React.FC<{ className?: string }> = ({ className = 'w-4 h-4' }) => (
  <svg className={className} fill="currentColor" viewBox="0 0 24 24">
    <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
  </svg>
);

export const App: React.FC = () => {
  // Load initial pool from localStorage or fallback to remote archive data (97 stocks)
  const [stocks, setStocks] = useState<ScoredStock[]>(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEY_POOL);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed;
        }
      }
    } catch {
      // ignore
    }
    return RAW_REMOTE_STOCKS as ScoredStock[];
  });
  const [poolStocks, setPoolStocks] = useState<ScoredStock[]>(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEY_POOL);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {
      // ignore
    }
    return RAW_REMOTE_STOCKS as ScoredStock[];
  });

  // Weights state
  const [weights, setWeights] = useState<WeightConfig>(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEY_WEIGHTS);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.model !== undefined) {
          return parsed;
        }
      }
    } catch {
      // ignore
    }
    return DEFAULT_WEIGHTS;
  });

  // Current active step/view
  const [currentStep, setCurrentStep] = useState<ResearchStep>(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEY_STEP);
      if (saved && ['研究看板', '股票池与数据', '综合评分', '历史回测', '研究记录'].includes(saved)) {
        return saved as ResearchStep;
      }
    } catch {
      // ignore
    }
    return '研究看板';
  });

  // Research runs list
  const [researchRuns, setResearchRuns] = useState<ArchiveRun[]>(ARCHIVE_RESEARCH_RUNS);
  const [isScoringRunning, setIsScoringRunning] = useState(false);
  const [scoringProgress, setScoringProgress] = useState<any | null>(null);
  const [isBackendOnline, setIsBackendOnline] = useState(false);
  const [systemStatus, setSystemStatus] = useState<SystemStatusResponse | null>(null);

  // Check backend and sync live data if available
  useEffect(() => {
    let isMounted = true;
    fetchSystemStatus().then((status) => {
      if (!isMounted) return;
      setSystemStatus(status);
      if (status && status.status === 'online') {
        setIsBackendOnline(true);
        fetchStockPool().then((pool) => {
          if (isMounted && pool && pool.length > 0) setPoolStocks(pool);
        const savedScoreTask = localStorage.getItem('active_scoring_task_id');
        if (savedScoreTask) {
          pollScoringTask(savedScoreTask);
        }
        });
        fetchLatestScores().then((scoresRes) => {
          if (!isMounted) return;
          if (scoresRes && scoresRes.stocks && scoresRes.stocks.length > 0) {
            setStocks(scoresRes.stocks);
          }
        });
        fetchResearchRuns().then((runs) => {
          if (!isMounted) return;
          if (runs && runs.length > 0) {
            setResearchRuns(runs);
          }
        });
      }
    });
    return () => {
      isMounted = false;
    };
  }, []);

  // Persist state
  useEffect(() => {
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY_POOL, JSON.stringify(poolStocks));
    } catch {
      // ignore
    }
  }, [poolStocks]);

  useEffect(() => {
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY_WEIGHTS, JSON.stringify(weights));
    } catch {
      // ignore
    }
  }, [weights]);

  useEffect(() => {
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY_STEP, currentStep);
    } catch {
      // ignore
    }
  }, [currentStep]);

  // Actions
  const handleAddStock = (newStock: ScoredStock) => {
    if (!poolStocks.some(s => s.symbol === newStock.symbol)) {
      setPoolStocks(prev => [newStock, ...prev]);
      if (isBackendOnline) {
        addPoolStocks([newStock.symbol], newStock.source, newStock.name, newStock.industry);
      }
    }
  };

  const handleRemoveStock = (symbol: string) => {
    setPoolStocks(prev => prev.filter(s => s.symbol !== symbol));
    if (isBackendOnline) {
      removePoolStock(symbol);
    }
  };

  const refreshPoolStocks = async () => {
    const pool = await fetchStockPool();
    if (pool) setPoolStocks(pool);
  };

  const handleResetToDefault = () => {
    if (window.confirm('确认重置本地股票池与因子权重为远程仓库初始默认状态（97只标的）吗？')) {
      setStocks(RAW_REMOTE_STOCKS as ScoredStock[]);
      setPoolStocks(RAW_REMOTE_STOCKS as ScoredStock[]);
      setWeights(DEFAULT_WEIGHTS);
      setCurrentStep('研究看板');
      localStorage.removeItem(LOCAL_STORAGE_KEY_POOL);
      localStorage.removeItem(LOCAL_STORAGE_KEY_WEIGHTS);
      localStorage.removeItem(LOCAL_STORAGE_KEY_STEP);
    }
  };

  const pollScoringTask = async (taskId: string) => {
    setIsScoringRunning(true);
    localStorage.setItem('active_scoring_task_id', taskId);
    try {
      while (true) {
        const progress = await fetchScoringProgress(taskId);
        setScoringProgress(progress);
        if (!progress.running) {
          localStorage.removeItem('active_scoring_task_id');
          if (progress.error) throw new Error(progress.error);
          break;
        }
        await new Promise(resolve => setTimeout(resolve, 1200));
      }
      const scoresRes = await fetchLatestScores();
      if (scoresRes && scoresRes.stocks && scoresRes.stocks.length > 0) {
        setStocks(scoresRes.stocks);
      }
      const runs = await fetchResearchRuns();
      if (runs && runs.length > 0) {
        setResearchRuns(runs);
      }
    } catch (err) {
      localStorage.removeItem('active_scoring_task_id');
      const message = err instanceof Error ? err.message : '评分任务失败';
      setScoringProgress((current: any) => ({
        ...(current || {}), running: false, error: message, message: `评分失败：${message}`,
      }));
    } finally {
      setIsScoringRunning(false);
    }
  };

  const handleRunScoring = async (config: ScoringConfig) => {
    setIsScoringRunning(true);
    if (isBackendOnline) {
      try {
        setScoringProgress({ running: true, percent: 0, message: '评分任务初始化...', details: [] });
        const task = await runScoring({
          ...config,
          weights,
        });
        if (task?.task_id) {
          await pollScoringTask(task.task_id);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : '评分任务失败';
        setScoringProgress((current: any) => ({
          ...(current || {}), running: false, error: message, message: `评分失败：${message}`,
        }));
        setIsScoringRunning(false);
      }
      return;
    }
    setScoringProgress({ running: false, percent: 0, message: '评分服务不可用', error: 'FastAPI 后台未连接，未执行任何模拟评分', details: [] });
    setIsScoringRunning(false);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans selection:bg-indigo-500 selection:text-white">
      <Navbar
        currentStep={currentStep}
        onSelectStep={setCurrentStep}
        stockCount={poolStocks.length}
        
        isBackendOnline={isBackendOnline}
        marketData={systemStatus?.market_data}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {currentStep === '研究看板' && (
          <ResearchDashboardView
            stocks={poolStocks}
            candidates={stocks}
            onNavigate={setCurrentStep}
            onSelectStock={(stock) => {
              setCurrentStep('综合评分');
            }}
          />
        )}

        {currentStep === '股票池与数据' && (
          <StockPoolView
            stocks={poolStocks}
            onAddStock={handleAddStock}
            onRemoveStock={handleRemoveStock}
            onRefreshPool={refreshPoolStocks}
            onSelectStock={(stock) => {
              setCurrentStep('综合评分');
            }}
          />
        )}

        {currentStep === '综合评分' && (
          <CompositeScoringView
            weights={weights}
            onUpdateWeights={setWeights}
            stocks={stocks}
            onSelectStock={() => {}}
            onRunScoring={handleRunScoring}
            isScoringRunning={isScoringRunning}
            scoringProgress={scoringProgress}
            onNavigateToData={() => setCurrentStep('股票池与数据')}
          />
        )}

        {currentStep === '历史回测' && (
          <BacktestView
            stocks={stocks}
          />
        )}

        {currentStep === '研究记录' && (
          <ResearchRunsView
            runs={researchRuns}
            stocks={poolStocks}
            onNavigate={setCurrentStep}
          />
        )}
      </main>

      {/* Modern Quant Footer */}
      <footer className="bg-white border-t border-slate-200 py-6 text-slate-500 text-xs text-center">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-left">
          <div>
            <p className="font-semibold text-slate-800">
              AlphaCraft 智能量化选股平台
            </p>
            <p className="text-slate-400 text-[11px] font-normal mt-0.5">
              多因子集成 (模型 / 技术 / 量价 / K线 / 舆情) · 滚动样本外无前瞻偏误回测 · 保守量化门禁审计
            </p>
          </div>
          <div className="flex items-center space-x-3 text-[11px] text-slate-500 shrink-0">
            <a
              href="https://github.com/cathubhome/stock-selection-model"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center text-slate-600 hover:text-indigo-600 transition-colors font-medium"
            >
              <GithubIcon className="w-3.5 h-3.5 mr-1" />
              <span>开源代码仓库</span>
            </a>
            <span className="text-slate-300">·</span>
            <span className="text-slate-400 font-mono">v2.5 Fullstack</span>
          </div>
        </div>
      </footer>
    </div>
  );
};
