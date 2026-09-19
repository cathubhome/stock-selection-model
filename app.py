# A股选股研究台 - 主界面
# 页面结构：研究看板 / 股票池与数据 / 综合评分 / 历史回测

from __future__ import annotations

import io
import json
import shutil
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

from stock_model.data import download_histories, get_symbols, load_panel, load_stock_universe, update_histories
from stock_model.benchmarks import BENCHMARK_NAMES, BENCHMARK_OPTIONS, load_benchmark_history, prepare_benchmark_returns
from stock_model.features import build_features
from stock_model.pool import add_to_pool, load_pool
from stock_model.governance import (
    assess_research_status, data_fingerprint, load_manifest, new_run_id, write_run_manifest,
)
from stock_model.metadata import (
    apply_historical_universe, archive_metadata, archive_universe_snapshot, fetch_current_metadata,
    latest_metadata_snapshot, load_metadata_history, load_universe_history, metadata_coverage,
    metadata_history_audit, universe_history_audit,
)
from stock_model.research import (
    DEFAULT_WEIGHTS, load_score_history, merge_asof_metadata, run_latest_research,
    run_walk_forward_backtest,
)
from stock_model.quality import a_share_equity_mask, audit_market_data, market_snapshot, market_sentiment, security_type

# ==================== 配置 ====================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "raw"
OUTPUT_DIR = BASE_DIR / "output"
UNIVERSE_PATH = BASE_DIR / "data" / "reference" / "a_share_universe.parquet"
POOL_PATH = BASE_DIR / "data" / "reference" / "local_stock_pool.csv"
FEATURE_VERSION = "technical_features_v1"
MODEL_VERSION = "walk_forward_lightgbm_v1"
MIN_BROAD_UNIVERSE = 300

SCORE_NAMES = {
    "model_score": "模型评分",
    "technical_score": "技术面",
    "volume_price_score": "量价关系",
    "candle_score": "K线走势",
    "sentiment_score": "舆情评分",
}
ODDS_NAMES = {
    "odds_reward_risk": "赔率（收益/风险）",
    "odds_win_rate": "历史胜率",
    "odds_expected_return": "期望收益",
}

TERM_HELP = {
    "cumulative_return": "回测区间内组合净值的总涨幅，已扣除模型设定的换仓成本。结果仍可能受幸存者偏差、涨跌停和成交假设影响。",
    "annualized_return": "把回测累计收益按复利折算为一年期收益率，便于比较不同长度的回测；短样本年化后可能被放大。",
    "cumulative_excess_return": "组合期末累计收益减去同期基准累计收益。正值表示回测组合跑赢基准，已包含模型设定的交易成本。",
    "rank_ic": "每个调仓日股票综合评分排名与随后实际收益排名之间的 Spearman 秩相关系数，再对各期取平均。范围为 -1 到 1；正值表示高分股票后来整体收益更高，0 表示几乎没有稳定排序关系，负值表示方向相反。应结合样本数、95%置信区间、ICIR 和样本外稳定性判断。",
    "icir": "平均 Rank IC ÷ 各期 Rank IC 的标准差，衡量选股排序能力的稳定性。越高通常表示 IC 更稳定，但本项目该值未年化，且小样本下容易失真。",
    "q5_q1": "每个调仓期最高评分组（Q5）的平均收益减去最低评分组（Q1）的平均收益，再对各期取平均。正值说明评分具有较好的收益分层方向。",
    "max_drawdown": "组合净值从历史峰值回落到随后谷底的最大幅度，衡量回测期间经历过的最深亏损。",
    "metadata_coverage": "当前行业覆盖率与总市值覆盖率中的较低者。覆盖不足会削弱行业约束、市值分析及历史可比性。",
    "industry_coverage": "本地 A 股个股中具有有效行业分类的比例。行业信息用于行业暴露约束和分组分析。",
    "market_cap_coverage": "本地 A 股个股中具有有效总市值数据的比例。市值信息用于容量判断和规模风格分析。",
    "universe_snapshot": "按日期归档的可选股票集合。历史快照用于避免回测把今天仍存在的股票池错误套用到过去。",
    "data_governance": "行业、市值元数据和历史股票池快照均达到当前可用门槛时显示“可用”；不等同于数据完全无误。",
    "benchmark_return": "同期可交易候选股票的等权平均收益，用作当前回测基准；它不是沪深 300 等外部指数。",
    "average_turnover": "每次调仓时被替换持仓所占的平均比例。换手越高，交易成本、滑点和成交冲击通常越大。",
    "annualized_volatility": "调仓期组合收益标准差按一年折算，衡量收益波动幅度；数值越高通常表示净值越不稳定。",
    "sharpe": "年化平均组合收益 ÷ 年化波动率，衡量单位总波动对应的收益。本项目按无风险利率为 0 计算。",
    "sortino": "年化平均组合收益 ÷ 下行波动，只惩罚负收益波动；数值越高通常越好，但小样本可能不稳定。",
    "calmar": "年化收益 ÷ 最大回撤绝对值，衡量单位历史回撤对应的收益；回测较短或回撤很小时可能被放大。",
    "information_ratio": "组合相对基准的平均超额收益 ÷ 超额收益波动率，并按年化折算；衡量持续跑赢基准的稳定性。",
    "win_rate": "净收益为正的调仓期占全部有效调仓期的比例。胜率不反映单次盈亏幅度，需结合赔率和期望收益。",
    "conditional_expected_return": "历史归档中该股票处于高分区间、且已走完当前持有周期的非重叠样本，其后续实现收益的平均值。",
    "conditional_win_rate": "历史归档中该股票处于高分区间、且已走完当前持有周期的非重叠样本，其后续收益为正的比例。",
    "conditional_sample_count": "满足高分条件且已完整走完持有周期的独立历史样本数。样本越少，胜率和期望收益的不确定性越大。",
    "credibility": "综合回测证据、条件样本量、排名稳定性和五维一致性的证据质量评分；它不是上涨概率，也不代表收益承诺。",
    "historical_win_rate": "该股票全部可用历史持有期样本中，后续收益为正的比例，不限定当前处于高分区间。",
    "expected_return": "该股票全部可用历史持有期样本的后续平均收益，不限定当前处于高分区间。",
    "reward_risk": "历史平均盈利幅度 ÷ 历史平均亏损幅度的绝对值。大于 1 表示平均盈利幅度高于平均亏损幅度。",
    "mae": "模型在样本外验证集中的平均绝对预测误差，单位为收益率；越小越好，例如 0.05 约等于 5 个百分点。",
    "r2": "模型对样本外收益差异的解释程度。越接近 1 越好；接近 0 表示解释力弱，负值表示不如直接预测验证集均值。",
}

VIEWS = ["研究看板", "股票池与数据", "综合评分", "历史回测", "研究记录"]

st.set_page_config(page_title="A股选股研究台", page_icon="📊", layout="wide")

if "research_view" not in st.session_state:
    st.session_state.research_view = VIEWS[0]

st.markdown(
    """<style>
    .stApp {background:#f7f8fa;color:#18212f;}
    [data-testid="stMainBlockContainer"] {max-width:1500px;padding-top:1.55rem !important;padding-bottom:3.5rem;}
    [data-testid="stSidebar"] {background:#ffffff;border-right:1px solid #e5e7eb;}
    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {padding-top:.9rem;}
    h1 {font-size:1.55rem !important;font-weight:650 !important;margin-bottom:.15rem !important;letter-spacing:0 !important;}
    h2 {font-size:1.08rem !important;font-weight:650 !important;margin-top:1.5rem !important;margin-bottom:.35rem !important;letter-spacing:0 !important;}
    h3 {font-size:.94rem !important;font-weight:650 !important;letter-spacing:0 !important;}
    [data-testid="stMetric"] {border-left:0;padding:.1rem .7rem .2rem 0;min-height:4.6rem;}
    [data-testid="stMetricLabel"] {font-size:.78rem;color:#667085;font-weight:500;}
    [data-testid="stMetricValue"] {font-size:1.35rem;color:#18212f;font-weight:650;}
    [data-testid="stDataFrame"] {border:1px solid #e3e7ed;border-radius:6px;overflow:hidden;background:#ffffff;}
    [data-testid="stForm"] {border:1px solid #dfe4ea !important;border-radius:6px !important;background:#ffffff;padding:1rem 1rem .85rem !important;}
    [data-testid="stExpander"] {border:1px solid #e3e7ed;border-radius:6px;background:#ffffff;}
    [data-testid="stTabs"] [data-baseweb="tab-list"] {gap:1.25rem;border-bottom:1px solid #e3e7ed;}
    [data-testid="stTabs"] button {height:2.5rem;padding:0 .1rem;color:#667085;font-size:.86rem;}
    [data-testid="stTabs"] button[aria-selected="true"] {color:#175cd3;font-weight:650;}
    [data-testid="stButton"] button {border-radius:5px;font-weight:600;min-height:2.2rem;}
    [data-testid="stDownloadButton"] button {border-radius:5px;font-weight:600;}
    [data-testid="stSegmentedControl"] {margin-bottom:.25rem;}
    .page-description {font-size:.9rem;color:#667085;margin:0 0 .35rem;max-width:760px;line-height:1.55;}
    .section-intro {font-size:.82rem;color:#667085;margin:-.15rem 0 .7rem;line-height:1.5;}
    .decision-panel {border-left:3px solid #f79009;background:#fffaf0;padding:.7rem .85rem;margin:.15rem 0 1rem;line-height:1.45;}
    .decision-panel.valid {border-color:#12b76a;background:#f0fdf4;}
    .decision-panel strong {display:block;font-size:.86rem;margin-bottom:.1rem;color:#344054;}
    .decision-panel span {font-size:.82rem;color:#667085;}
    .linkage-row {display:flex;align-items:center;gap:.55rem;flex-wrap:wrap;margin:.2rem 0 .85rem;}
    .status-chip {display:inline-flex;align-items:center;padding:.18rem .48rem;border-radius:4px;
                  font-size:.75rem;font-weight:650;border:1px solid #d0d5dd;background:#fff;color:#475467;}
    .status-chip.ok {border-color:#86efac;background:#ecfdf5;color:#166534;}
    .status-chip.warn {border-color:#fdba74;background:#fff7ed;color:#9a3412;}
    .status-chip.bad {border-color:#fda29b;background:#fff1f0;color:#b42318;}
    .status-detail {font-size:.79rem;color:#667085;}
    .compact-meta {font-size:.78rem;color:#667085;margin:.1rem 0 1.15rem;}
    @media (max-width: 900px) {
      [data-testid="stMainBlockContainer"] {padding-left:1rem;padding-right:1rem;padding-top:1.25rem !important;}
      [data-testid="stMetricValue"] {font-size:1.15rem;}
    }
    </style>""",
    unsafe_allow_html=True,
)


def page_header(_kicker: str, title: str, description: str, meta: str | None = None) -> None:
    st.header(title)
    st.markdown(f'<div class="page-description">{description}</div>', unsafe_allow_html=True)
    if meta:
        st.markdown(f'<div class="compact-meta">{meta}</div>', unsafe_allow_html=True)


def section_header(title: str, description: str | None = None) -> None:
    st.subheader(title)
    if description:
        st.markdown(f'<div class="section-intro">{description}</div>', unsafe_allow_html=True)


# ==================== 数据读取与缓存 ====================
def data_signature() -> str:
    files = sorted(DATA_DIR.glob("*.parquet"))
    return "|".join(f"{f.name}:{f.stat().st_mtime_ns}" for f in files)


@st.cache_data(ttl="1h")
def cached_data_summary(signature: str) -> dict[str, object]:
    del signature
    files = sorted(DATA_DIR.glob("*.parquet"))
    frames = []
    for file in files:
        try:
            frames.append(pd.read_parquet(file, columns=["date"]))
        except Exception:
            pass
    if not frames:
        return {"files": len(files), "rows": 0, "trading_days": 0, "start": "-", "end": "-"}
    dates = pd.concat(frames, ignore_index=True)["date"]
    dates = pd.to_datetime(dates)
    return {
        "files": len(files),
        "rows": len(dates),
        "trading_days": int(dates.nunique()),
        "start": str(dates.min().date()),
        "end": str(dates.max().date()),
    }


@st.cache_data(ttl="10m", max_entries=4)
def cached_panel(signature: str) -> pd.DataFrame:
    del signature
    return load_panel(DATA_DIR)


@st.cache_data(ttl="24h", max_entries=2)
def cached_universe(cache_mtime: float = 0) -> pd.DataFrame:
    del cache_mtime
    return load_stock_universe(UNIVERSE_PATH)


def universe() -> pd.DataFrame:
    try:
        mtime = UNIVERSE_PATH.stat().st_mtime if UNIVERSE_PATH.exists() else 0
        return cached_universe(mtime)
    except Exception as error:
        st.warning(f"股票目录加载失败：{error}")
        return pd.DataFrame(columns=["symbol", "name", "search_label"])


def data_summary() -> dict[str, object]:
    return cached_data_summary(data_signature())


def output_path(name: str) -> Path:
    return OUTPUT_DIR / name


def load_picks() -> pd.DataFrame | None:
    path = output_path("latest_picks.csv")
    if not path.exists():
        return None
    picks = pd.read_csv(path, dtype={"symbol": str})
    picks["symbol"] = picks["symbol"].str.zfill(6)
    return picks


def load_scores() -> pd.DataFrame | None:
    path = output_path("latest_scores.csv")
    if not path.exists():
        return None
    return pd.read_csv(path, dtype={"symbol": str})


def load_backtest() -> tuple[pd.DataFrame | None, dict]:
    periods_path = output_path("backtest_periods.csv")
    metrics_path = output_path("backtest_metrics.json")
    periods = pd.read_csv(periods_path, parse_dates=["date"]) if periods_path.exists() else None
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    return periods, metrics


def load_validation_metrics() -> dict:
    path = output_path("validation_metrics.json")
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_score_diagnostics() -> dict:
    path = output_path("score_diagnostics.json")
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_run_manifests() -> list[dict]:
    runs_dir = OUTPUT_DIR / "runs"
    manifests = []
    for path in sorted(runs_dir.glob("*.json"), reverse=True) if runs_dir.exists() else []:
        try:
            manifests.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return sorted(manifests, key=lambda item: str(item.get("created_at", "")), reverse=True)


def research_data_audits(panel: pd.DataFrame | None = None) -> tuple[dict, dict]:
    metadata = load_metadata_history(ARCHIVE_DIR)
    relevant_symbols = [
        path.stem for path in DATA_DIR.glob("*.parquet") if security_type(path.stem) == "A股个股"
    ]
    metadata_audit = metadata_coverage(latest_metadata_snapshot(metadata, relevant_symbols))
    if panel is None or panel.empty:
        universe_audit = universe_history_audit(load_universe_history(ARCHIVE_DIR))
    else:
        universe_audit = universe_history_audit(
            load_universe_history(ARCHIVE_DIR), panel["date"].min(), panel["date"].max()
        )
    return metadata_audit, universe_audit


def load_research_status() -> dict:
    metadata_audit, universe_audit = research_data_audits()
    backtest = load_backtest()[1]
    validation = load_validation_metrics()
    status = assess_research_status(backtest, validation, metadata_audit, universe_audit)
    warnings = status["warnings"]
    score_manifest = load_manifest(OUTPUT_DIR, "score")
    backtest_manifest = load_manifest(OUTPUT_DIR, "backtest")
    if score_manifest and backtest_manifest:
        config_match = _score_configs_match(score_manifest.get("config", {}), backtest_manifest.get("config", {}))
        data_match = score_manifest.get("data_fingerprint") == backtest_manifest.get("data_fingerprint")
        if not config_match:
            warnings.append("最近回测参数与评分参数不一致，不能为当前观察名单背书")
        elif not data_match:
            warnings.append("最近回测与评分使用的数据版本不一致，验证关系需要更新")
        elif score_manifest.get("governance_fingerprint") != backtest_manifest.get("governance_fingerprint"):
            warnings.append("最近回测与评分使用的元数据或历史股票池版本不一致")
    latest_end = data_summary().get("end", "-")
    picks = load_picks()
    pick_date = str(picks["date"].iloc[0])[:10] if picks is not None and len(picks) and "date" in picks else "-"
    if latest_end != "-" and pick_date != "-" and pick_date < str(latest_end):
        warnings.append(f"评分结果数据日为 {pick_date}，落后于本地行情 {latest_end}")
    backtest_end = str(backtest.get("data_end", "-"))[:10]
    if latest_end != "-" and backtest_end != "-" and backtest_end < str(latest_end):
        warnings.append(f"回测数据截止 {backtest_end}，落后于本地行情 {latest_end}")
    universe_status = research_universe_status()
    if not universe_status.get("broad"):
        warnings.append(f'当前仅覆盖 {universe_status.get("count", 0)} 只A股，属于{universe_status.get("level")}，不代表全市场选股结论')
    if warnings:
        status["passed"] = False
        status["result_term"] = "研究观察名单"
        if status.get("preliminary_passed"):
            status.update(status="preliminary", label="初步通过")
    return status


def _score_configs_match(score_config: dict, backtest_config: dict) -> bool:
    """Compare only fields that define the ranking and portfolio selection rule."""
    if not score_config or not backtest_config:
        return False
    if int(score_config.get("horizon", -1)) != int(backtest_config.get("horizon", -2)):
        return False
    if int(score_config.get("top_k", -1)) != int(backtest_config.get("top_k", -2)):
        return False
    score_weights = score_config.get("weights", {})
    backtest_weights = backtest_config.get("weights", {})
    score_uses_live_sentiment = bool(score_config.get("fetch_sentiment", False)) and float(score_weights.get("sentiment", 0)) > 0
    comparable_score_weights = score_weights if score_uses_live_sentiment else without_unvalidated_sentiment(score_weights)
    comparable_backtest_weights = backtest_weights
    weights_match = all(
        abs(float(comparable_score_weights.get(key, -1)) - float(comparable_backtest_weights.get(key, -2))) < 1e-8
        for key in DEFAULT_WEIGHTS
    )
    if not weights_match:
        return False
    if score_uses_live_sentiment and backtest_config.get("sentiment_mode") != "historical":
        return False
    if score_config.get("universe_count") is not None and backtest_config.get("universe_count") is not None:
        if int(score_config["universe_count"]) != int(backtest_config["universe_count"]):
            return False
    return all(
        score_config.get(key, value) == backtest_config.get(key, value)
        for key, value in (("feature_version", FEATURE_VERSION), ("model_version", MODEL_VERSION))
    )


def governance_fingerprint() -> str:
    files = [
        *ARCHIVE_DIR.glob("metadata_*.csv"),
        *ARCHIVE_DIR.glob("universe_*.csv"),
    ]
    return data_fingerprint(files)


