"""研究模块测试：评分归一化、回测指标、embargo、涨停约束、换手成本。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from conftest import make_panel
from stock_model.research import (
    DEFAULT_WEIGHTS,
    _executed_portfolio_return,
    _metrics,
    _moving_block_bootstrap_ci,
    _newey_west_mean_test,
    _rank,
    embargo_cutoff,
    estimate_conditional_signal_stats,
    exclude_limit_up_entries,
    period_turnover,
    run_walk_forward_backtest,
    select_with_exposure_constraints,
    score_snapshot,
    tradable_exit_at_next_open,
)
from stock_model.benchmarks import prepare_benchmark_returns


def _snapshot() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    rows = []
    for date in pd.to_datetime(["2024-06-03", "2024-06-04"]):
        for i, symbol in enumerate(["600000", "000001", "300750"]):
            rows.append({
                "date": date, "symbol": symbol,
                "ret_20": rng.normal(), "ret_60": rng.normal(), "sma_20_ratio": rng.normal(),
                "vol_20": abs(rng.normal()), "volume_ratio_20": rng.uniform(0.5, 2),
                "obv_slope_20": rng.normal(), "money_flow_20": rng.normal(),
                "close_position": rng.uniform(), "body_pct": rng.uniform(),
                "lower_shadow_pct": rng.uniform(), "upper_shadow_pct": rng.uniform(),
            })
    return pd.DataFrame(rows)


def test_rank_bounds_and_direction():
    values = pd.Series([1.0, 2.0, 3.0])
    ranked = _rank(values)
    assert ranked.between(0, 100).all()
    assert ranked.iloc[-1] == ranked.max()
    reversed_rank = _rank(values, higher_is_better=False)
    assert reversed_rank.iloc[0] == reversed_rank.max()


def test_score_snapshot_composite_in_range_and_weight_normalization():
    snapshot = _snapshot()
    prediction = pd.Series([0.01, 0.05, -0.02, 0.03, 0.0, 0.02])
    scored = score_snapshot(snapshot, prediction, weights={"model": 10, "technical": 5})
    assert scored["composite_score"].between(0, 100).all()
    # 只保留 model 权重时，综合分应等于模型分
    only_model = score_snapshot(snapshot, prediction, weights={"model": 1, "technical": 0})
    assert np.allclose(only_model["composite_score"], only_model["model_score"])


def test_metrics_known_series():
    returns = pd.Series([0.10, -0.05, 0.02])
    benchmark = pd.Series([0.01, 0.01, 0.01])
    result = _metrics(returns, benchmark, horizon=5)
    equity = (1 + returns).cumprod()
    assert result["periods"] == 3
    assert abs(result["cumulative_return"] - (equity.iloc[-1] - 1)) < 1e-12
    assert abs(result["win_rate"] - 2 / 3) < 1e-12
    drawdown = equity / equity.cummax() - 1
    assert abs(result["max_drawdown"] - drawdown.min()) < 1e-12


def test_embargo_cutoff_excludes_overlapping_labels():
    """训练集截止点必须再前移 horizon 个交易日，剔除标签窗口跨过评估日的样本。"""
    dates = pd.bdate_range("2024-01-01", periods=40)
    asof = dates[20]
    cutoff = embargo_cutoff(dates, asof, horizon=5)
    assert cutoff == dates[15]
    # horizon 超过可用历史时退化为最早日期（训练集为空，由调用方跳过）
    assert embargo_cutoff(dates, dates[3], horizon=10) == dates[0]


def test_exclude_limit_up_entries_board_aware():
    snapshot = pd.DataFrame({
        "symbol": ["600000", "300750", "688001", "000001"],
        "daily_return": [0.099, 0.199, 0.198, 0.05],  # 主板涨停/创业板涨停/科创板涨停/正常
    })
    mask = exclude_limit_up_entries(snapshot)
    assert list(snapshot.loc[mask, "symbol"]) == ["000001"]
    # 主板 9.9% 不应误伤 20cm 板块
    growth = pd.DataFrame({"symbol": ["300750"], "daily_return": [0.10]})
    assert exclude_limit_up_entries(growth).all()


def test_limit_down_or_suspended_holding_is_forced_to_remain():
    snapshot = pd.DataFrame({
        "symbol": ["600000", "000001", "300750"],
        "entry_gap_return": [-0.099, 0.0, 0.0], "entry_volume": [1000, 0, 1000],
        "composite_score": [1.0, 2.0, 100.0],
    })
    tradable = tradable_exit_at_next_open(snapshot)
    assert tradable.tolist() == [False, False, True]
    selected = select_with_exposure_constraints(snapshot, 2, required_symbols={"600000"})
    assert set(selected["symbol"]) == {"600000", "300750"}


def test_period_turnover():
    assert period_turnover(set(), {"A", "B"}, 2) == 1.0  # 建仓期全额成本
    assert period_turnover({"A", "B"}, {"A", "B"}, 2) == 0.0  # 未换仓零成本
    assert period_turnover({"A", "B"}, {"A", "C"}, 2) == pytest.approx(0.5)


def test_execution_applies_two_sided_costs_and_partial_fills():
    selected = pd.DataFrame({
        "symbol": ["A", "B"], "future_return": [0.10, 0.20],
        "amount_ma20": [1_000_000.0, 1_000_000.0],
    })
    result = _executed_portfolio_return(
        selected, {"A", "C"}, 2, buy_cost_bps=20, sell_cost_bps=30,
        slippage_bps=10, portfolio_capital=200_000, max_participation_rate=0.05,
    )
    assert result["buy_turnover"] == pytest.approx(0.5)
    assert result["sell_turnover"] == pytest.approx(0.5)
    assert result["average_fill_ratio"] == pytest.approx(0.75)
    assert result["gross_return"] == pytest.approx(0.10)
    assert result["transaction_cost"] == pytest.approx(0.0035)


def test_robust_ic_statistics_are_deterministic():
    values = pd.Series([0.04, 0.01, 0.06, -0.01, 0.03, 0.02, 0.05, 0.01, 0.04, 0.02])
    assert _moving_block_bootstrap_ci(values, samples=500, seed=7) == _moving_block_bootstrap_ci(values, samples=500, seed=7)
    low, high = _moving_block_bootstrap_ci(values, samples=500, seed=7)
    assert low < values.mean() < high
    standard_error, statistic, p_value = _newey_west_mean_test(values)
    assert standard_error > 0
    assert statistic > 0
    assert 0 <= p_value <= 1


def test_external_benchmark_returns_match_next_open_execution():
    dates = pd.bdate_range("2024-01-01", periods=8)
    history = pd.DataFrame({"date": dates, "open": np.arange(10.0, 18.0), "close": np.arange(10.5, 18.5)})
    result = prepare_benchmark_returns(history, horizon=2)
    expected = history.loc[3, "open"] / history.loc[1, "open"] - 1
    assert result.loc[result["date"] == dates[0], "benchmark_return"].iloc[0] == pytest.approx(expected)


def test_conditional_signal_stats_use_non_overlapping_archived_signals():
    dates = pd.bdate_range("2024-01-01", periods=12)
    frame = pd.DataFrame({
        "date": list(dates) * 2,
        "symbol": ["600000"] * len(dates) + ["000001"] * len(dates),
        "future_return": [0.10, 0.20, -0.10, 0.30, 0.10, -0.20, 0.10, 0.10, 0.10, 0.10, np.nan, np.nan] * 2,
    })
    history = pd.DataFrame({
        "archive_time": [f"2024-01-{i + 1:02d} 18:00:00" for i in range(10) for _ in range(2)],
        "date": [date for date in dates[:10] for _ in range(2)],
        "symbol": [symbol for _ in range(10) for symbol in ["600000", "000001"]],
        "composite_score": [90.0, 10.0] * 10,
    })
    result = estimate_conditional_signal_stats(frame, history, horizon=5, score_quantile=0.9)
    row = result[result["symbol"] == "600000"].iloc[0]
    assert row["conditional_sample_count"] == 2
    assert row["conditional_win_rate"] == pytest.approx(0.5)
    assert row["conditional_win_rate_low"] < row["conditional_win_rate"] < row["conditional_win_rate_high"]


def test_walk_forward_backtest_runs_and_reports_ic():
    """端到端小样本回测：应产出逐期记录、IC 指标与分位收益列。"""
    panel = make_panel({"600000": 10.0, "000001": 20.0, "300750": 50.0, "688001": 80.0},
                       days=220, seed=21)
    from stock_model.features import build_features

    frame, features = build_features(panel, horizon=5)
    periods, metrics = run_walk_forward_backtest(
        frame, features, horizon=5, top_k=2, min_train_days=40, max_points=6,
        transaction_cost_bps=20.0, exclude_limit_up=True)
    assert not periods.empty
    assert metrics["periods"] == len(periods)
    assert "ic_mean" in metrics and "icir" in metrics
    assert metrics["ic_confidence_method"] == "moving_block_bootstrap"
    assert set(metrics["simple_baselines"]) == {"model_only", "momentum_20", "momentum_60", "low_volatility"}
    assert len(metrics["cost_sensitivity"]) == 4
    for column in ["ic", "turnover", "q1_return", "q5_return"]:
        assert column in periods.columns
    # 涨停过滤开启时，任何入选股票的信号日涨幅都不得触及板块涨停阈值
    from stock_model.quality import board_limit_threshold

    for _, row in periods.iterrows():
        day = frame[frame["date"] == row["date"]]
        for symbol in str(row["selected_symbols"]).split(","):
            limit = board_limit_threshold(symbol)
            assert float(day.loc[day["symbol"] == symbol, "daily_return"].iloc[0]) < limit
