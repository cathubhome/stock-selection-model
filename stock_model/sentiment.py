from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd


# 这是可审计的轻量词典，不把关键词结果包装成“情绪真值”。
POSITIVE_WORDS = ("增长", "增持", "回购", "中标", "订单", "盈利", "预增", "突破", "创新高", "利好", "上涨", "扩产")
NEGATIVE_WORDS = ("减持", "亏损", "预亏", "暴跌", "下滑", "处罚", "问询", "诉讼", "风险", "利空", "退市", "违规")


def text_sentiment(text: object) -> float:
    value = str(text or "")
    positive = sum(value.count(word) for word in POSITIVE_WORDS)
    negative = sum(value.count(word) for word in NEGATIVE_WORDS)
    if positive + negative == 0:
        return 50.0
    return float(np.clip(50 + 18 * (positive - negative), 0, 100))


def _find_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    for column in candidates:
        if column in frame.columns:
            return column
    return None


def sentiment_from_frame(frame: pd.DataFrame, symbol: str, asof: pd.Timestamp | None = None) -> dict[str, object]:
    if frame is None or frame.empty:
        return {"symbol": symbol, "sentiment_score": 50.0, "sentiment_source": "无新闻/中性", "news_count": 0}
    title_column = _find_column(frame, ("新闻标题", "标题", "title", "新闻内容", "content"))
    date_column = _find_column(frame, ("发布时间", "日期", "date", "time"))
    if not title_column:
        return {"symbol": symbol, "sentiment_score": 50.0, "sentiment_source": "字段不足/中性", "news_count": 0}
    news = frame.copy()
    if date_column:
        news["_date"] = pd.to_datetime(news[date_column], errors="coerce")
        if asof is not None:
            lower = asof - timedelta(days=30)
            news = news[(news["_date"].isna()) | ((news["_date"] <= asof) & (news["_date"] >= lower))]
    scores = news[title_column].map(text_sentiment).dropna()
    return {
        "symbol": symbol,
        "sentiment_score": float(scores.mean()) if not scores.empty else 50.0,
        "sentiment_source": "关键词新闻评分" if not scores.empty else "无新闻/中性",
        "news_count": int(len(scores)),
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


def latest_sentiment_snapshot(symbols: list[str], asof: pd.Timestamp, enabled: bool = True) -> pd.DataFrame:
    if not enabled:
        return pd.DataFrame({"symbol": symbols, "sentiment_score": 50.0, "sentiment_source": "未抓取/中性", "news_count": 0})
    return pd.DataFrame([fetch_latest_sentiment(symbol, asof) for symbol in symbols])
