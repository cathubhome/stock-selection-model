"""External benchmark retrieval and point-in-time return preparation."""

from __future__ import annotations

from pathlib import Path
import time

import pandas as pd


BENCHMARK_OPTIONS = {
    "股票池等权": "eligible_universe_equal_weight",
    "沪深300": "000300",
    "中证500": "000905",
    "中证1000": "000852",
}

BENCHMARK_NAMES = {value: key for key, value in BENCHMARK_OPTIONS.items()}


def _normalize_index_history(frame: pd.DataFrame, code: str) -> pd.DataFrame:
    aliases = {"日期": "date", "开盘": "open", "收盘": "close"}
    result = frame.rename(columns=aliases).copy()
    if not {"date", "open", "close"}.issubset(result.columns):
        raise ValueError(f"基准 {code} 行情缺少日期、开盘或收盘字段")
    result = result[["date", "open", "close"]]
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    result["open"] = pd.to_numeric(result["open"], errors="coerce")
    result["close"] = pd.to_numeric(result["close"], errors="coerce")
    return result.dropna().drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)


def load_benchmark_history(
    code: str, start: str, end: str, cache_dir: Path, retries: int = 3,
) -> pd.DataFrame:
    """Load an A-share index history, refreshing a local cache when possible."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"index_{code}.parquet"
    cached = pd.read_parquet(target) if target.exists() else pd.DataFrame()
    start_date, end_date = pd.Timestamp(start), pd.Timestamp(end)
    if not cached.empty:
        cached = _normalize_index_history(cached, code)
        if cached["date"].min() <= start_date and cached["date"].max() >= end_date - pd.Timedelta(days=7):
            return cached[(cached["date"] >= start_date) & (cached["date"] <= end_date)].copy()

    import akshare as ak

    errors: list[str] = []
    for attempt in range(max(int(retries), 1)):
        try:
            raw = ak.index_zh_a_hist(
                symbol=code, period="daily",
                start_date=start_date.strftime("%Y%m%d"), end_date=end_date.strftime("%Y%m%d"),
            )
            fresh = _normalize_index_history(raw, code)
            combined = pd.concat([cached, fresh], ignore_index=True) if not cached.empty else fresh
            combined = _normalize_index_history(combined, code)
            combined.to_parquet(target, index=False)
            return combined[(combined["date"] >= start_date) & (combined["date"] <= end_date)].copy()
        except Exception as error:
            errors.append(f"东方财富第{attempt + 1}次：{error}")
        try:
            prefix = "sz" if str(code).startswith("399") else "sh"
            raw = ak.stock_zh_index_daily_tx(
                symbol=f"{prefix}{code}",
                start_date=start_date.strftime("%Y%m%d"), end_date=end_date.strftime("%Y%m%d"),
            )
            fresh = _normalize_index_history(raw, code)
            combined = pd.concat([cached, fresh], ignore_index=True) if not cached.empty else fresh
            combined = _normalize_index_history(combined, code)
            combined.to_parquet(target, index=False)
            return combined[(combined["date"] >= start_date) & (combined["date"] <= end_date)].copy()
        except Exception as error:
            errors.append(f"腾讯第{attempt + 1}次：{error}")
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    if not cached.empty:
        usable = cached[(cached["date"] >= start_date) & (cached["date"] <= end_date)].copy()
        if not usable.empty:
            return usable
    raise RuntimeError(f"基准指数 {code} 行情获取失败：{'；'.join(errors)}")


def prepare_benchmark_returns(history: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Create next-open to horizon-open returns aligned to signal dates."""
    frame = _normalize_index_history(history, "external")
    frame["entry_open"] = frame["open"].shift(-1)
    frame["exit_open"] = frame["open"].shift(-(int(horizon) + 1))
    frame["benchmark_return"] = frame["exit_open"] / frame["entry_open"] - 1
    return frame[["date", "benchmark_return"]].dropna().reset_index(drop=True)
