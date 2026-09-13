"""Validation gates and versioned run manifests for reproducible research."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


ARTIFACT_SCHEMA_VERSION = 3


def assess_research_status(
    backtest: dict[str, Any] | None,
    validation: dict[str, Any] | None = None,
    metadata_audit: dict[str, Any] | None = None,
    universe_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply conservative gates; a score is never interpreted as probability."""
    bt = backtest or {}
    val = validation or {}
    ic_low = bt.get("ic_confidence_low")
    ic_passed = float(ic_low) > 0 if ic_low is not None else float(bt.get("ic_mean", 0)) > 0
    core_checks = [
        ("periods", int(bt.get("periods", 0)) >= 36, "至少需要36个非重叠样本外调仓期"),
        ("excess_return", float(bt.get("cumulative_excess_return", 0)) > 0, "扣除成本后累计超额收益应为正"),
        ("rank_ic", ic_passed, "Rank IC 的95%置信区间下界应为正"),
        ("quantile_spread", float(bt.get("q5_q1_mean_return", 0)) > 0, "高分组相对低分组收益应为正"),
        ("excess_win_rate", float(bt.get("excess_win_rate", 0)) > 0.5, "超额收益胜率应高于50%"),
        ("validation_r2", float(val.get("r2", -1)) > 0, "验证集 R² 应为正"),
    ]
    robust_checks = [
        ("subperiod_stability", float(bt.get("positive_year_ratio", 0)) >= 0.75,
         "至少75%的年度子区间平均超额收益应为正"),
        ("robust_sample", int(bt.get("periods", 0)) >= 60, "稳健通过至少需要60个非重叠样本外调仓期"),
        ("simple_baselines", float(bt.get("best_simple_baseline_excess_return", -1)) > 0,
         "组合应跑赢仅模型评分、20日动量、60日动量和低波动基线"),
        ("ic_significance", float(bt.get("ic_p_value_adjusted", bt.get("ic_p_value", 1))) < 0.05,
         "Rank IC 经多重检验校正后的 p 值应低于0.05"),
        ("holding_valuation", int(bt.get("unresolved_holding_events", 0)) == 0,
         "跌停、停牌或退市持仓必须具有可连续估值的后续行情"),
    ]
    checks = [*core_checks, *robust_checks]
    warnings = []
    if metadata_audit and not metadata_audit.get("usable", False):
        warnings.append("行业与市值元数据覆盖不足，风险约束未完全验证")
    if universe_audit and not universe_audit.get("usable", False):
        warnings.append(str(universe_audit.get("reason") or "历史股票池覆盖不足"))
    failed = [message for _, passed, message in checks if not passed]
    core_passed = bool(bt) and all(passed for _, passed, _ in core_checks)
    robust_passed = core_passed and all(passed for _, passed, _ in robust_checks) and not warnings
    if not bt or int(bt.get("periods", 0)) == 0:
        level, label = "not_validated", "未验证"
    elif not core_passed:
        level, label = "research_observation", "研究观察"
    elif not robust_passed:
        level, label = "preliminary", "初步通过"
    else:
        level, label = "robust", "稳健通过"
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "passed": robust_passed,
        "preliminary_passed": core_passed,
        "status": level,
        "label": label,
        "result_term": "候选名单" if robust_passed else "研究观察名单",
        "checks": [{"name": name, "passed": ok, "message": message} for name, ok, message in checks],
        "failed_reasons": failed, "warnings": warnings,
    }


def new_run_id(kind: str) -> str:
    return f"{datetime.now():%Y%m%dT%H%M%S}_{kind}_{uuid4().hex[:8]}"


def data_fingerprint(files: list[Path]) -> str:
    payload = "|".join(
        f"{path.name}:{path.stat().st_size}:{path.stat().st_mtime_ns}"
        for path in sorted(files) if path.exists()
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def write_run_manifest(output_dir: Path, manifest: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        **manifest,
    }
    run_id = str(payload["run_id"])
    target = runs_dir / f"{run_id}.json"
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    target.write_text(encoded, encoding="utf-8")
    (output_dir / f"latest_{payload.get('kind', 'run')}_manifest.json").write_text(encoded, encoding="utf-8")
    return target


def load_manifest(output_dir: Path, kind: str) -> dict[str, Any]:
    path = output_dir / f"latest_{kind}_manifest.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
