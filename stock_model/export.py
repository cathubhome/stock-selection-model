# Candidate and research export utilities
from __future__ import annotations

import io
from datetime import date
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from stock_model.benchmarks import BENCHMARK_NAMES

CANDIDATE_EXPORT_SCHEMA: list[tuple[str, str, str]] = [
    ("排名", "排名", "按综合评分从高到低的本次候选顺序。"),
    ("排名变化", "排名变化", "相对上一次评分运行的名次变化；新进表示上次未进入候选。"),
    ("date", "数据日期", "本次评分使用的最新行情日期。"),
    ("symbol", "股票代码", "A 股六位证券代码。"),
    ("name", "股票名称", "证券简称。"),
    ("close", "收盘价（元）", "数据日期的收盘价。"),
    ("daily_return", "当日涨跌幅（%）", "相对上一交易日收盘价的涨跌幅。"),
    ("turnover", "换手率（%）", "当日成交量占流通股本的比例。"),
    ("amount", "成交额（亿元）", "当日成交金额。"),
    ("industry", "行业", "当前可得的行业分类，用于行业暴露审阅。"),
    ("market_cap", "总市值（亿元）", "当前可得的总市值，不等同于自由流通市值。"),
    ("pe_ttm", "滚动市盈率", "当前价格相对过去十二个月每股收益的倍数；亏损时可能为负。"),
    ("pb", "市净率", "当前价格相对每股净资产的倍数。"),
    ("composite_score", "综合评分", "五个评分维度按当前权重汇总的横截面排序分，不是上涨概率。"),
    ("model_score", "模型评分", "模型预测收益的当日横截面百分位，越高表示模型相对看好。"),
    ("technical_score", "技术面评分", "动量、均线乖离和波动率等技术特征的组合百分位。"),
    ("volume_price_score", "量价评分", "量能趋势、量比和资金流等量价特征的组合百分位。"),
    ("candle_score", "K线评分", "收盘位置、实体和影线等 K 线形态特征的组合百分位。"),
    ("sentiment_score", "舆情评分", "新闻标题关键词的时间加权评分；50 为中性，不等同于基本面判断。"),
    ("sentiment_source", "舆情来源", "舆情评分的数据来源与回退状态。"),
    ("odds_reward_risk", "赔率（收益/风险）", "历史平均盈利幅度除以平均亏损幅度。"),
    ("odds_win_rate", "历史胜率（%）", "按当前预测周期，历史上持有到期收益为正的样本比例。"),
    ("odds_expected_return", "期望收益（%）", "全部可用历史持有期样本的平均收益。"),
    ("conditional_win_rate", "条件胜率（%）", "历史高分区间样本中持有到期收益为正的比例。"),
    ("conditional_expected_return", "条件期望收益（%）", "历史高分区间样本持有到期的平均收益。"),
    ("conditional_sample_count", "条件样本数", "满足高分与间隔要求的历史样本数量。"),
    ("credibility_score", "可信度分", "个股历史证据充足度与稳定性综合打分（0~100）。"),
    ("credibility_grade", "可信度等级", "高/中/低；等级越低越需要人工核对并减少持仓规模。"),
    ("run_id", "运行编号", "本次评分运行的唯一标识。"),
]


def candidate_export_frame(picks: pd.DataFrame) -> pd.DataFrame:
    if picks is None or picks.empty:
        return pd.DataFrame()
    available = [(source, label) for source, label, _ in CANDIDATE_EXPORT_SCHEMA if source in picks]
    result = picks[[source for source, _ in available]].copy()
    for source in [
        "daily_return", "turnover", "odds_win_rate", "odds_expected_return",
        "conditional_win_rate", "conditional_expected_return",
    ]:
        if source in result:
            result[source] = pd.to_numeric(result[source], errors="coerce") * 100
    for source in ["amount", "market_cap"]:
        if source in result:
            result[source] = pd.to_numeric(result[source], errors="coerce") / 1e8
    return result.rename(columns=dict(available))


def candidate_export_dictionary(picks: pd.DataFrame) -> pd.DataFrame:
    if picks is None or picks.empty:
        return pd.DataFrame(columns=["字段", "说明"])
    return pd.DataFrame(
        [{"字段": label, "说明": description} for source, label, description in CANDIDATE_EXPORT_SCHEMA if source in picks]
    )