def score_backtest_differences(score: dict, backtest: dict) -> list[dict[str, str]]:
    score_config, backtest_config = score.get("config", {}), backtest.get("config", {})
    differences = []
    fields = [
        ("数据截止日期", score.get("data_end", "—"), backtest.get("data_end", "—")),
        ("预测/持有周期", score_config.get("horizon", "—"), backtest_config.get("horizon", "—")),
        ("候选/持仓数量", score_config.get("top_k", "—"), backtest_config.get("top_k", "—")),
        ("研究股票数量", score_config.get("universe_count", "旧版本未记录"), backtest_config.get("universe_count", "旧版本未记录")),
        ("特征版本", score_config.get("feature_version", "旧版本未记录"), backtest_config.get("feature_version", "旧版本未记录")),
        ("模型版本", score_config.get("model_version", "旧版本未记录"), backtest_config.get("model_version", "旧版本未记录")),
        ("舆情口径", "抓取最新舆情" if score_config.get("fetch_sentiment") else "中性值",
         {"historical": "历史舆情", "neutral_unvalidated": "中性值/未验证"}.get(backtest_config.get("sentiment_mode"), "旧版本未记录")),
        ("行情数据指纹", score.get("data_fingerprint", "—"), backtest.get("data_fingerprint", "—")),
        ("治理数据指纹", score.get("governance_fingerprint", "旧版本未记录"), backtest.get("governance_fingerprint", "旧版本未记录")),
    ]
    score_weights, backtest_weights = score_config.get("weights", {}), backtest_config.get("weights", {})
    for key, label in WEIGHT_LABELS:
        fields.append((f"{label}权重", f'{float(score_weights.get(key, 0)):.0%}', f'{float(backtest_weights.get(key, 0)):.0%}'))
    for item, score_value, backtest_value in fields:
        if score_value != backtest_value:
            differences.append({"差异项": item, "当前评分": str(score_value), "最近回测": str(backtest_value)})
    return differences


def research_linkage_status() -> dict[str, object]:
    """Describe whether the latest score is supported by a comparable backtest."""
    score = load_manifest(OUTPUT_DIR, "score")
    backtest = load_manifest(OUTPUT_DIR, "backtest")
    current_fingerprint = data_fingerprint(list(DATA_DIR.glob("*.parquet")))
    reasons: list[str] = []
    if not score:
        return {"level": "missing", "label": "尚无评分", "detail": "运行综合评分后才能建立验证关系。", "matched": False}
    if not backtest:
        return {"level": "missing", "label": "尚未回测", "detail": "当前评分没有历史验证证据。", "matched": False}
    config_match = _score_configs_match(score.get("config", {}), backtest.get("config", {}))
    data_match = score.get("data_fingerprint") == backtest.get("data_fingerprint")
    governance_match = bool(score.get("governance_fingerprint")) and score.get("governance_fingerprint") == backtest.get("governance_fingerprint")
    score_is_current = score.get("data_fingerprint") == current_fingerprint
    if not config_match:
        reasons.append("评分与回测的周期、候选数量或权重不同")
    if not data_match:
        reasons.append("评分与回测使用的数据版本不同")
    if not governance_match:
        reasons.append("行业、市值或历史股票池版本不同")
    if not score_is_current:
        reasons.append("评分后本地行情已发生变化")
    matched = config_match and data_match and governance_match and score_is_current
    if matched:
        linked_run = backtest.get("score_run_id")
        detail = "参数和数据版本一致，可作为当前评分方法的历史证据。"
        if linked_run and linked_run != score.get("run_id"):
            detail = "参数和数据版本一致；回测关联的是同配置的较早评分运行。"
        return {"level": "ok", "label": "已有匹配回测", "detail": detail, "matched": True}
    return {
        "level": "bad" if not config_match else "warn",
        "label": "验证关系不完整",
        "detail": "；".join(reasons),
        "matched": False,
    }


def render_linkage_status(linkage: dict[str, object]) -> None:
    css = {"ok": "ok", "warn": "warn", "bad": "bad", "missing": "warn"}.get(str(linkage.get("level")), "warn")
    st.markdown(
        f'<div class="linkage-row"><span class="status-chip {css}">{linkage.get("label", "待验证")}</span>'
        f'<span class="status-detail">{linkage.get("detail", "")}</span></div>',
        unsafe_allow_html=True,
    )
    if not linkage.get("matched"):
        score, backtest = load_manifest(OUTPUT_DIR, "score"), load_manifest(OUTPUT_DIR, "backtest")
        differences = score_backtest_differences(score, backtest) if score and backtest else []
        if differences:
            with st.expander(f"查看 {len(differences)} 项配置与数据差异"):
                st.dataframe(pd.DataFrame(differences), width="stretch", hide_index=True)


