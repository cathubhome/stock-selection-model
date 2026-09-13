from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED_MARKET_COLUMNS = ["date", "open", "high", "low", "close", "volume", "amount", "turnover"]


def security_type(symbol: object) -> str:
    text = str(symbol).strip().upper().zfill(6)
    if text.startswith("HK"):
        return "港股"
    if text.startswith(("510", "511", "512", "513", "515", "516", "517", "518", "520", "560", "561", "562", "563", "588", "159")):
        return "ETF/基金"
    if text.startswith(("110", "111", "113", "118", "123", "127", "128")):
        return "可转债"
    if text.startswith(("000", "001", "002", "003", "300", "301", "600", "601", "603", "605", "688", "689", "430", "830", "831", "832", "833", "834", "835", "836", "837", "838", "839", "870", "871", "872", "873", "920")):
        return "A股个股"
    return "其他"


def a_share_equity_mask(symbols: pd.Series) -> pd.Series:
    return symbols.astype(str).map(security_type).eq("A股个股")


def board_limit_threshold(symbol: object) -> float:
    """按代码推断板块涨跌停幅度：创业板(300/301)/科创板(688/689) 为 20%，其余主板 10%。

    ST 股票的 5% 幅度无法从代码识别，统一按所属板块口径处理。
    """
    text = str(symbol)
    return 0.198 if text.startswith(("300", "301", "688", "689")) else 0.098


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


def market_sentiment(panel: pd.DataFrame) -> dict[str, object]:
    """从本地行情合成市场情绪面：宽度（涨家数占比）、量能（放量倍数）、涨停占比。

    仅使用最新交易日及以前的数据，无未来信息。score 为 0~100，50 视为中性。
    """
    frame = panel.copy().sort_values(["symbol", "date"])
    frame["date"] = pd.to_datetime(frame["date"])
    latest_date = frame["date"].max()
    frame["pct"] = frame.groupby("symbol")["close"].pct_change()
    # Market breadth and limit-up counts describe A-share equities only;
    # ETFs/funds and convertible bonds have different limit rules.
    latest = frame[(frame["date"] == latest_date) & a_share_equity_mask(frame["symbol"])]
    if latest.empty:
        return {"date": str(latest_date.date()), "score": 50.0, "breadth": 0.5, "volume_ratio": 1.0,
                "limit_up_ratio": 0.0, "limit_up_count": 0, "limit_up_denominator": 0,
                "limit_up_rule": "主板涨幅≥9.8%；创业板/科创板涨幅≥19.8%（按代码识别）",
                "breadth_score": 50.0, "volume_score": 50.0, "limit_score": 50.0, "stocks": 0}
    if "volume" in frame.columns:
        ma20 = frame.groupby("symbol")["volume"].transform(lambda s: s.rolling(20, min_periods=5).mean())
        volume_ratio = float((latest["volume"] / ma20.loc[latest.index]).mean())
    else:
        volume_ratio = float("nan")
    breadth = float((latest["pct"] > 0).mean())
    # 涨停判定按板块阈值（主板 10%、创业板/科创板 20%），避免 20cm 板块漏计
    limit_thresholds = latest["symbol"].astype(str).map(board_limit_threshold)
    limit_up_mask = latest["pct"].ge(limit_thresholds).fillna(False)
    limit_up_count = int(limit_up_mask.sum())
    limit_up_ratio = float(limit_up_count / len(latest))
    breadth_score = breadth * 100
    volume_score = 50.0 if pd.isna(volume_ratio) else float(np.clip(50 + (volume_ratio - 1) * 100, 0, 100))
    limit_score = float(np.clip(50 + limit_up_ratio * 1000, 0, 100))
    score = float(np.nanmean([breadth_score, volume_score, limit_score]))
    return {
        "date": str(latest_date.date()),
        "score": score,
        "breadth": breadth,
        "volume_ratio": volume_ratio,
        "limit_up_ratio": limit_up_ratio,
        "limit_up_count": limit_up_count,
        "limit_up_denominator": int(len(latest)),
        "limit_up_rule": "主板涨幅≥9.8%；创业板/科创板涨幅≥19.8%（按代码识别）",
        "breadth_score": float(breadth_score),
        "volume_score": float(volume_score),
        "limit_score": limit_score,
        "stocks": int(len(latest)),
    }


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
        # 大涨大跌异常线按板块放宽（阈值 + 2 个百分点余量），创业板/科创板 20% 内的合法波动不误报
        move_limit = board_limit_threshold(symbol) + 0.02
        large_move = int((returns.abs() > move_limit).sum())
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
