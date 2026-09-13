from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from stock_model.metadata import archive_metadata, fetch_current_metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and archive current stock metadata")
    parser.add_argument("--date", default=None, help="Observation date, defaults to today")
    parser.add_argument("--output", default="data/archive")
    parser.add_argument("--symbols", default="", help="Comma-separated six-digit symbols")
    parser.add_argument("--pool", default="", help="CSV pool containing a symbol column")
    args = parser.parse_args()
    symbols = [item.strip().zfill(6) for item in args.symbols.split(",") if item.strip()]
    if args.pool:
        pool = pd.read_csv(args.pool, dtype={"symbol": str})
        if "symbol" not in pool:
            raise SystemExit("pool CSV has no symbol column")
        symbols.extend(pool["symbol"].dropna().astype(str).str.zfill(6).tolist())
    symbols = list(dict.fromkeys(symbols))
    snapshot, report = fetch_current_metadata(args.date, symbols=symbols or None)
    print(report)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metadata_sync_status.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if report.get("ok") and not snapshot.empty:
        print(f"archived {archive_metadata(snapshot, output_dir, args.date)} ({len(snapshot)} rows)")
    elif not report.get("ok"):
        raise SystemExit(report.get("error", "metadata fetch failed"))


if __name__ == "__main__":
    main()
