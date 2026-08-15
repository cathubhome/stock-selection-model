from __future__ import annotations

import argparse
from pathlib import Path

from stock_model.data import load_panel
from stock_model.features import build_features
from stock_model.model import train_and_rank


def main() -> None:
    parser = argparse.ArgumentParser(description="训练选股模型并输出候选股票（仅研究用途）")
    parser.add_argument("--data", default="data/raw")
    parser.add_argument("--output", default="output")
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--horizon", type=int, default=20)
    args = parser.parse_args()
    panel = load_panel(Path(args.data))
    frame, features = build_features(panel, horizon=args.horizon)
    picks = train_and_rank(frame, features, top_k=args.top_k, horizon=args.horizon, output_dir=Path(args.output))
    print(picks[["symbol", "close", "score"]].to_string(index=False))


if __name__ == "__main__":
    main()

