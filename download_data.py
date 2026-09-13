from __future__ import annotations

import argparse
from pathlib import Path

from stock_model.data import download_histories, get_symbols


def main() -> None:
    parser = argparse.ArgumentParser(description="下载A股研究数据（仅研究用途）")
    parser.add_argument("--symbols", help="逗号分隔的股票代码，例如000001,600519")
    parser.add_argument("--top-n", type=int, help="按当前成交额下载前N只股票，仅适合流程验证")
    parser.add_argument("--start", default="20180101")
    parser.add_argument("--end", default="20991231")
    parser.add_argument("--output", default="data/raw")
    args = parser.parse_args()
    symbols = get_symbols(args.symbols, args.top_n)
    print(f"准备下载 {len(symbols)} 只股票")
    download_histories(symbols, args.start, args.end, Path(args.output))


if __name__ == "__main__":
    main()

