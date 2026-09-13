"""数据质量阈值与股票池测试。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from conftest import make_panel
from stock_model.pool import add_to_pool, load_pool
from stock_model.quality import (
    a_share_equity_mask, audit_market_data, board_limit_threshold, market_sentiment, security_type,
)


def test_board_limit_threshold_by_code():
    assert board_limit_threshold("600000") == 0.098  # 主板 10%
    assert board_limit_threshold("000001") == 0.098
    assert board_limit_threshold("300750") == 0.198  # 创业板 20%
    assert board_limit_threshold("301001") == 0.198
    assert board_limit_threshold("688001") == 0.198  # 科创板 20%


def test_security_type_excludes_funds_and_convertible_bonds():
    symbols = pd.Series(["000001", "301291", "688146", "513050", "562590", "123001"])
    assert security_type("513050") == "ETF/基金"
    assert security_type("123001") == "可转债"
    assert a_share_equity_mask(symbols).tolist() == [True, True, True, False, False, False]


def test_market_sentiment_limit_up_counts_growth_boards():
    """20cm 板块的 +15% 不应被计为涨停，主板 +10% 应被计入。"""
    dates = pd.bdate_range("2024-01-01", periods=25)
    rows = []
    for symbol, base, last_ret in [("600000", 10.0, 0.101), ("300750", 50.0, 0.15)]:
        closes = base * np.cumprod(1 + np.full(len(dates) - 1, 0.001))
        closes = np.append(closes, closes[-1] * (1 + last_ret))
        for d, c in zip(dates, closes):
            rows.append({"date": d, "symbol": symbol, "close": c, "volume": 1000.0})
    panel = pd.DataFrame(rows)
    mood = market_sentiment(panel)
    assert mood["limit_up_ratio"] == pytest_approx(0.5)
    assert mood["limit_up_count"] == 1
    assert mood["limit_up_denominator"] == 2


def pytest_approx(value):
    from pytest import approx
    return approx(value)


def test_audit_large_move_respects_growth_board():
    """创业板单日 +18% 属于正常波动，不应标记为「需核查」的大涨异常。"""
    dates = pd.bdate_range("2024-01-01", periods=30)
    closes = np.linspace(10, 12, len(dates))
    closes[-1] = closes[-2] * 1.18  # 创业板合法大幅上涨
    panel = pd.DataFrame({
        "date": dates, "symbol": "300750", "open": closes * 0.99,
        "high": closes * 1.005, "low": closes * 0.985, "close": closes,
        "volume": 1000.0, "amount": 1000.0 * closes, "turnover": 1.0,
    })
    report, summary = audit_market_data(panel)
    row = report[report["symbol"] == "300750"].iloc[0]
    assert row["status"] == "正常"
    assert int(row["large_move_days"]) == 0


def test_add_and_load_pool_dedupes(tmp_path):
    pool_path = tmp_path / "pool.csv"
    frame = pd.DataFrame({"symbol": ["600000", "1"], "name": ["浦发银行", "平安银行"]})
    updated = add_to_pool(pool_path, frame, source="测试")
    assert len(updated) == 2  # "1" 归一化为 000001
    loaded = load_pool(pool_path)
    assert set(loaded["symbol"]) == {"600000", "000001"}
    # 重复加入保留最后一次来源
    again = pd.DataFrame({"symbol": ["600000"], "name": ["浦发银行"]})
    updated = add_to_pool(pool_path, again, source="再次加入")
    assert updated.loc[updated["symbol"] == "600000", "source"].iloc[0] == "再次加入"
    assert load_pool(pool_path)["symbol"].tolist().count("600000") == 1


def test_make_panel_deterministic():
    p1 = make_panel({"600000": 10.0}, days=30, seed=1)
    p2 = make_panel({"600000": 10.0}, days=30, seed=1)
    pd.testing.assert_frame_equal(p1, p2)
