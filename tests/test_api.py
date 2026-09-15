from fastapi.testclient import TestClient
import pytest
import server
from server import app

client = TestClient(app)

def test_api_status():
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert "version" in data
    assert "pool_count" in data
    assert "market_sentiment" in data

def test_api_universe_search():
    res = client.get("/api/universe/search?q=000001&limit=5")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert data[0]["symbol"] == "000001"

def test_api_pool_endpoints():
    res = client.get("/api/pool")
    assert res.status_code == 200
    initial_pool = res.json()
    assert len(initial_pool) > 0

    add_res = client.post("/api/pool", json={"symbols": ["999999"], "source": "pytest测试"})
    assert add_res.status_code == 200
    assert add_res.json()["ok"] is True

    del_res = client.delete("/api/pool/999999")
    assert del_res.status_code == 200
    assert del_res.json()["ok"] is True

def test_api_pool_batch():
    batch_text = "999991 测试股A\n999992 测试股B"
    res = client.post("/api/pool/batch", json={"text": batch_text, "source": "pytest批量导入"})
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["added"] >= 1
    client.delete("/api/pool/999991")
    client.delete("/api/pool/999992")

def test_api_latest_scores():
    res = client.get("/api/scores/latest")
    assert res.status_code == 200
    data = res.json()
    assert "stocks" in data
    assert len(data["stocks"]) > 0
    stock = data["stocks"][0]
    assert "symbol" in stock
    assert "composite_score" in stock
    assert "model_score" in stock
    assert "positive_evidences" in stock
    assert "negative_evidences" in stock
    assert "credibility_stability" in stock
    assert "conditional_sample_count" in stock
    assert "limitations" in stock
    assert "date" in stock


def test_api_scoring_context():
    res = client.get("/api/scores/context")
    assert res.status_code == 200
    data = res.json()
    assert {"manifest", "validation", "diagnostics", "research_status", "backtest", "importance"}.issubset(data)
    assert isinstance(data["importance"], list)


def test_api_scoring_rejects_invalid_weights():
    res = client.post("/api/scores/run", json={
        "horizon": 20,
        "top_k": 10,
        "weights": {
            "model": 0.35,
            "technical": 0.25,
            "volume_price": 0.20,
            "candle": 0.10,
            "sentiment": 0.20,
        },
        "fetch_sentiment": False,
    })
    assert res.status_code == 422
    assert "100%" in res.json()["detail"]


def test_api_scoring_starts_background_worker(monkeypatch):
    captured = {}

    def store_status(task_id, status):
        server._TASK_STATUS[task_id] = status

    def fake_worker(task_id, payload):
        captured["task_id"] = task_id
        captured["horizon"] = payload.horizon
        captured["top_k"] = payload.top_k
        captured["fetch_sentiment"] = payload.fetch_sentiment
        server._TASK_STATUS[task_id]["running"] = False

    server._TASK_STATUS.clear()
    monkeypatch.setattr(server, "_store_task_status", store_status)
    monkeypatch.setattr(server, "_background_scoring", fake_worker)
    res = client.post("/api/scores/run", json={
        "horizon": 10,
        "top_k": 5,
        "weights": {
            "model": 0.35,
            "technical": 0.25,
            "volume_price": 0.20,
            "candle": 0.10,
            "sentiment": 0.10,
        },
        "fetch_sentiment": False,
    })
    assert res.status_code == 200
    assert captured == {
        "task_id": res.json()["task_id"],
        "horizon": 10,
        "top_k": 5,
        "fetch_sentiment": False,
    }
    server._TASK_STATUS.clear()

def test_api_latest_backtest():
    res = client.get("/api/backtest/latest")
    assert res.status_code == 200
    data = res.json()
    assert "metrics" in data
    assert "curve" in data
    assert "periods" in data
    assert len(data["curve"]) > 0
    assert "strategy_nav" in data["curve"][0]
    assert "benchmark_nav" in data["curve"][0]

def test_api_governance_status():
    res = client.get("/api/governance/status")
    assert res.status_code == 200
    data = res.json()
    assert "checks" in data
    assert "passed" in data
    assert "label" in data
    assert len(data["checks"]) >= 6

def test_api_exports():
    res_excel = client.get("/api/export/excel")
    assert res_excel.status_code == 200
    assert len(res_excel.content) > 1000
    assert "spreadsheetml" in res_excel.headers.get("content-type", "")

    res_pdf = client.get("/api/export/pdf")
    assert res_pdf.status_code == 200
    assert len(res_pdf.content) > 1000
    assert "pdf" in res_pdf.headers.get("content-type", "")

    res_csv = client.get("/api/export/backtest-csv")
    assert res_csv.status_code == 200
    assert len(res_csv.content) > 100
    assert "csv" in res_csv.headers.get("content-type", "")

def test_api_runs():
    res = client.get("/api/runs")
    assert res.status_code == 200
    runs = res.json()
    assert isinstance(runs, list)
    assert len(runs) > 0
    run_id = runs[0]["run_id"]

    res_detail = client.get(f"/api/runs/{run_id}")
    assert res_detail.status_code == 200
    data_detail = res_detail.json()
    assert data_detail["run_id"] == run_id

def test_static_index_serving():
    res = client.get("/")
    assert res.status_code == 200
    assert "html" in res.headers.get("content-type", "").lower()
