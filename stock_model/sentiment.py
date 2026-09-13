from __future__ import annotations

import re
from datetime import timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd


# 这是可审计的轻量词典，不把关键词结果包装成“情绪真值”。
# 分级权重：强 2.0 / 中 1.0 / 弱 0.5，命中后按时间衰减加权求和。
POSITIVE_WORDS: dict[str, float] = {
    # 强
    "暴涨": 2.0, "涨停": 2.0, "创新高": 2.0, "预增": 2.0, "中标": 2.0, "扭亏": 2.0, "翻倍": 2.0, "超预期": 2.0,
    # 中
    "增长": 1.0, "增持": 1.0, "回购": 1.0, "订单": 1.0, "盈利": 1.0, "突破": 1.0, "利好": 1.0,
    "上涨": 1.0, "扩产": 1.0, "新高": 1.0, "涨价": 1.0, "签约": 1.0, "战略合作": 1.0,
    # 弱
    "回暖": 0.5, "改善": 0.5, "积极": 0.5, "向好": 0.5, "提振": 0.5, "景气": 0.5,
}
NEGATIVE_WORDS: dict[str, float] = {
    # 强
    "暴跌": 2.0, "跌停": 2.0, "退市": 2.0, "预亏": 2.0, "立案": 2.0, "终止上市": 2.0, "低于预期": 2.0, "爆仓": 2.0,
    # 中
    "处罚": 1.5, "减持": 1.0, "亏损": 1.0, "下滑": 1.0, "问询": 1.0, "利空": 1.0, "违规": 1.0,
    "诉讼": 1.0, "终止": 1.0, "失败": 1.0, "冻结": 1.0, "警示": 1.0,
    # 弱
    "降价": 0.5, "承压": 0.5, "疲软": 0.5, "放缓": 0.5, "回落": 0.5, "亏损扩大": 1.5,
}
# 标题出现这些词时，该条新闻的情绪净值得反转并减半（“澄清减持传闻”不应记为负面）。
NEGATION_MARKERS = ("否认", "澄清", "辟谣", "传闻", "不实", "假消息", "未发生", "不存在")

# 时间衰减：近 3 天 1.0，7 天内 0.5，30 天内 0.2，更早不计。
DECAY_BANDS = ((3, 1.0), (7, 0.5), (30, 0.2))
DEDUP_SIMILARITY = 0.8


def title_net_score(text: object) -> float:
    """单条标题的情绪净值：正面强度和 - 负面强度和，含否定反转处理。"""
    value = str(text or "")
    positive = sum(weight for word, weight in POSITIVE_WORDS.items() if word in value)
    negative = sum(weight for word, weight in NEGATIVE_WORDS.items() if word in value)
    net = positive - negative
    if any(marker in value for marker in NEGATION_MARKERS):
        net = -net * 0.5
    return net


def _decay_weight(days_old: float) -> float:
    for bound, weight in DECAY_BANDS:
        if days_old <= bound:
            return weight
    return 0.0


def _normalize_title(text: str) -> str:
    return re.sub(r"[\s，。！？、：；“”‘’()（）\[\]【】,!?]", "", str(text))


def _dedup_titles(titles: pd.Series) -> pd.Series:
    """同一事件多家转载只计一次：归一化后相似度 >= 0.8 视为重复，保留首条。"""
    normalized = titles.map(_normalize_title).tolist()
    keep: list[bool] = []
    kept_normalized: list[str] = []
    for text in normalized:
        duplicate = any(SequenceMatcher(None, text, other).ratio() >= DEDUP_SIMILARITY for other in kept_normalized)
        keep.append(not duplicate)
        if not duplicate:
            kept_normalized.append(text)
    return titles[pd.Series(keep, index=titles.index)]


def text_sentiment(text: object) -> float:
    """单条标题独立打分（不含时间衰减），保留给旧调用方。"""
    return float(np.clip(50 + 18 * title_net_score(text), 0, 100))


