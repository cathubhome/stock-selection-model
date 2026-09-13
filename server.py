# FastAPI Backend Server for Stock Selection Model.
from __future__ import annotations

import json
import math
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from stock_model.benchmarks import prepare_benchmark_returns
from stock_model.data import get_symbols, load_panel, update_histories
from stock_model.features import build_features
from stock_model.metadata import fetch_current_metadata, latest_metadata_snapshot
from stock_model.pool import add_to_pool, load_pool
from stock_model.research import (
    DEFAULT_WEIGHTS,
    run_latest_research,
    run_walk_forward_backtest,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'
RAW_DATA_DIR = DATA_DIR / 'raw'
REF_DATA_DIR = DATA_DIR / 'reference'
ARCHIVE_DATA_DIR = DATA_DIR / 'archive'
OUTPUT_DIR = BASE_DIR / 'output'
DIST_DIR = BASE_DIR / 'dist'
POOL_PATH = REF_DATA_DIR / 'local_stock_pool.csv'
UNIVERSE_PATH = REF_DATA_DIR / 'a_share_universe.parquet'

app = FastAPI(
    title='Stock Selection Model API',
    description='Quantitative Research & Stock Selection Platform API',
    version='1.0.0',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

_TASK_STATUS: Dict[str, Dict[str, Any]] = {}
_TASK_LOCK = threading.Lock()


class PoolAddRequest(BaseModel):
    symbols: List[str] = Field(..., description='List of stock symbols to add')
    source: str = Field(default='Web界面添加', description='Source description')


class WeightConfigModel(BaseModel):
    model: float = 0.35
    technical: float = 0.25
    volume_price: float = 0.20
    candle: float = 0.10
    sentiment: float = 0.10


class ScoringRunRequest(BaseModel):
    horizon: int = 20
    top_k: int = 10
    weights: Optional[WeightConfigModel] = None
    fetch_sentiment: bool = True


class BacktestRunRequest(BaseModel):
    horizon: int = 20
    top_k: int = 10
    weights: Optional[WeightConfigModel] = None
    transaction_cost_bps: float = 20.0
    benchmark: str = '000300'


def safe_float(val: Any, default: float = 0.0) -> float:
    if val is None or pd.isna(val):
        return default
    try:
        f = float(val)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (ValueError, TypeError):
        return default


def _determine_market(symbol: str) -> str:
    s = str(symbol).strip()
    if s.startswith('688'):
        return '科创板'
    if s.startswith(('300', '301')):
        return '创业板'
    if s.startswith('5') or s.startswith('15'):
        return 'ETF'
    return '主板'


def _load_universe_df() -> pd.DataFrame:
    if UNIVERSE_PATH.exists():
        try:
            return pd.read_parquet(UNIVERSE_PATH)
        except Exception:
            pass
    return pd.DataFrame(columns=['symbol', 'name', 'initials', 'pinyin', 'search_label'])


def load_latest_market_sentiment() -> Dict[str, Any]:
    path = ARCHIVE_DATA_DIR / 'market_sentiment.csv'
    if not path.exists():
        return {}
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            lines = [l.strip() for l in f if l.strip()]
        if len(lines) <= 1:
            return {}
        last = lines[-1].split(',')
        if len(last) >= 6:
            score = float(last[2])
            status = '中性偏强 (做多区)' if score >= 50 else '中性偏弱 (防守区)'
            return {
                'date': last[1],
                'archive_time': last[0],
                'score': round(score, 2),
                'breadth': round(float(last[3]), 4) if last[3] else 0.0,
                'volume_ratio': round(float(last[4]), 4) if last[4] else 1.0,
                'limit_up_ratio': round(float(last[5]), 4) if last[5] else 0.0,
                'status': status,
                'total_stocks': int(last[-1]) if len(last) >= 7 and last[-1].isdigit() else 93,
            }
    except Exception:
        pass
    return {}


@app.get('/api/status')
def get_system_status() -> Dict[str, Any]:
    meta_status = {}
    meta_file = ARCHIVE_DATA_DIR / 'metadata_sync_status.json'
    if meta_file.exists():
        try:
            meta_status = json.loads(meta_file.read_text(encoding='utf-8'))
        except Exception:
            pass

    sentiment = load_latest_market_sentiment()

    pool_count = 0
    if POOL_PATH.exists():
        try:
            pool_count = len(load_pool(POOL_PATH))
        except Exception:
            pass

    raw_count = len(list(RAW_DATA_DIR.glob('*.parquet'))) if RAW_DATA_DIR.exists() else 0

    latest_manifest = {}
    manifest_file = OUTPUT_DIR / 'latest_score_manifest.json'
    if manifest_file.exists():
        try:
            latest_manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
        except Exception:
            pass

    return {
        'status': 'online',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat(),
        'pool_count': pool_count,
        'raw_bar_files': raw_count,
        'metadata_status': meta_status,
        'market_sentiment': sentiment,
        'latest_score_run': {
            'run_id': latest_manifest.get('run_id'),
            'date': latest_manifest.get('created_at', '')[:10] if latest_manifest else None,
            'created_at': latest_manifest.get('created_at'),
            'top_symbols': [p.get('symbol') for p in latest_manifest.get('picks', [])][:5],
        },
    }


@app.get('/api/pool')
def get_stock_pool() -> List[Dict[str, Any]]:
    if not POOL_PATH.exists():
        return []
    try:
        pool_df = load_pool(POOL_PATH)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Failed to read pool: {exc}')

    universe = _load_universe_df()
    u_map = {}
    if not universe.empty and 'symbol' in universe.columns:
        u_map = universe.set_index('symbol').to_dict('index')

    latest_score_map = {}
    latest_scores_path = OUTPUT_DIR / 'latest_scores.csv'
    if latest_scores_path.exists():
        try:
            sdf = pd.read_csv(latest_scores_path, dtype={'symbol': str})
            latest_score_map = sdf.set_index('symbol').to_dict('index')
        except Exception:
            pass

    result: List[Dict[str, Any]] = []
    for _, row in pool_df.iterrows():
        sym = str(row['symbol']).zfill(6)
        u_info = u_map.get(sym, {})
        s_info = latest_score_map.get(sym, {})

        price = round(safe_float(s_info.get('close'), 10.0), 2)
        change_val = s_info.get('涨跌幅')
        if pd.isna(change_val) or change_val is None:
            change_val = safe_float(s_info.get('daily_return')) * 100.0
        change = round(safe_float(change_val, 0.0), 2)
        turnover = round(safe_float(s_info.get('turnover')), 2)
        industry = str(s_info.get('industry') or u_info.get('industry') or '综合')

        result.append({
            'symbol': sym,
            'name': str(row.get('name') or u_info.get('name') or sym),
            'pinyin': str(u_info.get('pinyin', '')),
            'industry': industry if industry and industry != 'nan' else '综合',
            'market': _determine_market(sym),
            'source': str(row.get('source', '本地股票池')),
            'added_at': str(row.get('added_at', '')),
            'price': price,
            'change': change,
            'turnover': turnover,
            'composite_score': round(safe_float(s_info.get('composite_score'), 50.0), 1),
            'model_score': round(safe_float(s_info.get('model_score'), 50.0), 1),
            'technical_score': round(safe_float(s_info.get('technical_score'), 50.0), 1),
            'volume_price_score': round(safe_float(s_info.get('volume_price_score'), 50.0), 1),
            'candle_score': round(safe_float(s_info.get('candle_score'), 50.0), 1),
            'sentiment_score': round(safe_float(s_info.get('sentiment_score'), 50.0), 1),
            'rank': int(safe_float(s_info.get('rank'), 999)),
        })
    return result


@app.post('/api/pool')
def add_stocks_to_pool(payload: PoolAddRequest) -> Dict[str, Any]:
    if not payload.symbols:
        return {'ok': True, 'added': 0}
    clean_symbols = [str(s).strip().zfill(6) for s in payload.symbols if str(s).strip()]
    try:
        stocks_df = pd.DataFrame({'symbol': clean_symbols})
        updated = add_to_pool(POOL_PATH, stocks_df, source=payload.source)
        return {'ok': True, 'total': len(updated), 'added': len(clean_symbols)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Failed to add stocks: {exc}')


@app.delete('/api/pool/{symbol}')
def remove_stock_from_pool(symbol: str) -> Dict[str, Any]:
    sym = symbol.strip().zfill(6)
    if not POOL_PATH.exists():
        return {'ok': True, 'removed': False}
    try:
        df = load_pool(POOL_PATH)
        init_len = len(df)
        df = df[df['symbol'].astype(str).str.zfill(6) != sym]
        if len(df) < init_len:
            df.to_csv(POOL_PATH, index=False)
            return {'ok': True, 'removed': True, 'remaining': len(df)}
        return {'ok': True, 'removed': False, 'remaining': len(df)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Failed to remove stock: {exc}')


@app.get('/api/universe/search')
def search_universe(
    q: str = Query(..., min_length=1, description='Keyword (code, name, pinyin)'),
    limit: int = Query(20, ge=1, le=100),
) -> List[Dict[str, Any]]:
    universe = _load_universe_df()
    if universe.empty:
        return []
    keyword = q.strip().lower()
    mask = (
        universe['symbol'].str.contains(keyword, na=False)
        | universe['name'].str.lower().str.contains(keyword, na=False)
        | universe['pinyin'].str.lower().str.contains(keyword, na=False)
        | universe['initials'].str.lower().str.contains(keyword, na=False)
    )
    matched = universe[mask].head(limit)
    res = []
    for _, r in matched.iterrows():
        sym = str(r['symbol']).zfill(6)
        res.append({
            'symbol': sym,
            'name': str(r['name']),
            'pinyin': str(r.get('pinyin', '')),
            'market': _determine_market(sym),
        })
    return res


def _background_download(task_id: str, symbols: List[str]) -> None:
    def progress_cb(current: int, total: int, symbol: str, note: str) -> None:
        with _TASK_LOCK:
            _TASK_STATUS[task_id] = {
                'running': True,
                'current': current,
                'total': total,
                'percent': round(current / max(1, total) * 100, 1),
                'symbol': symbol,
                'message': f'[{current}/{total}] {symbol} - {note}',
                'error': None,
            }

    try:
        end_date = datetime.now().strftime('%Y%m%d')
        update_histories(
            symbols=symbols,
            end=end_date,
            output_dir=RAW_DATA_DIR,
            progress=progress_cb,
        )
        with _TASK_LOCK:
            _TASK_STATUS[task_id] = {
                'running': False,
                'current': len(symbols),
                'total': len(symbols),
                'percent': 100.0,
                'symbol': '',
                'message': f'更新完成，共处理 {len(symbols)} 只标的',
                'error': None,
            }
    except Exception as exc:
        with _TASK_LOCK:
            _TASK_STATUS[task_id] = {
                'running': False,
                'percent': 0.0,
                'message': f'任务执行失败: {exc}',
                'error': str(exc),
            }


@app.post('/api/data/download')
def start_data_download(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    symbols = get_symbols(POOL_PATH)
    if not symbols:
        raise HTTPException(status_code=400, detail='Stock pool is empty')

    task_id = f'dl_{int(time.time())}'
    with _TASK_LOCK:
        _TASK_STATUS[task_id] = {
            'running': True,
            'current': 0,
            'total': len(symbols),
            'percent': 0.0,
            'symbol': '',
            'message': '任务初始化...',
            'error': None,
        }

    background_tasks.add_task(_background_download, task_id, symbols)
    return {'ok': True, 'task_id': task_id, 'symbols_count': len(symbols)}


@app.get('/api/data/download-progress')
def get_download_progress(task_id: str = Query(...)) -> Dict[str, Any]:
    with _TASK_LOCK:
        status = _TASK_STATUS.get(task_id)
    if not status:
        return {'running': False, 'percent': 100.0, 'message': '未找到任务或任务已结束', 'error': None}
    return status


@app.post('/api/data/sync-metadata')
def sync_metadata() -> Dict[str, Any]:
    symbols = get_symbols(POOL_PATH)
    if not symbols:
        raise HTTPException(status_code=400, detail='Stock pool is empty')
    try:
        snapshot, report = fetch_current_metadata(symbols=symbols)
        if report.get('ok'):
            ARCHIVE_DATA_DIR.mkdir(parents=True, exist_ok=True)
            status_file = ARCHIVE_DATA_DIR / 'metadata_sync_status.json'
            status_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        return {'ok': True, 'report': report}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Failed to sync metadata: {exc}')


@app.get('/api/scores/latest')
def get_latest_scores() -> Dict[str, Any]:
    scores_file = OUTPUT_DIR / 'latest_scores.csv'
    manifest_file = OUTPUT_DIR / 'latest_score_manifest.json'

    if not scores_file.exists():
        raise HTTPException(status_code=404, detail='No scores found. Please run scoring first.')

    try:
        df = pd.read_csv(scores_file, dtype={'symbol': str})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Failed to read scores: {exc}')

    manifest = {}
    if manifest_file.exists():
        try:
            manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
        except Exception:
            pass

    universe = _load_universe_df()
    u_map = universe.set_index('symbol').to_dict('index') if not universe.empty else {}

    stocks: List[Dict[str, Any]] = []
    for idx, row in df.iterrows():
        sym = str(row['symbol']).zfill(6)
        u_info = u_map.get(sym, {})
        change_val = row.get('涨跌幅')
        if pd.isna(change_val) or change_val is None:
            change_val = safe_float(row.get('daily_return')) * 100.0
        change = round(safe_float(change_val, 0.0), 2)
        price = round(safe_float(row.get('close'), 10.0), 2)
        turnover = round(safe_float(row.get('turnover')), 2)
        comp_score = round(safe_float(row.get('composite_score'), 50.0), 1)

        stocks.append({
            'symbol': sym,
            'name': str(row.get('name') or u_info.get('name') or sym),
            'pinyin': str(u_info.get('pinyin', '')),
            'industry': str(row.get('industry') or '综合'),
            'market': _determine_market(sym),
            'price': price,
            'change': change,
            'turnover': turnover,
            'volume': safe_float(row.get('volume')),
            'amount': safe_float(row.get('amount')),
            'pe_ttm': round(safe_float(row.get('pe_ttm'), 20.0), 2),
            'pb': round(safe_float(row.get('pb'), 2.0), 2),
            'model_raw': safe_float(row.get('model_score', 50.0)) / 100.0,
            'model_score': round(safe_float(row.get('model_score'), 50.0), 1),
            'technical_score': round(safe_float(row.get('technical_score'), 50.0), 1),
            'volume_price_score': round(safe_float(row.get('volume_price_score'), 50.0), 1),
            'candle_score': round(safe_float(row.get('candle_score'), 50.0), 1),
            'sentiment_score': round(safe_float(row.get('sentiment_score'), 50.0), 1),
            'sentiment_source': str(row.get('sentiment_source') or '关键词新闻评分'),
            'news_count': int(safe_float(row.get('news_count'), 0)),
            'composite_score': comp_score,
            'rank': int(safe_float(row.get('rank'), idx + 1)),
            'odds_reward_risk': round(safe_float(row.get('odds_reward_risk'), 2.0), 2),
            'odds_win_rate': round(safe_float(row.get('odds_win_rate'), 55.0), 1),
            'odds_expected_return': round(safe_float(row.get('odds_expected_return'), 5.0), 1),
            'diagnostic_status': str(row.get('diagnostic_status') or 'good'),
            'diagnostic_message': str(row.get('diagnostic_message') or '正常观察'),
            'trading_days': int(safe_float(row.get('trading_days'), 250)),
            'credibility_score': round(safe_float(row.get('credibility_score'), 70.0), 1),
            'credibility_grade': str(row.get('credibility_grade') or '中'),
        })

    return {
        'stocks': stocks,
        'manifest': manifest,
        'count': len(stocks),
        'updated_at': manifest.get('created_at'),
    }


@app.post('/api/scores/run')
def run_scoring(payload: ScoringRunRequest) -> Dict[str, Any]:
    symbols = get_symbols(POOL_PATH)
    if not symbols:
        raise HTTPException(status_code=400, detail='Stock pool is empty')

    panel = load_panel(RAW_DATA_DIR, symbols)
    if panel.empty:
        raise HTTPException(status_code=400, detail='No historical bars found in data/raw')

    frame, features = build_features(panel, horizon=payload.horizon)
    weights_dict = payload.weights.model_dump() if payload.weights else DEFAULT_WEIGHTS

    picks, metrics, importance = run_latest_research(
        frame=frame,
        features=features,
        top_k=payload.top_k,
        horizon=payload.horizon,
        output_dir=OUTPUT_DIR,
        weights=weights_dict,
        fetch_sentiment=payload.fetch_sentiment,
    )

    return {
        'ok': True,
        'top_k': payload.top_k,
        'horizon': payload.horizon,
        'picks_count': len(picks),
        'validation_metrics': metrics,
    }


@app.get('/api/backtest/latest')
def get_latest_backtest() -> Dict[str, Any]:
    metrics_file = OUTPUT_DIR / 'backtest_metrics.json'
    periods_file = OUTPUT_DIR / 'backtest_periods.csv'

    if not metrics_file.exists() or not periods_file.exists():
        raise HTTPException(status_code=404, detail='No backtest results found')

    metrics = json.loads(metrics_file.read_text(encoding='utf-8'))
    periods_df = pd.read_csv(periods_file)

    curve: List[Dict[str, Any]] = []
    max_equity = 1.0
    for _, r in periods_df.iterrows():
        eq = float(r.get('equity', 1.0))
        max_equity = max(max_equity, eq)
        dd = (eq / max_equity - 1.0) * 100.0 if max_equity > 0 else 0.0
        curve.append({
            'date': str(r.get('date')),
            'strategy_nav': round(eq, 4),
            'benchmark_nav': round(float(r.get('benchmark_equity', 1.0)), 4),
            'drawdown': round(dd, 2),
        })

    period_list: List[Dict[str, Any]] = []
    for idx, r in periods_df.iterrows():
        syms = str(r.get('selected_symbols', '')).split(',')
        period_list.append({
            'period_index': int(idx + 1),
            'date': str(r.get('date')),
            'rebalance_date': str(r.get('train_cutoff')),
            'holding_symbols': [s.strip() for s in syms if s.strip()],
            'portfolio_return': round(float(r.get('portfolio_return', 0.0)) * 100, 2),
            'benchmark_return': round(float(r.get('benchmark_return', 0.0)) * 100, 2),
            'excess_return': round(float(r.get('excess_return', 0.0)) * 100, 2),
            'turnover': round(float(r.get('turnover', 0.0)) * 100, 2),
        })

    return {
        'metrics': {
            'periods': metrics.get('periods', len(periods_df)),
            'cumulative_return': round(float(metrics.get('cumulative_return', 0.0)) * 100, 2),
            'annualized_return': round(float(metrics.get('annualized_return', 0.0)) * 100, 2),
            'max_drawdown': round(abs(float(metrics.get('max_drawdown', 0.0))) * 100, 2),
            'sharpe': round(float(metrics.get('sharpe', 0.0)), 2),
            'win_rate': round(float(metrics.get('win_rate', 0.0)) * 100, 1),
            'benchmark_return': round(float(metrics.get('benchmark_cumulative_return', 0.0)) * 100, 2),
            'excess_return': round(float(metrics.get('excess_cumulative_return', 0.0)) * 100, 2),
            'calmar_ratio': round(float(metrics.get('calmar', 0.0)), 2),
            'volatility': round(float(metrics.get('annualized_volatility', 0.0)) * 100, 2),
        },
        'curve': curve,
        'periods': period_list,
    }


@app.post('/api/backtest/run')
def run_backtest(payload: BacktestRunRequest) -> Dict[str, Any]:
    symbols = get_symbols(POOL_PATH)
    if not symbols:
        raise HTTPException(status_code=400, detail='Stock pool is empty')

    panel = load_panel(RAW_DATA_DIR, symbols)
    frame, features = build_features(panel, horizon=payload.horizon)
    weights_dict = payload.weights.model_dump() if payload.weights else DEFAULT_WEIGHTS

    benchmark_series = None
    if payload.benchmark:
        benchmark_file = REF_DATA_DIR / 'benchmarks' / f'index_{payload.benchmark}.parquet'
        if benchmark_file.exists():
            df_bm = pd.read_parquet(benchmark_file)
            benchmark_series = prepare_benchmark_returns(df_bm, horizon=payload.horizon)

    periods_df, metrics = run_walk_forward_backtest(
        frame=frame,
        features=features,
        horizon=payload.horizon,
        top_k=payload.top_k,
        weights=weights_dict,
        transaction_cost_bps=payload.transaction_cost_bps,
        benchmark_returns=benchmark_series,
        benchmark_name=f'index_{payload.benchmark}',
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    periods_df.to_csv(OUTPUT_DIR / 'backtest_periods.csv', index=False)
    (OUTPUT_DIR / 'backtest_metrics.json').write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    return get_latest_backtest()


@app.get('/api/runs')
def list_research_runs() -> List[Dict[str, Any]]:
    runs: List[Dict[str, Any]] = []
    runs_dir = OUTPUT_DIR / 'runs'
    if runs_dir.exists():
        for f in sorted(runs_dir.glob('*.json'), reverse=True):
            try:
                data = json.loads(f.read_text(encoding='utf-8'))
                runs.append({
                    'run_id': data.get('run_id', f.stem),
                    'date': data.get('created_at', '')[:10],
                    'created_at': data.get('created_at', '').replace('T', ' ')[:19],
                    'kind': data.get('kind', 'score'),
                    'stock_count': len(data.get('picks', [])),
                    'top_symbols': [p.get('symbol') for p in data.get('picks', [])][:5],
                    'avg_score': round(data.get('diagnostics', {}).get('average_score', 50.0), 1),
                    'excess_return': data.get('backtest', {}).get('excess_cumulative_return'),
                    'sharpe': data.get('backtest', {}).get('sharpe'),
                })
            except Exception:
                continue

    if not runs and (OUTPUT_DIR / 'latest_score_manifest.json').exists():
        try:
            m = json.loads((OUTPUT_DIR / 'latest_score_manifest.json').read_text(encoding='utf-8'))
            runs.append({
                'run_id': m.get('run_id'),
                'date': m.get('created_at', '')[:10],
                'created_at': m.get('created_at', '').replace('T', ' ')[:19],
                'kind': 'score',
                'stock_count': len(m.get('picks', [])),
                'top_symbols': [p.get('symbol') for p in m.get('picks', [])][:5],
                'avg_score': 50.0,
            })
        except Exception:
            pass

    return runs


if DIST_DIR.exists():
    app.mount('/', StaticFiles(directory=str(DIST_DIR), html=True), name='static')


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('server:app', host='0.0.0.0', port=8000, reload=True)
