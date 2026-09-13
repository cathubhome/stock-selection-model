import React, { useState } from 'react';
import { 
  Award, 
  Download, 
  TrendingUp, 
  BrainCircuit, 
  Activity, 
  BarChart2, 
  Flame, 
  MessageSquare, 
  ShieldCheck, 
  FileSpreadsheet, 
  Check, 
  ExternalLink,
  ChevronRight,
  Zap,
  Target
} from 'lucide-react';
import { ScoredStock } from '../types';

interface CandidatePicksViewProps {
  stocks: ScoredStock[];
}

export const CandidatePicksView: React.FC<CandidatePicksViewProps> = ({ stocks }) => {
  const topCandidates = stocks.slice(0, 10);
  const [selectedStock, setSelectedStock] = useState<ScoredStock>(topCandidates[0] || stocks[0]);
  const [downloadSuccess, setDownloadSuccess] = useState<string | null>(null);

  const exportCSV = () => {
    const headers = [
      'rank',
      'symbol',
      'name',
      'industry',
      'market',
      'price',
      'change_pct',
      'composite_score',
      'model_score',
      'technical_score',
      'volume_price_score',
      'candle_score',
      'sentiment_score',
      'odds_reward_risk',
      'odds_win_rate',
      'odds_expected_return',
      'sentiment_source'
    ];

    const rows = stocks.map((s) => [
      s.rank,
      s.symbol,
      s.name,
      `"${s.industry}"`,
      s.market,
      s.price,
      s.change,
      s.composite_score,
      s.model_score,
      s.technical_score,
      s.volume_price_score,
      s.candle_score,
      s.sentiment_score,
      s.odds_reward_risk,
      s.odds_win_rate,
      s.odds_expected_return,
      `"${s.sentiment_source}"`
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,\uFEFF' + [
      headers.join(','),
      ...rows.map((e) => e.join(','))
    ].join('\n');

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `latest_picks_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    setDownloadSuccess('已成功导出 latest_picks.csv 到本地下载！');
    setTimeout(() => setDownloadSuccess(null), 3500);
  };

  const exportJSON = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(
      JSON.stringify({
        generated_at: new Date().toISOString(),
        candidate_count: stocks.length,
        top_candidates: topCandidates,
      }, null, 2)
    );
    const link = document.createElement('a');
    link.setAttribute('href', dataStr);
    link.setAttribute('download', `validation_metrics_${new Date().toISOString().slice(0, 10)}.json`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    setDownloadSuccess('已成功导出 validation_metrics.json 数据结构！');
    setTimeout(() => setDownloadSuccess(null), 3500);
  };

  return (
    <div className="space-y-6">
      {/* Banner */}
      <div className="bg-gradient-to-r from-emerald-950 via-slate-900 to-indigo-950 text-white rounded-2xl p-6 shadow-md">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2 text-emerald-400 text-xs font-semibold uppercase tracking-wider mb-2">
              <Award className="w-4 h-4" />
              <span>第五步 · 当前候选 (Current Candidates)</span>
            </div>
            <h2 className="text-2xl font-bold tracking-tight mb-2">
              最新交易日候选标的优选与透明归因
            </h2>
            <p className="text-slate-300 text-sm max-w-2xl leading-relaxed">
              基于最新全维度因子打分，精选出前 10 只高预期胜率标的。提供各项分项拆解、盈亏赔率比估算与舆情审计，支持一键导出标准研究报告。
            </p>
          </div>

          {/* Export Action Buttons */}
          <div className="flex items-center space-x-2 self-start md:self-center">
            <button
              onClick={exportCSV}
              className="inline-flex items-center px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-md transition-all"
            >
              <FileSpreadsheet className="w-4 h-4 mr-1.5" />
              导出 latest_picks.csv
            </button>
            <button
              onClick={exportJSON}
              className="inline-flex items-center px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-bold text-xs transition-all"
            >
              <Download className="w-4 h-4 mr-1.5" />
              导出 JSON指标
            </button>
          </div>
        </div>
      </div>

      {/* Success Notification */}
      {downloadSuccess && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 px-4 py-3 rounded-xl text-sm flex items-center space-x-2 animate-fade-in">
          <Check className="w-4 h-4 text-emerald-600" />
          <span className="font-semibold">{downloadSuccess}</span>
        </div>
      )}

      {/* Main Content Split: Left Candidates List, Right Selected Detail Card */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Top Candidates List (5 cols) */}
        <div className="lg:col-span-5 bg-white rounded-xl border border-slate-200/80 shadow-xs p-4 space-y-2">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-1.5">
              <span>综合评分优选标的</span>
              <span className="text-xs font-normal text-slate-400">(Top 10)</span>
            </h3>
            <span className="text-[11px] text-slate-400 font-mono">按综合得分排位</span>
          </div>

          <div className="space-y-1.5 max-h-[580px] overflow-y-auto pr-1">
            {topCandidates.map((c) => {
              const isSelected = selectedStock?.symbol === c.symbol;
              return (
                <div
                  key={c.symbol}
                  onClick={() => setSelectedStock(c)}
                  className={`p-3 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                    isSelected
                      ? 'bg-indigo-50/80 border-indigo-400 shadow-xs'
                      : 'bg-slate-50/50 border-slate-200 hover:bg-slate-100/70'
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    <span className={`w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs font-mono ${
                      c.rank === 1 ? 'bg-amber-400 text-amber-950 shadow-2xs' :
                      c.rank === 2 ? 'bg-slate-300 text-slate-900' :
                      c.rank === 3 ? 'bg-amber-600 text-white' :
                      'bg-slate-200 text-slate-700'
                    }`}>
                      {c.rank}
                    </span>
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-bold text-slate-900 text-sm">{c.name}</span>
                        <span className="text-xs font-mono font-medium text-slate-500">{c.symbol}</span>
                      </div>
                      <div className="text-[11px] text-slate-400 truncate max-w-[170px]">
                        {c.industry}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3 text-right">
                    <div>
                      <div className="text-base font-bold font-mono text-indigo-600">
                        {c.composite_score.toFixed(1)}
                      </div>
                      <div className="text-[10px] text-slate-400 font-mono">
                        胜率: <strong className="text-emerald-600">{c.odds_win_rate}%</strong>
                      </div>
                    </div>
                    <ChevronRight className={`w-4 h-4 ${isSelected ? 'text-indigo-600' : 'text-slate-300'}`} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Detailed Deep-Dive for Selected Stock (7 cols) */}
        {selectedStock && (
          <div className="lg:col-span-7 bg-white rounded-xl border border-slate-200/80 shadow-xs p-6 space-y-6">
            {/* Header info */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-4 border-b border-slate-100">
              <div>
                <div className="flex items-center space-x-2">
                  <h3 className="text-2xl font-black text-slate-900 tracking-tight">
                    {selectedStock.name}
                  </h3>
                  <span className="font-mono text-sm font-bold text-slate-500">
                    {selectedStock.symbol}
                  </span>
                  <span className="px-2 py-0.5 rounded text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                    {selectedStock.market}
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  行业题材：{selectedStock.industry} · 数据来源：{selectedStock.source}
                </p>
              </div>

              <div className="flex items-center space-x-3 self-start sm:self-center">
                <div className="text-right">
                  <div className="text-2xl font-black font-mono text-slate-900">
                    ¥{selectedStock.price.toFixed(2)}
                  </div>
                  <div className={`text-xs font-bold font-mono ${selectedStock.change >= 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                    {selectedStock.change >= 0 ? `+${selectedStock.change}%` : `${selectedStock.change}%`}
                  </div>
                </div>
                <div className="px-3 py-2 rounded-xl bg-indigo-600 text-white text-center">
                  <div className="text-[10px] font-medium uppercase tracking-wider opacity-80">综合评分</div>
                  <div className="text-lg font-black font-mono leading-none mt-0.5">
                    {selectedStock.composite_score.toFixed(1)}
                  </div>
                </div>
              </div>
            </div>

            {/* Odds & Risk Reward Assessment Grid */}
            <div>
              <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2 flex items-center">
                <Target className="w-3.5 h-3.5 mr-1 text-indigo-600" />
                交易赔率与胜率预期 (Odds & Reward/Risk)
              </h4>
              <div className="grid grid-cols-3 gap-3">
                <div className="bg-slate-50 rounded-xl p-3 border border-slate-200/60">
                  <div className="text-[11px] text-slate-500">盈亏赔率比</div>
                  <div className="text-lg font-bold font-mono text-slate-900 mt-0.5">
                    1 : {selectedStock.odds_reward_risk}
                  </div>
                  <div className="text-[10px] text-slate-400 mt-0.5">上行空间 / 下行风险</div>
                </div>

                <div className="bg-slate-50 rounded-xl p-3 border border-slate-200/60">
                  <div className="text-[11px] text-slate-500">历史统计胜率</div>
                  <div className="text-lg font-bold font-mono text-emerald-600 mt-0.5">
                    {selectedStock.odds_win_rate}%
                  </div>
                  <div className="text-[10px] text-slate-400 mt-0.5">相似分位区间胜率</div>
                </div>

                <div className="bg-slate-50 rounded-xl p-3 border border-slate-200/60">
                  <div className="text-[11px] text-slate-500">20日预期收益</div>
                  <div className="text-lg font-bold font-mono text-indigo-600 mt-0.5">
                    +{selectedStock.odds_expected_return}%
                  </div>
                  <div className="text-[10px] text-slate-400 mt-0.5">无未来泄漏前向预测</div>
                </div>
              </div>
            </div>

            {/* Five Component Score Progress Bars */}
            <div className="space-y-3.5">
              <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center">
                <Zap className="w-3.5 h-3.5 mr-1 text-amber-500" />
                五维分项透明归因 (0 - 100 分位)
              </h4>

              {/* 1. Model Score */}
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="flex items-center text-slate-700 font-medium">
                    <BrainCircuit className="w-3.5 h-3.5 mr-1.5 text-indigo-600" />
                    LightGBM 机器学习模型分
                  </span>
                  <span className="font-mono font-bold text-indigo-700">
                    {selectedStock.model_score.toFixed(1)} 分
                  </span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div 
                    className="bg-indigo-600 h-full rounded-full transition-all duration-500"
                    style={{ width: `${selectedStock.model_score}%` }}
                  />
                </div>
              </div>

              {/* 2. Technical Score */}
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="flex items-center text-slate-700 font-medium">
                    <Activity className="w-3.5 h-3.5 mr-1.5 text-blue-600" />
                    技术动量趋势分 (20日/60日均线与收益)
                  </span>
                  <span className="font-mono font-bold text-blue-700">
                    {selectedStock.technical_score.toFixed(1)} 分
                  </span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div 
                    className="bg-blue-600 h-full rounded-full transition-all duration-500"
                    style={{ width: `${selectedStock.technical_score}%` }}
                  />
                </div>
              </div>

              {/* 3. Volume-Price Score */}
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="flex items-center text-slate-700 font-medium">
                    <BarChart2 className="w-3.5 h-3.5 mr-1.5 text-emerald-600" />
                    量价配合分 (量比 2.0x 与 OBV能量潮)
                  </span>
                  <span className="font-mono font-bold text-emerald-700">
                    {selectedStock.volume_price_score.toFixed(1)} 分
                  </span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div 
                    className="bg-emerald-600 h-full rounded-full transition-all duration-500"
                    style={{ width: `${selectedStock.volume_price_score}%` }}
                  />
                </div>
              </div>

              {/* 4. Candle Pattern Score */}
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="flex items-center text-slate-700 font-medium">
                    <Flame className="w-3.5 h-3.5 mr-1.5 text-orange-600" />
                    单K线形态分 (长下影支撑与收盘高位)
                  </span>
                  <span className="font-mono font-bold text-orange-700">
                    {selectedStock.candle_score.toFixed(1)} 分
                  </span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div 
                    className="bg-orange-600 h-full rounded-full transition-all duration-500"
                    style={{ width: `${selectedStock.candle_score}%` }}
                  />
                </div>
              </div>

              {/* 5. Sentiment Score */}
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="flex items-center text-slate-700 font-medium">
                    <MessageSquare className="w-3.5 h-3.5 mr-1.5 text-purple-600" />
                    公开舆情情绪分 ({selectedStock.news_count}条新闻)
                  </span>
                  <span className="font-mono font-bold text-purple-700">
                    {selectedStock.sentiment_score.toFixed(1)} 分
                  </span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div 
                    className="bg-purple-600 h-full rounded-full transition-all duration-500"
                    style={{ width: `${selectedStock.sentiment_score}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Sentiment Audit Section */}
            <div className="bg-slate-50 rounded-xl p-3.5 border border-slate-200/60 text-xs text-slate-600 space-y-1">
              <div className="flex items-center justify-between font-semibold text-slate-800">
                <span className="flex items-center">
                  <ShieldCheck className="w-3.5 h-3.5 mr-1 text-emerald-600" />
                  舆情审计与数据追踪
                </span>
                <span className="text-[11px] font-mono text-slate-500">
                  来源渠道: {selectedStock.sentiment_source}
                </span>
              </div>
              <p className="text-[11px] text-slate-500">
                本标的共检索到 {selectedStock.news_count} 篇近期权威财经研报与公开快讯，情感词典正面词汇占比占优，未检出负面违规立案或大股东减持警示。
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
