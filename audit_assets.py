# -*- coding: utf-8 -*-
import glob, os, json
import pandas as pd

print("=== 1. 本地股票池 local_stock_pool.csv ===")
pool_path = "data/reference/local_stock_pool.csv"
if os.path.exists(pool_path):
    pool = pd.read_csv(pool_path, dtype=str)
    print("标的总数:", len(pool))
    print("列:", pool.columns.tolist())
    print("重复代码数:", int(pool["symbol"].duplicated().sum()))
    invalid_codes = [s for s in pool["symbol"] if not (len(s)==6 and s.isdigit())]
    print("非标准代码:", invalid_codes)
    if "industry" in pool.columns:
        cov = (pool["industry"].str.strip().ne("") & pool["industry"].notna()).sum()
        print("行业填充覆盖:", f"{cov}/{len(pool)}")
else:
    print("local_stock_pool.csv 不存在")

print("\n=== 2. 本地行情数据 data/raw/*.parquet ===")
raw_files = glob.glob("data/raw/*.parquet")
print("行情文件总数:", len(raw_files))
pool_symbols = set(pool["symbol"].str.zfill(6)) if os.path.exists(pool_path) else set()
raw_symbols = set(os.path.basename(p).replace(".parquet", "") for p in raw_files)
missing_in_raw = pool_symbols - raw_symbols
print("股票池中有但 raw 无行情文件的股票:", len(missing_in_raw), list(missing_in_raw))

date_dist = {}
short_history = []
anomalies = []
file_dates = []
for p in raw_files:
    sym = os.path.basename(p).replace(".parquet", "")
    try:
        df = pd.read_parquet(p)
        if df.empty:
            anomalies.append((sym, "空文件"))
            continue
        if len(df) < 100:
            short_history.append((sym, len(df)))
        latest_d = str(pd.to_datetime(df["date"]).max())[:10]
        date_dist[latest_d] = date_dist.get(latest_d, 0) + 1
        file_dates.append((sym, latest_d, len(df)))
        bad_ohlc = int(((df["high"] < df["low"]) | (df["close"] <= 0)).sum())
        if bad_ohlc > 0:
            anomalies.append((sym, f"OHLC异常行数:{bad_ohlc}"))
    except Exception as e:
        anomalies.append((sym, str(e)))

print("最新行情日期分布:", sorted(date_dist.items(), reverse=True))
max_date = max(date_dist.keys()) if date_dist else ""
stale_list = [item for item in file_dates if item[1] < max_date and item[0] in pool_symbols]
print(f"池中滞后于最新日期 ({max_date}) 的标的数 (未同步):", len(stale_list))
for s in stale_list:
    print("  ->", s)

print("\n=== 3. 本地元数据归档 data/archive/metadata_*.csv ===")
meta_files = sorted(glob.glob("data/archive/metadata_*.csv"))
print("历史元数据快照数量:", len(meta_files))
if meta_files:
    latest_meta = meta_files[-1]
    mdf = pd.read_csv(latest_meta, dtype={"symbol": str})
    print("最新元数据文件:", os.path.basename(latest_meta), "行数:", len(mdf))
    ind_cov = mdf["industry"].notna().mean()
    cap_cov = mdf["market_cap"].notna().mean()
    print(f"行业覆盖率: {ind_cov:.1%}, 市值覆盖率: {cap_cov:.1%}")

print("\n=== 4. 市场情绪归档 data/archive/market_sentiment.csv ===")
sent_path = "data/archive/market_sentiment.csv"
if os.path.exists(sent_path):
    sdf = pd.read_csv(sent_path)
    print("情绪数据总条数:", len(sdf))
    if not sdf.empty:
        print("最新情绪条目:", sdf.iloc[-1].to_dict())

print("\n=== 5. 最新评分产物 output/latest_scores.csv ===")
scores_path = "output/latest_scores.csv"
if os.path.exists(scores_path):
    scdf = pd.read_csv(scores_path, dtype={"symbol": str})
    print("评分标的总数:", len(scdf))
    print("评分日期:", scdf["date"].iloc[0] if "date" in scdf.columns else "无date列")
    print("NaN值检查:", scdf[["composite_score", "model_score", "technical_score"]].isna().sum().to_dict())
