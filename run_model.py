from __future__ import annotations

import argparse
import sys
from pathlib import Path

from stock_model.data import load_panel
from stock_model.features import build_features
from stock_model.research import run_latest_research


def main() -> None:
    if sys.stdout.encoding != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="运行选股模型并生成候选观察名单（研究用途）")
    parser.add_argument("--data", default="data/raw", help="行情数据目录")
    parser.add_argument("--output", default="output", help="结果输出目录")
    parser.add_argument("--top-k", type=int, default=20, help="候选标的数量")
    parser.add_argument("--horizon", type=int, default=20, help="预测周期（交易日）")
    parser.add_argument("--no-sentiment", action="store_true", help="不抓取实时舆情，按中性50分处理")
    args = parser.parse_args()

    data_dir = Path(args.data)
    output_dir = Path(args.output)
    panel = load_panel(data_dir)
    frame, features = build_features(panel, horizon=args.horizon)
    picks, metrics, importance = run_latest_research(
        frame, features, top_k=args.top_k, horizon=args.horizon, output_dir=output_dir,
        fetch_sentiment=not args.no_sentiment,
    )
    cols = [c for c in ["date", "symbol", "close", "composite_score", "model_score", "credibility_grade"] if c in picks.columns]
    print(picks[cols].to_string(index=False))


if __name__ == "__main__":
    main()
