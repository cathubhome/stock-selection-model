"""Point-in-time security metadata collection helpers."""

from __future__ import annotations

from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from io import StringIO
import time
from typing import Callable

import pandas as pd
import requests

from .quality import security_type


METADATA_SCHEMA_VERSION = 2
INDUSTRY_COVERAGE_THRESHOLD = 0.90
MARKET_CAP_COVERAGE_THRESHOLD = 0.95


def _find_column(frame: pd.DataFrame, candidates: tuple[str, ...], contains: tuple[str, ...] = ()) -> str | None:
    for column in candidates:
        if column in frame.columns:
            return column
    for column in frame.columns:
        text = str(column).lower()
        if all(token.lower() in text for token in contains):
            return str(column)
    return None


def _numeric_value(value: object) -> float | None:
    if pd.isna(value):
        return None
    text = str(value).strip().replace(",", "")
    multiplier = 1.0
    if text.endswith("亿"):
        multiplier, text = 1e8, text[:-1]
    elif text.endswith("万"):
        multiplier, text = 1e4, text[:-1]
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def _individual_metadata(ak, symbols: list[str], snapshot_date: pd.Timestamp,
                         progress: Callable[[int, int, str], None] | None = None) -> tuple[pd.DataFrame, list[str]]:
    fetcher = getattr(ak, "stock_individual_info_em", None)
    if fetcher is None or not symbols:
        return pd.DataFrame(), []
    def fetch_one(symbol: str):
        try:
            try:
                raw = fetcher(symbol=symbol, timeout=5)
            except TypeError:
                raw = fetcher(symbol=symbol)
            if raw is None or raw.empty or raw.shape[1] < 2:
                raise ValueError("empty individual profile")
            items = {
                str(item).strip(): value
                for item, value in raw.iloc[:, :2].itertuples(index=False, name=None)
            }
            return {
                "symbol": symbol, "date": snapshot_date,
                "industry": items.get("行业") or items.get("所属行业"),
                "market_cap": _numeric_value(items.get("总市值")),
                "pe_ttm": _numeric_value(items.get("市盈率")),
                "pb": _numeric_value(items.get("市净率")),
                "source": "akshare.stock_individual_info_em",
            }, None
        except Exception as error:
            return None, f"{symbol}: {error}"

    rows, errors = [], []
    with ThreadPoolExecutor(max_workers=min(8, len(symbols))) as executor:
        outcomes = executor.map(fetch_one, symbols)
    for index, (symbol, outcome) in enumerate(zip(symbols, outcomes), start=1):
        if progress:
            progress(index, len(symbols), symbol)
        row, error = outcome
        if row:
            rows.append(row)
        if error:
            errors.append(error)
    return pd.DataFrame(rows), errors


def _tencent_metadata(symbols: list[str], snapshot_date: pd.Timestamp) -> tuple[pd.DataFrame, list[str]]:
    """Tencent quotes expose market cap, PE and PB but no reliable industry field."""
    rows, errors = [], []
    for offset in range(0, len(symbols), 50):
        chunk = symbols[offset:offset + 50]
        codes = [
            ("sh" if symbol.startswith(("5", "6", "9")) else "bj" if symbol.startswith(("4", "8")) else "sz") + symbol
            for symbol in chunk
        ]
        try:
            response = requests.get(
                "http://qt.gtimg.cn/q=" + ",".join(codes), timeout=10,
                headers={"User-Agent": "Mozilla/5.0", "Referer": "http://gu.qq.com/"},
            )
            response.raise_for_status()
            for line in response.content.decode("gbk", errors="ignore").splitlines():
                if '="' not in line:
                    continue
                fields = line.split('="', 1)[1].rstrip('";').split("~")
                if len(fields) <= 46 or not str(fields[2]).isdigit():
                    continue
                rows.append({
                    "symbol": str(fields[2]).zfill(6), "date": snapshot_date, "industry": pd.NA,
                    "market_cap": (_numeric_value(fields[45]) or 0) * 1e8 or None,
                    "pe_ttm": _numeric_value(fields[39]), "pb": _numeric_value(fields[46]),
                    "source": "tencent.quote",
                })
        except Exception as error:
            errors.append(f"tencent chunk {offset // 50 + 1}: {error}")
    return pd.DataFrame(rows), errors