def sentiment_from_frame(frame: pd.DataFrame, symbol: str, asof: pd.Timestamp | None = None) -> dict[str, object]:
    if frame is None or frame.empty:
        return {"symbol": symbol, "sentiment_score": 50.0, "sentiment_source": "无新闻/中性", "news_count": 0}
    title_column = next((c for c in ("新闻标题", "标题", "title", "新闻内容", "content") if c in frame.columns), None)
    date_column = next((c for c in ("发布时间", "日期", "date", "time") if c in frame.columns), None)
    if not title_column:
        return {"symbol": symbol, "sentiment_score": 50.0, "sentiment_source": "字段不足/中性", "news_count": 0}
    news = frame.copy()
    if date_column:
        news["_date"] = pd.to_datetime(news[date_column], errors="coerce")
        if asof is not None:
            lower = asof - timedelta(days=30)
            news = news[(news["_date"].isna()) | ((news["_date"] <= asof) & (news["_date"] >= lower))]
        news["_days_old"] = (asof - news["_date"]).dt.days if asof is not None else 0
    else:
        news["_days_old"] = 0
    titles = _dedup_titles(news[title_column])
    if titles.empty:
        return {"symbol": symbol, "sentiment_score": 50.0, "sentiment_source": "无新闻/中性", "news_count": 0}
    days = news.loc[titles.index, "_days_old"].astype(float)
    weights = days.map(_decay_weight)
    nets = titles.map(title_net_score)
    effective = int((weights * nets.abs() > 0).sum())
    if effective == 0:
        return {"symbol": symbol, "sentiment_score": 50.0, "sentiment_source": "无新闻/中性", "news_count": int(len(titles))}
    total_weight = float(weights.sum())
    if total_weight <= 0:
        return {"symbol": symbol, "sentiment_score": 50.0, "sentiment_source": "无新闻/中性", "news_count": int(len(titles))}
    raw_net = float((nets * weights).sum() / max(total_weight, 0.5))
    coverage_damping = min(1.0, float(np.log1p(effective) / np.log1p(3)))
    net = raw_net * coverage_damping
    return {
        "symbol": symbol,
        "sentiment_score": float(np.clip(50 + 18 * net, 0, 100)),
        "sentiment_source": "关键词新闻评分" if not nets[(weights > 0)].eq(0).all() else "无新闻/中性",
        "news_count": int(len(titles)),
    }


def fetch_latest_sentiment(symbol: str, asof: pd.Timestamp | None = None) -> dict[str, object]:
    try:
        import akshare as ak

        return sentiment_from_frame(ak.stock_news_em(symbol=symbol), symbol, asof)
    except Exception as error:
        return {
            "symbol": symbol,
            "sentiment_score": 50.0,
            "sentiment_source": f"新闻接口不可用/中性（{type(error).__name__}）",
            "news_count": 0,
        }


def normalize_sentiment_history(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize optional historical news scores. Expected columns: symbol,date,score."""
    frame = frame.rename(columns={"代码": "symbol", "日期": "date", "情绪分": "sentiment_score", "score": "sentiment_score"})
    required = {"symbol", "date", "sentiment_score"}
    if not required.issubset(frame.columns):
        raise ValueError("舆情历史文件需要 symbol、date、score 三列")
    frame["symbol"] = frame["symbol"].astype(str).str.zfill(6)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["sentiment_score"] = pd.to_numeric(frame["sentiment_score"], errors="coerce").clip(0, 100)
    return frame.dropna(subset=["symbol", "date", "sentiment_score"])


def load_sentiment_history(path: Path | None) -> pd.DataFrame:
    """Load optional historical news scores from CSV or parquet."""
    if path is None or not path.exists():
        return pd.DataFrame(columns=["symbol", "date", "sentiment_score"])
    frame = pd.read_csv(path, dtype={"symbol": str}) if path.suffix.lower() == ".csv" else pd.read_parquet(path)
    return normalize_sentiment_history(frame)


def latest_sentiment_snapshot(symbols: list[str], asof: pd.Timestamp, enabled: bool = True,
                              progress: "Callable[[int, int, str], None] | None" = None) -> pd.DataFrame:
    if not enabled:
        return pd.DataFrame({"symbol": symbols, "sentiment_score": 50.0, "sentiment_source": "未抓取/中性", "news_count": 0})
    total = len(symbols)
    rows = []
    for index, symbol in enumerate(symbols, start=1):
        if progress:
            progress(index, total, symbol)
        rows.append(fetch_latest_sentiment(symbol, asof))
    return pd.DataFrame(rows)
