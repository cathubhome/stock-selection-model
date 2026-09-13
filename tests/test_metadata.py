from __future__ import annotations

import sys
import types

import pandas as pd

from stock_model.metadata import (
    _sina_industry_metadata, _tencent_metadata, apply_historical_universe, archive_metadata,
    fetch_current_metadata, load_metadata_history, metadata_coverage,
    universe_history_audit,
)


def test_fetch_current_metadata_normalizes_spot_columns(monkeypatch):
    fake = types.SimpleNamespace(stock_zh_a_spot_em=lambda: pd.DataFrame({
        "代码": ["000001", "600000"], "所属行业": ["银行", "银行"],
        "总市值": [1.2e12, 8e11],
    }))
    monkeypatch.setitem(sys.modules, "akshare", fake)
    result, report = fetch_current_metadata("2026-08-29")
    assert report["ok"] is True
    assert result["symbol"].tolist() == ["000001", "600000"]
    assert result["industry"].notna().all()
    assert result["market_cap"].tolist() == [1.2e12, 8e11]


def test_metadata_archive_is_reloadable(tmp_path):
    frame = pd.DataFrame({"symbol": ["000001"], "date": pd.Timestamp("2026-08-29"), "industry": ["银行"], "market_cap": [1.0], "source": ["test"]})
    target = archive_metadata(frame, tmp_path, "2026-08-29")
    loaded = load_metadata_history(tmp_path)
    assert target.name == "metadata_20260829.csv"
    assert loaded.loc[0, "symbol"] == "000001"
    assert loaded.loc[0, "industry"] == "银行"


def test_code_only_metadata_is_not_reported_as_usable(monkeypatch):
    raw = pd.DataFrame({"代码": ["600000", "000001"], "最新价": [10.0, 11.0]})
    monkeypatch.setattr("akshare.stock_zh_a_spot_em", lambda: raw)
    result, report = fetch_current_metadata("2026-08-29")
    assert len(result) == 2
    assert report["ok"] is False
    assert report["status"] == "empty"
    assert report["industry_coverage"] == 0
    assert report["market_cap_coverage"] == 0


def test_individual_profile_fills_requested_metadata(monkeypatch):
    fake = types.SimpleNamespace(
        stock_zh_a_spot_em=lambda: pd.DataFrame({"代码": ["600000", "000001"]}),
        stock_individual_info_em=lambda symbol: pd.DataFrame({
            "item": ["股票代码", "行业", "总市值"],
            "value": [symbol, "银行", "120亿"],
        }),
    )
    monkeypatch.setitem(sys.modules, "akshare", fake)
    monkeypatch.setattr("stock_model.metadata._tencent_metadata", lambda symbols, snapshot_date: (pd.DataFrame(), []))
    monkeypatch.setattr("stock_model.metadata._sina_industry_metadata", lambda symbols, snapshot_date: (pd.DataFrame(), []))
    result, report = fetch_current_metadata("2026-08-29", symbols=["600000", "000001"])
    assert report["ok"] is True
    assert report["usable"] is True
    assert result["industry"].tolist() == ["银行", "银行"]
    assert result["market_cap"].tolist() == [12_000_000_000.0, 12_000_000_000.0]


def test_tencent_quote_parses_market_cap_and_valuation(monkeypatch):
    fields = [""] * 47
    fields[2], fields[39], fields[45], fields[46] = "000001", "5.20", "2260.79", "0.48"
    content = ('v_sz000001="' + "~".join(fields) + '";').encode("gbk")

    class Response:
        def __init__(self):
            self.content = content

        def raise_for_status(self):
            return None

    monkeypatch.setattr("stock_model.metadata.requests.get", lambda *args, **kwargs: Response())
    result, errors = _tencent_metadata(["000001"], pd.Timestamp("2026-08-29"))
    assert errors == []
    assert result.loc[0, "market_cap"] == 226_079_000_000.0
    assert result.loc[0, "pe_ttm"] == 5.2
    assert result.loc[0, "pb"] == 0.48


def test_sina_profile_parses_shenwan_industry(monkeypatch):
    html = """
    <table><tr><td>所属行业板块</td><td>同行业个股</td></tr>
    <tr><td>银行</td><td>点击查看</td></tr>
    <tr><td>备注：此为申万行业分类</td><td>备注：此为申万行业分类</td></tr></table>
    """

    class Response:
        content = html.encode("gbk")

        def raise_for_status(self):
            return None

    monkeypatch.setattr("stock_model.metadata.requests.get", lambda *args, **kwargs: Response())
    result, errors = _sina_industry_metadata(["000001"], pd.Timestamp("2026-08-29"))
    assert errors == []
    assert result.loc[0, "industry"] == "银行"


def test_same_day_archive_preserves_previous_valid_fields(tmp_path):
    first = pd.DataFrame({
        "symbol": ["000001"], "date": ["2026-08-29"], "industry": ["银行"],
        "market_cap": [pd.NA], "source": ["sina.sw_industry"],
    })
    second = pd.DataFrame({
        "symbol": ["000001"], "date": ["2026-08-29"], "industry": [pd.NA],
        "market_cap": [2.2e11], "source": ["tencent.quote"],
    })
    archive_metadata(first, tmp_path, "2026-08-29")
    archive_metadata(second, tmp_path, "2026-08-29")
    loaded = load_metadata_history(tmp_path)
    assert loaded.loc[0, "industry"] == "银行"
    assert loaded.loc[0, "market_cap"] == 2.2e11
    assert "sina.sw_industry" in loaded.loc[0, "source"]
    assert "tencent.quote" in loaded.loc[0, "source"]


def test_metadata_coverage_requires_quality_thresholds():
    frame = pd.DataFrame({
        "symbol": [f"{i:06d}" for i in range(100)],
        "date": pd.Timestamp("2026-08-29"),
        "industry": ["银行"] * 89 + [None] * 11,
        "market_cap": [1e9] * 96 + [None] * 4,
    })
    audit = metadata_coverage(frame)
    assert audit["industry_usable"] is False
    assert audit["market_cap_usable"] is True
    assert audit["usable"] is False


def test_universe_history_does_not_claim_historical_coverage_from_one_snapshot():
    history = pd.DataFrame({"symbol": ["600000"], "snapshot_date": [pd.Timestamp("2026-08-29")]})
    audit = universe_history_audit(history, "2020-01-01", "2026-08-28")
    assert audit["usable"] is False
    assert "幸存者偏差" in audit["reason"]


def test_historical_universe_filters_each_snapshot_interval():
    snapshot_dates = pd.date_range("2024-01-01", periods=12, freq="MS")
    history = pd.concat([
        pd.DataFrame({
            "symbol": ["600000"] if index < 6 else ["000001"],
            "name": ["浦发银行"] if index < 6 else ["平安银行"],
            "snapshot_date": snapshot_date,
        })
        for index, snapshot_date in enumerate(snapshot_dates)
    ], ignore_index=True)
    panel = pd.DataFrame({
        "date": [pd.Timestamp("2024-02-15"), pd.Timestamp("2024-02-15"),
                 pd.Timestamp("2024-08-15"), pd.Timestamp("2024-08-15")],
        "symbol": ["600000", "000001", "600000", "000001"],
        "close": [10, 11, 12, 13],
    })
    filtered = apply_historical_universe(panel, history)
    assert filtered["symbol"].tolist() == ["600000", "000001"]
