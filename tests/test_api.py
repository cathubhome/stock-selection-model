from fastapi.testclient import TestClient
import pytest
from server import app

client = TestClient(app)

def test_api_status():
    res = client.get('/api/status')
    assert res.status_code == 200
    data = res.json()
    assert data['status'] == 'online'
    assert 'version' in data
    assert 'pool_count' in data
    assert 'market_sentiment' in data

def test_api_universe_search():
    res = client.get('/api/universe/search?q=000001&limit=5')
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert data[0]['symbol'] == '000001'

def test_api_pool_endpoints():
    # 1. Get initial pool
    res = client.get('/api/pool')
    assert res.status_code == 200
    initial_pool = res.json()
    assert len(initial_pool) > 0

    # 2. Add a test symbol
    add_res = client.post('/api/pool', json={'symbols': ['999999'], 'source': 'pytest测试'})
    assert add_res.status_code == 200
    assert add_res.json()['ok'] is True

    # 3. Remove test symbol
    del_res = client.delete('/api/pool/999999')
    assert del_res.status_code == 200
    assert del_res.json()['ok'] is True

def test_api_latest_scores():
    res = client.get('/api/scores/latest')
    assert res.status_code == 200
    data = res.json()
    assert 'stocks' in data
    assert len(data['stocks']) > 0
    stock = data['stocks'][0]
    assert 'symbol' in stock
    assert 'composite_score' in stock
    assert 'model_score' in stock

def test_api_latest_backtest():
    res = client.get('/api/backtest/latest')
    assert res.status_code == 200
    data = res.json()
    assert 'metrics' in data
    assert 'curve' in data
    assert 'periods' in data
    assert len(data['curve']) > 0
    assert 'strategy_nav' in data['curve'][0]
    assert 'benchmark_nav' in data['curve'][0]

def test_api_runs():
    res = client.get('/api/runs')
    assert res.status_code == 200
    runs = res.json()
    assert isinstance(runs, list)
    assert len(runs) > 0
    assert 'run_id' in runs[0]

def test_static_index_serving():
    res = client.get('/')
    assert res.status_code == 200
    assert 'html' in res.headers.get('content-type', '').lower()
