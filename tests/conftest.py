"""共享测试夹具：确定性合成行情面板。"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def make_panel(symbols: dict[str, float], days: int = 80, seed: int = 7,
               start: str = "2024-01-02") -> pd.DataFrame:
    """构造确定性日线面板：symbols 为 {代码: 初始价格}，价格按几何随机游走演化。

    返回与 load_panel 相同的列结构（date/symbol/open/high/low/close/volume/amount/turnover）。
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, periods=days)
    frames = []
    for symbol, base in symbols.items():
        ret = rng.normal(0.0005, 0.015, size=days)
        close = base * np.cumprod(1 + ret)
        open_ = close * (1 + rng.normal(0, 0.004, size=days))
        high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.006, size=days)))
        low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.006, size=days)))
        volume = rng.integers(5_000_000, 50_000_000, size=days).astype(float)
        frames.append(pd.DataFrame({
            "date": dates, "symbol": symbol, "open": open_, "high": high,
            "low": low, "close": close, "volume": volume,
            "amount": volume * (open_ + close) / 2, "turnover": rng.uniform(0.5, 8, size=days),
        }))
    return pd.concat(frames, ignore_index=True)
