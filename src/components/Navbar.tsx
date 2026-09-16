import React from 'react';
import { 
  LayoutDashboard,
  Database, 
  Sliders, 
  LineChart, 
  History, 
  ShieldCheck,
  RotateCcw
} from 'lucide-react';
import { ResearchStep } from '../types';

const GithubIcon: React.FC<{ className?: string }> = ({ className = 'w-4 h-4' }) => (
  <svg className={className} fill="currentColor" viewBox="0 0 24 24">
    <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
  </svg>
);

interface NavbarProps {
  currentStep: ResearchStep;
  onSelectStep: (step: ResearchStep) => void;
  stockCount: number;
  onResetToDefault: () => void;
  isBackendOnline?: boolean;
  marketData?: { latest_date: string | null; age_days: number | null } | null;
}

const STEPS: { id: ResearchStep; label: string; icon: React.ElementType; desc: string }[] = [
  { id: '研究看板', label: '1. 研究看板', icon: LayoutDashboard, desc: '研究导引与全局资产概览' },
  { id: '股票池与数据', label: '2. 股票池与数据', icon: Database, desc: '标的检索、导入与质量诊断' },
  { id: '综合评分', label: '3. 综合评分', icon: Sliders, desc: '五维因子调优与候选研判' },
  { id: '历史回测', label: '4. 历史回测', icon: LineChart, desc: '前向滚动回测与多维执行' },
  { id: '研究记录', label: '5. 研究记录', icon: History, desc: '历次运行快照与版本差异' },
];

export const Navbar: React.FC<NavbarProps> = ({
  currentStep,
  onSelectStep,
  stockCount,
  onResetToDefault,
  isBackendOnline = false,
  marketData = null,
}) => {
  const getStepBadge = (stepId: ResearchStep) => {
    if (stepId === '股票池与数据') {
      if (marketData && marketData.age_days != null && marketData.age_days > 0) {
        return `${marketData.age_days}日待同步`;
      }
    }
    return null;
  };

  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-slate-200/80 shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Top Header Row */}
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-blue-500 flex items-center justify-center text-white shadow-md shadow-indigo-500/20">
              <LineChart className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-lg font-bold text-slate-900 tracking-tight">AlphaCraft 智能量化选股平台</h1>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                  v2.5 全栈多因子版
                </span>
                {isBackendOnline ? (
                  <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                    FastAPI 在线
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
                    本地离线演示
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 hidden sm:block">
                多因子集成 / 滚动前向训练 / 舆情关键词 / 严格去未来函数回测
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <div className="hidden md:flex items-center px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 text-xs font-medium border border-slate-200/60">
              <span className="w-2 h-2 rounded-full bg-emerald-500 mr-2 animate-pulse"></span>
              本地池标的: <strong className="ml-1 text-slate-900">{stockCount}</strong> 只
            </div>

            <button
              onClick={onResetToDefault}
              title="重置为初始研究状态"
              className="inline-flex items-center px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 bg-white hover:bg-slate-100 border border-slate-300 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5 mr-1 text-slate-500" />
              恢复默认
            </button>

            <a
              href="https://github.com/cathubhome/stock-selection-model"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-700 bg-white hover:bg-slate-100 border border-slate-300 transition-colors shadow-2xs"
              title="查看 GitHub 源码仓库 (cathubhome/stock-selection-model)"
            >
              <GithubIcon className="w-3.5 h-3.5 mr-1 text-slate-700" />
              <span>GitHub</span>
            </a>
          </div>
        </div>

        {/* Workflow Steps Tabs */}
        <div className="flex items-center space-x-1 sm:space-x-2 overflow-x-auto py-2.5 border-t border-slate-100 no-scrollbar">
          {STEPS.map((step) => {
            const Icon = step.icon;
            const isActive = currentStep === step.id;
            const dynamicBadge = getStepBadge(step.id);
            return (
              <button
                key={step.id}
                onClick={() => onSelectStep(step.id)}
                className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-xs sm:text-sm font-medium whitespace-nowrap transition-all duration-150 ${
                  isActive
                    ? 'bg-indigo-600 text-white shadow-xs font-semibold'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-400'}`} />
                <span>{step.label}</span>
                {dynamicBadge && (
                  <span
                    className={`ml-1 text-[10px] px-1.5 py-0.5 rounded-full font-medium transition-colors ${
                      isActive
                        ? 'bg-indigo-500 text-indigo-100'
                        : 'bg-amber-100 text-amber-800 animate-pulse'
                    }`}
                  >
                    {dynamicBadge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Non-investment advice disclaimer notice banner */}
      <div className="bg-slate-50 border-b border-slate-200/80 px-4 py-1 text-center">
        <p className="text-[11px] text-slate-600 flex items-center justify-center space-x-1 font-medium">
          <ShieldCheck className="w-3.5 h-3.5 text-slate-500 inline mr-1" />
          <span>研究模式声明：本系统所有模型预测与回测仅用于量化科研与流程验证，不构成投资建议，不连接券商，不自动下单。</span>
        </p>
      </div>
    </header>
  );
};