def save_research_status(status: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path("research_status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def panel_with_point_in_time_metadata(panel: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    metadata = load_metadata_history(ARCHIVE_DIR)
    merged = merge_asof_metadata(panel, metadata)
    audit = metadata_coverage(merged)
    source_audit = metadata_coverage(metadata)
    audit["archive_snapshot_start"] = source_audit.get("snapshot_start")
    audit["archive_snapshot_end"] = source_audit.get("snapshot_end")
    return merged, audit


def governed_research_panel(panel: pd.DataFrame) -> tuple[pd.DataFrame, dict, dict]:
    panel = panel.loc[a_share_equity_mask(panel["symbol"])].copy()
    history = load_universe_history(ARCHIVE_DIR)
    universe_audit = universe_history_audit(history, panel["date"].min(), panel["date"].max())
    governed = apply_historical_universe(panel, history)
    governed, metadata_audit = panel_with_point_in_time_metadata(governed)
    return governed, metadata_audit, universe_audit


def load_importance() -> pd.DataFrame | None:
    path = output_path("feature_importance.csv")
    return pd.read_csv(path) if path.exists() else None


def file_mtime(path: Path) -> str:
    if not path.exists():
        return "-"
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


def show_operation_error(title: str, error: Exception) -> None:
    st.error(f"{title}失败，原有结果未被删除。请检查数据状态后重试。")
    with st.expander("查看技术原因"):
        st.code(f"{type(error).__name__}: {error}")


def display_source(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    text = str(value).strip()
    if not text or text in {"-", "unavailable", "nan", "<NA>"}:
        return "—"
    mapping = {
        "tencent.quote": "腾讯报价",
        "sina.sw_industry": "新浪申万行业",
        "akshare.snapshot": "AKShare批量",
        "akshare.stock_individual_info_em": "东方财富个股资料",
        "本地数据": "本地数据",
    }
    return "+".join(mapping.get(item, item) for item in text.split("+"))


def fill_object_nulls(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in result.columns:
        if result[column].dtype == "object" or str(result[column].dtype).startswith("string"):
            result[column] = result[column].fillna("—").replace({"": "—", "-": "—"})
    return result


def picks_with_names(picks: pd.DataFrame) -> pd.DataFrame:
    names = universe()[["symbol", "name"]].drop_duplicates("symbol")
    names["symbol"] = names["symbol"].astype(str).str.zfill(6)
    return picks.merge(names, on="symbol", how="left")


def name_map() -> dict[str, str]:
    catalog = universe()
    if catalog.empty or "name" not in catalog.columns:
        return {}
    names = catalog[["symbol", "name"]].drop_duplicates("symbol")
    return names.set_index("symbol")["name"].fillna("").to_dict()


def with_names(frame: pd.DataFrame, symbol_column: str = "symbol") -> pd.DataFrame:
    """在含股票代码的表格中补充股票名称列。"""
    if "name" in frame.columns:
        return frame
    names = name_map()
    result = frame.copy()
    result.insert(
        list(result.columns).index(symbol_column) + 1, "name",
        result[symbol_column].astype(str).str.zfill(6).map(names).fillna(""),
    )
    return result


def format_amount(value: object) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return "-"
    number = float(number)
    if abs(number) >= 1e8:
        return f"{number / 1e8:.2f}亿"
    if abs(number) >= 1e4:
        return f"{number / 1e4:.2f}万"
    return f"{number:.0f}"


# ==================== 中文坐标轴图表 ====================
def _melt_cn(data: pd.DataFrame | pd.Series) -> pd.DataFrame:
    frame = data.to_frame() if isinstance(data, pd.Series) else data
    index_name = frame.index.name or "x"
    return (
        frame.rename_axis(index_name).reset_index()
        .melt(id_vars=index_name, var_name="series", value_name="value")
        .rename(columns={index_name: "x"})
    )


def _cn_chart(data, mark: str, y_title: str, x_title: str | None, height: int, y_format: str | None):
    source = _melt_cn(data)
    x_type = "T" if pd.api.types.is_datetime64_any_dtype(source["x"]) else "N"
    y_axis = alt.Axis(format=y_format) if y_format else alt.Axis()
    known_colors = {
        "组合": "#175cd3", "组合净值": "#175cd3", "基准": "#98a2b3", "基准净值": "#98a2b3",
        "回撤": "#d92d20", "超额": "#039855", "累计超额": "#039855",
    }
    fallback_colors = ["#175cd3", "#98a2b3", "#039855", "#f79009", "#7f56d9"]
    series_domain = [str(value) for value in source["series"].drop_duplicates()]
    series_range = [known_colors.get(value, fallback_colors[index % len(fallback_colors)])
                    for index, value in enumerate(series_domain)]
    mark_options = {"opacity": .28} if mark == "area" else ({"point": False, "strokeWidth": 2} if mark == "line" else {})
    chart = getattr(alt.Chart(source), f"mark_{mark}")(**mark_options).encode(
        x=alt.X(f"x:{x_type}", title=x_title),
        y=alt.Y("value:Q", title=y_title, axis=y_axis),
        color=alt.Color("series:N", title=None, scale=alt.Scale(domain=series_domain, range=series_range)),
        tooltip=[alt.Tooltip(f"x:{x_type}", title=x_title or ""), "series:N",
                 alt.Tooltip("value:Q", title=y_title, format=y_format or ".4f")],
    ).properties(height=height)
    st.altair_chart(chart, width="stretch")


def cn_line_chart(data, y_title: str, x_title: str | None = None, height: int = 300, y_format: str | None = None):
    _cn_chart(data, "line", y_title, x_title, height, y_format)


def cn_bar_chart(data, y_title: str, x_title: str | None = None, height: int = 260, y_format: str | None = None):
    _cn_chart(data, "bar", y_title, x_title, height, y_format)


def cn_area_chart(data, y_title: str, x_title: str | None = None, height: int = 180, y_format: str | None = None):
    _cn_chart(data, "area", y_title, x_title, height, y_format)


def _numeric(value: object, default: float | None = 0) -> float | None:
    """Coerce an artifact metric for gate evaluation, falling back on null/missing."""
    number = pd.to_numeric(value, errors="coerce")
    return default if pd.isna(number) else float(number)


def _fmt_metric(value: object, kind: str = "number", digits: int = 2) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return "—"
    if kind == "percent":
        return f"{float(number):.{digits}%}"
    return f"{float(number):.{digits}f}"


def backtest_gate_table(metrics: dict, validation: dict) -> pd.DataFrame:
    ic_low = _numeric(metrics.get("ic_confidence_low"), None)
    adjusted_p = _numeric(metrics.get("ic_p_value_adjusted", metrics.get("ic_p_value")), None)
    periods = _numeric(metrics.get("periods"))
    rows = [
        ("核心", "样本外调仓期", metrics.get("periods"), "≥ 36期", int(periods) >= 36, "integer"),
        ("核心", "扣费后累计超额", metrics.get("cumulative_excess_return"), "> 0%", _numeric(metrics.get("cumulative_excess_return")) > 0, "percent"),
        ("核心", "Rank IC区间下限", ic_low, "> 0", ic_low is not None and ic_low > 0, "number"),
        ("核心", "Q5-Q1平均收益", metrics.get("q5_q1_mean_return"), "> 0%", _numeric(metrics.get("q5_q1_mean_return")) > 0, "percent"),
        ("核心", "超额收益胜率", metrics.get("excess_win_rate"), "> 50%", _numeric(metrics.get("excess_win_rate")) > .5, "percent"),
        ("核心", "验证集R²", validation.get("r2"), "> 0", _numeric(validation.get("r2"), -1) > 0, "number"),
        ("稳健", "正收益年度占比", metrics.get("positive_year_ratio"), "≥ 75%", _numeric(metrics.get("positive_year_ratio")) >= .75, "percent"),
        ("稳健", "稳健样本量", metrics.get("periods"), "≥ 60期", int(periods) >= 60, "integer"),
        ("稳健", "跑赢最强简单基线", metrics.get("best_simple_baseline_excess_return"), "> 0%", _numeric(metrics.get("best_simple_baseline_excess_return"), -1) > 0, "percent"),
        ("稳健", "校正后Rank IC p值", adjusted_p, "< 0.05", adjusted_p is not None and adjusted_p < .05, "number"),
        ("稳健", "无法连续估值事件", metrics.get("unresolved_holding_events"), "= 0次", int(_numeric(metrics.get("unresolved_holding_events"))) == 0, "integer"),
    ]
    records = []
    for level, item, value, threshold, passed, kind in rows:
        if kind == "percent":
            shown = _fmt_metric(value, "percent")
        elif kind == "integer":
            shown = "—" if value is None else f"{int(value)}"
        else:
            shown = _fmt_metric(value, digits=3)
        records.append({"层级": level, "检查项": item, "当前结果": shown, "研究门槛": threshold,
                        "判定": "通过" if passed else "未通过"})
    return pd.DataFrame(records)


def render_backtest_workspace(periods: pd.DataFrame | None, metrics: dict) -> None:
    """Render backtest evidence by decision task instead of one long metric wall."""
    m = metrics
    validation = load_validation_metrics()
    manifest = load_manifest(OUTPUT_DIR, "backtest")
    config = manifest.get("config", {})
    status = load_research_status()
    linkage = research_linkage_status()
    section_header("本次回测", "先看研究结论，再分别核验有效性、收益风险、执行假设和组合暴露。")
    decision_reasons = status.get("failed_reasons", []) + status.get("warnings", [])
    st.markdown(
        f'<div class="decision-panel {"valid" if status.get("passed") else ""}">'
        f'<strong>验证结论：{status.get("label", "未验证")}</strong>'
        f'<span>{decision_reasons[0] if decision_reasons else "当前研究治理门槛均已满足。"}</span></div>',
        unsafe_allow_html=True,
    )
    render_linkage_status(linkage)
    st.caption(
        f'运行 {manifest.get("run_id", "-")} · 数据截至 {manifest.get("data_end", "-")} · '
        f'持有 {config.get("horizon", m.get("horizon_days", "-"))} 日 · Top {config.get("top_k", "-")} · '
        f'基准 {BENCHMARK_NAMES.get(m.get("benchmark_name"), "股票池等权")}'
    )

    overview_tab, validity_tab, risk_tab, execution_tab, exposure_tab, detail_tab = st.tabs(
        ["总览", "有效性", "收益风险", "执行", "暴露", "明细"]
    )
    with overview_tab:
        cols = st.columns(6)
        cols[0].metric("累计超额收益", _fmt_metric(m.get("cumulative_excess_return"), "percent"), help=TERM_HELP["cumulative_excess_return"])
        cols[1].metric("最大回撤", _fmt_metric(m.get("max_drawdown"), "percent"), help=TERM_HELP["max_drawdown"])
        cols[2].metric("Rank IC", _fmt_metric(m.get("ic_mean"), digits=3), help=TERM_HELP["rank_ic"])
        cols[3].metric("信息比率", _fmt_metric(m.get("information_ratio")), help=TERM_HELP["information_ratio"])
        cols[4].metric("平均成交比例", _fmt_metric(m.get("average_fill_ratio"), "percent"))
        cols[5].metric("调仓期数", str(m.get("periods", "—")))
        st.subheader("证据判定")
        st.caption("以下门槛是本产品采用的保守研究治理规则，并非行业统一标准。核心项全部通过才可初步通过，稳健项也全部通过才可稳健通过。")
        st.dataframe(backtest_gate_table(m, validation), width="stretch", hide_index=True)
        governance_warnings = status.get("warnings", [])
        if governance_warnings:
            st.info("数据治理限制：" + "；".join(governance_warnings))

    with validity_tab:
        stat_cols = st.columns(5)
        stat_cols[0].metric("Rank IC", _fmt_metric(m.get("ic_mean"), digits=3), help=TERM_HELP["rank_ic"])
        ic_low, ic_high = m.get("ic_confidence_low"), m.get("ic_confidence_high")
        interval = f"{float(ic_low):.3f} ~ {float(ic_high):.3f}" if ic_low is not None and ic_high is not None else "待评估"
        stat_cols[1].metric("95%置信区间", interval)
        stat_cols[2].metric("校正后p值", _fmt_metric(m.get("ic_p_value_adjusted", m.get("ic_p_value")), digits=3))
        stat_cols[3].metric("正IC期占比", _fmt_metric(m.get("ic_positive_ratio"), "percent"))
        stat_cols[4].metric("Q5-Q1", _fmt_metric(m.get("q5_q1_mean_return"), "percent"), help=TERM_HELP["q5_q1"])
        simple_baselines = m.get("simple_baselines", {})
        if simple_baselines:
            st.subheader("简单策略基线")
            baseline_rows = [{"策略": values.get("label", key),
                              "累计收益": values.get("cumulative_return", 0) * 100,
                              "本模型相对超额": values.get("portfolio_excess_return", 0) * 100,
                              "判定": "跑赢" if values.get("portfolio_excess_return", 0) > 0 else "未跑赢"}
                             for key, values in simple_baselines.items()]
            st.dataframe(pd.DataFrame(baseline_rows), width="stretch", hide_index=True,
                         column_config={"累计收益": st.column_config.NumberColumn(format="%.2f%%"),
                                        "本模型相对超额": st.column_config.NumberColumn(format="%.2f%%")})
        regimes = m.get("regime_metrics", {})
        if regimes:
            st.subheader("市场状态分段")
            regime_rows = [{"市场状态": key, "调仓期数": value.get("periods", 0),
                            "累计收益": value.get("cumulative_return", 0) * 100,
                            "累计超额": value.get("cumulative_excess_return", 0) * 100,
                            "平均Rank IC": value.get("rank_ic", 0)} for key, value in regimes.items()]
            st.dataframe(pd.DataFrame(regime_rows), width="stretch", hide_index=True,
                         column_config={"累计收益": st.column_config.NumberColumn(format="%.2f%%"),
                                        "累计超额": st.column_config.NumberColumn(format="%.2f%%"),
                                        "平均Rank IC": st.column_config.NumberColumn(format="%.3f")})
        nested = m.get("nested_validation", {})
        if nested:
            with st.expander("嵌套样本外验证"):
                st.write(f'外层调仓期 {nested.get("outer_periods", 0)} 个；内层候选叶子数 {nested.get("inner_candidates", [])}；选择分布 {nested.get("selected_leaf_distribution", {})}。')

    with risk_tab:
        risk_cols = st.columns(6)
        for col, label_text, key, kind in [
            (risk_cols[0], "累计收益", "cumulative_return", "percent"),
            (risk_cols[1], "年化收益", "annualized_return", "percent"),
            (risk_cols[2], "年化波动", "annualized_volatility", "percent"),
            (risk_cols[3], "夏普比率", "sharpe", "number"),
            (risk_cols[4], "Sortino", "sortino", "number"),
            (risk_cols[5], "Calmar", "calmar", "number"),
        ]:
            col.metric(label_text, _fmt_metric(m.get(key), kind))
        if periods is not None and not periods.empty:
            equity = periods.set_index("date")[["equity", "benchmark_equity"]].rename(columns={"equity": "组合净值", "benchmark_equity": "基准净值"})
            cn_line_chart(equity, "净值", height=300)
            drawdown = (periods.set_index("date")["equity"] / periods.set_index("date")["equity"].cummax() - 1).rename("回撤")
            cn_area_chart(drawdown, "回撤", height=180, y_format="%")

    with execution_tab:
        exec_cols = st.columns(5)
        exec_cols[0].metric("平均换手率", _fmt_metric(m.get("average_turnover"), "percent"), help=TERM_HELP["average_turnover"])
        exec_cols[1].metric("平均成交比例", _fmt_metric(m.get("average_fill_ratio"), "percent"))
        exec_cols[2].metric("买入成本", f'{m.get("buy_cost_bps", "—")} bps')
        exec_cols[3].metric("卖出成本", f'{m.get("sell_cost_bps", "—")} bps')
        exec_cols[4].metric("滑点", f'{m.get("slippage_bps", "—")} bps')
        sentiment_result = config.get("sentiment_audit", {})
        sentiment_mode = config.get("sentiment_mode", "旧版本未记录")
        st.caption(
            f'舆情回测口径：{sentiment_mode} · 历史快照 {sentiment_result.get("snapshot_count", 0)} 个 · '
            f'截面覆盖 {float(sentiment_result.get("coverage", 0)):.1%}'
        )
        if sentiment_mode == "neutral_unvalidated":
            st.warning("本次回测已排除未被历史数据支持的舆情维度，因此不能完整验证启用实时舆情的当前评分。")
        if m.get("forced_hold_events", 0):
            st.warning(f'发生 {m.get("forced_hold_events", 0)} 次无法卖出并强制延续持仓，涉及 {m.get("forced_hold_periods", 0)} 个调仓期。')
        if m.get("unresolved_holding_events", 0):
            st.error(f'有 {m.get("unresolved_holding_events", 0)} 次持仓无法连续估值，本次回测不能稳健通过。')
        sensitivity = m.get("cost_sensitivity", [])
        if sensitivity:
            st.subheader("交易成本敏感性")
            frame = pd.DataFrame(sensitivity).rename(columns={"cost_bps_per_direction": "单方向总成本（bps）", "cumulative_return": "累计收益"})
            frame["累计收益"] = frame["累计收益"] * 100
            st.dataframe(frame, width="stretch", hide_index=True,
                         column_config={"累计收益": st.column_config.NumberColumn(format="%.2f%%")})
        capacity_curve = m.get("capacity_curve", [])
        if capacity_curve:
            st.subheader("资金容量")
            capacity = pd.DataFrame([{"模拟资金（万元）": row.get("capital", 0) / 10_000,
                                      "可成交期覆盖率": row.get("period_coverage", 0) * 100,
                                      "历史中位容量（万元）": row.get("median_capacity", 0) / 10_000}
                                     for row in capacity_curve])
            st.dataframe(capacity, width="stretch", hide_index=True,
                         column_config={"可成交期覆盖率": st.column_config.NumberColumn(format="%.1f%%")})

    with exposure_tab:
        exposure = m.get("portfolio_exposure", {})
        if not exposure:
            st.info("本次回测没有可用的行业与市值暴露结果。")
        else:
            cols = st.columns(4)
            cols[0].metric("平均最大行业权重", _fmt_metric(exposure.get("average_max_industry_weight"), "percent"))
            cols[1].metric("平均行业HHI", _fmt_metric(exposure.get("average_industry_hhi"), digits=3))
            median_cap, mean_cap = exposure.get("median_market_cap"), exposure.get("mean_market_cap")
            cols[2].metric("持仓中位市值", f"{median_cap / 1e8:.1f}亿元" if median_cap else "—")
            cols[3].metric("持仓平均市值", f"{mean_cap / 1e8:.1f}亿元" if mean_cap else "—")
            weights = exposure.get("average_industry_weights", {})
            if weights:
                frame = pd.DataFrame({"行业": list(weights), "平均权重": [value * 100 for value in weights.values()]})
                st.dataframe(frame.sort_values("平均权重", ascending=False), width="stretch", hide_index=True,
                             column_config={"平均权重": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f%%")})

    with detail_tab:
        if periods is None or periods.empty:
            st.info("没有逐期回测明细。")
        else:
            available = [column for column in ["date", "selected_count", "gross_return", "portfolio_return", "benchmark_return", "selected_symbols"] if column in periods]
            detail = periods[available].rename(columns={"date": "调仓日", "selected_count": "持仓数", "gross_return": "毛收益", "portfolio_return": "净收益", "benchmark_return": "基准收益", "selected_symbols": "持仓"})
            st.dataframe(detail, width="stretch", hide_index=True, height=420,
                         column_config={"毛收益": st.column_config.NumberColumn(format="%.2f%%"), "净收益": st.column_config.NumberColumn(format="%.2f%%"), "基准收益": st.column_config.NumberColumn(format="%.2f%%")})
            st.download_button("下载回测明细 CSV", periods.to_csv(index=False).encode("utf-8-sig"),
                               "backtest_periods.csv", "text/csv", icon=":material/download:")


SCORE_PRESETS = {
    "标准综合": {
        "weights": DEFAULT_WEIGHTS,
        "description": "模型与技术面共同主导的默认研究配置。",
    },
    "模型信号优先": {
        "weights": {"model": .45, "technical": .15, "volume_price": .20, "candle": .10, "sentiment": .10},
        "description": "提高模型预测权重，用于检验模型是否有独立增量价值；不表示准确率一定更高。",
    },
    "技术确认均衡": {
        "weights": {"model": .30, "technical": .25, "volume_price": .20, "candle": .15, "sentiment": .10},
        "description": "降低模型单一影响，提高趋势和 K 线确认的作用。",
    },
}
WEIGHT_LABELS = [
    ("model", "模型"), ("technical", "技术面"), ("volume_price", "量价"),
    ("candle", "K线"), ("sentiment", "舆情"),
]


def _weight_key(namespace: str, factor: str) -> str:
    return f"{namespace}_weight_{factor}"


def set_weight_values(namespace: str, weights: dict[str, float]) -> None:
    for factor, _ in WEIGHT_LABELS:
        st.session_state[_weight_key(namespace, factor)] = int(round(float(weights.get(factor, 0)) * 100))


def normalized_weight_values(namespace: str) -> dict[str, float]:
    raw = {
        factor: float(st.session_state.get(_weight_key(namespace, factor), DEFAULT_WEIGHTS[factor] * 100)) / 100
        for factor, _ in WEIGHT_LABELS
    }
    total = sum(max(value, 0) for value in raw.values())
    return DEFAULT_WEIGHTS.copy() if total <= 0 else {factor: max(value, 0) / total for factor, value in raw.items()}


def matching_score_preset(namespace: str) -> str | None:
    current = normalized_weight_values(namespace)
    for name, preset in SCORE_PRESETS.items():
        if all(abs(current[factor] - float(preset["weights"][factor])) < 1e-9 for factor, _ in WEIGHT_LABELS):
            return name
    return None


def apply_score_preset() -> None:
    preset = st.session_state.get("score_preset", "标准综合")
    if preset in SCORE_PRESETS:
        set_weight_values("score", SCORE_PRESETS[preset]["weights"])


def sync_score_preset_from_weights() -> None:
    st.session_state["score_preset"] = matching_score_preset("score") or "自定义"


def weight_inputs(namespace: str, default_weights: dict[str, float] | None = None) -> dict[str, float]:
    defaults = default_weights or DEFAULT_WEIGHTS
    for factor, _ in WEIGHT_LABELS:
        state_key = _weight_key(namespace, factor)
        if state_key not in st.session_state:
            st.session_state[state_key] = int(round(float(defaults[factor]) * 100))
    st.caption("五项权重合计必须为 100%；可按 1% 调整。权重改变后应使用相同参数重新回测。")
    columns = st.columns(5)
    weights = {}
    for column, (key, label) in zip(columns, WEIGHT_LABELS):
        with column:
            weights[key] = st.number_input(
                f"{label}（%）", min_value=0, max_value=100, step=1,
                key=_weight_key(namespace, key), format="%d",
            ) / 100
    total = sum(weights.values())
    if total <= 0:
        st.warning("权重不能全部为 0，本次将使用默认权重。")
        return DEFAULT_WEIGHTS.copy()
    normalized = {key: value / total for key, value in weights.items()}
    if abs(total - 1.0) > 1e-8:
        st.error(f"当前权重合计为 {total:.0%}，请调整为 100% 后再运行。")
    else:
        st.caption("权重合计 100%，配置可运行。")
    return normalized


def weight_total(namespace: str) -> int:
    return sum(int(st.session_state.get(_weight_key(namespace, factor), 0)) for factor, _ in WEIGHT_LABELS)


def go_to_view(view: str):
    st.session_state.research_view = view


ARCHIVE_DIR = BASE_DIR / "data" / "archive"
CONFIG_PATH = BASE_DIR / "data" / "reference" / "download_config.json"


def historical_sentiment_data(data_start: object, data_end: object) -> tuple[pd.DataFrame, dict[str, object]]:
    history = load_score_history(ARCHIVE_DIR)
    required = {"symbol", "date", "sentiment_score"}
    if history.empty or not required.issubset(history.columns):
        return pd.DataFrame(), {"usable": False, "snapshot_count": 0, "coverage": 0.0,
                                "reason": "缺少可用于回测的历史舆情快照"}
    frame = history.copy()
    frame["symbol"] = frame["symbol"].astype(str).str.zfill(6)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["sentiment_score"] = pd.to_numeric(frame["sentiment_score"], errors="coerce")
    frame = frame.dropna(subset=["date", "sentiment_score"])
    if "archive_time" in frame:
        frame = frame.sort_values("archive_time").drop_duplicates(["date", "symbol"], keep="last")
    dates = frame["date"].drop_duplicates().sort_values()
    start, end = pd.to_datetime(data_start, errors="coerce"), pd.to_datetime(data_end, errors="coerce")
    covers_start = bool(len(dates) and pd.notna(start) and dates.min() <= start)
    covers_end = bool(len(dates) and pd.notna(end) and dates.max() >= end)
    expected_symbols = max(1, len([path for path in DATA_DIR.glob("*.parquet") if security_type(path.stem) == "A股个股"]))
    coverage = float(frame.groupby("date")["symbol"].nunique().median() / expected_symbols) if len(dates) else 0.0
    usable = bool(len(dates) >= 36 and covers_start and covers_end and coverage >= .8)
    reason = "" if usable else "历史舆情快照不足，回测将排除舆情维度，不能完整验证启用实时舆情的评分"
    return frame[["symbol", "date", "sentiment_score"]], {
        "usable": usable, "snapshot_count": int(len(dates)), "coverage": min(coverage, 1.0),
        "snapshot_start": str(dates.min().date()) if len(dates) else None,
        "snapshot_end": str(dates.max().date()) if len(dates) else None,
        "covers_data_start": covers_start, "covers_data_end": covers_end, "reason": reason,
    }


def without_unvalidated_sentiment(weights: dict[str, float]) -> dict[str, float]:
    result = {key: max(float(weights.get(key, 0)), 0) for key in DEFAULT_WEIGHTS}
    result["sentiment"] = 0.0
    total = sum(result.values())
    return {key: value / total for key, value in result.items()} if total > 0 else DEFAULT_WEIGHTS.copy()


def research_universe_status() -> dict[str, object]:
    symbols = [path.stem for path in DATA_DIR.glob("*.parquet") if security_type(path.stem) == "A股个股"]
    count = len(symbols)
    if count < 100:
        return {"count": count, "level": "流程验证", "broad": False}
    if count < MIN_BROAD_UNIVERSE:
        return {"count": count, "level": "有限股票池研究", "broad": False}
    return {"count": count, "level": "较宽研究范围", "broad": True}


def archive_run_artifacts(run_id: str, names: list[str]) -> Path:
    target = OUTPUT_DIR / "runs" / run_id
    target.mkdir(parents=True, exist_ok=True)
    manifest = OUTPUT_DIR / "runs" / f"{run_id}.json"
    if manifest.exists():
        shutil.copy2(manifest, target / "manifest.json")
    for name in names:
        source = OUTPUT_DIR / name
        if source.exists():
            shutil.copy2(source, target / name)
    return target


def effective_score_weights() -> dict[str, float]:
    saved = load_validation_metrics().get("weights", {})
    if isinstance(saved, dict) and all(key in saved for key in DEFAULT_WEIGHTS):
        total = sum(max(float(saved[key]), 0) for key in DEFAULT_WEIGHTS)
        if total > 0:
            return {key: max(float(saved[key]), 0) / total for key in DEFAULT_WEIGHTS}
    scores = load_scores()
    factor_keys = list(DEFAULT_WEIGHTS)
    factor_columns = [f"{key}_score" for key in factor_keys]
    if scores is not None and {"composite_score", *factor_columns}.issubset(scores.columns) and len(scores) >= len(factor_keys):
        x = scores[factor_columns].apply(pd.to_numeric, errors="coerce")
        y = pd.to_numeric(scores["composite_score"], errors="coerce")
        valid = x.notna().all(axis=1) & y.notna()
        if valid.sum() >= len(factor_keys):
            inferred = np.clip(np.linalg.lstsq(x.loc[valid].to_numpy(), y.loc[valid].to_numpy(), rcond=None)[0], 0, None)
            total = float(inferred.sum())
            if total > 0:
                return {key: float(value / total) for key, value in zip(factor_keys, inferred)}
    values = {
        key: float(st.session_state.get(f"weight_{key}", default * 100))
        for key, default in DEFAULT_WEIGHTS.items()
    }
    total = sum(max(value, 0) for value in values.values())
    return ({key: max(value, 0) / total for key, value in values.items()}
            if total > 0 else DEFAULT_WEIGHTS.copy())


def previous_score_ranks() -> dict[str, int]:
    try:
        history = load_score_history(ARCHIVE_DIR)
        if history.empty or not {"archive_time", "symbol", "composite_score"}.issubset(history.columns):
            return {}
        times = sorted(history["archive_time"].dropna().astype(str).unique())
        if len(times) < 2:
            return {}
        previous = history[history["archive_time"].astype(str) == times[-2]].copy()
        previous["symbol"] = previous["symbol"].astype(str).str.zfill(6)
        previous = previous.sort_values("composite_score", ascending=False).drop_duplicates("symbol")
        return {symbol: rank for rank, symbol in enumerate(previous["symbol"], start=1)}
    except Exception:
        return {}


def add_candidate_context(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.sort_values("composite_score", ascending=False).reset_index(drop=True).copy()
    result["排名"] = result.index + 1
    old_ranks = previous_score_ranks()
    changes = []
    for rank, symbol in zip(result["排名"], result["symbol"].astype(str).str.zfill(6)):
        old_rank = old_ranks.get(symbol)
        changes.append("-" if not old_ranks else ("新进" if old_rank is None else f"{old_rank - rank:+d}"))
    result["排名变化"] = changes
    return result


CANDIDATE_EXPORT_SCHEMA = [
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
    ("news_count", "新闻数量", "评分时纳入统计的去重新闻标题数量。"),
    ("odds_sample_count", "历史样本数", "用于个股历史收益统计的可用持有期样本数量。"),
    ("odds_win_rate", "历史胜率（%）", "历史样本中持有至预测周期结束后收益为正的比例。"),
    ("odds_reward_risk", "历史赔率（收益/风险）", "历史平均盈利幅度与平均亏损幅度的比值；不代表未来收益。"),
    ("odds_expected_return", "历史期望收益（%）", "历史样本在当前预测周期下的平均收益。"),
    ("conditional_sample_count", "条件高分样本数", "历史上满足高分条件且已实现、不重叠的样本数量；缺失表示尚未积累。"),
    ("conditional_win_rate", "条件胜率（%）", "条件高分样本中收益为正的比例。"),
    ("conditional_expected_return", "条件期望收益（%）", "条件高分样本在预测周期下的平均收益。"),
    ("credibility_score", "个股证据分", "综合策略验证、条件样本、稳定性、一致性和新闻覆盖的证据质量分，不参与综合排序。"),
    ("credibility_grade", "个股证据等级", "高、中、低三个等级，用于提示证据充分程度，不表示投资评级。"),
    ("run_id", "评分运行编号", "用于在研究记录中追溯本次评分的数据和参数。"),
]


def candidate_export_frame(picks: pd.DataFrame) -> pd.DataFrame:
    """Return a research-facing candidate export without internal feature columns."""
    available = [(source, label) for source, label, _ in CANDIDATE_EXPORT_SCHEMA if source in picks]
    result = picks[[source for source, _ in available]].copy()
    for source in ["daily_return", "turnover", "odds_win_rate", "odds_expected_return", "conditional_win_rate", "conditional_expected_return"]:
        if source in result:
            result[source] = pd.to_numeric(result[source], errors="coerce") * 100
    for source in ["amount", "market_cap"]:
        if source in result:
            result[source] = pd.to_numeric(result[source], errors="coerce") / 1e8
    return result.rename(columns=dict(available))


def candidate_export_dictionary(picks: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [{"字段": label, "说明": description} for source, label, description in CANDIDATE_EXPORT_SCHEMA if source in picks]
    )


def candidate_export_workbook(picks: pd.DataFrame) -> bytes:
    """Build one user-facing workbook with results and a data dictionary."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        candidate_export_frame(picks).to_excel(writer, sheet_name="候选明细", index=False)
        candidate_export_dictionary(picks).to_excel(writer, sheet_name="字段说明", index=False)
    return buffer.getvalue()


def load_download_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_download_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def archive_scoring_run() -> str:
    """评分/舆情快照每日留痕：同一评分日重复运行覆盖当日存档，跨日追加。"""
    scores = load_scores()
    if scores is None:
        return ""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now()
    scores = scores.copy()
    scores.insert(0, "archive_time", stamp.strftime("%Y-%m-%d %H:%M:%S"))
    day_path = ARCHIVE_DIR / f"scores_{stamp:%Y%m%d}.csv"
    scores.to_csv(day_path, index=False, encoding="utf-8-sig")
    history_path = ARCHIVE_DIR / "scores_history.csv"
    load_score_history(ARCHIVE_DIR).to_csv(history_path, index=False, encoding="utf-8-sig")
    return day_path.name


def archive_market_sentiment(mood: dict[str, object]) -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    row = pd.DataFrame([{
        "archive_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "date": mood.get("date", ""), "score": mood.get("score", 50.0),
        "breadth": mood.get("breadth", ""), "volume_ratio": mood.get("volume_ratio", ""),
        "limit_up_ratio": mood.get("limit_up_ratio", ""), "limit_up_count": mood.get("limit_up_count", 0),
        "limit_up_denominator": mood.get("limit_up_denominator", mood.get("stocks", 0)),
        "stocks": mood.get("stocks", 0),
    }])
    path = ARCHIVE_DIR / "market_sentiment.csv"
    if path.exists():
        row.to_csv(path, mode="a", header=False, index=False, encoding="utf-8-sig")
    else:
        row.to_csv(path, index=False, encoding="utf-8-sig")


# ==================== 侧边栏 ====================
summary = data_summary()
pool = load_pool(POOL_PATH)

with st.sidebar:
    st.title("选股研究台")
    st.radio(
        "研究流程",
        VIEWS,
        key="research_view",
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("数据资产")
    st.metric("本地行情文件", f'{summary["files"]} 只',
              help="已下载到本地的日线行情文件数量，是模型可用的全部数据范围")
    st.caption(f'共 {summary["rows"]:,} 行 · {summary["trading_days"]} 个交易日\n\n覆盖 {summary["start"]} 至 {summary["end"]}')
    st.caption(f"自选股票池：{len(pool)} 只")
    data_end = str(summary["end"])
    if data_end != "-":
        data_lag = (date.today() - pd.to_datetime(data_end).date()).days
        if data_lag > 4:
            st.warning(f"数据滞后 {data_lag} 天（最新 {data_end}），建议增量更新后再评分。")
            st.button("去更新数据", icon=":material/refresh:", width="stretch",
                      on_click=go_to_view, args=("股票池与数据",))
    st.divider()
    st.caption("研究用途声明：评分与回测仅供研究，不构成投资建议，不连接券商或自动下单。")

# ==================== PDF 报告 ====================
def export_pdf_report(picks: pd.DataFrame, backtest_metrics: dict, importance: pd.DataFrame) -> bytes:
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
    story = [
        Paragraph("A股研究观察名单报告", styles["Title"]),
        Paragraph(f"生成时间：{date.today()}（仅供研究，不构成投资建议）", styles["Normal"]),
        Spacer(1, 16),
    ]

    research_status = load_research_status()
    metadata_audit, universe_audit = research_data_audits()
    info_rows = [
        ["研究验证状态", research_status.get("label", "未验证")],
        ["观察标的数量", len(picks)], ["预测周期", f"{backtest_metrics.get('horizon_days', 20)} 日"],
        ["运行编号", str(picks.get("run_id", pd.Series(["-"])).iloc[0]) if len(picks) else "-"],
        ["行业/市值覆盖", f'{metadata_audit.get("industry_coverage", 0):.1%} / {metadata_audit.get("market_cap_coverage", 0):.1%}'],
        ["历史股票池控制", "已覆盖" if universe_audit.get("usable") else "未覆盖"],
        ["回测基准", BENCHMARK_NAMES.get(backtest_metrics.get("benchmark_name"), backtest_metrics.get("benchmark_name", "-"))],
        ["买入/卖出/滑点成本", f'{backtest_metrics.get("buy_cost_bps", "-")} / {backtest_metrics.get("sell_cost_bps", "-")} / {backtest_metrics.get("slippage_bps", "-")} bps'],
    ]
    for key, label in [("cumulative_return", "累计收益"), ("annualized_return", "年化收益"),
                       ("max_drawdown", "最大回撤"), ("win_rate", "胜率")]:
        value = backtest_metrics.get(key)
        info_rows.append([label, f"{value:.2%}" if isinstance(value, (int, float)) else "-"])
    sharpe = backtest_metrics.get("sharpe")
    info_rows.append(["夏普比率", f"{sharpe:.2f}" if isinstance(sharpe, (int, float)) else "-"])
    info_rows.append(["累计超额收益", f'{backtest_metrics.get("cumulative_excess_return", 0):.2%}'])
    info_rows.append(["Rank IC", f'{backtest_metrics.get("ic_mean", 0):.4f}'])
    if backtest_metrics.get("ic_confidence_low") is not None:
        info_rows.append(["Rank IC 95%区间", f'{backtest_metrics["ic_confidence_low"]:.4f} 至 {backtest_metrics["ic_confidence_high"]:.4f}'])
    info_table = Table(info_rows, colWidths=[150, 200])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [info_table, Spacer(1, 16), Paragraph("研究限制与执行假设", styles["Heading2"])]
    limitations = research_status.get("failed_reasons", []) + research_status.get("warnings", [])
    if limitations:
        for index, message in enumerate(limitations, start=1):
            story.append(Paragraph(f"{index}. {message}", styles["Normal"]))
    else:
        story.append(Paragraph("当前验证门槛未发现未通过项，但历史结果不代表未来收益。", styles["Normal"]))
    story.append(Paragraph(
        "信号在收盘后生成，下一交易日开盘建仓；跌停或停牌无法退出时强制延续持仓。"
        "资金容量、买卖成本和滑点均按本次回测参数模拟。", styles["Normal"],
    ))
    story += [Spacer(1, 16), Paragraph("候选股票列表", styles["Heading2"])]

    stock_rows = [["代码", "名称", "综合评分", "模型评分"]]
    for _, row in picks.iterrows():
        stock_rows.append([
            str(row.get("symbol", "")),
            str(row.get("name", ""))[:10],
            f'{row.get("composite_score", float("nan")):.1f}',
            f'{row.get("model_score", float("nan")):.1f}',
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
            [str(r["feature"])[:24], f'{r["importance"]:.4f}'] for _, r in importance.iterrows()]
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


# ==================== 页面：研究看板 ====================
if st.session_state.research_view == "研究看板":
    picks = load_picks()
    backtest_periods, backtest_metrics = load_backtest()

    dashboard_status = load_research_status()
    dashboard_metadata, dashboard_universe = research_data_audits()
    dashboard_linkage = research_linkage_status()
    page_header(
        "研究总览", "研究看板",
        "先确认研究证据和数据完整性，再审阅观察名单。综合评分用于横截面排序，不是上涨概率。",
        f'行情截至 {summary["end"]} · 研究样本范围：本地 {summary["files"]} 只证券',
    )
    decision_reasons = dashboard_status.get("failed_reasons", []) + dashboard_status.get("warnings", [])
    decision_text = decision_reasons[0] if decision_reasons else "核心有效性、稳健性与数据治理门槛均已满足。"
    decision_class = "valid" if dashboard_status.get("passed") else ""
    st.markdown(
        f'<div class="decision-panel {decision_class}"><strong>当前结论：{dashboard_status.get("label", "未验证")}</strong>'
        f'<span>{decision_text}</span></div>', unsafe_allow_html=True,
    )
    render_linkage_status(dashboard_linkage)
    if backtest_metrics:
        st.button("查看验证详情", icon=":material/fact_check:", key="dashboard_validation_detail",
                  on_click=go_to_view, args=("历史回测",))
    cockpit = st.columns(5)
    cockpit[0].metric("累计超额收益", _fmt_metric(backtest_metrics.get("cumulative_excess_return"), "percent"),
                      help=TERM_HELP["cumulative_excess_return"])
    cockpit[1].metric("Rank IC", _fmt_metric(backtest_metrics.get("ic_mean"), digits=4), help=TERM_HELP["rank_ic"])
    cockpit[2].metric("最大回撤", _fmt_metric(backtest_metrics.get("max_drawdown"), "percent"), help=TERM_HELP["max_drawdown"])
    cockpit[3].metric("当前元数据覆盖", f'{min(dashboard_metadata.get("industry_coverage", 0), dashboard_metadata.get("market_cap_coverage", 0)):.1%}',
                      help=TERM_HELP["metadata_coverage"])
    dashboard_universe_status = research_universe_status()
    cockpit[4].metric("研究A股范围", f'{dashboard_universe_status["count"]} 只',
                      help=f'当前属于{dashboard_universe_status["level"]}；少于 {MIN_BROAD_UNIVERSE} 只不代表全市场结论。')
    latest_score_manifest = load_manifest(OUTPUT_DIR, "score")
    latest_backtest_manifest = load_manifest(OUTPUT_DIR, "backtest")
    st.caption(
        f'评分运行 {latest_score_manifest.get("run_id", "-")} · '
        f'回测运行 {latest_backtest_manifest.get("run_id", "-")} · '
        f'历史股票池 {"已控制" if dashboard_universe.get("usable") else "未完整控制"}'
    )

    current_data_fingerprint = data_fingerprint(list(DATA_DIR.glob("*.parquet")))
    dashboard_data_end = pd.to_datetime(summary.get("end"), errors="coerce")
    dashboard_lag = (pd.Timestamp(date.today()) - dashboard_data_end).days if pd.notna(dashboard_data_end) else 999
    score_current = bool(
        picks is not None and latest_score_manifest
        and latest_score_manifest.get("data_fingerprint") == current_data_fingerprint
        and latest_score_manifest.get("governance_fingerprint") == governance_fingerprint()
    )
    step_states = {
        "股票池与数据": {
            "ready": bool(summary["files"] > 0 and dashboard_lag <= 4),
            "label": "可用" if summary["files"] > 0 and dashboard_lag <= 4 else ("需更新" if summary["files"] > 0 else "未准备"),
            "caption": f'研究样本 {summary["files"]} 只 · 覆盖至 {summary["end"]}',
        },
        "综合评分": {
            "ready": score_current,
            "label": "基于当前数据" if score_current else ("结果已过期" if picks is not None else "未运行"),
            "caption": f'上次生成 {file_mtime(output_path("latest_picks.csv"))}',
        },
        "历史回测": {
            "ready": bool(backtest_metrics and dashboard_linkage.get("matched")),
            "label": ("匹配但证据未通过" if dashboard_linkage.get("matched") and not dashboard_status.get("passed")
                      else "可引用" if dashboard_linkage.get("matched") else ("配置不匹配" if backtest_metrics else "未运行")),
            "caption": f'上次生成 {file_mtime(output_path("backtest_metrics.json"))}',
        },
    }
    steps = [
        ("准备数据", "更新研究范围内的行情和治理数据。", "股票池与数据"),
        ("综合评分", "使用当前数据重新生成候选与证据。", "综合评分"),
        ("历史回测", "使用一致配置建立可引用的历史证据。", "历史回测"),
    ]
    workflow_complete = all(state["ready"] for state in step_states.values())
    if not workflow_complete:
        section_header("完成研究流程", "仅展示尚未完成或需要补充的步骤。")
        pending_steps = [item for item in steps if not step_states[item[2]]["ready"]]
        for position, (title, desc, target_view) in enumerate(pending_steps, start=1):
            state = step_states[target_view]
            content_col, action_col = st.columns([7, 1], vertical_alignment="center")
            with content_col:
                st.markdown(f"**{position}. {title} · {state['label']}**")
                st.caption(f"{desc} {state['caption']}")
            with action_col:
                st.button("处理", key=f"go_{target_view}", on_click=go_to_view,
                          args=(target_view,), icon=":material/arrow_forward:", width="stretch")
    elif not dashboard_linkage.get("matched"):
        action_cols = st.columns([3, 1])
        action_cols[0].warning(f'当前候选尚无可直接引用的匹配回测：{dashboard_linkage.get("detail", "请重新验证")}')
        action_cols[1].button("去匹配回测", type="primary", width="stretch",
                              on_click=go_to_view, args=("历史回测",), icon=":material/history:")

    st.divider()

    left, right = st.columns([1.15, .85])
    with left:
        section_header("最新研究观察名单", "默认展示最需要审阅的十只标的；点击评分页可查看单股证据与因子贡献。")
        if picks is None:
            st.info("还没有评分结果。先到『股票池与数据』下载数据，再运行综合评分。")
        else:
            st.caption(f'生成于 {file_mtime(output_path("latest_picks.csv"))} · 数据日期 {str(picks["date"].iloc[0])[:10] if len(picks) else "-"}')
            shown = add_candidate_context(picks_with_names(picks)).head(10)
            if "conditional_win_rate" in shown:
                shown["条件胜率"] = pd.to_numeric(shown["conditional_win_rate"], errors="coerce") * 100
            if "conditional_expected_return" in shown:
                shown["条件期望收益"] = pd.to_numeric(shown["conditional_expected_return"], errors="coerce") * 100
            if "credibility_grade" in shown:
                shown["可信度"] = shown["credibility_grade"].fillna("低")
            shown = shown.rename(columns={"symbol": "代码", "name": "名称", "close": "收盘价", **SCORE_NAMES, **ODDS_NAMES})
            preferred = ["排名", "排名变化", "代码", "名称", "综合评分", "可信度", "条件期望收益", "条件胜率"]
            st.dataframe(
                shown[[c for c in preferred if c in shown.columns]],
                width="stretch", hide_index=True,
                column_config={
                    "排名": st.column_config.NumberColumn("排名", format="%d"),
                    "综合评分": st.column_config.ProgressColumn("综合评分", min_value=0, max_value=100, format="%.1f",
                                                                 help="五个维度按实际权重加权后的横截面排序分，不是上涨概率"),
                    "条件期望收益": st.column_config.NumberColumn("条件期望收益", format="%.2f%%", help=TERM_HELP["conditional_expected_return"]),
                    "条件胜率": st.column_config.NumberColumn("条件胜率", format="%.1f%%", help=TERM_HELP["conditional_win_rate"]),
                },
            )

    with right:
        section_header("回测概览", "先看收益风险，再前往历史回测核验执行假设、简单基线和统计显著性。")
        if not backtest_metrics:
            st.info("还没有回测结果。到『历史回测』运行滚动回测。")
        else:
            m1, m2 = st.columns(2)
            m1.metric("累计收益", f'{backtest_metrics.get("cumulative_return", 0):.2%}', help=TERM_HELP["cumulative_return"])
            m1.metric("最大回撤", f'{backtest_metrics.get("max_drawdown", 0):.2%}',
                      help=TERM_HELP["max_drawdown"])
            m2.metric("夏普比率", f'{backtest_metrics.get("sharpe", 0):.2f}',
                      help=TERM_HELP["sharpe"])
            m2.metric("胜率", f'{backtest_metrics.get("win_rate", 0):.2%}',
                      help=TERM_HELP["win_rate"])
            if backtest_periods is not None:
                st.caption(f'生成于 {file_mtime(output_path("backtest_metrics.json"))} · {backtest_metrics.get("periods", 0)} 个调仓期')
                equity = backtest_periods.set_index("date")[["equity", "benchmark_equity"]].rename(
                    columns={"equity": "组合净值", "benchmark_equity": "基准净值"})
                cn_line_chart(equity, "净值", height=220)

# ==================== 页面：股票池与数据 ====================
elif st.session_state.research_view == "股票池与数据":
    page_header(
        "数据治理", "股票池与数据",
        "维护研究股票池、行情和元数据。数据状态决定评分与回测能否被正确解释，不代表实时交易信号。",
        f'本地行情覆盖 {summary["start"]} 至 {summary["end"]} · {summary["trading_days"]} 个交易日',
    )
    section_header("数据任务中心", "行情下载会同时尝试同步行业、市值和历史股票池快照；各子任务独立记录成功或失败。")

    metadata_audit, universe_audit = research_data_audits()
    health_cols = st.columns(4)
    health_cols[0].metric("当前行业覆盖", f'{metadata_audit.get("industry_coverage", 0):.1%}', help=TERM_HELP["industry_coverage"])
    health_cols[1].metric("当前市值覆盖", f'{metadata_audit.get("market_cap_coverage", 0):.1%}', help=TERM_HELP["market_cap_coverage"])
    health_cols[2].metric("股票池快照", f'{universe_audit.get("snapshot_count", 0)} 个', help=TERM_HELP["universe_snapshot"])
    health_cols[3].metric("数据治理", "可用" if metadata_audit.get("usable") and universe_audit.get("usable") else "未完备",
                          help=TERM_HELP["data_governance"])
    metadata_history = load_metadata_history(ARCHIVE_DIR)
    all_local_symbols = [path.stem for path in DATA_DIR.glob("*.parquet")]
    relevant_symbols = [symbol for symbol in all_local_symbols if security_type(symbol) == "A股个股"]
    current_metadata = latest_metadata_snapshot(metadata_history, relevant_symbols)
    excluded_types = pd.Series([security_type(symbol) for symbol in all_local_symbols]).value_counts()
    excluded_count = len(all_local_symbols) - len(relevant_symbols)
    st.markdown(
        f'模型证券范围：A股个股 {len(relevant_symbols)} 只 · 排除非个股 {excluded_count} 只'
        + (f'（{", ".join(f"{name} {count}" for name, count in excluded_types.items() if name != "A股个股")}）' if excluded_count else ""),
    )
    metadata_sync_path = ARCHIVE_DIR / "metadata_sync_status.json"
    sync_report = {}
    if metadata_sync_path.exists():
        try:
            sync_report = json.loads(metadata_sync_path.read_text(encoding="utf-8"))
            sync_label = {"usable": "可用", "partial": "部分可用", "empty": "不可用"}.get(
                sync_report.get("status"), "未知"
            )
            st.caption(
                f'最近同步状态：{sync_label} · 请求 {sync_report.get("requested_rows", 0)} 只 · '
                f'来源 {display_source(sync_report.get("source", "—"))}'
            )
        except (OSError, ValueError):
            pass
    if not current_metadata.empty:
        latest_metadata_date = pd.to_datetime(current_metadata["date"], errors="coerce").max()
        sources = ", ".join(sorted({display_source(value) for value in current_metadata.get("source", pd.Series(dtype=str)).dropna()})) or "—"
        st.caption(
            f'最近元数据快照 {latest_metadata_date:%Y-%m-%d} · 本地相关 {len(current_metadata):,} 只 · 来源 {sources}'
        )
        industry_missing = current_metadata.get("industry", pd.Series(index=current_metadata.index, dtype="object")).isna()
        cap_missing = ~pd.to_numeric(current_metadata.get("market_cap"), errors="coerce").gt(0)
        missing_metadata = current_metadata.loc[industry_missing | cap_missing, ["symbol", "industry", "market_cap", "source"]].copy()
        if not missing_metadata.empty:
            missing_metadata = with_names(missing_metadata)
            missing_metadata["缺失字段"] = [
                "、".join([
                    *( ["行业"] if pd.isna(row.get("industry")) else [] ),
                    *( ["市值"] if not pd.notna(row.get("market_cap")) or float(row.get("market_cap") or 0) <= 0 else [] ),
                ])
                for _, row in missing_metadata.iterrows()
            ]
            with st.expander(f"查看元数据缺失股票（{len(missing_metadata)} 只）"):
                missing_metadata["source"] = missing_metadata["source"].map(display_source)
                missing_metadata["market_cap_yi"] = pd.to_numeric(missing_metadata["market_cap"], errors="coerce") / 1e8
                st.dataframe(
                    fill_object_nulls(missing_metadata.drop(columns=["market_cap"])).rename(columns={
                        "symbol": "代码", "name": "名称", "industry": "行业",
                        "market_cap_yi": "总市值（亿元）", "source": "来源",
                    }), width="stretch", hide_index=True,
                    column_config={"总市值（亿元）": st.column_config.NumberColumn("总市值（亿元）", format="%.2f")},
                )
    if not metadata_audit.get("usable"):
        st.warning("行业或市值覆盖未达到可用门槛；相关风险约束会自动关闭，不会伪装成已生效。")
    historical_metadata = metadata_history_audit(
        metadata_history, summary.get("start"), summary.get("end")
    )
    if not historical_metadata.get("usable"):
        st.info(historical_metadata.get("reason", "历史元数据快照不足"))
    if not universe_audit.get("usable"):
        st.info(universe_audit.get("reason", "历史股票池覆盖不足"))

    data_end = pd.to_datetime(summary.get("end"), errors="coerce")
    lag_days = (pd.Timestamp(date.today()) - data_end).days if pd.notna(data_end) else None
    task_rows = [
        {"子任务": "日线行情", "状态": "可用" if summary.get("files", 0) and (lag_days is None or lag_days <= 4) else ("需更新" if summary.get("files", 0) else "未下载"),
         "覆盖/结果": f'{summary.get("files", 0)} 只 · {summary.get("start", "-")} 至 {summary.get("end", "-")}',
         "下一步": "无需处理" if summary.get("files", 0) and (lag_days is None or lag_days <= 4) else "执行增量下载"},
        {"子任务": "当前行业元数据", "状态": "可用" if metadata_audit.get("industry_usable") else "部分可用",
         "覆盖/结果": f'{metadata_audit.get("industry_coverage", 0):.1%}',
         "下一步": "无需处理" if metadata_audit.get("industry_usable") else "下载时重试同步"},
        {"子任务": "当前市值元数据", "状态": "可用" if metadata_audit.get("market_cap_usable") else "部分可用",
         "覆盖/结果": f'{metadata_audit.get("market_cap_coverage", 0):.1%}',
         "下一步": "无需处理" if metadata_audit.get("market_cap_usable") else "下载时重试同步"},
        {"子任务": "历史行业/市值快照", "状态": "可用" if historical_metadata.get("usable") else "积累中",
         "覆盖/结果": f'{historical_metadata.get("snapshot_count", 0)} 个 · {historical_metadata.get("snapshot_start", "-")} 至 {historical_metadata.get("snapshot_end", "-")}',
         "下一步": "无需处理" if historical_metadata.get("usable") else "仅可前瞻积累，不应用当前值回填历史"},
        {"子任务": "历史股票池快照", "状态": "可用" if universe_audit.get("usable") else "积累中",
         "覆盖/结果": f'{universe_audit.get("snapshot_count", 0)} 个 · {universe_audit.get("snapshot_start", "-")} 至 {universe_audit.get("snapshot_end", "-")}',
         "下一步": "无需处理" if universe_audit.get("usable") else "随每次下载自动归档"},
    ]
    st.dataframe(pd.DataFrame(task_rows), width="stretch", hide_index=True,
                 column_config={"状态": st.column_config.TextColumn(width="small"),
                                "覆盖/结果": st.column_config.TextColumn(width="large"),
                                "下一步": st.column_config.TextColumn(width="medium")})
    if sync_report.get("status") in {"partial", "empty"}:
        st.warning("最近一次行情任务已完成，但元数据同步未完全成功。现有有效元数据已保留，可在下次下载时仅重试缺失部分。")
    if any(row["状态"] not in {"可用"} for row in task_rows):
        st.markdown("[前往下载与更新](#下载与更新)")

    st.divider()
    # ---- 检索添加 ----
    section_header("维护股票池", "支持股票代码、中文名称或拼音首字母检索，例如 300476 / 胜宏科技 / SHKJ。")
    catalog = universe()
    if catalog.empty:
        st.warning("股票目录不可用，请点击『更新目录』重试。")
    else:
        labels = catalog.set_index("symbol")["search_label"].to_dict()
        selected_symbols = st.multiselect(
            "选择股票",
            options=catalog["symbol"].tolist(),
            format_func=lambda s: labels.get(s, s),
            placeholder="例如：300476 / 胜宏科技 / SHKJ",
            filter_mode="contains",
            max_selections=500,
            key="pool_selected_symbols",
        )
        add_col, refresh_col = st.columns([4, 1])
        with add_col:
            if st.button("加入股票池", type="primary", icon=":material/add:", width="stretch",
                         disabled=not selected_symbols):
                imported = catalog[catalog["symbol"].isin(selected_symbols)][["symbol", "name"]]
                updated = add_to_pool(POOL_PATH, imported, source="检索多选导入")
                st.success(f"已加入 {len(imported)} 只，股票池共 {len(updated)} 只。")
        with refresh_col:
            if st.button("更新目录", icon=":material/refresh:", width="stretch",
                         help="重新获取最新股票代码与名称，不下载行情。"):
                try:
                    refreshed = load_stock_universe(UNIVERSE_PATH, refresh=True)
                    cached_universe.clear()
                    st.success(f"目录已更新，共 {len(refreshed):,} 只。")
                except Exception as error:
                    st.error(f"更新失败：{error}")

    st.divider()

    # ---- 下载与更新 ----
    st.subheader("下载与更新")
    pool = load_pool(POOL_PATH)
    with st.form("download_form", border=True):
        update_mode = st.radio(
            "更新方式",
            ["增量更新到最新（推荐）", "按日期范围完整重下"],
            key="dl_update_mode",
            horizontal=True,
            help=(
                "**增量更新到最新（推荐）：**日常收盘后用。自动读取每只股票本地数据的最后日期，只补缺失的尾部，无需选择开始日期。\n\n"
                "- 本地没有数据的股票会自动按完整区间下载\n"
                "- 停牌/未上市等取不到增量的保留旧数据并如实报告\n\n"
                "**按日期范围完整重下：**换复权方式、换数据源或数据损坏时用，整段重新下载并覆盖。"
            ),
        )
        incremental = update_mode.startswith("增量")
        start_date: date | None = None
        if incremental:
            end_date = st.date_input(
                "更新至", value=date.today(), max_value=date.today(), key="dl_end",
                help="默认今天；收盘后数据约当晚更新。")
        else:
            last_start = load_download_config().get("last_start", "2018-01-01")
            d1, d2 = st.columns(2)
            with d1:
                start_date = st.date_input(
                    "开始日期", value=pd.to_datetime(last_start).date(), max_value=date.today(), key="dl_start",
                    help=("**推荐 3~5 年以上。**不同用途的最低要求：\n\n"
                          "- 因子预热：动量因子需要 120 个交易日（约半年）历史，不足时早期数据会被剔除\n"
                          "- 综合评分：至少 100 个交易日\n"
                          "- 滚动回测：建议 4 年以上，才能形成约 80 个调仓期，结论更稳\n\n"
                          "数据越多下载越慢（87 只 × 8 年约数分钟），可先短后长分批扩充。默认记忆上次使用的开始日期。"))
            with d2:
                end_date = st.date_input(
                    "结束日期", value=date.today(), max_value=date.today(), key="dl_end",
                    help="默认今天。留作过去日期可做固定区间的可复现研究。")

        source_mode = st.radio(
            "下载范围",
            ["本地股票池", "检索并选择股票", "当前成交额前N只"],
            key="dl_source_mode",
            horizontal=True,
            help=(
                "**本地股票池**：下载自选股票池中的全部股票，适合日常更新已有池子。\n\n"
                "**检索并选择股票**：临时挑选股票下载（代码/名称/拼音检索），不会加入股票池，适合补充个别数据。\n\n"
                "**当前成交额前N只**：拉取全市场实时行情，按当前成交额从高到低取前 N 只下载，适合快速获取一批活跃股票验证流程。"
            ),
        )
        st.caption({
            "本地股票池": "将按上方日期区间下载股票池中的全部股票。",
            "检索并选择股票": "在下方选择股票后开始下载；这些股票不会加入股票池。",
            "当前成交额前N只": "N 在下方设置（10 至 500，默认 100）：按当前成交额从高到低取前 N 只下载。首次会拉取全市场行情，约需 30 至 60 秒。",
        }[source_mode])
        dl_symbols: list[str] = []
        top_n = None
        if source_mode == "当前成交额前N只":
            top_n = st.number_input(
                "股票数量 N", min_value=10, max_value=500, value=100, step=10, key="dl_top_n",
                help="按当前成交额排名取前 N 只。N 越大覆盖越广但下载越慢；100 只约需数分钟。")
        elif source_mode == "检索并选择股票":
            if not catalog.empty:
                dl_symbols = st.multiselect(
                    "股票检索",
                    options=catalog["symbol"].tolist(),
                    format_func=lambda s: labels.get(s, s),
                    placeholder="例如：300476 / 胜宏科技 / SHKJ",
                    filter_mode="contains",
                    max_selections=100,
                    key="dl_selected_symbols",
                )
        submitted = st.form_submit_button("开始下载", type="primary", icon=":material/download:", width="stretch")

    def run_download(symbols: list[str], start, end, incremental: bool = False):
        st.session_state.download_report = None
        dl_names = name_map()

        def dl_label(symbol: str) -> str:
            return f"{symbol} {dl_names.get(str(symbol), '')}".strip()

        mode_text = "增量更新" if incremental else f"完整下载（{start} 起）"
        with st.status(f"正在{mode_text} {len(symbols)} 只股票…", expanded=True) as status:
            bar = st.progress(0.0, text="准备下载…")
            log = st.empty()

            def on_progress(index: int, total: int, symbol: str, state: str):
                label = dl_label(symbol)
                bar.progress(index / total, text=f"[{index}/{total}] {label} {state}")
                log.write(f"[{index}/{total}] {label} {state}")

            if incremental:
                report = update_histories(
                    symbols, f"{end:%Y%m%d}", DATA_DIR,
                    full_start=f"{start:%Y%m%d}" if start else "20180101", progress=on_progress)
            else:
                report = download_histories(
                    symbols, f"{start:%Y%m%d}", f"{end:%Y%m%d}", DATA_DIR, progress=on_progress)
                save_download_config({"last_start": str(start)})
            ok = sum(1 for r in report if r["ok"])
            status.update(label=f"{'更新' if incremental else '下载'}完成：成功 {ok} / {len(report)}",
                          state="complete" if ok else "error")
        st.session_state.download_report = report
        st.session_state.download_params = {"start": start, "end": end, "incremental": incremental}
        cached_data_summary.clear()
        cached_panel.clear()
        current_universe = universe()
        if not current_universe.empty:
            archive_universe_snapshot(current_universe, ARCHIVE_DIR, date.today())
        # Keep market data and the point-in-time metadata snapshot in the same
        # daily update workflow; failures here do not invalidate price data.
        with st.spinner("同步行业与市值元数据…"):
            metadata, metadata_report = fetch_current_metadata(date.today(), symbols=symbols)
        (ARCHIVE_DIR / "metadata_sync_status.json").write_text(
            json.dumps(metadata_report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if metadata_report.get("ok") and not metadata.empty:
            archive_metadata(metadata, ARCHIVE_DIR, date.today())
            st.success(
                f'元数据已归档：行业覆盖 {metadata_report.get("industry_coverage", 0):.1%} · '
                f'市值覆盖 {metadata_report.get("market_cap_coverage", 0):.1%}'
            )
        else:
            # Metadata is an optional enhancement; never present an otherwise
            # successful price update as failed because an external API is down.
            st.warning(
                "行情已完成；行业与市值本次不可用，未将仅含代码的空覆盖结果视为成功。"
                f' 原因：{metadata_report.get("error", "外部接口不可用")}'
            )

    if submitted:
        try:
            if source_mode == "本地股票池":
                symbols = pool["symbol"].astype(str).tolist()
                if not symbols:
                    st.error("股票池为空，请先检索添加股票。")
                else:
                    run_download(symbols, start_date, end_date, incremental)
            elif source_mode == "当前成交额前N只":
                symbols = get_symbols(None, int(top_n))
                run_download(symbols, start_date, end_date, incremental)
            elif dl_symbols:
                run_download(dl_symbols, start_date, end_date, incremental)
            else:
                st.error("请先选择要下载的股票。")
        except Exception as error:
            st.error(f"下载失败：{error}")

    report = st.session_state.get("download_report")
    if report:
        report_frame = with_names(pd.DataFrame(report))
        successful = report_frame["ok"].fillna(False).astype(bool)
        no_new_rows = pd.to_numeric(report_frame.get("rows"), errors="coerce").fillna(0).eq(0)
        source_blank = report_frame.get("source", pd.Series(index=report_frame.index, dtype="object")).fillna("").astype(str).str.strip().isin(["", "-"])
        report_frame.loc[successful & no_new_rows & source_blank, "source"] = "本地数据"
        error_blank = report_frame.get("error", pd.Series(index=report_frame.index, dtype="object")).fillna("").astype(str).str.strip().eq("")
        report_frame.loc[successful & error_blank, "error"] = "无"
        report_frame["source"] = report_frame.get("source", "").map(display_source)
        report_frame["status"] = "失败"
        report_frame.loc[successful & no_new_rows, "status"] = "无需更新"
        report_frame.loc[successful & ~no_new_rows, "status"] = "已更新"
        report_frame = fill_object_nulls(report_frame)
        failed = report_frame[~report_frame["ok"]]
        report_columns = ["symbol", "name", "status", "ok", "rows", "start", "end", "source", "note"]
        if not failed.empty:
            report_columns.append("error")
        st.dataframe(
            report_frame[[column for column in report_columns if column in report_frame.columns]].rename(columns={
                "symbol": "代码", "name": "名称", "ok": "成功", "rows": "行数（增量模式下为新增）",
                "status": "状态", "start": "数据开始", "end": "数据结束", "source": "数据来源", "note": "说明", "error": "错误"}),
            width="stretch", hide_index=True, height=240,
            column_config={"状态": st.column_config.TextColumn("状态", width="small")},
        )
        if not failed.empty:
            st.warning(f'{len(failed)} 只下载失败。')
            if st.button(f"重试失败的 {len(failed)} 只", icon=":material/refresh:"):
                params = st.session_state.get("download_params", {})
                retry_start = params.get("start") or date(2018, 1, 1)
                run_download(failed["symbol"].astype(str).tolist(), retry_start,
                             params.get("end", end_date), params.get("incremental", False))

    st.divider()

    # ---- 我的股票池 ----
    local_symbols = {path.stem for path in DATA_DIR.glob("*.parquet")}
    pool_symbols = set(pool["symbol"].astype(str)) if not pool.empty else set()
    archived_local_count = len(local_symbols - pool_symbols)
    st.subheader(f"自选维护池（{len(pool)} 只）")
    if archived_local_count:
        st.caption(
            f"另有 {archived_local_count} 只本地归档行情未纳入维护池；"
            "它们仍计入研究样本范围。移除股票池默认不会删除本地行情。"
        )
    hk_count = int(pool["symbol"].astype(str).str.upper().str.startswith("HK").sum()) if not pool.empty else 0
    if hk_count:
        st.caption(f"池中有 {hk_count} 只港股代码：仅作自选清单保留，下载与评分只覆盖 A 股，港股会被跳过并如实报告。")
    if pool.empty:
        st.info("股票池为空。请在上方检索并添加需要长期维护行情的股票。综合评分候选不会自动改变研究股票池。")
    else:
        try:
            panel = cached_panel(data_signature())
            snapshot = market_snapshot(panel, scores=load_scores(), universe=universe())
            snapshot["symbol"] = snapshot["symbol"].astype(str).str.zfill(6)
            # 名称优先用股票池自带的，快照里的名称仅在池内缺失时兜底
            pool_side = pool[["symbol", "name", "added_at"]].rename(columns={"name": "pool_name"})
            pool_side["symbol"] = pool_side["symbol"].astype(str).str.zfill(6)
            overview = pool_side.merge(
                snapshot.drop(columns=["initials"], errors="ignore"), on="symbol", how="left")
            overview["name"] = overview["pool_name"].where(
                overview["pool_name"].astype(str).str.strip().ne(""), overview["name"].fillna(""))
            overview = overview.drop(columns=["pool_name"])
            # 数据新鲜度：与全池最新日期的差距
            overview["滞后天数"] = (pd.to_datetime(snapshot["date"]).max() - pd.to_datetime(overview["date"])).dt.days
            overview["数据日期"] = pd.to_datetime(overview["date"]).dt.strftime("%Y-%m-%d")
            overview["涨幅%"] = pd.to_numeric(overview.get("pct_change"), errors="coerce") * 100
            overview["turnover"] = pd.to_numeric(overview.get("turnover"), errors="coerce") * 100
            if "amount" in overview.columns:
                overview["成交额"] = overview["amount"].map(format_amount)
            else:
                overview["成交额"] = "-"
            overview["胜率%"] = pd.to_numeric(overview.get("odds_win_rate"), errors="coerce") * 100
            overview = overview.rename(columns={
                "symbol": "代码", "name": "名称", "close": "最新价", "turnover": "换手率%",
                "volume_ratio": "量比", "composite_score": "综合评分", "history_rows": "行情行数",
                "added_at": "加入时间"})
            columns = ["代码", "名称", "最新价", "涨幅%", "综合评分", "换手率%", "量比", "胜率%", "成交额", "数据日期", "滞后天数", "行情行数", "加入时间"]
            st.dataframe(
                overview[[c for c in columns if c in overview.columns]],
                width="stretch", hide_index=True,
                column_config={
                    "综合评分": st.column_config.ProgressColumn("综合评分", min_value=0, max_value=100, format="%.1f",
                                                               help="五个维度按可调权重加权后的总分（0~100）：模型/技术面/量价/K线/舆情"),
                    "涨幅%": st.column_config.NumberColumn("涨幅%", format="%.2f%%", help="最新交易日涨跌幅"),
                    "换手率%": st.column_config.NumberColumn("换手率%", format="%.2f%%", help="当日成交量占流通盘的比例，越高越活跃"),
                    "量比": st.column_config.NumberColumn("量比", format="%.2f", help="当日成交量与近 20 日平均之比，大于 1 表示放量"),
                    "胜率%": st.column_config.NumberColumn("胜率%", format="%.1f%%", help="按当前预测周期，该股票历史上持有到期收益为正的比例"),
                    "滞后天数": st.column_config.NumberColumn("滞后天数", format="%d",
                                                              help="该股票最新数据日期与全池最新日期的差距；大于 5 天说明数据滞后，建议增量更新或核查是否停牌"),
                })
        except FileNotFoundError:
            st.info("本地还没有行情数据，请先在上方下载。")

        # 个股走势
        with st.expander("个股走势"):
            detail_symbols = pool["symbol"].astype(str).tolist()
            trend_labels = pool.set_index("symbol")["name"].fillna("").to_dict()
            detail_symbol = st.selectbox("选择股票", detail_symbols,
                                         format_func=lambda s: f"{s}  {trend_labels.get(s, '')}".strip(),
                                         key="pool_detail_symbol")
            try:
                panel = cached_panel(data_signature())
                history = panel[panel["symbol"].astype(str).str.zfill(6) == detail_symbol].sort_values("date").tail(120)
                if history.empty:
                    st.caption("该股票暂无本地行情。")
                else:
                    cn_line_chart(history.set_index("date")["close"].rename("收盘价"), "收盘价")
            except FileNotFoundError:
                st.caption("本地还没有行情数据。")

        # 移除（弹层内一步确认）
        with st.popover("移除股票", icon=":material/delete:", width="stretch"):
            pool_names = pool.set_index("symbol")["name"].fillna("").to_dict()
            remove_symbols = st.multiselect(
                "选择要移除的股票",
                options=pool["symbol"].astype(str).tolist(),
                format_func=lambda s: f"{s}  {pool_names.get(s, '')}",
                key="remove_pool_symbols",
            )
            remove_data = st.checkbox("同步删除本地行情与评分记录", key="remove_pool_data")
            if st.button("确认移除", type="primary", disabled=not remove_symbols, key="remove_pool_button"):
                selected = set(remove_symbols)
                remaining = pool[~pool["symbol"].astype(str).isin(selected)]
                remaining.to_csv(POOL_PATH, index=False, encoding="utf-8-sig")
                removed_files = 0
                if remove_data:
                    for symbol in selected:
                        target = DATA_DIR / f"{symbol}.parquet"
                        if target.exists():
                            target.unlink()
                            removed_files += 1
                    for name in ["latest_scores.csv", "latest_picks.csv"]:
                        target = OUTPUT_DIR / name
                        if target.exists():
                            frame = pd.read_csv(target, dtype={"symbol": str})
                            frame = frame[~frame["symbol"].astype(str).isin(selected)]
                            frame.to_csv(target, index=False, encoding="utf-8-sig")
                    cached_data_summary.clear()
                    cached_panel.clear()
                st.success(f"已移除 {len(selected)} 只股票" + (f"，删除行情文件 {removed_files} 个。" if remove_data else "。"))
                st.rerun()

    # 数据质量
    with st.expander("数据质量诊断"):
        repair_result = st.session_state.pop("repair_result", None)
        if repair_result is not None:
            failed = repair_result["failed"]
            still = repair_result["still_repair"]
            names = name_map()

            def label(symbol: str) -> str:
                return f"{symbol} {names.get(symbol, '')}".strip()

            if not failed and not still:
                st.success("一键修复完成，重新下载成功且数据已全部恢复正常。")
            else:
                if failed:
                    st.warning(f'有 {len(failed)} 只重新下载失败，本地数据未更新：{"、".join(label(s) for s in failed)}')
                if still:
                    st.warning(f'重新下载后仍有 {len(still)} 只数据需修复：{"、".join(label(s) for s in still)}。'
                               "可能是数据源缺少字段（如腾讯接口无换手率列）或持续返回异常值，建议移出股票池或换数据源。")
        try:
            panel = cached_panel(data_signature())
            quality_report, quality_summary = audit_market_data(panel)
            q_names = name_map()

            def q_label(symbol: str) -> str:
                return f"{symbol} {q_names.get(str(symbol), '')}".strip()

            def q_list(mask, limit: int = 20) -> str:
                symbols = quality_report.loc[mask, "symbol"].astype(str).tolist()
                if not symbols:
                    return "无"
                shown = "、".join(q_label(s) for s in symbols[:limit])
                return shown + (f" 等 {len(symbols)} 只" if len(symbols) > limit else "")

            repair_mask = quality_report["status"] == "需修复"
            review_mask = quality_report["status"] == "需核查"
            missing_mask = quality_report["missing_required"] > 0
            q1, q2, q3 = st.columns(3)
            q1.metric("需修复", quality_summary["repair_count"],
                      help="字段缺失、日期重复或价格非法，通常重新下载即可解决。\n\n**涉及股票：**" + q_list(repair_mask))
            q2.metric("需核查", quality_summary["review_count"],
                      help="单日涨跌幅超±25%或数据滞后超5天，需人工判断是否真实行情。\n\n**涉及股票：**" + q_list(review_mask))
            q3.metric("缺失值", quality_summary["missing_values"],
                      help="必要字段（开高低收/成交量额/换手率）中的空值总数。\n\n**涉及股票：**" + q_list(missing_mask))
            st.dataframe(
                with_names(quality_report).rename(columns={
                    "symbol": "代码", "name": "名称", "rows": "行数", "start": "开始", "end": "结束",
                    "latest_lag_days": "滞后天数", "status": "状态"}), width="stretch", hide_index=True, height=260)
            repair_symbols = quality_report[quality_report["status"] == "需修复"]["symbol"].astype(str).tolist()
            if repair_symbols:
                st.caption(f'共 {len(repair_symbols)} 只股票状态为「需修复」，重新下载通常可以解决。')
                if st.button(f"一键修复：重新下载 {len(repair_symbols)} 只", type="primary", icon=":material/build:"):
                    repair_start = start_date or pd.to_datetime(load_download_config().get("last_start", "2018-01-01")).date()
                    run_download(repair_symbols, repair_start, end_date)
                    download_report = st.session_state.get("download_report") or []
                    failed_symbols = [str(r["symbol"]) for r in download_report if not r["ok"]]
                    fresh_report, _ = audit_market_data(cached_panel(data_signature()))
                    still_repair = fresh_report[fresh_report["status"] == "需修复"]["symbol"].astype(str).tolist()
                    st.session_state.repair_result = {"failed": failed_symbols, "still_repair": still_repair}
                    st.rerun()
        except FileNotFoundError:
            st.info("本地还没有行情数据。")

# ==================== 页面：综合评分 ====================
elif st.session_state.research_view == "综合评分":
    picks = load_picks()
    page_header(
        "选股研究", "综合评分",
        "对最新交易日逐只生成可解释排序。调整权重只会改变排序规则，需要使用相同配置重新回测验证。",
        f'行情截至 {summary["end"]} · 最近评分 {file_mtime(output_path("latest_picks.csv"))}',
    )
    score_universe = research_universe_status()
    _, score_sentiment_audit = historical_sentiment_data(summary.get("start"), summary.get("end"))
    if not score_universe["broad"]:
        st.warning(
            f'当前本地仅有 {score_universe["count"]} 只可识别A股，属于“{score_universe["level"]}”。'
            "当前候选只代表该有限集合内的相对排序，不代表全A股市场。"
        )
    run_ready = summary["trading_days"] >= 100
    if not run_ready:
        st.warning(f'当前本地数据 {summary["trading_days"]} 个交易日，综合评分至少需要 100 天。请到『股票池与数据』下载更长的历史数据。')

    legacy_presets = {"默认": "标准综合", "模型增强": "模型信号优先", "多维均衡": "技术确认均衡"}
    if st.session_state.get("score_preset") in legacy_presets:
        st.session_state.score_preset = legacy_presets[st.session_state.score_preset]
    if "score_preset" not in st.session_state:
        st.session_state.score_preset = "标准综合"
    if all(_weight_key("score", factor) not in st.session_state for factor, _ in WEIGHT_LABELS):
        set_weight_values("score", SCORE_PRESETS.get(st.session_state.score_preset, SCORE_PRESETS["标准综合"])["weights"])

    section_header("评分配置", "选择预设或修改权重，然后运行评分。预设不是准确率承诺，仅代表不同的研究假设。")
    render_linkage_status(research_linkage_status())
    score_preset = st.selectbox(
        "评分权重预设", [*SCORE_PRESETS, "自定义"], key="score_preset", on_change=apply_score_preset,
        help="预设只决定五个评分维度的相对权重，不代表已通过历史验证。手动修改任一权重后会自动标记为“自定义”。",
    )
    if score_preset in SCORE_PRESETS:
        preset = SCORE_PRESETS[score_preset]
        weights_text = " / ".join(f"{label}{preset['weights'][factor]:.0%}" for factor, label in WEIGHT_LABELS)
        st.caption(f"**{score_preset}：**{preset['description']} 当前权重：{weights_text}")
    else:
        st.caption("**自定义：**按研究假设手动调整权重。它只改变排序规则，需以相同权重重新回测检验。")

    with st.form("score_form", border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            horizon = st.slider("预测周期（交易日）", 5, 60, 20, 5, key="score_horizon")
        with c2:
            top_k = st.slider("候选数量", 5, 50, 10, 5, key="score_top_k")
        with c3:
            st.metric("当前权重模式", score_preset)
        st.caption("评分权重 · 合计需为 100%")
        weights = weight_inputs("score")
        score_total = weight_total("score")
        st.info(
            f"配置摘要：{score_preset} · 预测 {horizon} 个交易日 · 候选 {top_k} 只 · "
            + " / ".join(f"{label}{weights[key]:.0%}" for key, label in WEIGHT_LABELS)
        )
        with st.expander("高级参数"):
            fetch_sentiment = st.checkbox(
                "抓取最新舆情", value=True, key="fetch_sentiment",
                help=("**数据来源：**东方财富个股新闻接口，取评分日之前 30 天内的新闻标题。\n\n"
                      "**评价方式：**可审计的关键词词典计数。舆情分 = 50 + 18 ×（正面词次数 − 负面词次数），截断在 0~100。\n\n"
                      "- 正面词：增长、增持、回购、中标、订单、盈利、预增、突破、创新高、利好、上涨、扩产\n"
                      "- 负面词：减持、亏损、预亏、暴跌、下滑、处罚、问询、诉讼、风险、利空、退市、违规\n\n"
                      "无新闻、关键词未命中或接口失败时一律按 50 分中性处理，并在结果中如实标注来源，不伪造覆盖率。"))
            if fetch_sentiment and weights.get("sentiment", 0) > 0 and not score_sentiment_audit.get("usable"):
                st.warning("当前历史舆情不足：本次实时舆情会参与候选排序，但该维度无法被现有历史回测完整验证。关闭抓取后可按中性舆情口径验证其余维度。")
            show_market_mood = st.checkbox(
                "叠加市场情绪面", value=True, key="show_market_mood",
                help=("用本地行情合成大盘情绪，不改变当日个股排序。用于观察市场宽度、量能和涨停占比。"))
        run_score = st.form_submit_button(
            "运行综合评分", type="primary", icon=":material/analytics:", width="stretch",
            disabled=not run_ready or score_total != 100, on_click=sync_score_preset_from_weights,
        )

    if run_score:
        prev_picks = load_picks()
        prev_time = file_mtime(output_path("latest_picks.csv"))
        try:
            with st.status("正在运行综合评分…", expanded=True) as score_status:
                stage_text = st.empty()
                sent_bar = st.progress(0.0, text="等待舆情抓取阶段")
                sent_log = st.empty()

                def on_stage(message: str):
                    stage_text.write(message)

                def on_sentiment(index: int, total: int, symbol: str):
                    sent_bar.progress(index / total, text=f"抓取舆情 {index}/{total}")
                    sent_log.write(f"[{index}/{total}] {symbol}")

                stage_text.write("阶段 1/4：构建因子…")
                run_id = new_run_id("score")
                panel = cached_panel(data_signature())
                panel, metadata_audit, universe_audit = governed_research_panel(panel)
                frame, features = build_features(panel, horizon=horizon)
                picks, metrics, _ = run_latest_research(
                    frame, features, top_k, horizon, OUTPUT_DIR, weights, fetch_sentiment,
                    progress=on_stage, sentiment_progress=on_sentiment)
                config = {
                    "horizon": int(horizon), "top_k": int(top_k), "weights": weights,
                    "weight_mode": st.session_state.get("score_preset", "自定义"),
                    "fetch_sentiment": bool(fetch_sentiment),
                    "sentiment_mode": "latest_news" if fetch_sentiment else "neutral",
                    "feature_version": FEATURE_VERSION, "model_version": MODEL_VERSION,
                    "universe_count": int(panel["symbol"].nunique()),
                }
                metrics.update({"schema_version": 2, "run_id": run_id, "config": config})
                output_path("validation_metrics.json").write_text(
                    json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                all_scores = load_scores()
                if all_scores is not None:
                    all_scores["run_id"] = run_id
                    all_scores.to_csv(output_path("latest_scores.csv"), index=False, encoding="utf-8-sig")
                picks["run_id"] = run_id
                picks.to_csv(output_path("latest_picks.csv"), index=False, encoding="utf-8-sig")
                status_result = assess_research_status(
                    load_backtest()[1], metrics, metadata_audit, universe_audit
                )
                save_research_status(status_result)
                write_run_manifest(OUTPUT_DIR, {
                    "run_id": run_id, "kind": "score", "config": config,
                    "data_end": str(pd.Timestamp(panel["date"].max()).date()),
                    "data_fingerprint": data_fingerprint(list(DATA_DIR.glob("*.parquet"))),
                    "governance_fingerprint": governance_fingerprint(),
                    "candidate_snapshot": picks[[column for column in ["symbol", "name", "composite_score", "credibility_grade"] if column in picks]].to_dict("records"),
                    "metadata_audit": metadata_audit, "universe_audit": universe_audit,
                    "validation_status": status_result,
                })
                archive_run_artifacts(run_id, [
                    "latest_scores.csv", "latest_picks.csv", "validation_metrics.json",
                    "score_diagnostics.json", "feature_importance.csv",
                ])
                score_status.update(label="评分完成", state="complete")
            st.success(f"评分完成：{len(picks)} 只研究观察标的（结果见下方）。快照已存档：{archive_scoring_run()}")

            # 与上次结果对比：新进入 / 跌出候选
            new_picks = load_picks()
            if prev_picks is not None and not prev_picks.empty and new_picks is not None and not new_picks.empty:
                entered = sorted(set(new_picks["symbol"]) - set(prev_picks["symbol"]))
                exited = sorted(set(prev_picks["symbol"]) - set(new_picks["symbol"]))
                st.session_state.score_diff = (
                    {"entered": entered, "exited": exited, "prev_time": prev_time} if entered or exited else None
                )
        except Exception as error:
            show_operation_error("综合评分", error)

    picks = load_picks()
    if picks is None:
        st.info("尚无评分结果。设置好参数后点击『运行综合评分』。")
    else:
        saved_score_config = load_manifest(OUTPUT_DIR, "score").get("config", {})
        params_text = (
            f'生成于 {file_mtime(output_path("latest_picks.csv"))} · 数据日期 {str(picks["date"].iloc[0])[:10] if len(picks) else "-"} · '
            f'周期 {saved_score_config.get("horizon", "待重跑记录")} 日 · '
            f'Top {saved_score_config.get("top_k", len(picks))}'
        )
        st.caption(params_text)

        # 与上次评分结果的对比（权重调整研究闭环）
        diff = st.session_state.get("score_diff")
        if diff:
            diff_names = name_map()

            def diff_label(symbol: str) -> str:
                return f"{symbol} {diff_names.get(symbol, '')}".strip()

            diff_in, diff_out = st.columns(2)
            with diff_in:
                if diff["entered"]:
                    shown = "、".join(diff_label(s) for s in diff["entered"][:15])
                    if len(diff["entered"]) > 15:
                        shown += f" 等 {len(diff['entered'])} 只"
                    st.info(f"新进入观察名单（{len(diff['entered'])} 只）：{shown}")
            with diff_out:
                if diff["exited"]:
                    shown = "、".join(diff_label(s) for s in diff["exited"][:15])
                    if len(diff["exited"]) > 15:
                        shown += f" 等 {len(diff['exited'])} 只"
                    st.caption(f"移出观察名单（{len(diff['exited'])} 只）：{shown}")
            st.caption(f"与上次评分结果（{diff['prev_time']}）对比；调整权重/周期后重跑可刷新对比。")

        # 市场情绪面（叠加在个股名单之上的环境判断，不改变排序）
        if st.session_state.get("show_market_mood", True):
            try:
                mood = market_sentiment(cached_panel(data_signature()))
                archive_market_sentiment(mood)
                with st.expander("市场环境", expanded=False):
                    mood_cols = st.columns(4)
                    mood_cols[0].metric(
                        "市场情绪分", f'{mood["score"]:.0f}',
                        help="上涨家数占比、量能、涨停占比三项各映射为 0~100 后取平均；50 为中性，低于 40 偏弱，高于 60 偏强")
                    mood_cols[1].metric(
                        "上涨家数占比", f'{mood["breadth"]:.0%}',
                        help="本地股票最新交易日上涨的比例（市场宽度），高于 55% 视为普涨环境")
                    mood_cols[2].metric(
                        "量能（对20日均量）", f'{mood["volume_ratio"]:.2f}',
                        help="最新成交量相对近 20 日平均的放大倍数，大于 1 表示放量，0.8 以下明显缩量")
                    mood_cols[3].metric(
                        "涨停家数占比",
                        f'{int(mood.get("limit_up_count", 0))} / {int(mood.get("limit_up_denominator", mood.get("stocks", 0)))} '
                        f'（{mood["limit_up_ratio"]:.2%}）',
                        help="仅统计 A 股个股；主板涨幅≥9.8%，创业板/科创板涨幅≥19.8%。ETF、基金和可转债不纳入分母。"
                    )
                    if mood["score"] < 40:
                        st.warning(f'当前市场情绪偏弱（{mood["score"]:.0f} 分）：弱势环境下候选名单的历史胜率通常下降，建议谨慎对待或降低预期。')
                    elif mood["score"] >= 60:
                        st.info(f'当前市场情绪偏强（{mood["score"]:.0f} 分）：环境对候选名单相对友好。')
                    st.caption(f'数据日期 {mood["date"]} · 基于 {mood["stocks"]} 只本地股票 · 每次评分自动存档到 data/archive/')
            except FileNotFoundError:
                pass

        picks = add_candidate_context(picks_with_names(picks))
        shown = picks.rename(columns={
            "date": "数据日期", "symbol": "代码", "name": "名称", "close": "收盘价", **SCORE_NAMES, **ODDS_NAMES})
        if "conditional_win_rate" in shown:
            shown["条件胜率"] = pd.to_numeric(shown["conditional_win_rate"], errors="coerce") * 100
        if "conditional_expected_return" in shown:
            shown["条件期望收益"] = pd.to_numeric(shown["conditional_expected_return"], errors="coerce") * 100
        shown = shown.rename(columns={
            "conditional_sample_count": "条件样本数", "credibility_grade": "可信度",
            "credibility_score": "可信度分",
        })
        if "历史胜率" in shown:
            shown["历史胜率"] = pd.to_numeric(shown["历史胜率"], errors="coerce") * 100
        if "期望收益" in shown:
            shown["期望收益"] = pd.to_numeric(shown["期望收益"], errors="coerce") * 100
        section_header("研究观察名单", "按决策、证据或因子切换视图。综合评分用于排序，可信度用于识别证据质量。")
        table_view = st.segmented_control(
            "结果视图", ["决策", "证据", "因子"], default="决策",
            key="candidate_table_view", label_visibility="collapsed",
        )
        view_columns = {
            "决策": ["排名", "排名变化", "代码", "名称", "综合评分", "可信度", "可信度分"],
            "证据": ["排名", "代码", "名称", "条件期望收益", "条件胜率", "条件样本数",
                     "赔率（收益/风险）", "历史胜率", "期望收益"],
            "因子": ["排名", "代码", "名称", "综合评分", "模型评分", "技术面", "量价关系", "K线走势", "舆情评分"],
        }
        preferred = view_columns.get(table_view or "决策", view_columns["决策"])
        st.dataframe(
            shown[[c for c in preferred if c in shown.columns]],
            width="stretch", hide_index=True,
            height=min(420, 38 + len(shown) * 35),
            column_config={
                "排名": st.column_config.NumberColumn("排名", format="%d"),
                "综合评分": st.column_config.ProgressColumn("综合评分", min_value=0, max_value=100, format="%.1f",
                                                           help="五个维度按实际权重加权后的横截面排序分（0~100），不是上涨概率"),
                "模型评分": st.column_config.NumberColumn("模型评分", format="%.1f",
                                                          help="模型预测未来收益的当日截面百分位（0~100），越高表示模型越看好"),
                "技术面": st.column_config.NumberColumn("技术面", format="%.1f",
                                                        help="动量、均线乖离、波动率的组合百分位（0~100）"),
                "量价关系": st.column_config.NumberColumn("量价关系", format="%.1f",
                                                          help="量能趋势、量比、资金流向的组合百分位（0~100）"),
                "K线走势": st.column_config.NumberColumn("K线走势", format="%.1f",
                                                         help="K 线形态（收盘位置、实体、影线）的百分位（0~100）"),
                "舆情评分": st.column_config.NumberColumn("舆情评分", format="%.1f",
                                                           help="新闻标题关键词词典打分（0~100），50 为中性"),
                "赔率（收益/风险）": st.column_config.NumberColumn("赔率（收益/风险）", format="%.2f",
                                                                   help=TERM_HELP["reward_risk"]),
                "可信度分": st.column_config.ProgressColumn("可信度分", min_value=0, max_value=100, format="%.1f",
                                                            help=TERM_HELP["credibility"]),
                "条件胜率": st.column_config.NumberColumn("条件胜率", format="%.2f%%",
                                                          help=TERM_HELP["conditional_win_rate"]),
                "条件期望收益": st.column_config.NumberColumn("条件期望收益", format="%.2f%%",
                                                              help=TERM_HELP["conditional_expected_return"]),
                "条件样本数": st.column_config.NumberColumn("条件样本数", format="%d",
                                                            help=TERM_HELP["conditional_sample_count"]),
                "历史胜率": st.column_config.NumberColumn("历史胜率", format="%.2f%%", help=TERM_HELP["historical_win_rate"]),
                "期望收益": st.column_config.NumberColumn("期望收益", format="%.2f%%", help=TERM_HELP["expected_return"]),
            })

        # 个股维度解释
        section_header("个股维度解释", "选择候选，查看分项得分、权重贡献和历史条件证据。")
        explain_labels = {r["symbol"]: f'{r["symbol"]} {str(r.get("name", "") or "")}'.strip()
                          for _, r in picks.iterrows()}
        explain_options = picks["symbol"].astype(str).tolist()
        if st.session_state.get("explain_symbol") not in explain_options:
            st.session_state.explain_symbol = explain_options[0]
        explain_symbol = st.selectbox("选择股票", explain_options,
                                      format_func=lambda s: explain_labels.get(s, s), key="explain_symbol")
        row = picks[picks["symbol"] == explain_symbol].iloc[0]
        dims = pd.Series(
            {label: float(row[key]) for key, label in SCORE_NAMES.items()}, name="分项得分")
        conditional_sample_value = pd.to_numeric(row.get("conditional_sample_count"), errors="coerce")
        conditional_available = pd.notna(conditional_sample_value)
        conditional_count = int(conditional_sample_value) if conditional_available else None
        summary_top = st.columns(3)
        summary_evidence = st.columns(3)
        summary_top[0].metric("候选排名", f'{int(row["排名"])} / {len(picks)}', delta=row.get("排名变化", "-"))
        summary_top[1].metric("综合评分", f'{row["composite_score"]:.1f}',
                               help="五个维度按实际权重加权后的横截面排序分，不是上涨概率")
        credibility_value = row.get("credibility_score", float("nan"))
        summary_top[2].metric("个股证据等级", f'{row.get("credibility_grade", "低")} · {credibility_value:.1f}' if pd.notna(credibility_value) else "待评估",
                               help=TERM_HELP["credibility"])
        summary_evidence[0].metric("条件期望收益", f'{row.get("conditional_expected_return", float("nan")):.2%}' if conditional_available and pd.notna(row.get("conditional_expected_return")) else "未积累",
                                   help=TERM_HELP["conditional_expected_return"])
        summary_evidence[1].metric("条件胜率", f'{row.get("conditional_win_rate", float("nan")):.2%}' if conditional_available and pd.notna(row.get("conditional_win_rate")) else "未积累",
                                   help=TERM_HELP["conditional_win_rate"])
        summary_evidence[2].metric("条件样本", f'{conditional_count:,}' if conditional_available else "未积累",
                                   help=TERM_HELP["conditional_sample_count"] + " 未积累表示尚无满足间隔与已兑现要求的历史高分样本，不等于零样本统计结果。")

        strategy_status = load_research_status()
        linkage = research_linkage_status()
        data_fields = []
        if "industry" in row.index:
            data_fields.append(pd.notna(row.get("industry")) and str(row.get("industry", "")).strip() not in {"", "-", "未知行业"})
        if "market_cap" in row.index:
            cap_value = pd.to_numeric(row.get("market_cap"), errors="coerce")
            data_fields.append(pd.notna(cap_value) and float(cap_value) > 0)
        data_grade = "完整" if data_fields and all(data_fields) else ("部分缺失" if data_fields else "待评估")
        evidence_levels = st.columns(3)
        evidence_levels[0].metric("策略验证等级", strategy_status.get("label", "未验证"),
                                  help="评价整个评分方法的历史样本外证据，不评价单只股票。")
        evidence_levels[1].metric("验证关系", linkage.get("label", "待验证"),
                                  help="评分配置、回测配置和数据版本均一致时，回测才可为当前名单提供直接证据。")
        evidence_levels[2].metric("个股数据完整性", data_grade,
                                  help="检查结果中可用的行业和市值字段；待评估不代表数据完整。")

        sentiment_value = float(row["sentiment_score"])
        sentiment_source = str(row.get("sentiment_source", "未提供/中性"))
        news_count_value = pd.to_numeric(row.get("news_count"), errors="coerce")
        news_count = int(news_count_value) if pd.notna(news_count_value) else 0
        factor_values = [(SCORE_NAMES[f"{key}_score"], float(row[f"{key}_score"])) for key in ["model", "technical", "volume_price", "candle", "sentiment"]]
        strongest = sorted(factor_values, key=lambda item: item[1], reverse=True)[:2]
        weakest = sorted(factor_values, key=lambda item: item[1])[:2]
        positives = [f"{name}得分 {value:.1f}，是本次排序的主要正向来源" for name, value in strongest if value >= 50]
        negatives = [
            (f"舆情评分触及负面评分下限（来源：{sentiment_source}；新闻：{news_count} 条），对当前排序形成拖累"
             if name == "舆情评分" and value <= 0 else f"{name}得分 {value:.1f}，对当前排序形成拖累")
            for name, value in weakest if value < 50
        ]
        conditional_return = pd.to_numeric(row.get("conditional_expected_return"), errors="coerce")
        conditional_win = pd.to_numeric(row.get("conditional_win_rate"), errors="coerce")
        if pd.notna(conditional_return) and conditional_return > 0:
            positives.append(f"相似高分历史样本的条件期望收益为 {conditional_return:.2%}")
        elif pd.notna(conditional_return):
            negatives.append(f"相似高分历史样本的条件期望收益为 {conditional_return:.2%}")
        if pd.notna(conditional_win) and conditional_win > .5:
            positives.append(f"相似高分历史样本的条件胜率为 {conditional_win:.1%}")
        elif pd.notna(conditional_win):
            negatives.append(f"相似高分历史样本的条件胜率仅为 {conditional_win:.1%}")
        limitations = []
        if not conditional_available:
            limitations.append("条件高分历史样本尚未积累，暂无可统计的条件胜率与期望收益")
        elif conditional_count < 10:
            limitations.append(f"独立条件样本仅 {conditional_count} 个，区间估计不稳定")
        if not linkage.get("matched"):
            limitations.append(str(linkage.get("detail", "当前评分缺少匹配回测")))
        if data_grade != "完整":
            limitations.append("行业或市值字段不完整，暴露判断可能受限")
        evidence_cols = st.columns(3)
        with evidence_cols[0]:
            st.markdown("**正面证据**")
            for item in (positives[:3] or ["当前没有达到展示条件的明确正面证据"]):
                st.write(f"- {item}")
        with evidence_cols[1]:
            st.markdown("**反面证据**")
            for item in (negatives[:3] or ["当前没有达到展示条件的明确反面证据"]):
                st.write(f"- {item}")
        with evidence_cols[2]:
            st.markdown("**数据与验证限制**")
            for item in (limitations[:3] or ["当前未识别到额外限制；历史表现仍不代表未来收益"]):
                st.write(f"- {item}")
        st.caption("综合评分只表示当前股票池内的相对排序，不是上涨概率；应同时审阅反面证据、样本量和匹配回测。")

        weights = effective_score_weights()
        factor_keys = ["model", "technical", "volume_price", "candle", "sentiment"]
        contribution = pd.DataFrame({
            "维度": [SCORE_NAMES[f"{key}_score"] for key in factor_keys],
            "分项得分": [float(row[f"{key}_score"]) for key in factor_keys],
            "实际权重": [weights[key] * 100 for key in factor_keys],
            "加权贡献": [float(row[f"{key}_score"]) * weights[key] for key in factor_keys],
        })
        e1, e2 = st.columns([2, 3])
        with e1:
            cn_bar_chart(dims, "得分", height=260)
        with e2:
            st.dataframe(
                contribution, width="stretch", hide_index=True,
                column_config={
                    "分项得分": st.column_config.NumberColumn("分项得分", format="%.1f"),
                    "实际权重": st.column_config.NumberColumn("实际权重", format="%.1f%%"),
                    "加权贡献": st.column_config.NumberColumn("加权贡献", format="%.1f"),
                },
            )
            st.caption(
                f'贡献合计 {contribution["加权贡献"].sum():.1f} · '
                f'舆情来源 {sentiment_source} · 新闻 {news_count} 条'
            )
            if sentiment_value <= 0 and news_count > 0:
                st.caption("舆情评分已触及负面评分下限：这是新闻标题关键词的加权结果，不等同于公司基本面结论。")
        if not conditional_available:
            st.info("条件高分历史样本尚未积累，胜率与期望收益暂不展示；可信度中的条件维度已按保守值处理。")
        elif conditional_count < 10:
            st.warning(f"条件高分独立样本仅 {conditional_count} 个，胜率和期望收益证据不足，当前候选不应仅凭综合评分决策。")
        else:
            st.caption(
                f'条件胜率95%区间 {row.get("conditional_win_rate_low", float("nan")):.1%} 至 '
                f'{row.get("conditional_win_rate_high", float("nan")):.1%} · '
                f'条件收益95%区间 {row.get("conditional_return_low", float("nan")):.2%} 至 '
                f'{row.get("conditional_return_high", float("nan")):.2%}'
            )

        # 模型质量
        validation = load_validation_metrics()
        importance = load_importance()
        diagnostics = load_score_diagnostics()
        _, credibility_backtest = load_backtest()
        model_col, imp_col = st.columns(2)
        with model_col:
            st.subheader("模型验证")
            if validation:
                v1, v2 = st.columns(2)
                v1.metric("样本外 MAE", f'{validation.get("mae", 0):.2%}',
                          help=TERM_HELP["mae"])
                v2.metric("样本外 R²", f'{validation.get("r2", 0):.3f}',
                          help=TERM_HELP["r2"])
                st.caption(f'验证区间 {validation.get("validation_start", "-")[:10]} 至 {validation.get("validation_end", "-")[:10]}')
                if "ic_mean" in credibility_backtest:
                    validation_metrics = st.columns(3)
                    validation_metrics[0].metric("滚动 Rank IC", f'{credibility_backtest.get("ic_mean", 0):.3f}', help=TERM_HELP["rank_ic"])
                    validation_metrics[1].metric("ICIR", f'{credibility_backtest.get("icir", 0):.3f}', help=TERM_HELP["icir"])
                    validation_metrics[2].metric("Q5-Q1", f'{credibility_backtest.get("q5_q1_mean_return", 0):.2%}', help=TERM_HELP["q5_q1"])
        with imp_col:
            st.subheader("因子重要性")
            if importance is not None and not importance.empty:
                cn_bar_chart(importance.set_index("feature")["importance"].head(15), "重要性")

        with st.expander("因子重复度与权重稳健性"):
            if diagnostics:
                d1, d2, d3 = st.columns(3)
                d1.metric("最大因子相关性", f'{diagnostics.get("max_absolute_factor_correlation", 0):.2f}')
                d2.metric("最低排序相关性", f'{diagnostics.get("minimum_rank_correlation", 0):.2f}')
                d3.metric("最低候选重合率", f'{diagnostics.get("minimum_top_k_overlap", 0):.0%}')
                tests = pd.DataFrame(diagnostics.get("robustness_tests", []))
                if not tests.empty:
                    tests = tests.rename(columns={"test": "测试", "rank_correlation": "排序相关性", "top_k_overlap": "候选重合率"})
                    tests["候选重合率"] = tests["候选重合率"] * 100
                    st.dataframe(
                        tests, width="stretch", hide_index=True,
                        column_config={
                            "排序相关性": st.column_config.NumberColumn("排序相关性", format="%.3f"),
                            "候选重合率": st.column_config.NumberColumn("候选重合率", format="%.1f%%"),
                        },
                    )
                if diagnostics.get("max_absolute_factor_correlation", 0) >= 0.8:
                    st.warning("存在高度相关的评分维度，综合评分可能重复计权同一类信号。")
            else:
                st.info("重新运行综合评分后生成因子消融与权重扰动诊断。")

        # 候选已属于本次观察名单；研究股票池仅在数据页维护，避免反向收窄样本范围。
        st.subheader("导出与留存")
        st.caption("候选明细与字段说明合并在同一 Excel 文件的两个工作表中；研究报告用于留存本次研究结论、证据和限制。")
        export_excel_col, export_pdf_col = st.columns(2)
        with export_excel_col:
            try:
                candidate_workbook = candidate_export_workbook(picks)
                st.download_button("下载候选明细 Excel", candidate_workbook,
                                   "候选明细.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   icon=":material/download:", width="stretch")
            except Exception as error:
                st.error(f"候选明细导出失败：{error}")
        with export_pdf_col:
            _, backtest_metrics_for_pdf = load_backtest()
            try:
                # DataFrame cannot be evaluated as a scalar boolean; only default when absent.
                pdf_bytes = export_pdf_report(
                    picks,
                    backtest_metrics_for_pdf,
                    importance if importance is not None else pd.DataFrame(),
                )
                st.download_button("下载研究报告 PDF", pdf_bytes, f"研究报告_{date.today()}.pdf",
                                   "application/pdf", icon=":material/picture_as_pdf:", width="stretch")
            except Exception as error:
                st.error(f"PDF 导出失败：{error}")


# ==================== 页面：研究记录 ====================
elif st.session_state.research_view == "研究记录":
    page_header(
        "研究治理", "研究记录",
        "追溯每次评分与回测使用的数据、参数和验证结论。对比运行用于识别变化，不用于挑选历史表现最好的参数。",
        f'运行清单目录 {OUTPUT_DIR / "runs"}',
    )
    manifests = load_run_manifests()
    if not manifests:
        st.info("尚无研究运行记录。完成一次综合评分或历史回测后会自动归档。")
    else:
        type_filter = st.segmented_control("运行类型", ["全部", "评分", "回测"], default="评分", key="run_type_filter")
        kind_map = {"score": "评分", "backtest": "回测"}
        filtered = [item for item in manifests if type_filter == "全部" or kind_map.get(item.get("kind")) == type_filter]
        history_rows = []
        for item in filtered:
            config = item.get("config", {})
            weights = config.get("weights", {})
            status = item.get("validation_status", {})
            run_id = str(item.get("run_id", "-"))
            compact_run_id = "_".join(run_id.split("_")[-2:]) if "_" in run_id else run_id
            history_rows.append({
                "运行时间": str(item.get("created_at", ""))[:19].replace("T", " "),
                "运行编号": compact_run_id, "类型": kind_map.get(item.get("kind"), item.get("kind", "-")),
                "数据截至": item.get("data_end", "-"), "周期": config.get("horizon", "—"),
                "候选/持仓数": config.get("top_k", "—"), "权重（模/技/量/K/舆）": " / ".join(
                    f"{float(weights.get(key, 0)):.0%}" for key, _ in WEIGHT_LABELS
                ) if weights else "—", "验证结论": status.get("label", "待评估"),
                "归档": "完整" if (OUTPUT_DIR / "runs" / run_id).exists() else "旧记录",
            })
        st.dataframe(pd.DataFrame(history_rows), width="stretch", hide_index=True, height=360,
                     column_config={
                         "运行时间": st.column_config.TextColumn(width="medium"),
                         "运行编号": st.column_config.TextColumn(width="medium"),
                         "类型": st.column_config.TextColumn(width="small"),
                         "数据截至": st.column_config.TextColumn(width="small"),
                         "周期": st.column_config.NumberColumn(width="small"),
                         "候选/持仓数": st.column_config.NumberColumn(width="small"),
                         "权重（模/技/量/K/舆）": st.column_config.TextColumn(width="medium"),
                         "验证结论": st.column_config.TextColumn(width="medium"),
                         "归档": st.column_config.TextColumn(width="small"),
                     })

        section_header("运行对比", "选择两个版本核对数据、参数和结论差异。")
        run_lookup = {str(item.get("run_id")): item for item in filtered}
        run_options = list(run_lookup)
        selected_runs = st.multiselect(
            "选择两个运行", run_options, default=run_options[:2], max_selections=2, key="run_compare_selection",
            format_func=lambda run_id: f'{run_lookup[run_id].get("created_at", "")[:19].replace("T", " ")} · {kind_map.get(run_lookup[run_id].get("kind"), "运行")} · {run_id}',
            label_visibility="collapsed",
        )
        if len(selected_runs) == 2:
            left_run, right_run = (run_lookup[run_id] for run_id in selected_runs)
            left_kind, right_kind = left_run.get("kind"), right_run.get("kind")
            cross_type = left_kind != right_kind
            left_label = kind_map.get(left_kind, "版本A") if cross_type else "版本A"
            right_label = kind_map.get(right_kind, "版本B") if cross_type else "版本B"
            compare_rows = []
            fields = [
                ("数据截至", lambda item: item.get("data_end", "—")),
                ("数据指纹", lambda item: item.get("data_fingerprint", "—")),
                ("治理数据指纹", lambda item: item.get("governance_fingerprint", "旧记录未记录")),
                ("研究股票数量", lambda item: item.get("config", {}).get("universe_count", "旧记录未记录")),
                ("预测/持有周期", lambda item: item.get("config", {}).get("horizon", "—")),
                ("候选/持仓数量", lambda item: item.get("config", {}).get("top_k", "—")),
                ("权重模式", lambda item: item.get("config", {}).get("weight_mode", "自定义/未记录")),
                *[(f"{label}权重", lambda item, key=key: f'{float(item.get("config", {}).get("weights", {}).get(key, 0)):.0%}')
                  for key, label in WEIGHT_LABELS],
                ("特征版本", lambda item: item.get("config", {}).get("feature_version", "旧记录未记录")),
                ("模型版本", lambda item: item.get("config", {}).get("model_version", "旧记录未记录")),
                ("验证结论", lambda item: item.get("validation_status", {}).get("label", "待评估")),
            ]
            if left_kind == right_kind == "backtest":
                fields.extend([
                    ("累计超额收益", lambda item: _fmt_metric(item.get("metrics_summary", {}).get("cumulative_excess_return"), "percent")),
                    ("Rank IC", lambda item: _fmt_metric(item.get("metrics_summary", {}).get("ic_mean"), digits=3)),
                    ("最大回撤", lambda item: _fmt_metric(item.get("metrics_summary", {}).get("max_drawdown"), "percent")),
                ])
            for label_text, getter in fields:
                left_value, right_value = getter(left_run), getter(right_run)
                compare_rows.append({"比较项": label_text, left_label: str(left_value), right_label: str(right_value),
                                     "是否一致": "是" if left_value == right_value else "否"})
            comparison_frame = pd.DataFrame(compare_rows)
            st.dataframe(comparison_frame, width="stretch", hide_index=True,
                         column_config={
                             "比较项": st.column_config.TextColumn(width="medium"),
                             left_label: st.column_config.TextColumn(width="medium"),
                             right_label: st.column_config.TextColumn(width="medium"),
                             "是否一致": st.column_config.TextColumn(width="small"),
                         })
            if left_kind == right_kind == "score":
                left_candidates = {
                    str(item.get("symbol")): {**item, "rank": rank}
                    for rank, item in enumerate(left_run.get("candidate_snapshot", []), start=1)
                }
                right_candidates = {
                    str(item.get("symbol")): {**item, "rank": rank}
                    for rank, item in enumerate(right_run.get("candidate_snapshot", []), start=1)
                }
                candidate_rows = []
                names = name_map()
                for symbol in set(left_candidates).union(right_candidates):
                    left_item, right_item = left_candidates.get(symbol), right_candidates.get(symbol)
                    left_score = pd.to_numeric(left_item.get("composite_score"), errors="coerce") if left_item else np.nan
                    right_score = pd.to_numeric(right_item.get("composite_score"), errors="coerce") if right_item else np.nan
                    if left_item and right_item:
                        change = "共同入选"
                        rank_change = left_item["rank"] - right_item["rank"]
                    elif right_item:
                        change, rank_change = "新进入", np.nan
                    else:
                        change, rank_change = "退出", np.nan
                    left_grade = left_item.get("credibility_grade", "—") if left_item else "—"
                    right_grade = right_item.get("credibility_grade", "—") if right_item else "—"
                    candidate_rows.append({
                        "状态": change, "代码": symbol,
                        "名称": (right_item or left_item).get("name") or names.get(symbol, "—"),
                        "版本A排名": left_item.get("rank") if left_item else np.nan,
                        "A综合评分": left_score,
                        "版本B排名": right_item.get("rank") if right_item else np.nan,
                        "B综合评分": right_score,
                        "评分变化（B-A）": right_score - left_score if pd.notna(left_score) and pd.notna(right_score) else np.nan,
                        "排名变化（正值上升）": rank_change,
                        "可信度变化": f"{left_grade} → {right_grade}",
                    })
                if candidate_rows:
                    candidate_frame = pd.DataFrame(candidate_rows)
                    status_order = {"共同入选": 0, "新进入": 1, "退出": 2}
                    candidate_frame["_status_order"] = candidate_frame["状态"].map(status_order)
                    candidate_frame = candidate_frame.sort_values(
                        ["_status_order", "版本B排名", "版本A排名"], na_position="last"
                    ).drop(columns="_status_order")
                    common = candidate_frame[candidate_frame["状态"].eq("共同入选")]
                    overview = st.columns(4)
                    overview[0].metric("共同入选", len(common))
                    overview[1].metric("版本B新进入", int(candidate_frame["状态"].eq("新进入").sum()))
                    overview[2].metric("版本A退出", int(candidate_frame["状态"].eq("退出").sum()))
                    average_delta = pd.to_numeric(common["评分变化（B-A）"], errors="coerce").mean()
                    overview[3].metric("共同候选平均评分变化", f"{average_delta:+.1f}" if pd.notna(average_delta) else "—")
                    section_header("候选评分差异", "共同入选、新进入和退出均展示两次排名与综合评分；评分变化为版本B减版本A。")
                    st.dataframe(candidate_frame, width="stretch", hide_index=True,
                                 column_config={
                                     "状态": st.column_config.TextColumn(width="small"),
                                     "代码": st.column_config.TextColumn(width="small"),
                                     "名称": st.column_config.TextColumn(width="small"),
                                     "版本A排名": st.column_config.NumberColumn(width="small", format="%d"),
                                     "A综合评分": st.column_config.NumberColumn(width="small", format="%.1f"),
                                     "版本B排名": st.column_config.NumberColumn(width="small", format="%d"),
                                     "B综合评分": st.column_config.NumberColumn(width="small", format="%.1f"),
                                     "评分变化（B-A）": st.column_config.NumberColumn(width="small", format="%+.1f"),
                                     "排名变化（正值上升）": st.column_config.NumberColumn(width="small", format="%+d"),
                                     "可信度变化": st.column_config.TextColumn(width="small"),
                                 })
                else:
                    st.caption("两次评分运行缺少候选快照，无法比较候选评分差异。")
            elif cross_type:
                score_run = left_run if left_kind == "score" else right_run
                backtest_run = left_run if left_kind == "backtest" else right_run
                config_match = _score_configs_match(score_run.get("config", {}), backtest_run.get("config", {}))
                data_match = score_run.get("data_fingerprint") == backtest_run.get("data_fingerprint")
                governance_match = (
                    bool(score_run.get("governance_fingerprint"))
                    and score_run.get("governance_fingerprint") == backtest_run.get("governance_fingerprint")
                )
                if config_match and data_match and governance_match:
                    st.success("该评分运行与回测运行的配置、行情数据和治理数据一致，回测可用于验证该评分运行。")
                else:
                    mismatches = []
                    if not config_match:
                        mismatches.append("配置")
                    if not data_match:
                        mismatches.append("行情数据")
                    if not governance_match:
                        mismatches.append("治理数据")
                    st.warning(f'两次运行的{ "、".join(mismatches) }不一致，回测不能直接为该评分运行提供验证。')
                summary = backtest_run.get("metrics_summary", {})
                section_header("回测结果摘要", "回测收益指标只属于历史回测，不与评分运行作数值差异比较。")
                result_cols = st.columns(3)
                result_cols[0].metric("累计超额收益", _fmt_metric(summary.get("cumulative_excess_return"), "percent"))
                result_cols[1].metric("Rank IC", _fmt_metric(summary.get("ic_mean"), digits=3), help=TERM_HELP["rank_ic"])
                result_cols[2].metric("最大回撤", _fmt_metric(summary.get("max_drawdown"), "percent"), help=TERM_HELP["max_drawdown"])
        else:
            st.info("请选择两个运行版本进行对比。")


# ==================== 页面：历史回测 ====================
elif st.session_state.research_view == "历史回测":
    page_header(
        "策略验证", "历史回测",
        "滚动训练时每个调仓日只使用此前可得数据。回测用于检验研究假设，不构成未来收益承诺。",
        f'最近回测 {file_mtime(output_path("backtest_metrics.json"))} · 结果需与评分参数一致才可用于验证当前观察名单',
    )

    score_manifest = load_manifest(OUTPUT_DIR, "score")
    score_config = score_manifest.get("config", {})
    sentiment_history, sentiment_audit = historical_sentiment_data(summary.get("start"), summary.get("end"))
    backtest_horizon_value = st.session_state.get("backtest_horizon", int(score_config.get("horizon", 20)))
    min_days_needed = 120 + backtest_horizon_value + 1
    run_ready = summary["trading_days"] >= min_days_needed
    if not run_ready:
        st.warning(f'当前本地数据 {summary["trading_days"]} 个交易日，该持有周期下回测至少需要 {min_days_needed} 天。'
                   "请到『股票池与数据』下载更长的历史数据，或缩短持有周期。")

    section_header("回测配置", "默认沿用最近评分的周期、候选数量与权重。只有配置一致的回测，才能为当前评分结果提供证据。")
    if not sentiment_audit.get("usable"):
        st.warning(sentiment_audit.get("reason", "历史舆情不可用"))
    if score_config and st.button("沿用最近评分配置", icon=":material/sync:"):
        st.session_state.backtest_horizon = int(score_config.get("horizon", 20))
        st.session_state.backtest_top_k = int(score_config.get("top_k", 10))
        set_weight_values("backtest", score_config.get("weights", DEFAULT_WEIGHTS))
        st.rerun()

    with st.form("backtest_form", border=True):
        metadata_audit, _ = research_data_audits()
        historical_metadata_audit = metadata_history_audit(
            load_metadata_history(ARCHIVE_DIR), summary.get("start"), summary.get("end")
        )
        industry_available = bool(
            metadata_audit.get("industry_usable", False) and historical_metadata_audit.get("usable", False)
        )
        if score_config:
            st.caption(
                f'最近评分配置：周期 {score_config.get("horizon", "-")} 日 · '
                f'Top {score_config.get("top_k", "-")}。回测应使用相同周期、持仓数和权重。'
            )
        b1, b2, b3 = st.columns(3)
        with b1:
            backtest_horizon = st.slider(
                "持有周期（交易日）", 5, 60, int(score_config.get("horizon", 20)), 5, key="backtest_horizon"
            )
        with b2:
            backtest_top_k = st.slider(
                "每期持仓数量", 1, 50, int(score_config.get("top_k", 10)), 1, key="backtest_top_k"
            )
        with b3:
            benchmark_label = st.selectbox(
                "回测基准", list(BENCHMARK_OPTIONS), index=0, key="backtest_benchmark",
                help="股票池等权用于检验池内选股能力；沪深300、中证500和中证1000用于检验相对市场指数的表现。",
            )
        with st.expander("高级约束与权重"):
            cost_cols = st.columns(3)
            with cost_cols[0]:
                buy_cost_bps = st.number_input(
                    "买入成本（bps）", min_value=0.0, max_value=200.0,
                    value=20.0, step=5.0, key="buy_cost_bps",
                    help="买入佣金和买卖价差等成本。1 bps = 0.01%，20 bps = 0.20%。",
                )
            with cost_cols[1]:
                sell_cost_bps = st.number_input(
                    "卖出成本（bps）", min_value=0.0, max_value=200.0,
                    value=20.0, step=5.0, key="sell_cost_bps",
                    help="卖出佣金、印花税和买卖价差等成本。",
                )
            with cost_cols[2]:
                slippage_bps = st.number_input(
                    "单方向滑点（bps）", min_value=0.0, max_value=200.0,
                    value=10.0, step=5.0, key="slippage_bps",
                    help="成交价相对理论开盘价的不利偏移，买入和卖出方向分别扣除。建议进行多档压力测试。",
                )
            c1, c2 = st.columns(2)
            with c1:
                exclude_limit_up = st.checkbox("排除涨停及停牌股票", value=True, key="exclude_limit_up")
            with c2:
                min_average_amount_ten_thousand = st.number_input(
                    "最低20日平均成交额（万元）", min_value=0.0, max_value=1_000_000.0,
                    value=2_000.0, step=500.0, key="min_average_amount_ten_thousand",
                    help="用于排除流动性不足的股票。默认 2,000 万元，等于原来的 20 百万元。",
                )
            capacity_cols = st.columns(2)
            with capacity_cols[0]:
                portfolio_capital_ten_thousand = st.number_input(
                    "模拟组合资金（万元）", min_value=0.0, max_value=10_000_000.0,
                    value=20.0, step=10.0, key="portfolio_capital_ten_thousand",
                    help="按等权持仓估算策略容量，默认 20 万元；设为 0 表示不启用资金容量过滤。",
                )
            with capacity_cols[1]:
                max_participation_pct = st.number_input(
                    "单票成交参与率上限", min_value=0.1, max_value=20.0,
                    value=5.0, step=0.5, key="max_participation_pct",
                    help="单票计划交易额不超过其20日平均成交额的该比例。",
                )
            max_industry_weight = st.slider(
                "单行业最大持仓占比", 20, 100, 30 if industry_available else 100, 5,
                key="max_industry_weight_pct", disabled=not industry_available,
                help=("行业覆盖达到90%后启用，默认限制为30%。" if industry_available else
                      f'当前行业覆盖 {metadata_audit.get("industry_coverage", 0):.1%}；'
                      f'{historical_metadata_audit.get("reason", "历史快照不足")}，控件已禁用。'),
            ) / 100
            backtest_weights = weight_inputs("backtest", score_config.get("weights", DEFAULT_WEIGHTS))
            backtest_total = weight_total("backtest")
            effective_backtest_weights = (
                backtest_weights if sentiment_audit.get("usable") else without_unvalidated_sentiment(backtest_weights)
            )
            if not sentiment_audit.get("usable") and backtest_weights.get("sentiment", 0) > 0:
                st.caption(
                    "实际回测权重：" + " / ".join(
                        f"{label}{effective_backtest_weights[key]:.1%}" for key, label in WEIGHT_LABELS
                    )
                )
        run_backtest = st.form_submit_button("运行滚动回测", type="primary", icon=":material/history:", width="stretch",
                                             disabled=not run_ready or backtest_total != 100)

    if run_backtest:
        try:
            with st.status("正在执行滚动训练与逐期回测…", expanded=True) as bt_status:
                bt_bar = st.progress(0.0, text="准备回测…")
                bt_log = st.empty()

                def on_bt_progress(index: int, total: int, current_date: pd.Timestamp):
                    bt_bar.progress(index / total, text=f"调仓期 {index}/{total} · 训练截至 {current_date:%Y-%m-%d}")
                    bt_log.write(f"[{index}/{total}] 调仓日 {current_date:%Y-%m-%d}")

                run_id = new_run_id("backtest")
                panel = cached_panel(data_signature())
                panel, metadata_audit, universe_audit = governed_research_panel(panel)
                effective_industry_weight = max_industry_weight if metadata_audit.get("industry_usable") else 1.0
                frame, features = build_features(panel, horizon=backtest_horizon)
                benchmark_code = BENCHMARK_OPTIONS[benchmark_label]
                benchmark_returns = None
                if benchmark_code != "eligible_universe_equal_weight":
                    bt_log.write(f"正在加载{benchmark_label}基准行情…")
                    benchmark_history = load_benchmark_history(
                        benchmark_code, str(panel["date"].min()), str(panel["date"].max()),
                        BASE_DIR / "data" / "reference" / "benchmarks",
                    )
                    benchmark_returns = prepare_benchmark_returns(benchmark_history, backtest_horizon)
                periods, backtest_metrics = run_walk_forward_backtest(
                    frame, features, backtest_horizon, backtest_top_k, effective_backtest_weights,
                    sentiment_history=sentiment_history if sentiment_audit.get("usable") else None,
                    buy_cost_bps=buy_cost_bps,
                    sell_cost_bps=sell_cost_bps,
                    slippage_bps=slippage_bps,
                    exclude_limit_up=exclude_limit_up,
                    min_average_amount=min_average_amount_ten_thousand * 10_000,
                    max_industry_weight=effective_industry_weight,
                    portfolio_capital=portfolio_capital_ten_thousand * 10_000,
                    max_participation_rate=max_participation_pct / 100,
                    benchmark_returns=benchmark_returns,
                    benchmark_name=benchmark_code,
                    progress=on_bt_progress)
                config = {
                    "horizon": int(backtest_horizon), "top_k": int(backtest_top_k),
                    "weights": effective_backtest_weights, "requested_weights": backtest_weights,
                    "sentiment_mode": "historical" if sentiment_audit.get("usable") else "neutral_unvalidated",
                    "sentiment_audit": sentiment_audit,
                    "feature_version": FEATURE_VERSION, "model_version": MODEL_VERSION,
                    "universe_count": int(panel["symbol"].nunique()),
                    "benchmark_name": benchmark_code,
                    "buy_cost_bps": float(buy_cost_bps), "sell_cost_bps": float(sell_cost_bps),
                    "slippage_bps": float(slippage_bps),
                    "exclude_limit_up": bool(exclude_limit_up),
                    "min_average_amount": float(min_average_amount_ten_thousand * 10_000),
                    "max_industry_weight": float(effective_industry_weight),
                    "portfolio_capital": float(portfolio_capital_ten_thousand * 10_000),
                    "max_participation_rate": float(max_participation_pct / 100),
                }
                score_comparable = _score_configs_match(score_config, config)
                backtest_metrics.update({
                    "schema_version": 3, "run_id": run_id, "config": config,
                    "score_config_comparable": score_comparable,
                    "survivorship_bias_controlled": bool(universe_audit.get("usable", False)),
                })
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                periods.to_csv(OUTPUT_DIR / "backtest_periods.csv", index=False, encoding="utf-8-sig")
                (OUTPUT_DIR / "backtest_metrics.json").write_text(
                    json.dumps(backtest_metrics, ensure_ascii=False, indent=2), encoding="utf-8")
                validation = load_validation_metrics()
                status_result = assess_research_status(
                    backtest_metrics, validation, metadata_audit, universe_audit
                )
                if not score_comparable:
                    status_result["warnings"].append("本次回测参数与最近评分参数不一致，不能直接为当前观察名单背书")
                    status_result["passed"] = False
                    if status_result.get("preliminary_passed"):
                        status_result["status"] = "preliminary"
                        status_result["label"] = "初步通过"
                    status_result["result_term"] = "研究观察名单"
                save_research_status(status_result)
                write_run_manifest(OUTPUT_DIR, {
                    "run_id": run_id, "kind": "backtest", "config": config,
                    "score_run_id": score_manifest.get("run_id"),
                    "score_config_comparable": score_comparable,
                    "data_end": str(pd.Timestamp(panel["date"].max()).date()),
                    "data_fingerprint": data_fingerprint(list(DATA_DIR.glob("*.parquet"))),
                    "governance_fingerprint": governance_fingerprint(),
                    "metrics_summary": {key: backtest_metrics.get(key) for key in [
                        "periods", "cumulative_return", "cumulative_excess_return", "max_drawdown",
                        "sharpe", "ic_mean", "ic_confidence_low", "ic_confidence_high",
                        "ic_p_value_adjusted", "q5_q1_mean_return", "average_fill_ratio",
                    ]},
                    "metadata_audit": metadata_audit, "universe_audit": universe_audit,
                    "validation_status": status_result,
                })
                archive_run_artifacts(run_id, ["backtest_periods.csv", "backtest_metrics.json"])
                bt_status.update(label=f"回测完成：{backtest_metrics['periods']} 个调仓期", state="complete")
            st.success(f"回测完成：{backtest_metrics['periods']} 个调仓期（结果见下方）。")
        except Exception as error:
            show_operation_error("历史回测", error)

    periods, backtest_metrics = load_backtest()
    if not backtest_metrics:
        st.info("尚无回测结果。设置好参数后点击『运行滚动回测』。")
    else:
        render_backtest_workspace(periods, backtest_metrics)
