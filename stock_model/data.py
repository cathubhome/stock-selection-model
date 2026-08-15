from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

import pandas as pd


COLUMN_MAP = {
    "日期": "date",
    "开盘": "open",
    "最高": "high",
    "最低": "low",
    "收盘": "close",
    "成交量": "volume",
    "成交额": "amount",
    "换手率": "turnover",
}


def load_stock_universe(cache_path: Path, refresh: bool = False) -> pd.DataFrame:
    """Load an A-share code/name catalog with searchable Pinyin initials."""
    if cache_path.exists() and not refresh:
        return pd.read_parquet(cache_path)

    import akshare as ak
    from pypinyin import Style, lazy_pinyin

    frame = ak.stock_info_a_code_name().rename(columns={"code": "symbol", "name": "name"})
    if not {"symbol", "name"}.issubset(frame.columns):
        raise ValueError("股票列表接口缺少代码或名称字段")
    frame = frame[["symbol", "name"]].dropna().copy()
    frame["symbol"] = frame["symbol"].astype(str).str.zfill(6)
    frame["name"] = frame["name"].astype(str).str.strip()
    frame["initials"] = frame["name"].map(lambda value: "".join(lazy_pinyin(value, style=Style.FIRST_LETTER)).upper())
    frame["pinyin"] = frame["name"].map(lambda value: "".join(lazy_pinyin(value)).lower())
    frame["search_label"] = frame.apply(
        lambda row: f'{row["symbol"]}  {row["name"]}  ·  {row["initials"]}', axis=1
    )
    frame = frame.drop_duplicates("symbol").sort_values("symbol").reset_index(drop=True)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(cache_path, index=False)
    return frame


def normalize_history(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    frame = frame.rename(columns=COLUMN_MAP).copy()
    # 腾讯接口会额外返回“股票代码”，统一由 symbol 字段承担，避免展示和拼接时产生重复列。
    frame = frame.drop(columns=["股票代码", "代码"], errors="ignore")
    required = {"date", "close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{symbol}缺少字段: {sorted(missing)}")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in ["open", "high", "low", "close", "volume", "amount", "turnover"]:
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["symbol"] = symbol
    return frame.dropna(subset=["date", "close"]).sort_values("date")


def get_symbols(symbols: str | None, top_n: int | None) -> list[str]:
    if symbols:
        return [item.strip().zfill(6) for item in symbols.split(",") if item.strip()]
    if not top_n:
        raise ValueError("请使用--symbols或--top-n指定股票")
    import akshare as ak

    spot = ak.stock_zh_a_spot_em()
    spot = spot.rename(columns={"代码": "symbol", "成交额": "amount"})
    spot["amount"] = pd.to_numeric(spot["amount"], errors="coerce")
    return (
        spot.dropna(subset=["symbol", "amount"])
        .sort_values("amount", ascending=False)
        .head(top_n)["symbol"]
        .astype(str)
        .str.zfill(6)
        .tolist()
    )


def download_histories(
    symbols: Iterable[str],
    start: str,
    end: str,
    output_dir: Path,
    progress: Callable[[int, int, str, str], None] | None = None,
) -> list[dict[str, object]]:
    import akshare as ak

    symbols = list(symbols)
    total = len(symbols)
    report: list[dict[str, object]] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    for index, symbol in enumerate(symbols, start=1):
        target = output_dir / f"{symbol}.parquet"
        print(f"[{index}] 下载 {symbol}")
        try:
            if str(symbol).upper().startswith("HK"):
                raise ValueError("当前行情下载器仅支持 A 股，港股代码已保留在股票池中")
            source = "东方财富"
            try:
                frame = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start,
                    end_date=end,
                    adjust="qfq",
                )
            except Exception as eastmoney_error:
                print(f"    东方财富接口失败，切换腾讯接口：{eastmoney_error}")
                market_prefix = (
                    "sh" if symbol.startswith(("5", "6"))
                    else "sz" if symbol.startswith(("0", "3"))
                    else "bj"
                )
                frame = ak.stock_zh_a_hist_tx(
                    symbol=f"{market_prefix}{symbol}",
                    start_date=start,
                    end_date=end,
                    adjust="qfq",
                )
                source = "腾讯"
            normalized = normalize_history(frame, symbol)
            if normalized.empty:
                raise ValueError("接口返回空数据")
            normalized.to_parquet(target, index=False)
            print(f"    保存 {len(normalized)} 行")
            report.append({
                "symbol": symbol,
                "ok": True,
                "rows": len(normalized),
                "start": str(normalized["date"].min().date()),
                "end": str(normalized["date"].max().date()),
                "source": source,
                "error": "",
            })
            if progress:
                progress(index, total, symbol, "完成")
        except Exception as error:
            print(f"    跳过：{error}")
            report.append({"symbol": symbol, "ok": False, "rows": 0, "start": "", "end": "", "source": "", "error": str(error)})
            if progress:
                progress(index, total, symbol, f"失败：{error}")
    return report


def load_panel(data_dir: Path) -> pd.DataFrame:
    files = sorted(data_dir.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"没有找到数据文件：{data_dir}")
    panel = pd.concat((pd.read_parquet(file) for file in files), ignore_index=True)
    return panel.drop(columns=["股票代码", "代码"], errors="ignore").sort_values(["date", "symbol"])
