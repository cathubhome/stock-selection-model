from __future__ import annotations

import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    "ret_5", "ret_20", "ret_60", "ret_120", "vol_20",
    "sma_20_ratio", "sma_60_ratio", "volume_ratio_20", "amount_log",
    "body_pct", "close_position", "upper_shadow_pct", "lower_shadow_pct",
    "obv_slope_20", "money_flow_20",
]


def build_features(panel: pd.DataFrame, horizon: int = 20) -> tuple[pd.DataFrame, list[str]]:
    panel = panel.copy().sort_values(["symbol", "date"])
    grouped = panel.groupby("symbol", group_keys=False)
    panel["ret_5"] = grouped["close"].pct_change(5)
    panel["ret_20"] = grouped["close"].pct_change(20)
    panel["ret_60"] = grouped["close"].pct_change(60)
    panel["ret_120"] = grouped["close"].pct_change(120)
    panel["daily_return"] = grouped["close"].pct_change()
    panel["vol_20"] = panel.groupby("symbol")["daily_return"].transform(lambda s: s.rolling(20).std() * np.sqrt(252))
    panel["sma_20_ratio"] = panel["close"] / grouped["close"].transform(lambda s: s.rolling(20).mean()) - 1
    panel["sma_60_ratio"] = panel["close"] / grouped["close"].transform(lambda s: s.rolling(60).mean()) - 1
    if "volume" in panel:
        panel["volume_ratio_20"] = panel["volume"] / grouped["volume"].transform(lambda s: s.rolling(20).mean())
        direction = np.sign(grouped["close"].diff()).fillna(0)
        panel["obv"] = (direction * panel["volume"].fillna(0)).groupby(panel["symbol"]).cumsum()
        panel["obv_slope_20"] = panel.groupby("symbol")["obv"].transform(lambda s: s.diff(20) / s.shift(20).abs().replace(0, np.nan))
    else:
        panel["volume_ratio_20"] = np.nan
        panel["obv_slope_20"] = np.nan
    panel["amount_log"] = np.log1p(panel["amount"].clip(lower=0)) if "amount" in panel else np.nan
    if {"open", "high", "low"}.issubset(panel.columns):
        price_range = (panel["high"] - panel["low"]).replace(0, np.nan)
        body = (panel["close"] - panel["open"]).abs()
        panel["body_pct"] = body / price_range
        panel["close_position"] = (panel["close"] - panel["low"]) / price_range
        panel["upper_shadow_pct"] = (panel["high"] - panel[["open", "close"]].max(axis=1)) / price_range
        panel["lower_shadow_pct"] = (panel[["open", "close"]].min(axis=1) - panel["low"]) / price_range
    else:
        for column in ["body_pct", "close_position", "upper_shadow_pct", "lower_shadow_pct"]:
            panel[column] = np.nan
    panel["money_flow_20"] = grouped["close"].pct_change().mul(panel.get("volume", 0)).groupby(panel["symbol"]).transform(lambda s: s.rolling(20).sum())
    panel["future_return"] = grouped["close"].shift(-horizon) / panel["close"] - 1
    panel["date"] = pd.to_datetime(panel["date"])
    result = panel.replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURE_COLUMNS)
    return result, FEATURE_COLUMNS
