from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score

from .sentiment import latest_sentiment_snapshot


DEFAULT_WEIGHTS = {"model": 0.35, "technical": 0.25, "volume_price": 0.20, "candle": 0.10, "sentiment": 0.10}


def make_estimator():
    try:
        from lightgbm import LGBMRegressor

        return LGBMRegressor(objective="regression", n_estimators=250, learning_rate=0.03, num_leaves=31,
                             subsample=0.8, colsample_bytree=0.8, random_state=42, verbosity=-1)
    except ImportError:
        from sklearn.ensemble import HistGradientBoostingRegressor

        return HistGradientBoostingRegressor(max_iter=250, learning_rate=0.05, random_state=42)


def _rank(values: pd.Series, higher_is_better: bool = True) -> pd.Series:
    result = values.rank(pct=True, method="average") * 100
    return result if higher_is_better else 100 - result


def _date_rank(frame: pd.DataFrame, column: str, higher_is_better: bool = True) -> pd.Series:
    return frame.groupby("date", group_keys=False)[column].transform(lambda values: _rank(values, higher_is_better))


def score_snapshot(snapshot: pd.DataFrame, model_prediction: pd.Series, sentiment: pd.DataFrame | None = None,
                   weights: dict[str, float] | None = None) -> pd.DataFrame:
    """Create transparent 0-100 component scores for one or more as-of dates."""
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
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
    scored["volume_price_score"] = (
        _date_rank(scored, "ret_20") * 0.35
        + _date_rank(scored, "volume_ratio_20") * 0.25
        + _date_rank(scored, "obv_slope_20") * 0.20
        + _date_rank(scored, "money_flow_20") * 0.20
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
    sharpe = float(returns.mean() / returns.std() * math.sqrt(annual_factor)) if returns.std() > 0 else 0.0
    return {"periods": int(len(returns)), "cumulative_return": float(equity.iloc[-1] - 1), "annualized_return": annualized,
            "max_drawdown": float(drawdown.min()), "sharpe": sharpe, "win_rate": float((returns > 0).mean()),
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


def run_walk_forward_backtest(frame: pd.DataFrame, features: list[str], horizon: int, top_k: int,
                              weights: dict[str, float] | None = None, min_train_days: int = 120,
                              max_points: int = 80, sentiment_history: pd.DataFrame | None = None,
                              transaction_cost_bps: float = 20.0) -> tuple[pd.DataFrame, dict[str, object]]:
    dates = sorted(pd.to_datetime(frame["date"]).unique())
    labeled = frame.dropna(subset=["future_return"]).copy()
    if len(dates) <= min_train_days + horizon:
        raise ValueError(f"有效交易日不足，至少需要 {min_train_days + horizon + 1} 天")
    candidate_dates = dates[min_train_days:-horizon or None]
    step = max(1, int(np.ceil(len(candidate_dates) / max_points)))
    records: list[dict[str, object]] = []
    for current_date in candidate_dates[::step]:
        current_date = pd.Timestamp(current_date)
        train = labeled[labeled["date"] < current_date]
        snapshot = frame[frame["date"] == current_date].dropna(subset=features).copy()
        if train["date"].nunique() < min_train_days or snapshot.empty:
            continue
        estimator = make_estimator()
        estimator.fit(train[features], train["future_return"])
        date_sentiment = None
        if sentiment_history is not None and not sentiment_history.empty:
            # 舆情文件可能是周频；只使用当日及之前最近30天的记录，不能读取未来情绪。
            history_window = sentiment_history[
                (sentiment_history["date"] <= current_date)
                & (sentiment_history["date"] >= current_date - pd.Timedelta(days=30))
            ].sort_values("date")
            date_sentiment = history_window.groupby("symbol", as_index=False).tail(1) if not history_window.empty else None
        scored = score_snapshot(snapshot, estimator.predict(snapshot[features]), sentiment=date_sentiment, weights=weights)
        selected = scored.nlargest(min(top_k, len(scored)), "composite_score")
        gross_return = float(selected["future_return"].mean())
        records.append({
            "date": current_date,
            "selected_count": len(selected),
            "gross_return": gross_return,
            "portfolio_return": gross_return - transaction_cost_bps / 10000,
            "benchmark_return": float(snapshot["future_return"].mean()),
            "selected_symbols": ",".join(selected["symbol"].astype(str).str.zfill(6)),
        })
    periods = pd.DataFrame(records)
    if periods.empty:
        raise ValueError("回测没有生成有效调仓期，请增加股票数量或历史数据")
    periods["date"] = pd.to_datetime(periods["date"])
    periods["equity"] = (1 + periods["portfolio_return"]).cumprod()
    periods["benchmark_equity"] = (1 + periods["benchmark_return"]).cumprod()
    result_metrics = _metrics(periods["portfolio_return"], periods["benchmark_return"], horizon)
    result_metrics["transaction_cost_bps"] = float(transaction_cost_bps)
    result_metrics["sentiment_history_used"] = bool(sentiment_history is not None and not sentiment_history.empty)
    return periods, result_metrics


def run_latest_research(frame: pd.DataFrame, features: list[str], top_k: int, horizon: int,
                        output_dir: Path, weights: dict[str, float] | None = None,
                        fetch_sentiment: bool = True) -> tuple[pd.DataFrame, dict[str, object], pd.DataFrame]:
    dates = sorted(pd.to_datetime(frame["date"]).unique())
    if len(dates) < 100:
        raise ValueError("有效交易日不足100天，无法运行综合研究")
    prediction_date = dates[-1]
    labeled = frame.dropna(subset=["future_return"])
    train = labeled[labeled["date"] < prediction_date]
    split_date = dates[max(1, int(len(dates) * 0.8))]
    train_fit = train[train["date"] < split_date]
    validation = train[train["date"] >= split_date]
    if train_fit.empty or validation.empty:
        raise ValueError("训练集或验证集为空，请增加历史数据")
    estimator = make_estimator()
    estimator.fit(train_fit[features], train_fit["future_return"])
    validation_pred = estimator.predict(validation[features])
    metrics: dict[str, object] = {
        "validation_start": str(split_date), "validation_end": str(validation["date"].max()),
        "mae": float(mean_absolute_error(validation["future_return"], validation_pred)),
        "r2": float(r2_score(validation["future_return"], validation_pred)), "horizon_days": horizon,
        "score_definition": "模型35% + 技术25% + 量价20% + K线10% + 舆情10%（权重可调）",
    }
    estimator.fit(train[features], train["future_return"])
    latest = frame[frame["date"] == prediction_date].dropna(subset=features).copy()
    sentiment = latest_sentiment_snapshot(latest["symbol"].astype(str).str.zfill(6).tolist(), pd.Timestamp(prediction_date), fetch_sentiment)
    latest = score_snapshot(latest, estimator.predict(latest[features]), sentiment, weights)
    odds = estimate_reward_risk(frame)
    if not odds.empty:
        latest = latest.merge(odds, on="symbol", how="left")
    all_latest = latest.sort_values("composite_score", ascending=False).copy()
    latest = all_latest.head(top_k)
    importance = pd.DataFrame({"feature": features, "importance": getattr(estimator, "feature_importances_", np.zeros(len(features)))})
    importance = importance.sort_values("importance", ascending=False)
    output_dir.mkdir(parents=True, exist_ok=True)
    all_latest.to_csv(output_dir / "latest_scores.csv", index=False, encoding="utf-8-sig")
    latest.to_csv(output_dir / "latest_picks.csv", index=False, encoding="utf-8-sig")
    importance.to_csv(output_dir / "feature_importance.csv", index=False, encoding="utf-8-sig")
    (output_dir / "validation_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return latest, metrics, importance
