from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED_MARKET_COLUMNS = ["date", "open", "high", "low", "close", "volume", "amount", "turnover"]


def market_snapshot(panel: pd.DataFrame, scores: pd.DataFrame | None = None, universe: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build a latest daily market view from local daily bars."""
    frame = panel.copy().sort_values(["symbol", "date"])
    grouped = frame.groupby("symbol", group_keys=False)
    frame["pct_change"] = grouped["close"].pct_change()
    if "volume" in frame:
        frame["volume_ratio"] = frame["volume"] / grouped["volume"].transform(lambda values: values.shift(1).rolling(20, min_periods=5).mean())
    else:
        frame["volume_ratio"] = np.nan
    latest = frame.groupby("symbol", as_index=False).tail(1).copy()
    latest["history_rows"] = grouped["close"].transform("size").loc[latest.index].astype(int).to_numpy()
    if universe is not None and not universe.empty:
        names = universe[["symbol", "name", "initials"]].drop_duplicates("symbol")
        latest = latest.merge(names, on="symbol", how="left")
    else:
        latest["name"] = ""
        latest["initials"] = ""
    if scores is not None and not scores.empty:
        score_columns = ["symbol", "composite_score", "model_score", "technical_score", "volume_price_score", "candle_score", "sentiment_score", "odds_reward_risk", "odds_win_rate", "odds_expected_return", "odds_sample_count"]
        scores = scores[[column for column in score_columns if column in scores.columns]].copy()
        scores["symbol"] = scores["symbol"].astype(str).str.zfill(6)
        latest["symbol"] = latest["symbol"].astype(str).str.zfill(6)
        latest = latest.merge(scores, on="symbol", how="left")
    return latest.sort_values("symbol").reset_index(drop=True)


def audit_market_data(panel: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    """Audit completeness and obvious daily-bar anomalies without pretending to validate source truth."""
    frame = panel.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["symbol"] = frame["symbol"].astype(str).str.zfill(6)
    latest_date = frame["date"].max()
    rows: list[dict[str, object]] = []
    for symbol, stock in frame.groupby("symbol"):
        stock = stock.sort_values("date")
        returns = stock["close"].pct_change()
        required_missing = int(stock[[column for column in REQUIRED_MARKET_COLUMNS if column in stock.columns]].isna().sum().sum())
        missing_columns = [column for column in REQUIRED_MARKET_COLUMNS if column not in stock.columns]
        duplicate_dates = int(stock["date"].duplicated().sum())
        invalid_price = int((stock["close"].le(0) | stock["open"].le(0) | stock["high"].le(0) | stock["low"].le(0)).fillna(False).sum())
        invalid_ohlc = int(((stock["high"] < stock[["open", "close"]].max(axis=1)) | (stock["low"] > stock[["open", "close"]].min(axis=1))).fillna(False).sum())
        large_move = int((returns.abs() > 0.25).sum())
        lag_days = int((latest_date - stock["date"].max()).days) if pd.notna(stock["date"].max()) else None
        status = "正常"
        if missing_columns or required_missing or duplicate_dates or invalid_price or invalid_ohlc:
            status = "需修复"
        elif large_move or (lag_days is not None and lag_days > 5):
            status = "需核查"
        rows.append({
            "symbol": symbol, "rows": len(stock), "start": stock["date"].min().date() if stock["date"].notna().any() else None,
            "end": stock["date"].max().date() if stock["date"].notna().any() else None, "latest_lag_days": lag_days,
            "missing_required": required_missing, "missing_columns": ",".join(missing_columns),
            "duplicate_dates": duplicate_dates, "invalid_price": invalid_price, "invalid_ohlc": invalid_ohlc,
            "large_move_days": large_move, "status": status,
        })
    report = pd.DataFrame(rows).sort_values(["status", "symbol"]).reset_index(drop=True)
    summary = {
        "symbols": int(len(report)), "rows": int(len(frame)), "latest_date": str(latest_date.date()) if pd.notna(latest_date) else "-",
        "repair_count": int((report["status"] == "需修复").sum()), "review_count": int((report["status"] == "需核查").sum()),
        "missing_values": int(report["missing_required"].sum()), "duplicate_dates": int(report["duplicate_dates"].sum()),
        "large_move_days": int(report["large_move_days"].sum()),
    }
    return report, summary
