from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score


def train_and_rank(frame: pd.DataFrame, features: list[str], top_k: int, horizon: int, output_dir: Path) -> pd.DataFrame:
    dates = sorted(frame["date"].unique())
    if len(dates) < 100:
        raise ValueError("有效交易日不足100天，无法训练模型")
    prediction_date = dates[-1]
    labeled = frame.dropna(subset=["future_return"]).copy()
    train = labeled[labeled["date"] < prediction_date].copy()
    split_date = dates[max(0, int(len(dates) * 0.8))]
    train_fit = train[train["date"] < split_date]
    validation = train[train["date"] >= split_date]
    if train_fit.empty or validation.empty:
        raise ValueError("训练集或验证集为空，请增加历史数据")

    try:
        from lightgbm import LGBMRegressor

        estimator = LGBMRegressor(
            objective="regression",
            n_estimators=300,
            learning_rate=0.03,
            num_leaves=31,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbosity=-1,
        )
    except ImportError:
        from sklearn.ensemble import HistGradientBoostingRegressor

        estimator = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, random_state=42)

    estimator.fit(train_fit[features], train_fit["future_return"])
    validation_pred = estimator.predict(validation[features])
    metrics = {
        "validation_start": str(split_date),
        "validation_end": str(validation["date"].max()),
        "mae": float(mean_absolute_error(validation["future_return"], validation_pred)),
        "r2": float(r2_score(validation["future_return"], validation_pred)),
        "horizon_days": horizon,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "validation_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    estimator.fit(train[features], train["future_return"])
    latest = frame[frame["date"] == prediction_date].copy()
    latest["score"] = estimator.predict(latest[features])
    latest = latest.sort_values("score", ascending=False).head(top_k)
    columns = ["date", "symbol", "close", "score", *features]
    latest[columns].to_csv(output_dir / "latest_picks.csv", index=False, encoding="utf-8-sig")

    if hasattr(estimator, "feature_importances_"):
        importance = pd.DataFrame({"feature": features, "importance": estimator.feature_importances_}).sort_values("importance", ascending=False)
        importance.to_csv(output_dir / "feature_importance.csv", index=False, encoding="utf-8-sig")
    return latest[columns]
