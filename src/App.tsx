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
import { fetchSystemStatus, fetchStockPool, addPoolStocks, removePoolStock, fetchLatestScores, runScoring, fetchScoringProgress, fetchResearchRuns } from './api/client';

const LOCAL_STORAGE_KEY_POOL = 'a_share_stock_model_pool_v2';
const LOCAL_STORAGE_KEY_WEIGHTS = 'a_share_stock_model_weights_v2';
const LOCAL_STORAGE_KEY_STEP = 'a_share_stock_model_step_v2';

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

  // Check backend and sync live data if available
  useEffect(() => {
    let isMounted = true;
    fetchSystemStatus().then((status) => {
      if (!isMounted) return;
      if (status && status.status === 'online') {
        setIsBackendOnline(true);
        fetchStockPool().then((pool) => {
          if (isMounted && pool && pool.length > 0) setPoolStocks(pool);
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
          while (true) {
            const progress = await fetchScoringProgress(task.task_id);
            setScoringProgress(progress);
            if (!progress.running) {
              if (progress.error) throw new Error(progress.error);
              break;
            }
            await new Promise(resolve => setTimeout(resolve, 1200));
          }
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
        const message = err instanceof Error ? err.message : '评分任务失败';
        setScoringProgress((current: any) => ({
          ...(current || {}), running: false, error: message, message: `评分失败：${message}`,
        }));
      } finally {
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
        onResetToDefault={handleResetToDefault}
        isBackendOnline={isBackendOnline}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {currentStep === '研究看板' && (
          <ResearchDashboardView
            stocks={stocks}
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
            stocks={stocks}
          />
        )}
      </main>

      {/* Modern Quant Footer */}
      <footer className="bg-white border-t border-slate-200 py-6 text-slate-500 text-xs text-center">
        <div className="max-w-7xl mx-auto px-4 space-y-1">
          <p className="font-medium text-slate-700">
            A股选股研究台 · 基于远程仓库 cathubhome/stock-selection-model 最新代码与数据架构
          </p>
          <p className="text-slate-400 text-[11px]">
            五维综合打分 (模型 35% / 技术 25% / 量价 20% / K线 10% / 舆情 10%) · 滚动样本外无未来数据回测 · 保守量化门禁审计
          </p>
        </div>
      </footer>
    </div>
  );
};
