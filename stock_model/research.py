from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score

from .quality import board_limit_threshold
from .sentiment import latest_sentiment_snapshot


DEFAULT_WEIGHTS = {"model": 0.35, "technical": 0.25, "volume_price": 0.20, "candle": 0.10, "sentiment": 0.10}


def model_target(frame: pd.DataFrame) -> str:
    if "future_industry_excess_return" in frame and frame["future_industry_excess_return"].notna().mean() >= 0.80:
        return "future_industry_excess_return"
    return "future_excess_return" if "future_excess_return" in frame.columns else "future_return"


def model_matrix(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Use daily cross-sectional ranks to reduce scale and identity leakage."""
    numeric = frame[features].apply(pd.to_numeric, errors="coerce")
    if "date" not in frame:
        return numeric
    ranked = numeric.groupby(pd.to_datetime(frame["date"])).rank(method="average", pct=True)
    return ranked.fillna(0.5).clip(0.01, 0.99)


def neutralize_prediction(snapshot: pd.DataFrame, prediction) -> np.ndarray:
    """Remove broad industry and market-cap exposures when metadata is adequate."""
    values = pd.Series(np.asarray(prediction, dtype=float), index=snapshot.index)
    controls = []
    if "market_cap" in snapshot and pd.to_numeric(snapshot["market_cap"], errors="coerce").gt(0).mean() >= 0.80:
        log_cap = np.log(pd.to_numeric(snapshot["market_cap"], errors="coerce").clip(lower=1))
        controls.append(log_cap.rank(pct=True).rename("market_cap"))
    if "industry" in snapshot and snapshot["industry"].notna().mean() >= 0.80:
        dummies = pd.get_dummies(snapshot["industry"], prefix="industry", dtype=float, drop_first=True)
        controls.extend([dummies[column] for column in dummies.columns])
    if not controls or len(snapshot) <= len(controls) + 5:
        return values.to_numpy()
    design = pd.concat(controls, axis=1).fillna(0.5)
    design.insert(0, "intercept", 1.0)
    fitted = design.to_numpy() @ np.linalg.lstsq(design.to_numpy(), values.to_numpy(), rcond=None)[0]
    return (values - fitted).to_numpy()


def load_score_history(archive_dir: Path) -> pd.DataFrame:
    """Load versioned daily score snapshots with a union of evolving columns."""
    frames = []
    for path in sorted(archive_dir.glob("scores_????????.csv")):
        try:
            frame = pd.read_csv(path, dtype={"symbol": str})
            if "archive_time" not in frame:
                frame.insert(0, "archive_time", pd.Timestamp(path.stem[-8:]).strftime("%Y-%m-%d 00:00:00"))
            frames.append(frame)
        except Exception:
            continue
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def make_estimator(num_leaves: int = 31):
    try:
        from lightgbm import LGBMRegressor

        return LGBMRegressor(
            objective="regression",
            n_estimators=300,
            learning_rate=0.03,
            num_leaves=int(num_leaves),
            max_depth=8,
            min_data_in_leaf=20,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbosity=-1,
        )
    except ImportError:
        from sklearn.ensemble import HistGradientBoostingRegressor

        return HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, random_state=42)


def _rank(values: pd.Series, higher_is_better: bool = True) -> pd.Series:
    result = values.rank(pct=True, method="average") * 100
    return result if higher_is_better else 100 - result


def _date_rank(frame: pd.DataFrame, column: str, higher_is_better: bool = True) -> pd.Series:
    return frame.groupby("date", group_keys=False)[column].transform(lambda values: _rank(values, higher_is_better))


def score_snapshot(snapshot: pd.DataFrame, model_prediction: pd.Series, sentiment: pd.DataFrame | None = None,
                   weights: dict[str, float] | None = None) -> pd.DataFrame:
    """Create transparent 0-100 component scores for one or more as-of dates."""
    weights = DEFAULT_WEIGHTS.copy() if weights is None else {
        key: float(weights.get(key, 0.0)) for key in DEFAULT_WEIGHTS
    }
    total = sum(max(float(value), 0) for value in weights.values()) or 1.0
    weights = {key: max(float(value), 0) / total for key, value in weights.items()}
    scored = snapshot.copy()
    scored["model_raw"] = np.asarray(model_prediction, dtype=float)
    scored["model_score"] = _date_rank(scored, "model_raw")
    scored["technical_score"] = (
        _date_rank(scored, "ret_20") * 0.35
        + _date_rank(scored, "ret_60") * 0.25
        + _date_rank(scored, "sma_20_ratio") * 0.20
        + _date_rank(scored, "vol_20", False) * 0.20
    )
    vwap_or_ret = _date_rank(scored, "vwap_dev") if "vwap_dev" in scored.columns else _date_rank(scored, "ret_20")
    scored["volume_price_score"] = (
        _date_rank(scored, "volume_ratio_20") * 0.30
        + _date_rank(scored, "obv_slope_20") * 0.25
        + _date_rank(scored, "money_flow_20") * 0.25
        + vwap_or_ret * 0.20
    )
    scored["candle_score"] = (
        _date_rank(scored, "close_position") * 0.35
        + _date_rank(scored, "body_pct") * 0.20
        + _date_rank(scored, "lower_shadow_pct") * 0.25
        + _date_rank(scored, "upper_shadow_pct", False) * 0.20
    )
    scored["sentiment_score"] = 50.0
    scored["sentiment_source"] = "未提供/中性"
    scored["news_count"] = 0
    if sentiment is not None and not sentiment.empty:
        sentiment = sentiment.copy()
        sentiment["symbol"] = sentiment["symbol"].astype(str).str.zfill(6)
        scored["symbol"] = scored["symbol"].astype(str).str.zfill(6)
        scored = scored.merge(sentiment[["symbol", "sentiment_score", "sentiment_source", "news_count"]], on="symbol", how="left", suffixes=("", "_news"))
        scored["sentiment_score"] = scored["sentiment_score_news"].fillna(50.0)
        scored["sentiment_source"] = scored["sentiment_source_news"].fillna("未提供/中性")
        scored["news_count"] = scored["news_count_news"].fillna(0).astype(int)
        scored = scored.drop(columns=["sentiment_score_news", "sentiment_source_news", "news_count_news"])
    scored["composite_score"] = (
        scored["model_score"] * weights["model"]
        + scored["technical_score"] * weights["technical"]
        + scored["volume_price_score"] * weights["volume_price"]
        + scored["candle_score"] * weights["candle"]
        + scored["sentiment_score"] * weights["sentiment"]
    )
    return scored.sort_values(["date", "composite_score"], ascending=[True, False]).reset_index(drop=True)


def _metrics(returns: pd.Series, benchmark: pd.Series, horizon: int) -> dict[str, float | int]:
    returns = pd.to_numeric(returns, errors="coerce").dropna()
    benchmark = pd.to_numeric(benchmark, errors="coerce").dropna()
    if returns.empty:
        return {"periods": 0, "cumulative_return": 0.0, "annualized_return": 0.0, "max_drawdown": 0.0, "sharpe": 0.0, "win_rate": 0.0, "benchmark_return": 0.0}
    equity = (1 + returns).cumprod()
    drawdown = equity / equity.cummax() - 1
    annual_factor = 252 / max(horizon, 1)
    annualized = float(equity.iloc[-1] ** (annual_factor / len(returns)) - 1) if equity.iloc[-1] > 0 else -1.0
    volatility = float(returns.std() * math.sqrt(annual_factor)) if returns.std() > 0 else 0.0
    sharpe = float(returns.mean() / returns.std() * math.sqrt(annual_factor)) if returns.std() > 0 else 0.0
    downside = returns.clip(upper=0)
    downside_deviation = float(np.sqrt((downside ** 2).mean()))
    sortino = float(returns.mean() / downside_deviation * math.sqrt(annual_factor)) if downside_deviation > 0 else 0.0
    calmar = float(annualized / abs(drawdown.min())) if drawdown.min() < 0 else 0.0
    paired = pd.concat([returns.rename("portfolio"), benchmark.rename("benchmark")], axis=1).dropna()
    excess = paired["portfolio"] - paired["benchmark"] if not paired.empty else pd.Series(dtype=float)
    information_ratio = float(excess.mean() / excess.std() * math.sqrt(annual_factor)) if excess.std() > 0 else 0.0
    loss_runs = returns.lt(0).astype(int).groupby(returns.ge(0).cumsum()).sum()
    return {"periods": int(len(returns)), "cumulative_return": float(equity.iloc[-1] - 1), "annualized_return": annualized,
            "annualized_volatility": volatility, "max_drawdown": float(drawdown.min()), "sharpe": sharpe,
            "sortino": sortino, "calmar": calmar, "information_ratio": information_ratio,
            "win_rate": float((returns > 0).mean()),
            "excess_win_rate": float((excess > 0).mean()) if not excess.empty else 0.0,
            "max_consecutive_losses": int(loss_runs.max()) if not loss_runs.empty else 0,
            "benchmark_return": float((1 + benchmark).prod() - 1) if not benchmark.empty else 0.0}


def estimate_reward_risk(frame: pd.DataFrame) -> pd.DataFrame:
    """Estimate historical reward/risk statistics for each symbol."""
    records: list[dict[str, object]] = []
    labeled = frame.dropna(subset=["symbol", "future_return"])
    for symbol, values in labeled.groupby("symbol")["future_return"]:
        returns = pd.to_numeric(values, errors="coerce").dropna()
        gains = returns[returns > 0]
        losses = returns[returns < 0]
        avg_gain = float(gains.mean()) if not gains.empty else np.nan
        avg_loss = float(-losses.mean()) if not losses.empty else np.nan
        win_rate = float((returns > 0).mean()) if not returns.empty else np.nan
        reward_risk = avg_gain / avg_loss if pd.notna(avg_gain) and pd.notna(avg_loss) and avg_loss > 0 else np.nan
        expected_return = win_rate * avg_gain - (1 - win_rate) * avg_loss if pd.notna(avg_gain) and pd.notna(avg_loss) else np.nan
        records.append({
            "symbol": str(symbol),
            "odds_sample_count": int(len(returns)),
            "odds_win_rate": win_rate,
            "odds_avg_gain": avg_gain,
            "odds_avg_loss": avg_loss,
            "odds_reward_risk": reward_risk,
            "odds_expected_return": expected_return,
        })
    return pd.DataFrame(records)


def estimate_conditional_signal_stats(
    frame: pd.DataFrame, score_history: pd.DataFrame | None, horizon: int,
    score_quantile: float = 0.9,
) -> pd.DataFrame:
    """Estimate outcomes only when an archived signal was historically strong.

    Repeated runs on the same date are deduplicated and observations for each
    stock are spaced by at least ``horizon`` trading days, avoiding the false
    precision caused by overlapping forward-return windows.
    """
    columns = [
        "symbol", "conditional_sample_count", "conditional_win_rate",
        "conditional_win_rate_low", "conditional_win_rate_high",
        "conditional_expected_return", "conditional_return_low",
        "conditional_return_high", "conditional_reward_risk",
    ]
    if score_history is None or score_history.empty:
        return pd.DataFrame(columns=columns)
    required = {"date", "symbol", "composite_score"}
    if not required.issubset(score_history.columns):
        return pd.DataFrame(columns=columns)
    history = score_history.copy()
    history["date"] = pd.to_datetime(history["date"], errors="coerce")
    history["symbol"] = history["symbol"].astype(str).str.zfill(6)
    history["composite_score"] = pd.to_numeric(history["composite_score"], errors="coerce")
    sort_columns = ["date", "symbol"] + (["archive_time"] if "archive_time" in history else [])
    history = history.dropna(subset=["date", "composite_score"]).sort_values(sort_columns)
    history = history.drop_duplicates(["date", "symbol"], keep="last")
    history["score_percentile"] = history.groupby("date")["composite_score"].rank(pct=True, method="average")
    history = history[history["score_percentile"] >= float(score_quantile)]

    if "future_return" in history.columns:
        history = history.drop(columns=["future_return"])

    outcomes = frame[["date", "symbol", "future_return"]].dropna().copy()
    outcomes["date"] = pd.to_datetime(outcomes["date"])
    outcomes["symbol"] = outcomes["symbol"].astype(str).str.zfill(6)
    matched = history.merge(outcomes, on=["date", "symbol"], how="inner", suffixes=("_history", ""))
    if matched.empty:
        return pd.DataFrame(columns=columns)
    calendar = {date: index for index, date in enumerate(sorted(pd.to_datetime(frame["date"]).unique()))}
    records = []
    for symbol, stock in matched.sort_values("date").groupby("symbol"):
        accepted = []
        last_position = -max(int(horizon), 1)
        for _, signal in stock.iterrows():
            position = calendar.get(pd.Timestamp(signal["date"]))
            if position is not None and position - last_position >= max(int(horizon), 1):
                accepted.append(float(signal["future_return"]))
                last_position = position
        returns = pd.Series(accepted, dtype=float).dropna()
        if returns.empty:
            continue
        n = len(returns)
        wins = int((returns > 0).sum())
        p = wins / n
        z = 1.96
        denominator = 1 + z * z / n
        center = (p + z * z / (2 * n)) / denominator
        half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
        standard_error = float(returns.std(ddof=1) / math.sqrt(n)) if n > 1 else float("nan")
        gains, losses = returns[returns > 0], -returns[returns < 0]
        reward_risk = float(gains.mean() / losses.mean()) if not gains.empty and not losses.empty and losses.mean() > 0 else np.nan
        records.append({
            "symbol": symbol, "conditional_sample_count": n,
            "conditional_win_rate": p,
            "conditional_win_rate_low": max(0.0, center - half),
            "conditional_win_rate_high": min(1.0, center + half),
            "conditional_expected_return": float(returns.mean()),
            "conditional_return_low": float(returns.mean() - z * standard_error) if pd.notna(standard_error) else np.nan,
            "conditional_return_high": float(returns.mean() + z * standard_error) if pd.notna(standard_error) else np.nan,
            "conditional_reward_risk": reward_risk,
        })
    return pd.DataFrame(records, columns=columns)


def add_signal_credibility(
    latest: pd.DataFrame, score_history: pd.DataFrame | None,
    backtest_metrics: dict[str, object] | None,
) -> pd.DataFrame:
    """Add evidence-quality scores that are separate from the alpha ranking."""
    result = latest.copy()
    def numeric_column(name: str, default: float) -> pd.Series:
        if name not in result:
            return pd.Series(default, index=result.index, dtype=float)
        return pd.to_numeric(result[name], errors="coerce").fillna(default)

    components = ["model_score", "technical_score", "volume_price_score", "candle_score", "sentiment_score"]
    dispersion = result[components].std(axis=1)
    agreement = (result[components].ge(50).mean(axis=1) * 50 + (100 - dispersion.mul(2)).clip(0, 100) * 0.5)

    stability = pd.Series(30.0, index=result.index)
    if score_history is not None and not score_history.empty and {"date", "symbol", "composite_score"}.issubset(score_history.columns):
        history = score_history.copy()
        history["date"] = pd.to_datetime(history["date"], errors="coerce")
        if "archive_time" in history:
            latest_archive = history["archive_time"].astype(str).max()
            history = history[history["archive_time"].astype(str) == latest_archive]
        history["symbol"] = history["symbol"].astype(str).str.zfill(6)
        history = history.sort_values("composite_score", ascending=False).drop_duplicates("symbol")
        previous_percentile = history.set_index("symbol")["composite_score"].rank(pct=True)
        current_percentile = result["composite_score"].rank(pct=True)
        symbols = result["symbol"].astype(str).str.zfill(6)
        previous = symbols.map(previous_percentile)
        known = previous.notna()
        stability.loc[known] = (100 - (current_percentile.loc[known] - previous.loc[known]).abs() * 100).clip(0, 100)

    n = numeric_column("conditional_sample_count", 0)
    win_low = numeric_column("conditional_win_rate_low", 0)
    return_low = numeric_column("conditional_return_low", -0.10)
    conditional = (
        n.div(20).clip(0, 1).mul(50)
        + win_low.sub(0.40).div(0.20).clip(0, 1).mul(25)
        + return_low.add(0.05).div(0.10).clip(0, 1).mul(25)
    )

    metrics = backtest_metrics or {}
    if {"ic_mean", "q5_q1_mean_return", "excess_win_rate"}.issubset(metrics):
        strategy = float(np.mean([
            np.clip(float(metrics.get("ic_mean", 0)) / 0.05 * 100, 0, 100),
            np.clip(float(metrics.get("q5_q1_mean_return", 0)) / 0.05 * 100, 0, 100),
            np.clip((float(metrics.get("excess_win_rate", 0.5)) - 0.5) / 0.15 * 100, 0, 100),
        ]))
    else:
        strategy = 25.0
    news_coverage = numeric_column("news_count", 0).gt(0).astype(float) * 100
    credibility = strategy * 0.30 + conditional * 0.30 + stability * 0.20 + agreement * 0.15 + news_coverage * 0.05
    result["credibility_score"] = credibility.clip(0, 100)
    result["credibility_grade"] = np.where(
        (result["credibility_score"] >= 70) & (n >= 10) & (strategy >= 50), "高",
        np.where(result["credibility_score"] >= 50, "中", "低"),
    )
    result["credibility_strategy"] = strategy
    result["credibility_conditional"] = conditional
    result["credibility_stability"] = stability
    result["credibility_agreement"] = agreement
    return result


def score_robustness_diagnostics(
    scored: pd.DataFrame, weights: dict[str, float], top_k: int,
) -> dict[str, object]:
    factor_keys = ["model", "technical", "volume_price", "candle", "sentiment"]
    columns = [f"{key}_score" for key in factor_keys]
    correlation = scored[columns].corr(method="spearman")
    pairs = []
    for left_index, left in enumerate(columns):
        for right in columns[left_index + 1:]:
            value = correlation.loc[left, right]
            pairs.append({"left": left, "right": right, "correlation": float(value) if pd.notna(value) else None})
    baseline = scored["composite_score"]
    baseline_top = set(scored.nlargest(min(top_k, len(scored)), "composite_score")["symbol"].astype(str))
    tests = []
    for omitted in factor_keys:
        remaining = {key: value for key, value in weights.items() if key != omitted}
        total = sum(remaining.values()) or 1.0
        alternative = sum(scored[f"{key}_score"] * value / total for key, value in remaining.items())
        alternative_top = set(scored.assign(_score=alternative).nlargest(min(top_k, len(scored)), "_score")["symbol"].astype(str))
        tests.append({
            "test": f"omit_{omitted}",
            "rank_correlation": float(baseline.corr(alternative, method="spearman")),
            "top_k_overlap": float(len(baseline_top & alternative_top) / max(len(baseline_top), 1)),
        })
    for stressed in factor_keys:
        adjusted = dict(weights)
        adjusted[stressed] = adjusted.get(stressed, 0) * 1.2
        total = sum(adjusted.values()) or 1.0
        alternative = sum(scored[f"{key}_score"] * value / total for key, value in adjusted.items())
        alternative_top = set(scored.assign(_score=alternative).nlargest(min(top_k, len(scored)), "_score")["symbol"].astype(str))
        tests.append({
            "test": f"weight_plus_20pct_{stressed}",
            "rank_correlation": float(baseline.corr(alternative, method="spearman")),
            "top_k_overlap": float(len(baseline_top & alternative_top) / max(len(baseline_top), 1)),
        })
    return {
        "factor_correlations": pairs,
        "max_absolute_factor_correlation": max((abs(item["correlation"]) for item in pairs if item["correlation"] is not None), default=0.0),
        "robustness_tests": tests,
        "minimum_rank_correlation": min((item["rank_correlation"] for item in tests), default=0.0),
        "minimum_top_k_overlap": min((item["top_k_overlap"] for item in tests), default=0.0),
    }


def embargo_cutoff(dates, asof, horizon: int) -> pd.Timestamp:
    calendar = pd.DatetimeIndex(sorted(pd.to_datetime(pd.Index(dates)).unique()))
    if calendar.empty:
        raise ValueError("交易日历为空")
    position = int(calendar.searchsorted(pd.Timestamp(asof), side="left"))
    return pd.Timestamp(calendar[max(0, position - max(int(horizon), 0))])


def exclude_limit_up_entries(snapshot: pd.DataFrame) -> pd.Series:
    return_column = "entry_gap_return" if "entry_gap_return" in snapshot else "daily_return"
    returns = pd.to_numeric(snapshot.get(return_column), errors="coerce")
    thresholds = snapshot["symbol"].astype(str).map(board_limit_threshold)
    if "is_st" in snapshot:
        thresholds = thresholds.where(~snapshot["is_st"].fillna(False).astype(bool), 0.048)
    eligible = returns.notna() & returns.lt(thresholds)
    volume_column = "entry_volume" if "entry_volume" in snapshot else "volume"
    if volume_column in snapshot:
        eligible &= pd.to_numeric(snapshot[volume_column], errors="coerce").fillna(0).gt(0)
    return eligible


def tradable_exit_at_next_open(snapshot: pd.DataFrame) -> pd.Series:
    """Whether an existing holding can be sold at the next session open."""
    returns = pd.to_numeric(snapshot.get("entry_gap_return"), errors="coerce")
    thresholds = snapshot["symbol"].astype(str).map(board_limit_threshold)
    if "is_st" in snapshot:
        thresholds = thresholds.where(~snapshot["is_st"].fillna(False).astype(bool), 0.048)
    tradable = returns.notna() & returns.gt(-thresholds)
    if "entry_volume" in snapshot:
        tradable &= pd.to_numeric(snapshot["entry_volume"], errors="coerce").fillna(0).gt(0)
    return tradable


def period_turnover(previous: set[str], current: set[str], target_count: int) -> float:
    return float(min(len(current - previous) / max(int(target_count), 1), 1.0))


def trade_turnover(previous: set[str], current: set[str], target_count: int) -> tuple[float, float]:
    """Return one-way buy and sell turnover for an equal-weight portfolio."""
    denominator = max(int(target_count), 1)
    return (
        float(min(len(current - previous) / denominator, 1.0)),
        float(min(len(previous - current) / denominator, 1.0)),
    )


def _executed_portfolio_return(
    selected: pd.DataFrame,
    previous_symbols: set[str],
    top_k: int,
    buy_cost_bps: float,
    sell_cost_bps: float,
    slippage_bps: float,
    portfolio_capital: float,
    max_participation_rate: float,
) -> dict[str, object]:
    """Apply equal-weight capacity, partial-fill and two-sided cost assumptions."""
    symbols = selected["symbol"].astype(str).str.zfill(6)
    current_symbols = set(symbols)
    normalized_previous = {str(symbol).zfill(6) for symbol in previous_symbols}
    buy_turnover, sell_turnover = trade_turnover(normalized_previous, current_symbols, top_k)
    target_weight = 1.0 / max(int(top_k), 1)
    fill = pd.Series(1.0, index=selected.index, dtype=float)
    if portfolio_capital > 0 and max_participation_rate > 0:
        target_amount = float(portfolio_capital) * target_weight
        liquidity = pd.to_numeric(selected.get("amount_ma20"), errors="coerce")
        new_position = ~symbols.isin(normalized_previous).to_numpy()
        capacity_fill = (liquidity * float(max_participation_rate) / target_amount).clip(0, 1).fillna(0)
        fill.loc[new_position] = capacity_fill.loc[new_position]
    returns = pd.to_numeric(selected["future_return"], errors="coerce").fillna(0)
    gross_return = float((returns * fill * target_weight).sum())
    cost = (
        buy_turnover * (float(buy_cost_bps) + float(slippage_bps))
        + sell_turnover * (float(sell_cost_bps) + float(slippage_bps))
    ) / 10000
    return {
        "symbols": current_symbols,
        "gross_return": gross_return,
        "portfolio_return": gross_return - cost,
        "transaction_cost": float(cost),
        "turnover": float(max(buy_turnover, sell_turnover)),
        "buy_turnover": buy_turnover,
        "sell_turnover": sell_turnover,
        "average_fill_ratio": float(fill.mean()) if not fill.empty else 0.0,
        "partial_fill_count": int(fill.lt(1).sum()),
    }


def _moving_block_bootstrap_ci(values: pd.Series, samples: int = 2000, seed: int = 42) -> tuple[float | None, float | None]:
    """Deterministic moving-block bootstrap confidence interval for a mean."""
    clean = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    n = len(clean)
    if n < 8:
        return None, None
    block = max(2, int(round(n ** (1 / 3))))
    rng = np.random.default_rng(seed)
    starts = np.arange(n)
    means = np.empty(max(int(samples), 200), dtype=float)
    for index in range(len(means)):
        chosen = []
        while len(chosen) < n:
            start = int(rng.choice(starts))
            chosen.extend(clean[(start + offset) % n] for offset in range(block))
        means[index] = float(np.mean(chosen[:n]))
    low, high = np.quantile(means, [0.025, 0.975])
    return float(low), float(high)


def _newey_west_mean_test(values: pd.Series) -> tuple[float | None, float | None, float | None]:
    """Return HAC standard error, t statistic and two-sided normal p value."""
    clean = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    n = len(clean)
    if n < 8:
        return None, None, None
    demeaned = clean - clean.mean()
    lag = max(1, int(np.floor(4 * (n / 100) ** (2 / 9))))
    long_run_variance = float(np.dot(demeaned, demeaned) / n)
    for offset in range(1, min(lag, n - 1) + 1):
        covariance = float(np.dot(demeaned[offset:], demeaned[:-offset]) / n)
        long_run_variance += 2 * (1 - offset / (lag + 1)) * covariance
    standard_error = math.sqrt(max(long_run_variance, 0) / n)
    if standard_error <= 0:
        return 0.0, None, None
    statistic = float(clean.mean() / standard_error)
    p_value = float(math.erfc(abs(statistic) / math.sqrt(2)))
    return float(standard_error), statistic, p_value


def _quantile_returns(scored: pd.DataFrame, groups: int = 5) -> dict[str, float]:
    if scored.empty:
        return {f"q{i}_return": float("nan") for i in range(1, groups + 1)}
    buckets = np.minimum(np.ceil(scored["composite_score"].rank(method="first", pct=True) * groups), groups).astype(int)
    values = scored.assign(_bucket=buckets).groupby("_bucket")["future_return"].mean()
    return {f"q{i}_return": float(values.get(i, np.nan)) for i in range(1, groups + 1)}


def select_with_exposure_constraints(
    scored: pd.DataFrame, top_k: int, max_industry_weight: float = 1.0,
    industry_column: str = "industry", required_symbols: set[str] | None = None,
) -> pd.DataFrame:
    """Select by score while capping the number of names per industry.

    Metadata is optional: without an industry column this is exactly a Top-K
    selection, which keeps older datasets and research runs compatible.
    """
    ranked = scored.sort_values("composite_score", ascending=False)
    required = {str(symbol).zfill(6) for symbol in (required_symbols or set())}
    symbol_values = ranked["symbol"].astype(str).str.zfill(6)
    forced = ranked.loc[symbol_values.isin(required)].head(top_k)
    remaining = ranked.loc[~symbol_values.isin(set(forced["symbol"].astype(str).str.zfill(6)))]
    if industry_column not in ranked.columns or max_industry_weight >= 1 or max_industry_weight <= 0:
        return pd.concat([forced, remaining.head(max(top_k - len(forced), 0))])
    cap = max(1, int(np.floor(float(top_k) * max_industry_weight)))
    counts: dict[object, int] = {}
    selected_rows = list(forced.index)
    for _, row in forced.iterrows():
        industry = row.get(industry_column)
        industry = "__unknown__" if pd.isna(industry) else industry
        counts[industry] = counts.get(industry, 0) + 1
    for index, row in remaining.iterrows():
        industry = row.get(industry_column)
        if pd.isna(industry):
            industry = "__unknown__"
        if counts.get(industry, 0) >= cap:
            continue
        selected_rows.append(index)
        counts[industry] = counts.get(industry, 0) + 1
        if len(selected_rows) >= top_k:
            break
    return ranked.loc[selected_rows]


def merge_asof_metadata(frame: pd.DataFrame, metadata: pd.DataFrame | None) -> pd.DataFrame:
    """Attach point-in-time industry/market-cap metadata without look-ahead."""
    if metadata is None or metadata.empty or "symbol" not in metadata:
        return frame
    left = frame.copy()
    meta = metadata.copy()
    left["symbol"] = left["symbol"].astype(str).str.zfill(6)
    meta["symbol"] = meta["symbol"].astype(str).str.zfill(6)
    allowed = [c for c in (
        "industry", "market_cap", "pe_ttm", "pb", "roe", "roic", "revenue_growth",
        "profit_growth", "debt_ratio", "cashflow_quality",
    ) if c in meta.columns]
    if not allowed:
        return left
    if "date" not in meta.columns:
        allowed = [c for c in allowed if c == "industry"]
        return left.merge(meta[["symbol", *allowed]].drop_duplicates("symbol"), on="symbol", how="left") if allowed else left
    meta["date"] = pd.to_datetime(meta["date"], errors="coerce")
    meta = meta.dropna(subset=["date"]).sort_values(["symbol", "date"])
    parts = []
    for symbol, stock in left.groupby("symbol", sort=False):
        history = meta[meta["symbol"] == symbol][["date", *allowed]]
        stock = stock.sort_values("date")
        parts.append(pd.merge_asof(stock, history.sort_values("date"), on="date", direction="backward") if not history.empty else stock.assign(**{c: np.nan for c in allowed}))
    return pd.concat(parts, ignore_index=True).sort_values(["date", "symbol"])


def run_walk_forward_backtest(frame: pd.DataFrame, features: list[str], horizon: int, top_k: int,
                              weights: dict[str, float] | None = None, min_train_days: int = 120,
                              max_points: int = 80, sentiment_history: pd.DataFrame | None = None,
                              transaction_cost_bps: float = 20.0,
                              buy_cost_bps: float | None = None,
                              sell_cost_bps: float | None = None,
                              slippage_bps: float = 0.0,
                              exclude_limit_up: bool = True,
                              min_average_amount: float = 0.0,
                              max_industry_weight: float = 1.0,
                              portfolio_capital: float = 0.0,
                              max_participation_rate: float = 0.05,
                              benchmark_returns: pd.DataFrame | None = None,
                              benchmark_name: str = "eligible_universe_equal_weight",
                              progress: Callable[[int, int, pd.Timestamp], None] | None = None) -> tuple[pd.DataFrame, dict[str, object]]:
    dates = sorted(pd.to_datetime(frame["date"]).unique())
    target = model_target(frame)
    labeled = frame.dropna(subset=[target]).copy()
    if len(dates) <= min_train_days + 2 * horizon:
        raise ValueError(f"有效交易日不足，至少需要 {min_train_days + horizon + 1} 天")
    candidate_dates = dates[min_train_days + horizon:-(horizon + 1):horizon]
    # 保持连续非重叠调仓期，杜绝步长跨度跳空导致的时间断层与复利虚高
    if max_points and len(candidate_dates) > max_points:
        planned_dates = candidate_dates[-max_points:]
    else:
        planned_dates = candidate_dates
    records: list[dict[str, object]] = []
    previous_symbols: set[str] = set()
    previous_baselines = {
        "model_only": set(), "momentum_20": set(), "momentum_60": set(), "low_volatility": set(),
    }
    nested_choices: list[int] = []
    buy_cost_bps = float(transaction_cost_bps if buy_cost_bps is None else buy_cost_bps)
    sell_cost_bps = float(transaction_cost_bps if sell_cost_bps is None else sell_cost_bps)
    external_benchmark = None
    if benchmark_returns is not None and not benchmark_returns.empty:
        external_benchmark = benchmark_returns.copy()
        external_benchmark["date"] = pd.to_datetime(external_benchmark["date"])
        external_benchmark = external_benchmark.dropna(subset=["date", "benchmark_return"]).set_index("date")["benchmark_return"]
    for index, current_date in enumerate(planned_dates, start=1):
        if progress:
            progress(index, len(planned_dates), pd.Timestamp(current_date))
        current_date = pd.Timestamp(current_date)
        cutoff = embargo_cutoff(dates, current_date, horizon)
        train = labeled[labeled["date"] < cutoff]
        day_all = frame[frame["date"] == current_date].copy()
        snapshot_all = day_all.dropna(subset=features).copy()
        if train["date"].nunique() < min_train_days or (snapshot_all.empty and not previous_symbols):
            continue
        sellable_symbols = set(
            day_all.loc[tradable_exit_at_next_open(day_all), "symbol"].astype(str).str.zfill(6)
        ) if not day_all.empty else set()
        forced_symbols = previous_symbols - sellable_symbols
        forced_baselines = {
            name: symbols - sellable_symbols for name, symbols in previous_baselines.items()
        }
        all_forced = set(forced_symbols).union(*(forced_baselines.values()))
        # 停牌或缺失特征的受困持仓必须保留在候选池中连续估值，不可直接从组合中抹除
        missing_forced = all_forced - set(snapshot_all["symbol"].astype(str).str.zfill(6))
        if missing_forced:
            forced_rows = day_all[day_all["symbol"].astype(str).str.zfill(6).isin(missing_forced)].copy()
            absent_forced = missing_forced - set(forced_rows["symbol"].astype(str).str.zfill(6))
            if absent_forced:
                synthetic = pd.DataFrame([
                    {"date": current_date, "symbol": sym, "future_return": 0.0, "amount_ma20": 0.0}
                    for sym in absent_forced
                ])
                forced_rows = pd.concat([forced_rows, synthetic], ignore_index=True)
            for feat in features:
                if feat not in forced_rows:
                    forced_rows[feat] = 0.5
                else:
                    forced_rows[feat] = forced_rows[feat].fillna(0.5)
            if "future_return" not in forced_rows:
                forced_rows["future_return"] = 0.0
            else:
                forced_rows["future_return"] = forced_rows["future_return"].fillna(0.0)
            snapshot_all = pd.concat([snapshot_all, forced_rows], ignore_index=True)

        snapshot_symbols = snapshot_all["symbol"].astype(str).str.zfill(6)
        buy_eligible = pd.Series(True, index=snapshot_all.index)
        if exclude_limit_up:
            buy_eligible &= exclude_limit_up_entries(snapshot_all)
        if min_average_amount > 0:
            liquidity = pd.to_numeric(snapshot_all.get("amount_ma20"), errors="coerce")
            buy_eligible &= liquidity.ge(float(min_average_amount))
        if portfolio_capital > 0 and max_participation_rate > 0:
            liquidity = pd.to_numeric(snapshot_all.get("amount_ma20"), errors="coerce")
            buy_eligible &= liquidity.gt(0)
        snapshot = snapshot_all.loc[buy_eligible | snapshot_symbols.isin(all_forced)].copy()
        if snapshot.empty:
            continue
        if external_benchmark is not None and current_date not in external_benchmark.index:
            continue
        # Nested time-series selection: choose model complexity on an inner,
        # purged validation slice, then refit the selected candidate on all
        # observations available to the outer test date.
        train_dates = sorted(pd.to_datetime(train["date"]).unique())
        inner_split = train_dates[max(1, int(len(train_dates) * 0.8))] if len(train_dates) >= 10 else None
        candidate_leaves = (15, 31)
        selected_leaves = 31
        if inner_split is not None:
            inner_cutoff = embargo_cutoff(train_dates, inner_split, horizon)
            inner_fit = train[train["date"] < inner_cutoff]
            inner_valid = train[train["date"] >= inner_split]
            if not inner_fit.empty and not inner_valid.empty:
                candidate_errors = {}
                for leaves in candidate_leaves:
                    candidate = make_estimator(leaves)
                    candidate.fit(model_matrix(inner_fit, features), inner_fit[target])
                    prediction = candidate.predict(model_matrix(inner_valid, features))
                    candidate_errors[leaves] = float(np.mean(np.abs(prediction - inner_valid[target])))
                selected_leaves = min(candidate_errors, key=candidate_errors.get)
        nested_choices.append(int(selected_leaves))
        estimator = make_estimator(selected_leaves)
        estimator.fit(model_matrix(train, features), train[target])
        date_sentiment = None
        if sentiment_history is not None and not sentiment_history.empty:
            # 舆情文件可能是周频；只使用当日及之前最近30天的记录，不能读取未来情绪。
            history_window = sentiment_history[
                (sentiment_history["date"] <= current_date)
                & (sentiment_history["date"] >= current_date - pd.Timedelta(days=30))
            ].sort_values("date")
            date_sentiment = history_window.groupby("symbol", as_index=False).tail(1) if not history_window.empty else None
        raw_prediction = estimator.predict(model_matrix(snapshot, features))
        scored = score_snapshot(
            snapshot, neutralize_prediction(snapshot, raw_prediction),
            sentiment=date_sentiment, weights=weights,
        )
        selected = select_with_exposure_constraints(
            scored, min(top_k, len(scored)), max_industry_weight, required_symbols=forced_symbols,
        )
        execution = _executed_portfolio_return(
            selected, previous_symbols, top_k, buy_cost_bps, sell_cost_bps, slippage_bps,
            portfolio_capital, max_participation_rate,
        )
        selected_symbols = execution["symbols"]
        selected_liquidity = pd.to_numeric(selected.get("amount_ma20"), errors="coerce")
        estimated_capacity = (
            float(selected_liquidity.min() * max_participation_rate * top_k)
            if selected_liquidity.notna().any() else float("nan")
        )
        benchmark_return = (
            float(external_benchmark.loc[current_date])
            if external_benchmark is not None else float(snapshot["future_return"].mean())
        )
        ic = scored["composite_score"].corr(scored["future_return"], method="spearman")
        industry_weights = {}
        if "industry" in selected.columns:
            industries = selected["industry"].fillna("未知行业").astype(str).replace({"": "未知行业"})
            industry_weights = industries.value_counts(normalize=True).round(6).to_dict()
        selected_market_cap = (
            pd.to_numeric(selected["market_cap"], errors="coerce")
            if "market_cap" in selected else pd.Series(np.nan, index=selected.index, dtype=float)
        )
        baseline_values = {}
        baseline_definitions = {
            "model_only": ("model_score", False),
            "momentum_20": ("ret_20", False),
            "momentum_60": ("ret_60", False),
            "low_volatility": ("vol_20", True),
        }
        for baseline, (column, ascending) in baseline_definitions.items():
            baseline_scored = scored.assign(composite_score=pd.to_numeric(scored[column], errors="coerce") * (-1 if ascending else 1))
            baseline_selected = select_with_exposure_constraints(
                baseline_scored, min(top_k, len(baseline_scored)), max_industry_weight,
                required_symbols=forced_baselines[baseline],
            )
            baseline_execution = _executed_portfolio_return(
                baseline_selected, previous_baselines[baseline], top_k,
                buy_cost_bps, sell_cost_bps, slippage_bps, portfolio_capital, max_participation_rate,
            )
            baseline_values[f"baseline_{baseline}_return"] = baseline_execution["portfolio_return"]
            previous_baselines[baseline] = baseline_execution["symbols"]
        records.append({
            "date": current_date,
            "train_cutoff": cutoff,
            "train_observations": int(len(train)),
            "eligible_count": int(len(snapshot)),
            "selected_count": len(selected),
            "gross_return": execution["gross_return"],
            "turnover": execution["turnover"],
            "buy_turnover": execution["buy_turnover"],
            "sell_turnover": execution["sell_turnover"],
            "transaction_cost": execution["transaction_cost"],
            "portfolio_return": execution["portfolio_return"],
            "benchmark_return": benchmark_return,
            "excess_return": execution["portfolio_return"] - benchmark_return,
            "ic": float(ic) if pd.notna(ic) else np.nan,
            "selected_symbols": ",".join(sorted(selected_symbols)),
            "estimated_capacity": estimated_capacity,
            "average_fill_ratio": execution["average_fill_ratio"],
            "partial_fill_count": execution["partial_fill_count"],
            "forced_hold_count": int(len(forced_symbols)),
            "unresolved_holding_count": int(len(forced_symbols - set(snapshot_symbols))),
            "industry_weights": json.dumps(industry_weights, ensure_ascii=False),
            "max_industry_exposure": float(max(industry_weights.values(), default=0.0)),
            "market_cap_median": float(selected_market_cap.median()) if selected_market_cap.notna().any() else float("nan"),
            "market_cap_mean": float(selected_market_cap.mean()) if selected_market_cap.notna().any() else float("nan"),
            **baseline_values,
            **_quantile_returns(scored),
        })
        previous_symbols = selected_symbols
    periods = pd.DataFrame(records)
    if periods.empty:
        raise ValueError("回测没有生成有效调仓期，请增加股票数量或历史数据")
    periods["date"] = pd.to_datetime(periods["date"])
    periods["equity"] = (1 + periods["portfolio_return"]).cumprod()
    periods["benchmark_equity"] = (1 + periods["benchmark_return"]).cumprod()
    regime_signal = periods["benchmark_return"].rolling(6, min_periods=3).mean()
    periods["market_regime"] = np.select(
        [regime_signal.gt(0.02), regime_signal.lt(-0.02)], ["牛市", "熊市"], default="震荡市",
    )
    result_metrics = _metrics(periods["portfolio_return"], periods["benchmark_return"], horizon)
    result_metrics["schema_version"] = 2
    result_metrics["transaction_cost_bps"] = float(transaction_cost_bps)
    result_metrics["buy_cost_bps"] = buy_cost_bps
    result_metrics["sell_cost_bps"] = sell_cost_bps
    result_metrics["slippage_bps"] = float(slippage_bps)
    result_metrics["average_turnover"] = float(periods["turnover"].mean())
    result_metrics["average_buy_turnover"] = float(periods["buy_turnover"].mean())
    result_metrics["average_sell_turnover"] = float(periods["sell_turnover"].mean())
    result_metrics["average_fill_ratio"] = float(periods["average_fill_ratio"].mean())
    result_metrics["partial_fill_periods"] = int(periods["partial_fill_count"].gt(0).sum())
    result_metrics["forced_hold_periods"] = int(periods["forced_hold_count"].gt(0).sum())
    result_metrics["forced_hold_events"] = int(periods["forced_hold_count"].sum())
    result_metrics["unresolved_holding_events"] = int(periods["unresolved_holding_count"].sum())
    result_metrics["cumulative_excess_return"] = float(
        (1 + periods["portfolio_return"]).prod() - (1 + periods["benchmark_return"]).prod()
    )
    valid_ic = periods["ic"].dropna()
    ic_std = float(valid_ic.std(ddof=1)) if len(valid_ic) > 1 else 0.0
    result_metrics["ic_mean"] = float(valid_ic.mean()) if not valid_ic.empty else 0.0
    result_metrics["ic_std"] = ic_std
    result_metrics["icir"] = float(valid_ic.mean() / ic_std) if ic_std > 0 else 0.0
    result_metrics["ic_positive_ratio"] = float(valid_ic.gt(0).mean()) if not valid_ic.empty else 0.0
    bootstrap_low, bootstrap_high = _moving_block_bootstrap_ci(valid_ic)
    result_metrics["ic_confidence_method"] = "moving_block_bootstrap"
    result_metrics["ic_confidence_low"] = bootstrap_low
    result_metrics["ic_confidence_high"] = bootstrap_high
    hac_se, ic_t_stat, ic_p_value = _newey_west_mean_test(valid_ic)
    result_metrics["ic_hac_standard_error"] = hac_se
    result_metrics["ic_t_stat"] = ic_t_stat
    result_metrics["ic_p_value"] = ic_p_value
    result_metrics["ic_hypotheses"] = 4
    result_metrics["ic_p_value_adjusted"] = (
        min(1.0, float(ic_p_value) * result_metrics["ic_hypotheses"])
        if ic_p_value is not None else None
    )
    quantile_means = {f"q{i}_mean_return": float(periods[f'q{i}_return'].mean()) for i in range(1, 6)}
    result_metrics.update(quantile_means)
    q5_q1 = periods["q5_return"] - periods["q1_return"]
    result_metrics["q5_q1_mean_return"] = float(q5_q1.mean())
    result_metrics["q5_q1_win_rate"] = float((q5_q1 > 0).mean())
    q_values = pd.Series([quantile_means[f"q{i}_mean_return"] for i in range(1, 6)], index=range(1, 6))
    result_metrics["quantile_monotonicity"] = float(q_values.corr(pd.Series(range(1, 6), index=range(1, 6)), method="spearman"))
    result_metrics["average_eligible_count"] = float(periods["eligible_count"].mean())
    result_metrics["horizon_days"] = int(horizon)
    result_metrics["rebalance_days"] = int(horizon)
    result_metrics["embargo_days"] = int(horizon)
    result_metrics["benchmark_name"] = str(benchmark_name)
    result_metrics["exclude_limit_up"] = bool(exclude_limit_up)
    result_metrics["min_average_amount"] = float(min_average_amount)
    result_metrics["portfolio_capital"] = float(portfolio_capital)
    result_metrics["max_participation_rate"] = float(max_participation_rate)
    result_metrics["median_estimated_capacity"] = float(periods["estimated_capacity"].median())
    result_metrics["minimum_estimated_capacity"] = float(periods["estimated_capacity"].min())
    result_metrics["max_industry_weight"] = float(max_industry_weight)
    result_metrics["industry_constraint_applied"] = bool("industry" in frame.columns and max_industry_weight < 1.0)
    result_metrics["data_end"] = str(pd.Timestamp(frame["date"].max()).date())
    result_metrics["sentiment_history_used"] = bool(sentiment_history is not None and not sentiment_history.empty)
    result_metrics["target_definition"] = target
    result_metrics["feature_transform"] = "daily_cross_sectional_percentile_rank"
    result_metrics["metadata_industry_coverage"] = (
        float(frame["industry"].notna().mean()) if "industry" in frame else 0.0
    )
    result_metrics["metadata_market_cap_coverage"] = (
        float(pd.to_numeric(frame["market_cap"], errors="coerce").gt(0).mean()) if "market_cap" in frame else 0.0
    )
    baseline_labels = {
        "model_only": "仅模型评分",
        "momentum_20": "20日动量",
        "momentum_60": "60日动量",
        "low_volatility": "低波动",
    }
    simple_baselines = {}
    for baseline, label in baseline_labels.items():
        values = periods[f"baseline_{baseline}_return"]
        cumulative = float((1 + values).prod() - 1)
        simple_baselines[baseline] = {
            "label": label,
            "cumulative_return": cumulative,
            "portfolio_excess_return": float(result_metrics["cumulative_return"] - cumulative),
        }
    result_metrics["simple_baselines"] = simple_baselines
    result_metrics["best_simple_baseline_excess_return"] = min(
        (item["portfolio_excess_return"] for item in simple_baselines.values()), default=0.0,
    )
    cost_sensitivity = []
    for total_direction_bps in (10.0, 20.0, 40.0, 60.0):
        stressed_returns = periods["gross_return"] - (
            periods["buy_turnover"] + periods["sell_turnover"]
        ) * total_direction_bps / 10000
        cost_sensitivity.append({
            "cost_bps_per_direction": total_direction_bps,
            "cumulative_return": float((1 + stressed_returns).prod() - 1),
        })
    result_metrics["cost_sensitivity"] = cost_sensitivity
    result_metrics["capacity_curve"] = [
        {
            "capital": float(capital),
            "period_coverage": float(periods["estimated_capacity"].ge(capital).mean()),
            "median_capacity": float(periods["estimated_capacity"].median()),
        }
        for capital in (200_000.0, 1_000_000.0, 5_000_000.0, 10_000_000.0)
    ]
    exposure_accumulator: dict[str, list[float]] = {}
    for encoded in periods["industry_weights"].dropna():
        try:
            weights_for_period = json.loads(encoded)
        except (TypeError, ValueError):
            weights_for_period = {}
        for industry, weight in weights_for_period.items():
            exposure_accumulator.setdefault(str(industry), []).append(float(weight))
    industry_exposure = {
        industry: float(np.mean(values)) for industry, values in exposure_accumulator.items() if values
    }
    def _industry_hhi(encoded: object) -> float:
        if not isinstance(encoded, str) or not encoded:
            return 0.0
        try:
            return float(sum(float(value) ** 2 for value in json.loads(encoded).values()))
        except (TypeError, ValueError, json.JSONDecodeError):
            return 0.0
    result_metrics["portfolio_exposure"] = {
        "average_industry_weights": dict(sorted(industry_exposure.items(), key=lambda item: item[1], reverse=True)),
        "average_max_industry_weight": float(periods["max_industry_exposure"].mean()),
        "average_industry_hhi": float(periods["industry_weights"].map(_industry_hhi).mean()),
        "median_market_cap": float(periods["market_cap_median"].median()) if periods["market_cap_median"].notna().any() else None,
        "mean_market_cap": float(periods["market_cap_mean"].mean()) if periods["market_cap_mean"].notna().any() else None,
    }
    result_metrics["nested_validation"] = {
        "protocol": "purged_nested_walk_forward",
        "outer_periods": int(len(periods)),
        "inner_candidates": [15, 31],
        "selected_leaf_distribution": {str(value): nested_choices.count(value) for value in (15, 31)},
    }
    result_metrics["regime_metrics"] = {
        str(regime): {
            "periods": int(len(group)),
            "cumulative_return": float((1 + group["portfolio_return"]).prod() - 1),
            "cumulative_excess_return": float((1 + group["portfolio_return"]).prod() - (1 + group["benchmark_return"]).prod()),
            "rank_ic": float(group["ic"].mean()),
        }
        for regime, group in periods.groupby("market_regime")
    }
    yearly = periods.assign(year=periods["date"].dt.year).groupby("year")["excess_return"].agg(["count", "mean"])
    result_metrics["positive_year_ratio"] = float((yearly["mean"] > 0).mean()) if not yearly.empty else 0.0
    result_metrics["yearly_excess"] = [
        {"year": int(year), "periods": int(row["count"]), "mean_excess_return": float(row["mean"])}
        for year, row in yearly.iterrows()
    ]
    return periods, result_metrics


def run_latest_research(frame: pd.DataFrame, features: list[str], top_k: int, horizon: int,
                        output_dir: Path, weights: dict[str, float] | None = None,
                        fetch_sentiment: bool = True,
                        progress: Callable[[str], None] | None = None,
                        sentiment_progress: Callable[[int, int, str], None] | None = None) -> tuple[pd.DataFrame, dict[str, object], pd.DataFrame]:
    def stage(message: str):
        if progress:
            progress(message)

    dates = sorted(pd.to_datetime(frame["date"]).unique())
    if len(dates) < 100:
        raise ValueError("有效交易日不足100天，无法运行综合研究")
    prediction_date = dates[-1]
    target = model_target(frame)
    labeled = frame.dropna(subset=[target])
    train = labeled[labeled["date"] < prediction_date]
    split_date = dates[max(1, int(len(dates) * 0.8))]
    split_cutoff = embargo_cutoff(dates, split_date, horizon)
    train_fit = train[train["date"] < split_cutoff]
    validation = train[train["date"] >= split_date]
    if train_fit.empty or validation.empty:
        raise ValueError("训练集或验证集为空，请增加历史数据")
    stage("阶段 2/4：样本外验证训练…")
    estimator = make_estimator()
    estimator.fit(model_matrix(train_fit, features), train_fit[target])
    validation_pred = estimator.predict(model_matrix(validation, features))
    score_weights = DEFAULT_WEIGHTS.copy() if weights is None else {
        key: max(float(weights.get(key, 0.0)), 0.0) for key in DEFAULT_WEIGHTS
    }
    weight_total = sum(score_weights.values()) or 1.0
    score_weights = {key: value / weight_total for key, value in score_weights.items()}
    metrics: dict[str, object] = {
        "schema_version": 2,
        "validation_start": str(split_date), "validation_end": str(validation["date"].max()),
        "mae": float(mean_absolute_error(validation[target], validation_pred)),
        "r2": float(r2_score(validation[target], validation_pred)), "horizon_days": horizon,
        "target_definition": target, "feature_transform": "daily_cross_sectional_percentile_rank",
        "weights": score_weights,
        "score_definition": "模型35% + 技术25% + 量价20% + K线10% + 舆情10%（权重可调）",
    }
    stage("阶段 3/4：全量训练与舆情抓取…")
    estimator.fit(model_matrix(train, features), train[target])
    latest = frame[frame["date"] == prediction_date].dropna(subset=features).copy()
    sentiment = latest_sentiment_snapshot(
        latest["symbol"].astype(str).str.zfill(6).tolist(), pd.Timestamp(prediction_date), fetch_sentiment,
        progress=sentiment_progress)
    stage("阶段 4/4：综合评分与结果输出…")
    raw_prediction = estimator.predict(model_matrix(latest, features))
    latest = score_snapshot(
        latest, neutralize_prediction(latest, raw_prediction), sentiment, score_weights
    )
    odds = estimate_reward_risk(frame)
    if not odds.empty:
        latest = latest.merge(odds, on="symbol", how="left")
    score_history = load_score_history(output_dir.parent / "data" / "archive")
    conditional = estimate_conditional_signal_stats(frame, score_history, horizon)
    if not conditional.empty:
        latest = latest.merge(conditional, on="symbol", how="left")
    backtest_path = output_dir / "backtest_metrics.json"
    try:
        backtest_evidence = json.loads(backtest_path.read_text(encoding="utf-8")) if backtest_path.exists() else {}
    except Exception:
        backtest_evidence = {}
    latest = add_signal_credibility(latest, score_history, backtest_evidence)
    all_latest = latest.sort_values("composite_score", ascending=False).copy()
    latest = all_latest.head(top_k)
    diagnostics = score_robustness_diagnostics(all_latest, score_weights, top_k)
    diagnostics["schema_version"] = 2

    # SHAP 解释（模型可解释性增强）
    try:
        import shap
        X_train = model_matrix(train, features).values
        explainer = shap.TreeExplainer(estimator)
        shap_values = explainer.shap_values(X_train)
        importance = pd.DataFrame({
            "feature": features,
            "importance": np.abs(shap_values).mean(axis=0)
        }).sort_values("importance", ascending=False)
        importance.to_csv(output_dir / "feature_importance.csv", index=False, encoding="utf-8-sig")
    except Exception:
        importance = pd.DataFrame({"feature": features, "importance": getattr(estimator, "feature_importances_", np.zeros(len(features)))})
        importance = importance.sort_values("importance", ascending=False)

    output_dir.mkdir(parents=True, exist_ok=True)
    all_latest.to_csv(output_dir / "latest_scores.csv", index=False, encoding="utf-8-sig")
    latest.to_csv(output_dir / "latest_picks.csv", index=False, encoding="utf-8-sig")
    importance.to_csv(output_dir / "feature_importance.csv", index=False, encoding="utf-8-sig")
    (output_dir / "validation_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "score_diagnostics.json").write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")
    return latest, metrics, importance

