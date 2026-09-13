from __future__ import annotations

from pathlib import Path
import pandas as pd

from .research import run_latest_research


def train_and_rank(frame: pd.DataFrame, features: list[str], top_k: int, horizon: int, output_dir: Path) -> pd.DataFrame:
    """Train the standardized multi-dimensional model and rank candidates.

    Maintains backward compatibility by delegating to research pipeline.
    """
    picks, _, _ = run_latest_research(
        frame, features, top_k=top_k, horizon=horizon, output_dir=output_dir, fetch_sentiment=False,
    )
    if "score" not in picks.columns and "composite_score" in picks.columns:
        picks["score"] = picks["composite_score"]
    return picks
