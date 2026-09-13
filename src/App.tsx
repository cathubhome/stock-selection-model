import React, { useState, useMemo, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { ResearchDashboardView } from './components/ResearchDashboardView';
import { StockPoolView } from './components/StockPoolView';
import { CompositeScoringView } from './components/CompositeScoringView';
import { BacktestView } from './components/BacktestView';
import { ResearchRunsView } from './components/ResearchRunsView';
import { ResearchStep, ScoredStock, WeightConfig, ArchiveRun } from './types';
import { RAW_REMOTE_STOCKS, ARCHIVE_RESEARCH_RUNS } from './data/remoteArchiveData';
import { DEFAULT_WEIGHTS } from './utils/scoring';

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

  // Persist state
  useEffect(() => {
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY_POOL, JSON.stringify(stocks));
    } catch {
      // ignore
    }
  }, [stocks]);

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
    if (!stocks.some(s => s.symbol === newStock.symbol)) {
      setStocks(prev => [newStock, ...prev]);
    }
  };

  const handleRemoveStock = (symbol: string) => {
    setStocks(prev => prev.filter(s => s.symbol !== symbol));
  };

  const handleResetToDefault = () => {
    if (window.confirm('确认重置本地股票池与因子权重为远程仓库初始默认状态（97只标的）吗？')) {
      setStocks(RAW_REMOTE_STOCKS as ScoredStock[]);
      setWeights(DEFAULT_WEIGHTS);
      setCurrentStep('研究看板');
      localStorage.removeItem(LOCAL_STORAGE_KEY_POOL);
      localStorage.removeItem(LOCAL_STORAGE_KEY_WEIGHTS);
      localStorage.removeItem(LOCAL_STORAGE_KEY_STEP);
    }
  };

  const handleRunScoring = () => {
    setIsScoringRunning(true);
    setTimeout(() => {
      setIsScoringRunning(false);
      const now = new Date();
      const pad = (n: number) => n.toString().padStart(2, '0');
      const timeStr = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}T${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
      const newRunId = `${timeStr}_score_${Math.random().toString(36).substring(2, 8)}`;
      
      const newRun: ArchiveRun = {
        run_id: newRunId,
        date: now.toISOString().slice(0, 10),
        created_at: now.toISOString().replace('T', ' ').slice(0, 19),
        kind: 'score',
        stock_count: stocks.length,
        top_symbols: stocks.slice(0, 5).map(s => s.symbol),
        avg_score: Number((stocks.reduce((acc, cur) => acc + cur.composite_score, 0) / stocks.length).toFixed(1))
      };

      setResearchRuns(prev => [newRun, ...prev]);
    }, 600);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans selection:bg-indigo-500 selection:text-white">
      <Navbar
        currentStep={currentStep}
        onSelectStep={setCurrentStep}
        stockCount={stocks.length}
        onResetToDefault={handleResetToDefault}
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
            stocks={stocks}
            onAddStock={handleAddStock}
            onRemoveStock={handleRemoveStock}
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