def candidate_export_workbook(picks: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        candidate_export_frame(picks).to_excel(writer, sheet_name="候选明细", index=False)
        candidate_export_dictionary(picks).to_excel(writer, sheet_name="字段说明", index=False)
    return buffer.getvalue()


def export_pdf_report(
    picks: pd.DataFrame,
    backtest_metrics: dict[str, Any] | None = None,
    importance: pd.DataFrame | None = None,
    research_status: dict[str, Any] | None = None,
    metadata_audit: dict[str, Any] | None = None,
    universe_audit: dict[str, Any] | None = None,
) -> bytes:
    bt = backtest_metrics or {}
    st_status = research_status or {}
    meta = metadata_audit or {}
    univ = universe_audit or {}

    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        font_name = "STSong-Light"
    except Exception:
        font_name = "Helvetica"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    styles = getSampleStyleSheet()
    styles["Title"].fontName = font_name
    styles["Normal"].fontName = font_name
    styles["Heading2"].fontName = font_name

    today_str = date.today().isoformat()
    story = [
        Paragraph("A股量化选股研究观察名单报告", styles["Title"]),
        Paragraph("生成时间：" + today_str + "（仅供量化投研，不构成投资建议）", styles["Normal"]),
        Spacer(1, 16),
    ]

    picks_count = len(picks) if picks is not None else 0
    run_id_val = "-"
    if picks is not None and not picks.empty and "run_id" in picks:
        run_id_val = str(picks["run_id"].iloc[0])

    benchmark_name_raw = bt.get("benchmark_name", "-")
    benchmark_display = BENCHMARK_NAMES.get(benchmark_name_raw, benchmark_name_raw)

    ind_cov = float(meta.get("industry_coverage", 0.95))
    cap_cov = float(meta.get("market_cap_coverage", 1.0))
    horizon_val = bt.get("horizon_days", bt.get("horizon", 20))
    buy_bps = bt.get("buy_cost_bps", 15)
    sell_bps = bt.get("sell_cost_bps", 15)
    slip_bps = bt.get("slippage_bps", 15)

    info_rows = [
        ["研究验证状态", st_status.get("label", "待评估")],
        ["观察标的数量", f"{picks_count} 只"],
        ["预测/持有周期", f"{horizon_val} 日"],
        ["运行编号", run_id_val],
        ["行业/市值覆盖", f"{ind_cov:.1%} / {cap_cov:.1%}"],
        ["历史股票池控制", "已覆盖" if univ.get("usable", True) else "未覆盖"],
        ["回测基准", str(benchmark_display)],
        ["买入/卖出/滑点摩擦", f"{buy_bps} / {sell_bps} / {slip_bps} bps"],
    ]

    for key, label in [
        ("cumulative_return", "累计收益"),
        ("annualized_return", "年化收益"),
        ("max_drawdown", "最大回撤"),
        ("win_rate", "胜率"),
    ]:
        val = bt.get(key)
        info_rows.append([label, f"{val:.2%}" if isinstance(val, (int, float)) else "-"])

    sharpe_val = bt.get("sharpe")
    info_rows.append(["夏普比率", f"{sharpe_val:.2f}" if isinstance(sharpe_val, (int, float)) else "-"])
    cum_excess = bt.get("cumulative_excess_return", 0)
    info_rows.append(["累计超额收益", f"{cum_excess:.2%}" if isinstance(cum_excess, (int, float)) else str(cum_excess)])
    ic_mean = bt.get("ic_mean", 0)
    info_rows.append(["Rank IC", f"{ic_mean:.4f}" if isinstance(ic_mean, (int, float)) else str(ic_mean)])

    if bt.get("ic_confidence_low") is not None:
        ic_low = bt["ic_confidence_low"]
        ic_high = bt.get("ic_confidence_high", 0)
        info_rows.append(["Rank IC 95%区间", f"{ic_low:.4f} 至 {ic_high:.4f}"])

    info_table = Table(info_rows, colWidths=[150, 200])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [info_table, Spacer(1, 16), Paragraph("研究限制与执行假设", styles["Heading2"])]

    limitations = st_status.get("failed_reasons", []) + st_status.get("warnings", [])
    if limitations:
        for idx, msg in enumerate(limitations, start=1):
            story.append(Paragraph(f"{idx}. {msg}", styles["Normal"]))
    else:
        story.append(Paragraph("当前验证门槛未发现未通过项，但历史结果不代表未来收益。", styles["Normal"]))

    story.append(Paragraph(
        "信号在收盘后生成，下一交易日开盘建仓；跌停或停牌无法退出时强制延续持仓。资金容量、买卖成本和滑点均按本次回测参数模拟。",
        styles["Normal"],
    ))
    story += [Spacer(1, 16), Paragraph("候选股票列表", styles["Heading2"])]

    stock_rows = [["代码", "名称", "综合评分", "模型评分"]]
    if picks is not None and not picks.empty:
        for _, row in picks.head(15).iterrows():
            c_score = row.get("composite_score", 0)
            m_score = row.get("model_score", 0)
            stock_rows.append([
                str(row.get("symbol", "")),
                str(row.get("name", ""))[:10],
                f"{c_score:.1f}" if isinstance(c_score, (int, float)) else str(c_score),
                f"{m_score:.1f}" if isinstance(m_score, (int, float)) else str(m_score),
            ])
    stock_table = Table(stock_rows, colWidths=[90, 160, 90, 90])
    stock_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(stock_table)

    if importance is not None and not importance.empty:
        story += [Spacer(1, 16), Paragraph("模型因子重要性", styles["Heading2"])]
        imp_rows = [["因子", "重要性"]] + [
            [str(r.get("feature", ""))[:24], f"{float(r.get('importance', 0)):.4f}"]
            for _, r in importance.head(10).iterrows()
        ]
        imp_table = Table(imp_rows, colWidths=[220, 100])
        imp_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#14532d")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(imp_table)

    doc.build(story)
    return buffer.getvalue()
