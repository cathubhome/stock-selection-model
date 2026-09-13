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

interface NavbarProps {
  currentStep: ResearchStep;
  onSelectStep: (step: ResearchStep) => void;
  stockCount: number;
  onResetToDefault: () => void;
  isBackendOnline?: boolean;
}

const STEPS: { id: ResearchStep; label: string; icon: React.ElementType; desc: string; badge?: string }[] = [
  { id: '研究看板', label: '1. 研究看板', icon: LayoutDashboard, desc: '研究导引与全局资产概览' },
  { id: '股票池与数据', label: '2. 股票池与数据', icon: Database, desc: '标的检索、导入与质量诊断', badge: '可更新' },
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
}) => {
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
                <h1 className="text-lg font-bold text-slate-900 tracking-tight">A股选股研究台</h1>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                  v2.4 全栈量化版
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
          </div>
        </div>

        {/* Workflow Steps Tabs */}
        <div className="flex items-center space-x-1 sm:space-x-2 overflow-x-auto py-2.5 border-t border-slate-100 no-scrollbar">
          {STEPS.map((step) => {
            const Icon = step.icon;
            const isActive = currentStep === step.id;
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
                {step.badge && (
                  <span
                    className={`ml-1 text-[10px] px-1.5 py-0.5 rounded-full font-medium transition-colors ${
                      isActive
                        ? 'bg-indigo-500 text-indigo-100'
                        : 'bg-amber-100 text-amber-800'
                    }`}
                  >
                    {step.badge}
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
