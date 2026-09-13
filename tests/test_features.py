"""特征工程测试：分组正确性、指标口径、标签计算。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from conftest import make_panel
from stock_model.features import FEATURE_COLUMNS, build_features


def _bollinger_pctb_manual(stock: pd.DataFrame) -> pd.Series:
    """独立实现 %B 公式，用于对照验证。"""
    mid = ((stock["high"] + stock["low"]) / 2).rolling(20).mean()
    std = stock["close"].rolling(20).std()
    upper, lower = mid + 2 * std, mid - 2 * std
    return (stock["close"] - lower) / (upper - lower)


def test_bollinger_matches_manual_formula_per_symbol():
    """%B 必须按 symbol 分组滚动且公式正确：与逐只股票的手工计算完全一致。"""
    panel = make_panel({"600000": 10.0, "688001": 1000.0}, days=150, seed=11)
    combined, _ = build_features(panel.copy(), horizon=5)

    for symbol in ["600000", "688001"]:
        stock = panel[panel["symbol"] == symbol].sort_values("date").reset_index(drop=True)
        expected = _bollinger_pctb_manual(stock)
        got = combined[combined["symbol"] == symbol].set_index("date")["bollinger_pctb"]
        exp = expected.set_axis(stock["date"]).dropna()
        shared = exp.index.intersection(got.index)
        assert len(shared) > 20
        assert np.allclose(got.loc[shared], exp.loc[shared], atol=1e-10)


def test_bollinger_no_cross_symbol_contamination():
    """价格量级悬殊的两只股票，各自 %B 都应落在合理范围；跨边界污染会产生极端值。"""
    panel = make_panel({"600000": 10.0, "688001": 1000.0}, days=150, seed=11)
    combined, _ = build_features(panel.copy(), horizon=5)
    assert combined["bollinger_pctb"].between(-1, 2).all()


def test_rsi_bounds_and_extremes():
    """rsi_14 应为真实 RSI：取值 0~100，连续上涨≈100，连续下跌≈0。"""
    panel = make_panel({"600000": 100.0}, days=140, seed=3)

    def _with_realistic_ohlc(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        out["open"] = out["close"].shift(1).fillna(out["close"].iloc[0])
        out["high"] = out[["open", "close"]].max(axis=1) * 1.001  # 保持振幅非零，行不被预热剔除
        out["low"] = out[["open", "close"]].min(axis=1) * 0.999
        return out

    up = panel.copy()
    up["close"] = np.linspace(100, 200, len(up))  # 单调上涨
    features_up, _ = build_features(_with_realistic_ohlc(up), horizon=5)
    assert not features_up.empty
    assert features_up["rsi_14"].min() >= 99.0

    down = panel.copy()
    down["close"] = np.linspace(200, 100, len(down))  # 单调下跌
    features_down, _ = build_features(_with_realistic_ohlc(down), horizon=5)
    assert features_down["rsi_14"].max() <= 1.0


def test_atr_pct_uses_true_range():
    """atr_pct_14 必须包含跳空与高低价区间：巨震K线应显著抬高 ATR%。"""
    panel = make_panel({"600000": 100.0}, days=170, seed=5)
    # 长期窄幅盘整：收盘日变动与振幅都在 0.x% 量级，ATR% 基线极低
    rng = np.random.default_rng(5)
    panel["close"] = 100 * np.cumprod(1 + rng.normal(0, 0.0005, len(panel)))
    panel["open"] = panel["close"] * (1 + rng.normal(0, 0.0005, len(panel)))
    panel["high"] = panel[["open", "close"]].max(axis=1) * 1.001
    panel["low"] = panel[["open", "close"]].min(axis=1) * 0.999
    shock = panel.index[135]  # 必须在 120 天特征预热期之后
    panel.loc[shock, "high"] = 112.0  # TR = high-low = 12 → ATR% 明显抬升
    panel.loc[shock, "low"] = 92.0
    features, _ = build_features(panel, horizon=5)
    before = features[features["date"] < panel.loc[shock, "date"]]
    after = features[features["date"] >= panel.loc[shock, "date"]]
    assert not after.empty and not before.empty
    baseline = float(before["atr_pct_14"].median())
    assert baseline < 0.008  # 盘整期基线确实很低
    assert float(after["atr_pct_14"].iloc[0]) > baseline * 2  # 巨震显著抬高真实波幅


def test_future_return_matches_horizon():
    panel = make_panel({"600000": 50.0}, days=160, seed=9)
    frame, _ = build_features(panel, horizon=5)
    stock = frame.reset_index(drop=True)
    sample = stock.iloc[10]
    close = panel.set_index("date")["close"]
    dates = close.index
    pos = dates.searchsorted(sample["date"])
    stock_panel = panel.set_index("date")
    expected = stock_panel["open"].iloc[pos + 6] / stock_panel["open"].iloc[pos + 1] - 1
    assert abs(sample["future_return"] - expected) < 1e-12


def test_all_feature_columns_computed_and_scale_free():
    """规范数据下所有特征列都应有非空值，且无量纲特征不随价格量级变化。"""
    panel = make_panel({"600000": 20.0, "300750": 300.0}, days=140, seed=13)
    frame, _ = build_features(panel, horizon=5)
    assert not frame.empty
    counts = frame[FEATURE_COLUMNS].isna().sum()
    assert int(counts.sum()) == 0, f"特征列存在缺失：{counts[counts > 0].to_dict()}"
    # 无量纲特征在两只价格量级悬殊的股票上应有可比的取值范围（RSI 合法范围 0~100 单列）
    scale_free = ["macd_pct", "signal_pct", "atr_pct_14", "vwap_dev", "bollinger_pctb"]
    ranges = frame.groupby("symbol")[scale_free].max().abs().max()
    assert (ranges < 5).all(), f"疑似残留绝对价格尺度：{ranges.to_dict()}"
    assert frame["rsi_14"].between(0, 100).all()


def test_normalize_history_renames_and_dedupes():
    from stock_model.data import normalize_history

    raw = pd.DataFrame({
        "日期": ["2024-01-02", "2024-01-03", "2024-01-03"],
        "开盘": [1.0, 2.0, 2.0], "收盘": [1.5, 2.5, 2.5],
        "最高": [1.6, 2.6, 2.6], "最低": [0.9, 1.9, 1.9],
        "成交量": [100, 200, 200], "成交额": [150, 500, 500], "换手率": [1.0, 2.0, 2.0],
    })
    result = normalize_history(raw, "600000")
    assert {"date", "open", "high", "low", "close", "volume", "amount", "turnover", "symbol"} <= set(result.columns)
    assert len(result) == 2  # 重复日期保留最后一条
    assert (result["symbol"] == "600000").all()


def test_normalize_empty_history_returns_standard_schema():
    from stock_model.data import normalize_history

    result = normalize_history(pd.DataFrame(), "600000")
    assert {"date", "close", "symbol"}.issubset(result.columns)
    assert result.empty