def _sina_industry_metadata(symbols: list[str], snapshot_date: pd.Timestamp,
                            progress: Callable[[int, int, str], None] | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Read Sina's per-security Shenwan industry classification."""
    if not symbols:
        return pd.DataFrame(), []

    def fetch_one(symbol: str):
        url = (
            "http://vip.stock.finance.sina.com.cn/corp/go.php/"
            f"vCI_CorpOtherInfo/stockid/{symbol}/menu_num/2.phtml"
        )
        try:
            response = requests.get(url, timeout=6, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            html = response.content.decode("gbk", errors="ignore")
            industry = None
            excluded = {"所属行业板块", "同行业个股", "点击查看"}
            for table in pd.read_html(StringIO(html)):
                values = [str(value).strip() for value in table.to_numpy().ravel() if pd.notna(value)]
                if not any("申万行业分类" in value for value in values):
                    continue
                candidates = [
                    value for value in values
                    if value not in excluded and not value.startswith("备注") and "申万行业分类" not in value
                ]
                if candidates:
                    industry = candidates[0]
                    break
            if not industry:
                raise ValueError("response has no Shenwan industry")
            return {
                "symbol": symbol, "date": snapshot_date, "industry": industry,
                "market_cap": pd.NA, "pe_ttm": pd.NA, "pb": pd.NA,
                "source": "sina.sw_industry",
            }, None
        except Exception as error:
            return None, f"{symbol}: {error}"

    rows, errors = [], []
    with ThreadPoolExecutor(max_workers=min(8, len(symbols))) as executor:
        outcomes = executor.map(fetch_one, symbols)
    for index, (symbol, outcome) in enumerate(zip(symbols, outcomes), start=1):
        if progress:
            progress(index, len(symbols), symbol)
        row, error = outcome
        if row:
            rows.append(row)
        if error:
            errors.append(error)
    return pd.DataFrame(rows), errors


def fetch_current_metadata(asof: str | date | None = None, symbols: list[str] | None = None,
                           progress: Callable[[int, int, str], None] | None = None) -> tuple[pd.DataFrame, dict[str, object]]:
    """Fetch a current metadata snapshot from AKShare.

    The returned date is the observation date, not a historical restatement.
    """
    import akshare as ak

    snapshot_date = pd.Timestamp(asof or date.today()).normalize()
    requested = list(dict.fromkeys(str(symbol).zfill(6) for symbol in (symbols or []) if str(symbol).strip()))
    raw = None
    errors = []
    # For an explicit universe, Tencent plus per-security profiles is faster
    # than downloading an often-disconnected full-market table.
    sources = [] if requested else [("akshare.stock_zh_a_spot_em", ak.stock_zh_a_spot_em)]
    for source_name, fetcher in sources:
        for attempt in range(3):
            try:
                raw = fetcher()
                if raw is not None and not raw.empty:
                    break
            except Exception as error:
                errors.append(f"{source_name} attempt {attempt + 1}: {error}")
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
        if raw is not None and not raw.empty:
            break
    if raw is not None and not raw.empty:
        symbol_col = _find_column(raw, ("symbol", "code", "代码", "证券代码"), ("代", "码"))
        if symbol_col is None:
            errors.append("bulk response has no symbol column")
            result = pd.DataFrame()
        else:
            industry_col = _find_column(raw, ("industry", "行业", "所属行业"), contains=("行业",))
            cap_col = _find_column(raw, ("market_cap", "总市值", "总市值(元)", "总市值（元）"), contains=("市值",))
            pe_col = _find_column(raw, ("pe_ttm", "市盈率-动态", "市盈率(动态)", "市盈率"), contains=("市盈率",))
            pb_col = _find_column(raw, ("pb", "市净率"), contains=("市净率",))
            result = pd.DataFrame({"symbol": raw[symbol_col].astype(str).str.extract(r"(\d{6})", expand=False)})
            result["date"] = snapshot_date
            result["industry"] = raw[industry_col].astype(str) if industry_col else pd.NA
            result["market_cap"] = pd.to_numeric(raw[cap_col], errors="coerce") if cap_col else pd.NA
            result["pe_ttm"] = pd.to_numeric(raw[pe_col], errors="coerce") if pe_col else pd.NA
            result["pb"] = pd.to_numeric(raw[pb_col], errors="coerce") if pb_col else pd.NA
            result["source"] = "akshare.snapshot"
    else:
        result = pd.DataFrame(columns=["symbol", "date", "industry", "market_cap", "pe_ttm", "pb", "source"])
    if requested:
        result = result[result["symbol"].astype(str).isin(requested)].copy() if not result.empty else result
        tencent, tencent_errors = _tencent_metadata(requested, snapshot_date)
        errors.extend(tencent_errors)
        sina, sina_errors = _sina_industry_metadata(requested, snapshot_date)
        errors.extend(sina_errors)
        available_industry = set(
            result.loc[result.get("industry", pd.Series(index=result.index)).notna(), "symbol"].astype(str)
        ) if not result.empty else set()
        if not sina.empty:
            available_industry.update(sina.loc[sina["industry"].notna(), "symbol"].astype(str))
        individual_symbols = [symbol for symbol in requested if symbol not in available_industry]
        individual, individual_errors = _individual_metadata(ak, individual_symbols, snapshot_date, progress)
        errors.extend(individual_errors)
        combined_rows = []
        frames = [frame for frame in (result, tencent, sina, individual) if not frame.empty]
        for symbol in requested:
            row = {"symbol": symbol, "date": snapshot_date, "industry": pd.NA,
                   "market_cap": pd.NA, "pe_ttm": pd.NA, "pb": pd.NA}
            row_sources = []
            for source_frame in frames:
                matches = source_frame[source_frame["symbol"].astype(str).eq(symbol)]
                if matches.empty:
                    continue
                match = matches.iloc[-1]
                used = False
                for column in ["industry", "market_cap", "pe_ttm", "pb"]:
                    if pd.isna(row[column]) and pd.notna(match.get(column)):
                        row[column], used = match.get(column), True
                if used:
                    row_sources.append(str(match.get("source", "unknown")))
            row["source"] = "+".join(dict.fromkeys(row_sources)) or "unavailable"
            combined_rows.append(row)
        result = pd.DataFrame(combined_rows)
    result = result.dropna(subset=["symbol"]).drop_duplicates(["symbol", "date"]).reset_index(drop=True)
    coverage = metadata_coverage(result)
    useful = coverage["industry_rows"] > 0 or coverage["market_cap_rows"] > 0
    source_names = ",".join(
        sorted(result.get("source", pd.Series(dtype=str)).dropna().astype(str).unique())
    ) or "unavailable"
    partial_message = ""
    if useful and not coverage["usable"]:
        partial_message = (
            f'部分可用：行业覆盖 {coverage["industry_coverage"]:.1%}，'
            f'市值覆盖 {coverage["market_cap_coverage"]:.1%}'
        )
    return result, {
        "ok": bool(useful), "status": "usable" if coverage["usable"] else ("partial" if useful else "empty"),
        "date": str(snapshot_date.date()), "source": source_names,
        **coverage,
        "requested_rows": len(requested),
        "missing_industry_symbols": int(coverage.get("equity_rows", coverage["rows"]) - coverage["industry_rows"]),
        "missing_market_cap_symbols": int(coverage["rows"] - coverage["market_cap_rows"]),
        "failed_symbols": int(coverage["rows"] - max(coverage["industry_rows"], coverage["market_cap_rows"])),
        "request_error_count": len(errors),
        "error": partial_message if useful else (" | ".join(errors[-5:]) or "接口没有返回可用的行业或市值字段"),
    }


def metadata_coverage(frame: pd.DataFrame | None) -> dict[str, object]:
    """Return auditable coverage without treating code-only rows as metadata."""
    if frame is None or frame.empty:
        return {
            "schema_version": METADATA_SCHEMA_VERSION, "rows": 0, "equity_rows": 0,
            "industry_rows": 0, "market_cap_rows": 0,
            "industry_coverage": 0.0, "market_cap_coverage": 0.0,
            "industry_usable": False, "market_cap_usable": False, "usable": False,
            "snapshot_start": None, "snapshot_end": None,
        }
    rows = len(frame)
    symbols = frame.get("symbol", pd.Series(index=frame.index, dtype="object")).astype(str)
    equity_mask = symbols.map(security_type).eq("A股个股")
    equity_rows = int(equity_mask.sum())
    industry = frame.get("industry", pd.Series(index=frame.index, dtype="object"))
    industry_valid = equity_mask & industry.notna() & industry.astype(str).str.strip().ne("") & industry.astype(str).ne("nan")
    market_cap = pd.to_numeric(frame.get("market_cap", pd.Series(index=frame.index, dtype="float64")), errors="coerce")
    market_cap_valid = market_cap.gt(0)
    industry_coverage = float(industry_valid.sum() / equity_rows) if equity_rows else 0.0
    market_cap_coverage = float(market_cap_valid.mean())
    dates = pd.to_datetime(frame.get("date"), errors="coerce") if "date" in frame else pd.Series(dtype="datetime64[ns]")
    return {
        "schema_version": METADATA_SCHEMA_VERSION, "rows": int(rows), "equity_rows": equity_rows,
        "industry_rows": int(industry_valid.sum()), "market_cap_rows": int(market_cap_valid.sum()),
        "industry_coverage": industry_coverage, "market_cap_coverage": market_cap_coverage,
        "industry_usable": industry_coverage >= INDUSTRY_COVERAGE_THRESHOLD,
        "market_cap_usable": market_cap_coverage >= MARKET_CAP_COVERAGE_THRESHOLD,
        "usable": industry_coverage >= INDUSTRY_COVERAGE_THRESHOLD and market_cap_coverage >= MARKET_CAP_COVERAGE_THRESHOLD,
        "snapshot_start": str(dates.min().date()) if not dates.empty and dates.notna().any() else None,
        "snapshot_end": str(dates.max().date()) if not dates.empty and dates.notna().any() else None,
    }


def archive_metadata(snapshot: pd.DataFrame, output_dir: Path, asof: str | date | None = None) -> Path:
    """Merge a daily snapshot without erasing valid fields from an earlier attempt."""
    stamp = pd.Timestamp(asof or date.today()).strftime("%Y%m%d")
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"metadata_{stamp}.csv"
    incoming = snapshot.copy()
    incoming["symbol"] = incoming["symbol"].astype(str).str.zfill(6)
    if target.exists():
        existing = pd.read_csv(target, dtype={"symbol": str})
        existing["symbol"] = existing["symbol"].astype(str).str.zfill(6)
        incoming["_priority"], existing["_priority"] = 0, 1
        combined = pd.concat([incoming, existing], ignore_index=True, sort=False)
        columns = [column for column in combined.columns if column not in {"symbol", "_priority"}]
        rows = []
        for symbol, group in combined.sort_values("_priority").groupby("symbol", sort=False):
            row = {"symbol": symbol}
            for column in columns:
                values = group[column].dropna()
                if column == "source":
                    valid = [str(value) for value in values if str(value).strip() not in {"", "unavailable", "nan"}]
                    row[column] = "+".join(dict.fromkeys(valid)) or "unavailable"
                else:
                    valid = [value for value in values if str(value).strip() not in {"", "nan", "<NA>"}]
                    row[column] = valid[0] if valid else pd.NA
            rows.append(row)
        incoming = pd.DataFrame(rows)
    incoming.to_csv(target, index=False, encoding="utf-8-sig")
    return target


def load_metadata_history(output_dir: Path) -> pd.DataFrame:
    files = sorted(output_dir.glob("metadata_*.csv"))
    if not files:
        return pd.DataFrame(columns=["symbol", "date", "industry", "market_cap", "source"])
    return pd.concat((pd.read_csv(file, dtype={"symbol": str}, parse_dates=["date"]) for file in files), ignore_index=True)


def latest_metadata_snapshot(history: pd.DataFrame | None, symbols: list[str] | None = None) -> pd.DataFrame:
    """Return one latest known row per security for current-asset coverage."""
    if history is None or history.empty:
        return pd.DataFrame(columns=["symbol", "date", "industry", "market_cap", "source"])
    frame = history.copy()
    frame["symbol"] = frame["symbol"].astype(str).str.zfill(6)
    if symbols is not None:
        wanted = {str(symbol).zfill(6) for symbol in symbols}
        frame = frame[frame["symbol"].isin(wanted)]
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    return frame.sort_values("date").groupby("symbol", as_index=False).tail(1).reset_index(drop=True)


def metadata_history_audit(history: pd.DataFrame | None, data_start=None, data_end=None) -> dict[str, object]:
    """Assess whether metadata can support historical point-in-time constraints."""
    if history is None or history.empty or "date" not in history:
        return {"usable": False, "snapshot_count": 0, "reason": "缺少历史行业与市值快照"}
    dates = pd.to_datetime(history["date"], errors="coerce").dropna().drop_duplicates().sort_values()
    start = pd.Timestamp(data_start) if data_start is not None else None
    end = pd.Timestamp(data_end) if data_end is not None else None
    covers_start = bool(start is not None and len(dates) and dates.min() <= start)
    covers_end = bool(end is not None and len(dates) and dates.max() >= end)
    usable = bool(len(dates) >= 12 and covers_start and covers_end)
    return {
        "usable": usable, "snapshot_count": int(len(dates)),
        "snapshot_start": str(dates.min().date()) if len(dates) else None,
        "snapshot_end": str(dates.max().date()) if len(dates) else None,
        "covers_data_start": covers_start, "covers_data_end": covers_end,
        "reason": "" if usable else "当前元数据只适合最新截面，尚不足以启用历史行业约束",
    }


def archive_universe_snapshot(universe: pd.DataFrame, output_dir: Path, asof: str | date | None = None) -> Path:
    """Archive the observable universe; snapshots accumulate prospectively."""
    stamp = pd.Timestamp(asof or date.today()).strftime("%Y%m%d")
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"universe_{stamp}.csv"
    snapshot = universe.copy()
    snapshot["symbol"] = snapshot["symbol"].astype(str).str.zfill(6)
    snapshot["snapshot_date"] = pd.Timestamp(asof or date.today()).normalize()
    snapshot.to_csv(target, index=False, encoding="utf-8-sig")
    return target


def load_universe_history(output_dir: Path) -> pd.DataFrame:
    files = sorted(output_dir.glob("universe_*.csv"))
    if not files:
        return pd.DataFrame(columns=["symbol", "snapshot_date"])
    frames = []
    for file in files:
        frame = pd.read_csv(file, dtype={"symbol": str})
        if "snapshot_date" not in frame:
            frame["snapshot_date"] = pd.to_datetime(file.stem.rsplit("_", 1)[-1], format="%Y%m%d")
        frame["snapshot_date"] = pd.to_datetime(frame["snapshot_date"], errors="coerce")
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def universe_history_audit(history: pd.DataFrame | None, data_start=None, data_end=None) -> dict[str, object]:
    if history is None or history.empty or "snapshot_date" not in history:
        return {"usable": False, "snapshot_count": 0, "reason": "缺少历史股票池快照，回测存在幸存者偏差"}
    dates = pd.to_datetime(history["snapshot_date"], errors="coerce").dropna().drop_duplicates().sort_values()
    start = pd.Timestamp(data_start) if data_start is not None else None
    end = pd.Timestamp(data_end) if data_end is not None else None
    covers_start = bool(start is not None and len(dates) and dates.min() <= start)
    covers_end = bool(end is not None and len(dates) and dates.max() >= end)
    usable = bool(len(dates) >= 12 and covers_start and covers_end)
    return {
        "usable": usable, "snapshot_count": int(len(dates)),
        "snapshot_start": str(dates.min().date()) if len(dates) else None,
        "snapshot_end": str(dates.max().date()) if len(dates) else None,
        "covers_data_start": covers_start, "covers_data_end": covers_end,
        "reason": "" if usable else "历史股票池覆盖不足，回测仍可能存在幸存者偏差",
    }


def apply_historical_universe(panel: pd.DataFrame, history: pd.DataFrame | None) -> pd.DataFrame:
    """Filter observations by the latest universe snapshot known on each date."""
    audit = universe_history_audit(history, panel["date"].min(), panel["date"].max())
    if not audit["usable"]:
        return panel
    frame = panel.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["symbol"] = frame["symbol"].astype(str).str.zfill(6)
    snapshots = history.copy()
    snapshots["snapshot_date"] = pd.to_datetime(snapshots["snapshot_date"], errors="coerce")
    snapshot_dates = sorted(snapshots["snapshot_date"].dropna().unique())
    parts = []
    for index, snapshot_date in enumerate(snapshot_dates):
        start = pd.Timestamp(snapshot_date)
        end = pd.Timestamp(snapshot_dates[index + 1]) if index + 1 < len(snapshot_dates) else None
        mask = frame["date"].ge(start)
        if end is not None:
            mask &= frame["date"].lt(end)
        snapshot = snapshots.loc[snapshots["snapshot_date"].eq(start)].copy()
        snapshot["symbol"] = snapshot["symbol"].astype(str).str.zfill(6)
        allowed = set(snapshot["symbol"])
        part = frame.loc[mask & frame["symbol"].isin(allowed)].copy()
        if "name" in snapshot:
            names = snapshot[["symbol", "name"]].drop_duplicates("symbol").rename(columns={"name": "security_name"})
            part = part.merge(names, on="symbol", how="left")
            part["is_st"] = part["security_name"].astype(str).str.upper().str.contains(r"(?:^|\*)ST")
        parts.append(part)
    return pd.concat(parts, ignore_index=True) if parts else frame.iloc[0:0].copy()
