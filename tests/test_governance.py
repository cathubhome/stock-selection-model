from pathlib import Path

from stock_model.governance import assess_research_status, load_manifest, write_run_manifest


def test_failed_alpha_metrics_cannot_pass_validation():
    status = assess_research_status(
        {"periods": 46, "cumulative_excess_return": -0.4, "ic_mean": -0.01,
         "q5_q1_mean_return": 0.001, "excess_win_rate": 0.48},
        {"r2": -0.08}, {"usable": False}, {"usable": False, "reason": "历史股票池不足"},
    )
    assert status["passed"] is False
    assert status["status"] == "research_observation"
    assert status["result_term"] == "研究观察名单"
    assert len(status["failed_reasons"]) >= 3


def test_validation_levels_distinguish_preliminary_and_robust():
    common = {
        "cumulative_excess_return": 0.1, "ic_mean": 0.05, "ic_confidence_low": 0.01,
        "q5_q1_mean_return": 0.02, "excess_win_rate": 0.6, "positive_year_ratio": 0.8,
        "best_simple_baseline_excess_return": 0.03, "ic_p_value": 0.01,
    }
    preliminary = assess_research_status(
        {**common, "periods": 40}, {"r2": 0.02}, {"usable": True}, {"usable": True},
    )
    assert preliminary["status"] == "preliminary"
    assert preliminary["preliminary_passed"] is True
    assert preliminary["passed"] is False

    robust = assess_research_status(
        {**common, "periods": 60}, {"r2": 0.02}, {"usable": True}, {"usable": True},
    )
    assert robust["status"] == "robust"
    assert robust["passed"] is True


def test_uncomputable_metrics_fail_gates_without_raising():
    status = assess_research_status(
        {
            "periods": 60,
            "cumulative_excess_return": 0.1,
            "ic_mean": 0.05,
            "ic_confidence_low": None,
            "q5_q1_mean_return": 0.02,
            "excess_win_rate": 0.6,
            "positive_year_ratio": 0.8,
            "best_simple_baseline_excess_return": 0.03,
            "ic_p_value_adjusted": None,
            "unresolved_holding_events": None,
        },
        {"r2": 0.02}, {"usable": True}, {"usable": True},
    )
    checks = {check["name"]: check["passed"] for check in status["checks"]}
    assert checks["rank_ic"] is True
    assert checks["ic_significance"] is False
    assert checks["holding_valuation"] is True
    assert status["status"] == "preliminary"


def test_run_manifest_is_versioned_and_reloadable(tmp_path: Path):
    write_run_manifest(tmp_path, {"run_id": "run-1", "kind": "score", "config": {"top_k": 10}})
    loaded = load_manifest(tmp_path, "score")
    assert loaded["schema_version"] == 3
    assert loaded["run_id"] == "run-1"
