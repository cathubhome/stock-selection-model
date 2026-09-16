from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pandas as pd


CODE_COLUMNS = ("symbol", "代码", "股票代码", "证券代码", "股票编号", "code")
NAME_COLUMNS = ("name", "名称", "股票名称", "证券简称")


def _extract_codes(value: object) -> list[str]:
    """Extract A-share six-digit symbols and HK symbols such as HK1024."""
    text = str(value or "").upper()
    hk_codes = re.findall(r"(?<![A-Z0-9])HK\d{1,5}(?!\d)", text)
    a_codes = re.findall(r"(?<!\d)\d{6}(?!\d)", text)
    return list(dict.fromkeys(hk_codes + a_codes))


def _normalize_symbol(value: object) -> str:
    """Normalize a stored symbol without turning HK codes into A-share codes."""
    text = str(value or "").strip().upper()
    hk_match = re.search(r"HK\d{1,5}", text)
    if hk_match:
        return hk_match.group(0)
    match = re.search(r"\d{6}", text)
    if match:
        return match.group(0)
    return text.zfill(6) if text.isdigit() and 1 <= len(text) <= 6 else ""


def parse_pool_text(text: str, universe: pd.DataFrame | None = None) -> pd.DataFrame:
    """Parse codes/names pasted from a watchlist or exported text."""
    sw_names = [
        '农林牧渔', '基础化工', '钢铁', '有色金属', '电子', '家用电器', '食品饮料',
        '纺织服饰', '轻工制造', '医药生物', '公用事业', '交通运输', '房地产', '商贸零售',
        '社会服务', '银行', '非银金融', '综合', '建筑材料', '建筑装饰', '电力设备',
        '国防军工', '计算机', '传媒', '通信', '煤炭', '石油石化', '环保', '汽车',
        '机械设备', '美容护理'
    ]
    rows = []
    for raw_line in text.strip().splitlines():
        line = raw_line.strip()
        codes = _extract_codes(line)
        if not codes:
            continue
        code = codes[0]
        found_ind = ''
        for ind in sw_names:
            if ind in line:
                found_ind = ind
                break
        rows.append({"symbol": code, "name": "", "industry": found_ind})
    if not rows:
        rows = [{"symbol": code, "name": "", "industry": ""} for code in _extract_codes(text)]
    result = pd.DataFrame(rows, columns=["symbol", "name", "industry"]).drop_duplicates("symbol")
    if result.empty or universe is None or universe.empty:
        return result.drop_duplicates("symbol")
    names = universe[["symbol", "name"]].drop_duplicates("symbol")
    merged = result.drop(columns=["name"]).merge(names, on="symbol", how="left").fillna("")
    return merged[["symbol", "name", "industry"]]


def parse_pool_file(uploaded_file, universe: pd.DataFrame | None = None) -> pd.DataFrame:
    name = str(getattr(uploaded_file, "name", "")).lower()
    if name.endswith((".csv", ".xlsx")):
        try:
            frame = pd.read_excel(uploaded_file) if name.endswith(".xlsx") else pd.read_csv(
                uploaded_file, dtype=str, encoding="utf-8-sig"
            )
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            frame = pd.read_csv(uploaded_file, dtype=str, encoding="gb18030")
        code_column = next((column for column in CODE_COLUMNS if column in frame.columns), None)
        if code_column:
            result = pd.DataFrame({"symbol": frame[code_column].map(lambda value: (_extract_codes(value) or [""])[0])})
            name_column = next((column for column in NAME_COLUMNS if column in frame.columns), None)
            result["name"] = frame[name_column].fillna("").astype(str) if name_column else ""
            result = result[result["symbol"].ne("")]
            if universe is not None and not universe.empty:
                names = universe[["symbol", "name"]].drop_duplicates("symbol").rename(columns={"name": "catalog_name"})
                result = result.merge(names, on="symbol", how="left")
                result["name"] = result["name"].where(result["name"].str.strip().ne(""), result["catalog_name"])
                result = result.drop(columns=["catalog_name"])
            return result.drop_duplicates("symbol").reset_index(drop=True)
        uploaded_file.seek(0)
    content = uploaded_file.getvalue().decode("utf-8-sig", errors="ignore")
    return parse_pool_text(content, universe)


def load_pool(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["symbol", "name", "industry", "source", "added_at"])
    frame = pd.read_csv(path, dtype={"symbol": str}).fillna("")
    for column in ["industry", "source", "added_at"]:
        if column not in frame:
            frame[column] = ""
    frame["symbol"] = frame["symbol"].map(_normalize_symbol)
    return frame[frame["symbol"].ne("")].drop_duplicates("symbol").reset_index(drop=True)


def add_to_pool(path: Path, stocks: pd.DataFrame, source: str = "手工导入") -> pd.DataFrame:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_pool(path)
    incoming = stocks[[column for column in ["symbol", "name", "industry"] if column in stocks.columns]].copy()
    incoming["symbol"] = incoming["symbol"].map(_normalize_symbol)
    incoming = incoming[incoming["symbol"].ne("")]
    if "industry" not in incoming:
        incoming["industry"] = ""
    incoming["source"] = source
    incoming["added_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = pd.concat([existing, incoming], ignore_index=True)
    result = result.drop_duplicates("symbol", keep="last").sort_values("symbol").reset_index(drop=True)
    result.to_csv(path, index=False, encoding="utf-8-sig")
    return result
