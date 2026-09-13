from __future__ import annotations

import numpy as np
import pandas as pd


# 全部特征均为无量纲口径（收益率/比率/位置量），保证横截面可比。
# 历史教训：绝对价格尺度的指标（MACD、OBV、布林上轨下轨、ATR 的价格值）在
# 不同股票间相差数量级，树模型只能把它们当「股票身份」代理用过拟合，
# 且后复权价与真实价的比例因股票而异会进一步扭曲。因此统一相对化：
#   macd/signal → 除以收盘价；ATR → 除以收盘价（ATR%）；
#   OBV 累计值删除（obv_slope_20 已表达方向）；布林带 → %B 位置；
#   vwap_ratio 因后复权失真改为 close 相对典型价格的偏离；money_flow 改为量加权平均收益。
FEATURE_COLUMNS = [
    "ret_5", "ret_20", "ret_60", "ret_120", "vol_20",
    "sma_20_ratio", "sma_60_ratio", "volume_ratio_20", "amount_log",
    "body_pct", "close_position", "upper_shadow_pct", "lower_shadow_pct",
    "obv_slope_20", "money_flow_20",
    "rsi_14", "macd_pct", "signal_pct", "atr_pct_14", "vwap_dev", "bollinger_pctb",
]

OPTIONAL_POINT_IN_TIME_FEATURES = [
    "market_cap_log", "earnings_yield", "book_to_price", "roe", "roic",
    "revenue_growth", "profit_growth", "debt_ratio", "cashflow_quality",
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
    panel["market_cap_log"] = (
        np.log(pd.to_numeric(panel["market_cap"], errors="coerce").clip(lower=1))
        if "market_cap" in panel else np.nan
    )
    panel["earnings_yield"] = (
        1 / pd.to_numeric(panel["pe_ttm"], errors="coerce").where(lambda values: values.gt(0))
        if "pe_ttm" in panel else np.nan
    )
    panel["book_to_price"] = (
        1 / pd.to_numeric(panel["pb"], errors="coerce").where(lambda values: values.gt(0))
        if "pb" in panel else np.nan
    )
    panel["amount_ma20"] = (
        grouped["amount"].transform(lambda s: s.rolling(20, min_periods=5).mean())
        if "amount" in panel else np.nan
    )

    # 真实 RSI（Wilder 平滑）：上涨均值 / (上涨均值 + 下跌均值)，取值 0~100
    delta = grouped["close"].diff()
    gains = delta.clip(lower=0)
    losses = (-delta).clip(lower=0)
    avg_gain = gains.groupby(panel["symbol"]).transform(
        lambda s: s.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean())
    avg_loss = losses.groupby(panel["symbol"]).transform(
        lambda s: s.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean())
    denominator = (avg_gain + avg_loss).replace(0, np.nan)
    panel["rsi_14"] = (100 * avg_gain / denominator).fillna(50.0)

    # MACD 除以收盘价，消除价格量级差异
    ema_12 = grouped["close"].transform(lambda s: s.ewm(span=12, adjust=False).mean())
    ema_26 = grouped["close"].transform(lambda s: s.ewm(span=26, adjust=False).mean())
    panel["macd_pct"] = (ema_12 - ema_26) / panel["close"]
    panel["signal_pct"] = panel.groupby("symbol")["macd_pct"].transform(lambda s: s.ewm(span=9, adjust=False).mean())

    # 真实波幅 ATR（含跳空与高低区间），除以收盘价得到无量纲波动率
    prev_close = grouped["close"].shift(1)
    true_range = pd.concat([
        panel["high"] - panel["low"],
        (panel["high"] - prev_close).abs(),
        (panel["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    panel["atr_pct_14"] = (
        true_range.groupby(panel["symbol"]).transform(lambda s: s.rolling(14).mean()) / panel["close"]
    )

    # close 相对典型价格 (H+L+C)/3 的偏离：不含后复权失真的日内强弱
    typical_price = (panel["high"] + panel["low"] + panel["close"]) / 3
    panel["vwap_dev"] = panel["close"] / typical_price - 1

    if {"open", "high", "low", "close"}.issubset(panel.columns):
        # K 线形态：实体占比、收盘位置、上下影线占比（分母为当日振幅，振幅为零记 NaN）
        amplitude = (panel["high"] - panel["low"]).replace(0, np.nan)
        panel["body_pct"] = (panel["close"] - panel["open"]).abs() / amplitude
        panel["close_position"] = (panel["close"] - panel["low"]) / amplitude
        panel["upper_shadow_pct"] = (panel["high"] - panel[["open", "close"]].max(axis=1)) / amplitude
        panel["lower_shadow_pct"] = (panel[["open", "close"]].min(axis=1) - panel["low"]) / amplitude

        # 布林带 %B 位置：close 在 [下轨, 上轨] 中的相对位置（0 下轨 ~ 1 上轨），严格按 symbol 分组滚动
        typical_mid = (panel["high"] + panel["low"]) / 2
        band_mid = typical_mid.groupby(panel["symbol"]).transform(lambda s: s.rolling(20).mean())
        band_std = grouped["close"].transform(lambda s: s.rolling(20).std())
        band_upper = band_mid + 2 * band_std
        band_lower = band_mid - 2 * band_std
        panel["bollinger_pctb"] = (panel["close"] - band_lower) / (band_upper - band_lower).replace(0, np.nan)
    else:
        panel["body_pct"] = np.nan
        panel["close_position"] = np.nan
        panel["upper_shadow_pct"] = np.nan
        panel["lower_shadow_pct"] = np.nan
        panel["bollinger_pctb"] = np.nan

    # 量加权平均收益：Σ(ret×vol)/Σ(vol)，消除成交量绝对规模差异
    signed_flow = grouped["close"].pct_change().mul(panel.get("volume", 0)).fillna(0)
    flow_sum = signed_flow.groupby(panel["symbol"]).transform(lambda s: s.rolling(20).sum())
    if "volume" in panel:
        volume_sum = panel["volume"].groupby(panel["symbol"]).transform(
            lambda s: s.rolling(20).sum()).replace(0, np.nan)
        panel["money_flow_20"] = flow_sum / volume_sum
    else:
        panel["money_flow_20"] = flow_sum
    # Signal is formed after today's close. The tradable label enters at the
    # next session's open and exits ``horizon`` sessions later at the open.
    panel["entry_open"] = grouped["open"].shift(-1)
    panel["exit_open"] = grouped["open"].shift(-(horizon + 1))
    panel["entry_gap_return"] = panel["entry_open"] / panel["close"] - 1
    panel["entry_volume"] = grouped["volume"].shift(-1) if "volume" in panel else np.nan
    panel["future_return"] = panel["exit_open"] / panel["entry_open"] - 1
    # Separate stock-selection alpha from the market move at label time.
    panel["future_market_return"] = panel.groupby("date")["future_return"].transform("mean")
    panel["future_excess_return"] = panel["future_return"] - panel["future_market_return"]
    if "industry" in panel.columns:
        valid_industry = panel["industry"].notna() & panel["industry"].astype(str).str.strip().ne("")
        panel.loc[valid_industry, "future_industry_return"] = (
            panel.loc[valid_industry].groupby(["date", "industry"])["future_return"].transform("mean")
        )
        panel["future_industry_excess_return"] = panel["future_return"] - panel["future_industry_return"]
    panel["date"] = pd.to_datetime(panel["date"])
    result = panel.replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURE_COLUMNS)
    optional = [column for column in OPTIONAL_POINT_IN_TIME_FEATURES if column in result and result[column].notna().mean() >= 0.50]
    return result, [*FEATURE_COLUMNS, *optional]
