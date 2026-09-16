import React, { useState } from 'react';
import { HelpCircle } from 'lucide-react';

export const TERM_EXPLANATIONS: Record<string, { title: string; desc: string; guide?: string }> = {
  '模型评分': {
    title: '模型评分 (Model Score)',
    desc: '基于 LightGBM 机器学习模型对全市场标的历史量价、动量及截面特征训练得出的超额收益预测百分位得分（0~100）。',
    guide: '得分越高，表示算法模型预测未来超额收益的潜力越强；非确定性涨跌概率。'
  },
  '技术面': {
    title: '技术面评分 (Technical Indicators)',
    desc: '综合均线系统（MA5/20/60）、MACD金死叉、RSI超买超卖、布林带通道突破等经典量化趋势指标计算的相对强弱得分。',
    guide: '衡量当前股价是否处于多头共振或超跌反弹的有利技术形态。'
  },
  '技术评分': {
    title: '技术评分 (Technical Score)',
    desc: '综合均线系统、MACD、RSI、布林带通道等经典技术形态指标的截面归一化得分。',
    guide: '反映个股相对同期大盘与行业板块的顺势趋势强度。'
  },
  '量价评分': {
    title: '量价评分 (Volume-Price Dynamics)',
    desc: '衡量量价配合健康度（放量上涨/缩量回调、换手率异常、量比、主力资金成交集中度）的量化分值。',
    guide: '识别是否有增量主力资金持续介入或缩量健康洗盘。'
  },
  'K线评分': {
    title: 'K线走势评分 (Candle Pattern)',
    desc: '根据日K实体长短、上下影线比例、跳空缺口及近3日反转K线组合形态打分。',
    guide: '刻画日内多空力量对比及关键支撑阻力位的争夺结果。'
  },
  '舆情评分': {
    title: '舆情情绪评分 (Sentiment Score)',
    desc: '基于个股近期新闻标题、行业研报情感词库打分，50分为中性。',
    guide: '辅助识别市场突发事件的情绪偏向与舆论催化，防范黑天鹅或把握热点。'
  },
  '综合评分': {
    title: '五维多因子综合评分 (Composite Score)',
    desc: '将模型、技术、量价、K线、舆情五大维度按动态权重加权后的横截面排序分（0~100）。',
    guide: '是排序候选的核心依据，反映多维度共振强度，不是绝对上涨概率。'
  },
  'Rank IC': {
    title: '秩相关系数 (Rank IC)',
    desc: '每个调仓日股票综合评分排名与随后实际收益排名之间的 Spearman 秩相关系数的平均值。',
    guide: '范围在 -1 到 1 之间。通常 Rank IC > 0.03 且 t统计显著表示选股排序能力优良。'
  },
  'ICIR': {
    title: '信息比率 (IC Information Ratio)',
    desc: '平均 Rank IC 除以各期 Rank IC 的标准差，衡量选股模型排序能力的稳定性。',
    guide: 'ICIR 越高（一般 > 0.5），表示模型在各个市场周期下的选股胜率越稳定。'
  },
  'Q5-Q1': {
    title: '多空收益分层 (Q5 - Q1 Spread)',
    desc: '每个调仓期最高评分组（前20%头部股票Q5）的平均收益减去最低评分组（末20%尾部股票Q1）的平均收益。',
    guide: '正值且越大，说明因子分层单调性越好，高分股真实跑赢低分股。'
  },
  '夏普比率': {
    title: '夏普比率 (Sharpe Ratio)',
    desc: '年化平均超额收益除以年化收益率波动率，衡量承担单位总风险所换取的超额回报。',
    guide: '夏普 > 1.0 为优良策略，> 1.5 为极稳健策略。'
  },
  '最大回撤': {
    title: '最大回撤 (Maximum Drawdown, MDD)',
    desc: '策略净值在回测历史中从任意历史高点到随后最低谷底的最大跌幅百分比。',
    guide: '衡量可能经历的最极端亏损风险，对实盘持仓心理承受力至关重要。'
  },
  '条件胜率': {
    title: '条件胜率 (Conditional Win Rate)',
    desc: '历史归档中该股票处于高分区间、且已完整走完当前持有周期的非重叠样本中，后续实现正收益的比例。',
    guide: '比泛化的历史胜率更具当前环境下的参考价值。'
  },
  '条件期望收益': {
    title: '条件期望收益 (Conditional Expected Return)',
    desc: '该股在历史处于相似高分截面后，持有对应周期所获得的实际平均收益。',
    guide: '体现高分触发时的平均盈利空间。'
  },
  '条件样本数': {
    title: '条件样本数 (Conditional Sample Count)',
    desc: '历史上该个股满足高分触发条件、且已走完持有周期的独立历史样本总数。',
    guide: '样本数过少（如 < 5期）时，胜率和期望收益统计误差较大，需谨慎采信。'
  },
  '未来函数审计': {
    title: '未来函数与前瞻泄露审计 (Lookahead Bias Audit)',
    desc: '严格审计数据截面是否包含未发生事件，财务数据采用严格公告披露日而非报告期末，零前瞻泄露。',
    guide: '保障历史回测与评分结论能真实被实盘复制，避免“事后诸葛亮”。'
  },
  '申万一级行业': {
    title: '申万一级行业分类 (Shenwan Level-1)',
    desc: '申万宏源研究建立的中国 A 股权威行业分类体系（2021标准共31个大类），用于行业暴露与风格约束。',
    guide: '有效归一化个股主营属性，支持跨周期横向比较与行业中性化。'
  },
  '数据时效状态': {
    title: '数据时效状态 (Data Freshness)',
    desc: '本地 K 线日线历史与中国 A 股最近已完成交易日收盘行情的对齐状态。',
    guide: '工作日 16:00 前以昨日收盘为准；16:00 后收盘数据更新后将提示当日最新。'
  }
};

interface TermTooltipProps {
  term: string;
  children?: React.ReactNode;
  className?: string;
  showIcon?: boolean;
}

export const TermTooltip: React.FC<TermTooltipProps> = ({
  term,
  children,
  className = '',
  showIcon = false
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const info = TERM_EXPLANATIONS[term] || {
    title: term,
    desc: '该指标为量化分析与多因子选股模型体系中的重要评估参数。'
  };

  return (
    <span
      className={`relative inline-flex items-center group cursor-help ${className}`}
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
    >
      <span className="border-b border-dashed border-slate-300 group-hover:border-indigo-500 transition-colors">
        {children || term}
      </span>
      {showIcon && (
        <HelpCircle className="w-3 h-3 ml-0.5 text-slate-400 group-hover:text-indigo-600 transition-colors inline" />
      )}
      {isOpen && (
        <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-slate-900/95 backdrop-blur-md text-white rounded-xl shadow-2xl text-left pointer-events-none animate-in fade-in zoom-in-95 duration-150">
          <div className="text-xs font-bold text-indigo-300 mb-1 flex items-center justify-between">
            <span>{info.title}</span>
          </div>
          <p className="text-[11px] leading-relaxed text-slate-200 font-normal">
            {info.desc}
          </p>
          {info.guide && (
            <div className="mt-1.5 pt-1.5 border-t border-slate-700/80 text-[10px] text-amber-300 leading-snug font-normal">
              💡 {info.guide}
            </div>
          )}
          <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-slate-900 rotate-45" />
        </div>
      )}
    </span>
  );
};
