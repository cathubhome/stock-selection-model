import React from 'react';
import { 
  ArrowRight, 
  CheckCircle2, 
  Clock, 
  Activity, 
  TrendingUp, 
  Database, 
  Sliders, 
  LineChart, 
  Award,
  AlertCircle
} from 'lucide-react';
import { ScoredStock, ResearchStep } from '../types';
import { LATEST_MARKET_SENTIMENT, REMOTE_METADATA_STATUS } from '../data/remoteArchiveData';

interface ResearchDashboardViewProps {
  stocks: ScoredStock[];
  onNavigate: (step: ResearchStep) => void;
  onSelectStock: (stock: ScoredStock) => void;
}

export const ResearchDashboardView: React.FC<ResearchDashboardViewProps> = ({
  stocks,
  onNavigate,
  onSelectStock,
}) => {
  const topStocks = stocks.slice(0, 5);

  return (
    <div className="space-y-6">
      {/* Top Banner / Hero */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-2xl p-6 text-white shadow-xl border border-slate-800 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20"></div>
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/20 text-indigo-300 text-xs font-medium border border-indigo-400/30">
              <Activity className="w-3.5 h-3.5" />
              <span>数据截至 2026-09-05 · 运行已归档</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
              A股量化多因子选股研究工作台
            </h2>
            <p className="text-sm text-slate-300 leading-relaxed">
              严格遵循量化严谨原则：滚动前向训练去除未来函数、公告日财务数据对齐、公开舆情词典审计、换仓成本与滑点摩擦测算。
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => onNavigate('综合评分')}
              className="inline-flex items-center px-4 py-2.5 rounded-xl text-sm font-semibold bg-indigo-500 hover:bg-indigo-400 text-white shadow-lg shadow-indigo-500/30 transition-all hover:scale-[1.02] active:scale-[0.98]"
            >
              <Sliders className="w-4 h-4 mr-2" />
              调整评分权重
              <ArrowRight className="w-4 h-4 ml-1.5" />
            </button>
            <button
              onClick={() => onNavigate('历史回测')}
              className="inline-flex items-center px-4 py-2.5 rounded-xl text-sm font-semibold bg-white/10 hover:bg-white/20 text-white border border-white/15 transition-all"
            >
              <LineChart className="w-4 h-4 mr-2" />
              运行滚动回测
            </button>
          </div>
        </div>
      </div>

      {/* 3-Step Research Process Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Step 1 */}
        <div 
          onClick={() => onNavigate('股票池与数据')}
          className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs hover:border-indigo-300 hover:shadow-md transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between mb-3">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
              <Database className="w-5 h-5" />
            </div>
            <span className="inline-flex items-center text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
              <CheckCircle2 className="w-3 h-3 mr-1" /> 已就绪
            </span>
          </div>
          <h3 className="font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
            1. 本地池与行情数据
          </h3>
          <p className="text-xs text-slate-500 mt-1.5">
            当前本地股票池共 <strong>{stocks.length}</strong> 只标的，行业覆盖率 {(REMOTE_METADATA_STATUS.industry_coverage * 100).toFixed(1)}%，无未来函数。
          </p>
          <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-indigo-600 font-medium">
            <span>进入股票池与质量诊断</span>
            <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
          </div>
        </div>

        {/* Step 2 */}
        <div 
          onClick={() => onNavigate('综合评分')}
          className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs hover:border-indigo-300 hover:shadow-md transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between mb-3">
            <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center font-bold">
              <Sliders className="w-5 h-5" />
            </div>
            <span className="inline-flex items-center text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
              <CheckCircle2 className="w-3 h-3 mr-1" /> 2026-09-05 已评分
            </span>
          </div>
          <h3 className="font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
            2. 五维多因子综合评分
          </h3>
          <p className="text-xs text-slate-500 mt-1.5">
            模型(35%) + 技术(25%) + 量价(20%) + K线(10%) + 舆情(10%)，支持自动归一化与胜率赔率测算。
          </p>
          <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-indigo-600 font-medium">
            <span>配置权重并查看优选</span>
            <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
          </div>
        </div>

        {/* Step 3 */}
        <div 
          onClick={() => onNavigate('历史回测')}
          className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs hover:border-indigo-300 hover:shadow-md transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between mb-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
              <LineChart className="w-5 h-5" />
            </div>
            <span className="inline-flex items-center text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
              <CheckCircle2 className="w-3 h-3 mr-1" /> 36期门禁通过
            </span>
          </div>
          <h3 className="font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
            3. 前向无未来函数回测
          </h3>
          <p className="text-xs text-slate-500 mt-1.5">
            滚动训练36期，年化超额 +18.6%，扣除印花税/滑点后夏普比率 1.68，通过保守研究门禁。
          </p>
          <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-indigo-600 font-medium">
            <span>查看净值曲线与执行摩擦</span>
            <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
          </div>
        </div>
      </div>

      {/* Market Sentiment Overview & Data Health */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Market Sentiment Gauge */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2">
              <Activity className="w-4 h-4 text-indigo-600" />
              <h4 className="font-bold text-slate-900 text-sm">市场情绪指数 (Market Sentiment)</h4>
            </div>
            <span className="text-xs text-slate-500">{LATEST_MARKET_SENTIMENT.date}</span>
          </div>

          <div className="flex items-baseline space-x-3 mb-3">
            <div className="text-3xl font-extrabold text-slate-900">
              {LATEST_MARKET_SENTIMENT.score.toFixed(1)}
            </div>
            <span className="text-xs px-2 py-0.5 rounded font-semibold bg-amber-50 text-amber-700 border border-amber-200">
              {LATEST_MARKET_SENTIMENT.status}
            </span>
          </div>

          {/* Sentiment Progress Bar */}
          <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden mb-4">
            <div 
              className="h-full bg-gradient-to-r from-amber-500 to-emerald-500 rounded-full"
              style={{ width: `${LATEST_MARKET_SENTIMENT.score}%` }}
            ></div>
          </div>

          {/* 3 Indicators Breakdown */}
          <div className="grid grid-cols-3 gap-2 pt-3 border-t border-slate-100 text-center">
            <div className="bg-slate-50 p-2 rounded-lg">
              <span className="text-[11px] text-slate-500 block">上涨家数占比</span>
              <strong className="text-xs font-semibold text-slate-800">
                {(LATEST_MARKET_SENTIMENT.breadth * 100).toFixed(1)}%
              </strong>
            </div>
            <div className="bg-slate-50 p-2 rounded-lg">
              <span className="text-[11px] text-slate-500 block">全市场量能比</span>
              <strong className="text-xs font-semibold text-slate-800">
                {LATEST_MARKET_SENTIMENT.volume_ratio.toFixed(2)}x
              </strong>
            </div>
            <div className="bg-slate-50 p-2 rounded-lg">
              <span className="text-[11px] text-slate-500 block">涨停家数占比</span>
              <strong className="text-xs font-semibold text-slate-800">
                {(LATEST_MARKET_SENTIMENT.limit_up_ratio * 100).toFixed(1)}%
              </strong>
            </div>
          </div>

          <p className="text-[11px] text-slate-500 mt-3">
            注：市场情绪面用于判断宏观环境与调仓风险敞口，不改变当日截面个股综合排序。
          </p>
        </div>

        {/* Global Local Assets Status */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2">
              <Database className="w-4 h-4 text-emerald-600" />
              <h4 className="font-bold text-slate-900 text-sm">本地数据资产与元数据状态</h4>
            </div>
            <span className="inline-flex items-center text-xs font-medium text-emerald-600 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
              数据源: Tencent / Sina SW
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
            <div className="border border-slate-100 rounded-lg p-3 bg-slate-50/50">
              <span className="text-xs text-slate-500">股票池标的</span>
              <p className="text-lg font-bold text-slate-900 mt-0.5">{stocks.length} 只</p>
              <span className="text-[10px] text-emerald-600">全部加载</span>
            </div>
            <div className="border border-slate-100 rounded-lg p-3 bg-slate-50/50">
              <span className="text-xs text-slate-500">行业覆盖率</span>
              <p className="text-lg font-bold text-slate-900 mt-0.5">
                {(REMOTE_METADATA_STATUS.industry_coverage * 100).toFixed(1)}%
              </p>
              <span className="text-[10px] text-slate-500">申万一级行业</span>
            </div>
            <div className="border border-slate-100 rounded-lg p-3 bg-slate-50/50">
              <span className="text-xs text-slate-500">市值覆盖率</span>
              <p className="text-lg font-bold text-slate-900 mt-0.5">100.0%</p>
              <span className="text-[10px] text-slate-500">总市值/流通市值</span>
            </div>
            <div className="border border-slate-100 rounded-lg p-3 bg-slate-50/50">
              <span className="text-xs text-slate-500">行情有效性</span>
              <p className="text-lg font-bold text-emerald-700 mt-0.5">通过对齐</p>
              <span className="text-[10px] text-emerald-600">无缺失停牌交易日</span>
            </div>
          </div>

          <div className="p-3 bg-indigo-50/60 rounded-xl border border-indigo-100/80 flex items-start space-x-3 text-xs text-indigo-950">
            <AlertCircle className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
            <div>
              <strong className="font-semibold">研究规范提示：</strong>
              <span>
                模型训练每个调仓日严格仅使用历史截面数据。回测计算已全额扣除印花税（万5）、双边佣金（万2.5）和可配置买卖冲击滑点（默认15 bps）。
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Look: Top 5 Candidates on 2026-09-05 */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-bold text-slate-900 flex items-center space-x-2">
              <Award className="w-5 h-5 text-amber-500" />
              <span>最新综合评分前五候选标的 (2026-09-05 截面)</span>
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              经过五因子加权、正负向证据校验与决策可信度评估后的核心入选标的
            </p>
          </div>
          <button
            onClick={() => onNavigate('综合评分')}
            className="inline-flex items-center text-xs font-semibold text-indigo-600 hover:text-indigo-800"
          >
            <span>查看完整 97 只标的与参数配置</span>
            <ArrowRight className="w-4 h-4 ml-1" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-50 text-slate-600 text-[11px] font-semibold border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">排名</th>
                <th className="py-3 px-4">标的 / 代码</th>
                <th className="py-3 px-4">所属行业</th>
                <th className="py-3 px-4">现价 / 涨跌</th>
                <th className="py-3 px-4">综合评分</th>
                <th className="py-3 px-4">模型 / 技术 / 量价 / K线 / 舆情</th>
                <th className="py-3 px-4">胜率 / 盈亏比</th>
                <th className="py-3 px-4">可信度</th>
                <th className="py-3 px-4 text-right">研判操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {topStocks.map((stock) => (
                <tr key={stock.symbol} className="hover:bg-indigo-50/40 transition-colors">
                  <td className="py-3 px-4 font-bold text-slate-900">
                    <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-amber-100 text-amber-800 text-[11px]">
                      {stock.rank}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <div className="font-bold text-slate-900">{stock.name}</div>
                    <div className="text-[10px] text-slate-400 font-mono">{stock.symbol}</div>
                  </td>
                  <td className="py-3 px-4 text-slate-600">{stock.industry}</td>
                  <td className="py-3 px-4">
                    <span className="font-semibold text-slate-900">¥{stock.price.toFixed(2)}</span>
                    <span className={`ml-1.5 text-[11px] font-medium ${stock.change >= 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                      {stock.change >= 0 ? `+${stock.change.toFixed(2)}%` : `${stock.change.toFixed(2)}%`}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-indigo-100 text-indigo-800">
                      {stock.composite_score.toFixed(1)}
                    </span>
                  </td>
                  <td className="py-3 px-4 font-mono text-[11px] text-slate-600">
                    {stock.model_score.toFixed(0)} / {stock.technical_score.toFixed(0)} / {stock.volume_price_score.toFixed(0)} / {stock.candle_score.toFixed(0)} / {stock.sentiment_score.toFixed(0)}
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-slate-800 font-medium">{stock.odds_win_rate}%</span>
                    <span className="text-slate-400 mx-1">·</span>
                    <span className="text-slate-600">{stock.odds_reward_risk}R</span>
                  </td>
                  <td className="py-3 px-4">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700">
                      {stock.credibility_score?.toFixed(0) || '40'}分 ({stock.credibility_grade || '中'})
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button
                      onClick={() => {
                        onSelectStock(stock);
                        onNavigate('综合评分');
                      }}
                      className="text-indigo-600 hover:text-indigo-800 font-semibold text-xs"
                    >
                      详情证据
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
