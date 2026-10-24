"""T47/R21 评测骨架直属测试 (任务卡 T47 指定位置, 覆盖 C01–C06 骨架级断言)。

全部离线: fixture manifest 显式 synthetic 且置于 tmp_path, 不读写 benchmarks/,
不连 DB, 不调用真实模型。一切被测输出必须显式标注 fixture-scale。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from ai_intel.evaluation.configs import (
    ABLATION_DEFAULT_ON_STATUS,
    ABLATION_NOT_WIRED_STATUS,
    AblationFlags,
    ConfigContractError,
    ExperimentConfig,
    config_digest,
    load_dev_set_manifest,
    load_experiment_config,
)
from ai_intel.evaluation.metrics import (
    MetricsContractError,
    assert_metric_pair_present,
    coverage_matrix,
    summarize_run_metrics,
)
from ai_intel.evaluation.records import FIXTURE_DISCLAIMER, MetricTriple
from ai_intel.evaluation.registry import BASELINE_REGISTRY, validate_config_against_registry
from ai_intel.evaluation.replay import compare_runs
from ai_intel.evaluation.runners import (
    CaseRunContext,
    build_result_record,
    build_runner,
)
from ai_intel.evaluation.writers import (
    RECEIPT_HEADER_NOTE,
    LiveResultsForbidden,
    ReceiptWriteError,
    RunSummary,
    write_live_results_receipt,
    write_run_receipt,
)
from ai_intel.infrastructure.models.clients import (
    ProductionFixtureForbidden,
    assert_runtime_allows_fixture_provider,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
RUN_EVAL = REPO_ROOT / "experiments" / "run_eval.py"


def make_config(**overrides: object) -> ExperimentConfig:
    """内存构造合法实验配置; 覆盖项用于负例与变体。"""
    payload: dict[str, object] = {
        "baseline_id": "B2b",
        "title": "unit fixture config",
        "strategy": "B2b",
        "ablation": AblationFlags(),
        "data_mode": "fixture",
        "data_ref": {"manifest_path": "fixture/manifest.json", "expected_sha256": None},
        "model_config": {
            "provider": "fixture",
            "approved_model": "fixture-provider",
            "credential_env_var": None,
        },
        "budget": {"max_model_calls": 3, "max_tool_calls": 8, "cost_cap": 0},
        "seed": 20261024,
        "hardware_note": "unit test workstation",
    }
    payload.update(overrides)
    return ExperimentConfig.model_validate(payload)


def make_context(config: ExperimentConfig, case_count: int = 2) -> CaseRunContext:
    """确定性可比上下文: hash 为固定合成值, environ 显式为空。"""
    return CaseRunContext(
        run_id="run-unit-0001",
        config=config,
        config_sha256=config_digest(config),
        data_sha256="a" * 64,
        data_hash_verified=False,
        code_sha256="b" * 40,
        code_dirty=True,
        case_count=case_count,
        environ={},
    )


def make_record(
    context: CaseRunContext,
    case_id: str,
    *,
    status: str,
    error_code: str | None = None,
) -> object:
    """按状态构造统一记录, 供 C02/C05 的组合场景使用。"""
    return build_result_record(
        context,
        case_id,
        status=status,  # type: ignore[arg-type]
        error_code=error_code,
        tool_calls=0,
        model_calls=0,
        latency_ms=1.0,
    )


def make_summary(records: tuple[object, ...], case_count: int) -> RunSummary:
    """构造合法 run 汇总, 指标由 summarize_run_metrics 同源计算。"""
    first = records[0]
    status_counts: dict[str, int] = {}
    for record in records:
        status_counts[record.status] = status_counts.get(record.status, 0) + 1  # type: ignore[attr-defined]
    return RunSummary.model_validate(
        {
            "run_id": "run-unit-0001",
            "baseline_id": first.baseline_id,
            "strategy": first.strategy,
            "title": "unit summary",
            "config_sha256": "c" * 64,
            "data_sha256": "a" * 64,
            "data_ref_path": "fixture/manifest.json",
            "data_hash_verified": False,
            "code_sha256": "b" * 40,
            "code_dirty": True,
            "model_provider": "fixture",
            "model_name": "fixture-provider",
            "budget": {"max_model_calls": 3, "max_tool_calls": 8, "cost_cap": 0},
            "seed": 20261024,
            "hardware_note": "unit test workstation",
            "ablation_flags": first.ablation_flags,
            "ablation_status": first.ablation_status,
            "command": "unit",
            "cwd": ".",
            "started_at": "2026-10-25T03:00:00+08:00",
            "ended_at": "2026-10-25T03:00:01+08:00",
            "exit_code": 0,
            "case_count": case_count,
            "data_kind_counts": {"synthetic": case_count},
            "status_counts": status_counts,
            "metrics": summarize_run_metrics(records, case_count),  # type: ignore[arg-type]
            "coverage": coverage_matrix(records),  # type: ignore[arg-type]
            "scale": "fixture",
            "data_mode": "fixture",
            "disclaimer": FIXTURE_DISCLAIMER,
        }
    )


def write_fixture_manifest(tmp_path: Path, name: str = "manifest.json") -> Path:
    """显式 synthetic fixture manifest, 只存在于 tmp_path, 不触碰 benchmarks/。"""
    manifest = {
        "schema_version": 1,
        "dev_set_id": "unit_dev_set_fixture_v1",
        "cases": [
            {
                "case_id": "unit_synth_001",
                "data_kind": "synthetic",
                "split": "dev",
                "label_status": "awaiting_human_label",
            },
            {
                "case_id": "unit_synth_002",
                "data_kind": "synthetic",
                "split": "dev",
                "label_status": "awaiting_human_label",
            },
        ],
        "gold": {"human_gold_count": 0},
    }
    path = tmp_path / name
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return path


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    """以当前解释器执行 run_eval CLI (backend venv 内 ai_intel 可导入)。"""
    return subprocess.run(
        [sys.executable, str(RUN_EVAL), *arguments],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=180,
        check=False,
    )


def write_cli_config(tmp_path: Path, manifest_path: Path) -> Path:
    """CLI 端到端 fixture: 配置引用 tmp manifest 并绑定实测 sha256。"""
    config_payload = {
        "baseline_id": "B2b",
        "title": "CLI end-to-end fixture config",
        "strategy": "B2b",
        "data_mode": "fixture",
        "data_ref": {
            "manifest_path": str(manifest_path),
            "expected_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        },
        "model_config": {
            "provider": "fixture",
            "approved_model": "fixture-provider",
            "credential_env_var": None,
        },
        "budget": {"max_model_calls": 3, "max_tool_calls": 8, "cost_cap": 0},
        "seed": 20261024,
        "hardware_note": "CLI end-to-end fixture",
    }
    config_path = tmp_path / "cli_config.json"
    config_path.write_text(json.dumps(config_payload, ensure_ascii=False), encoding="utf-8")
    return config_path


# ---------------------------------------------------------------------------
# C01 同任务资源可比
# ---------------------------------------------------------------------------


def test_c01_available_baselines_share_comparable_fields() -> None:
    """B0/B2/B2b/B3 stub 记录的资源可比字段一致, 仅基线/策略/config 绑定不同。

    注: config_sha256 绑定整份配置 (含 baseline_id/strategy), 跨基线必然不同;
    其可比性语义是"同基线复跑不变"(replay 测试覆盖) + 资源字段跨基线一致。
    """
    comparable_fields = (
        "data_sha256",
        "data_hash_verified",
        "code_sha256",
        "code_dirty",
        "seed",
        "budget",
        "model_provider",
        "model_name",
        "ablation_flags",
        "case_count",
        "scale",
        "data_mode",
        "disclaimer",
    )
    expected = {"B0": None, "B2": "B2", "B2b": "B2b", "B3": "B3"}
    records = []
    for baseline_id, strategy in expected.items():
        config = make_config(baseline_id=baseline_id, strategy=strategy)
        context = make_context(config)
        record = build_runner(BASELINE_REGISTRY[baseline_id]).run_case("unit_synth_001", context)
        assert record.status == "completed"
        assert record.tool_calls == 0 and record.model_calls == 0
        assert record.config_sha256 == config_digest(config)
        records.append(record)
    for field_name in comparable_fields:
        reference = getattr(records[0], field_name)
        assert all(getattr(record, field_name) == reference for record in records), (
            f"{field_name} differs across baselines"
        )
    assert {record.baseline_id for record in records} == set(expected)
    assert {record.strategy for record in records} == {"B2", "B2b", "B3", None}
    assert len({record.config_sha256 for record in records}) == len(records)


def test_c01_b1_registration_blocks_without_metrics() -> None:
    """B1 如实登记: blocked_baseline_missing 且不生成任何指标值 (T47-C02 诚实版)。"""
    config = make_config(baseline_id="B1", strategy=None)
    record = build_runner(BASELINE_REGISTRY["B1"]).run_case("unit_synth_001", make_context(config))
    assert record.status == "blocked_baseline_missing"
    assert record.error_code == "baseline_not_implemented"
    assert record.metrics == {}


# ---------------------------------------------------------------------------
# C02 N/A 不算错、不从覆盖矩阵消失
# ---------------------------------------------------------------------------


def test_c02_not_applicable_stays_visible_and_denominator_intact() -> None:
    """not_applicable 记录不产出指标, 但保留在覆盖矩阵, 分母仍是全部 case。"""
    config = make_config()
    context = make_context(config, case_count=2)
    completed = make_record(context, "unit_synth_001", status="completed")
    not_applicable = make_record(context, "unit_synth_002", status="not_applicable")
    records = (completed, not_applicable)  # type: ignore[list-item]

    summary_metrics = summarize_run_metrics(records, 2)
    assert summary_metrics["accuracy"].numerator is None
    assert summary_metrics["accuracy"].status == "not_computable_no_gold"
    assert summary_metrics["accuracy"].denominator == 2
    assert summary_metrics["completion_rate"].numerator == 1
    assert summary_metrics["completion_rate"].denominator == 2

    coverage = coverage_matrix(records)
    assert {entry["case_id"] for entry in coverage} == {"unit_synth_001", "unit_synth_002"}
    assert not_applicable.metrics == {}


# ---------------------------------------------------------------------------
# C03 fixture 结果不混入真实效果报告
# ---------------------------------------------------------------------------


def test_c03_records_carry_fixture_annotation_and_writer_enforces_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """记录/汇总全带 fixture 标注; 缺标注拒绝落盘; live 通道预算=0 恒拒绝。"""
    config = make_config()
    context = make_context(config, case_count=2)
    records = tuple(
        make_record(context, case_id, status="completed")
        for case_id in ("unit_synth_001", "unit_synth_002")
    )
    assert all(record.scale == "fixture" for record in records)
    assert all(record.disclaimer == FIXTURE_DISCLAIMER for record in records)

    receipt_dir = write_run_receipt(make_summary(records, 2), records, tmp_path / "eval_ok")  # type: ignore[arg-type]
    lines = (receipt_dir / "records.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    for line in lines:
        payload = json.loads(line)
        assert payload["scale"] == "fixture"
        assert payload["data_mode"] == "fixture"
        assert payload["disclaimer"] == FIXTURE_DISCLAIMER
    summary_payload = json.loads((receipt_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary_payload["header_note"] == RECEIPT_HEADER_NOTE
    assert summary_payload["cross_baseline_comparison"] == "not_generated"

    tampered_disclaimer = records[0].model_copy(update={"disclaimer": "被篡改的声明"})
    with pytest.raises(ReceiptWriteError, match="fixture_scale_annotation_missing"):
        write_run_receipt(
            make_summary(records, 2),
            (tampered_disclaimer, records[1]),  # type: ignore[list-item]
            tmp_path / "eval_bad1",
        )
    tampered_scale = records[0].model_copy(update={"scale": "live"})
    with pytest.raises(ReceiptWriteError, match="fixture_scale_annotation_missing"):
        write_run_receipt(
            make_summary(records, 2),
            (tampered_scale, records[1]),  # type: ignore[list-item]
            tmp_path / "eval_bad2",
        )

    monkeypatch.setenv("AI_INTEL_EVAL_LIVE_RESULTS_AUTHORIZED", "1")
    with pytest.raises(LiveResultsForbidden, match="live_results_forbidden_budget_zero"):
        write_live_results_receipt({"scale": "live"}, tmp_path / "eval_live")
    assert not (tmp_path / "eval_live").exists()


def test_c03_harness_environment_is_never_production() -> None:
    """harness 的 fixture 门必须以非 production 环境名通过, production 一律拒绝。"""
    assert_runtime_allows_fixture_provider("evaluation-fixture")
    with pytest.raises(ProductionFixtureForbidden):
        assert_runtime_allows_fixture_provider("production")


# ---------------------------------------------------------------------------
# C04 消融开关: 声明面进配置与记录, 不产出效果数字
# ---------------------------------------------------------------------------


def test_c04_ablation_flags_default_on_and_off_marks_not_wired() -> None:
    """default 全 on 与现行为一致; scope_watch 置 off 标记机制未接线, 无消融效果数字。"""
    default_config = make_config()
    default_context = make_context(default_config)
    default_record = build_runner(BASELINE_REGISTRY["B2b"]).run_case(
        "unit_synth_001", default_context
    )
    assert default_record.ablation_flags == {
        "condition_retention": True,
        "evidence_check": True,
        "conflict_handling": True,
        "scope_watch": True,
        "dynamic_dispatch": True,
    }
    assert default_record.ablation_status == ABLATION_DEFAULT_ON_STATUS
    assert not any("ablation" in metric_name for metric_name in default_record.metrics)

    off_config = make_config(
        ablation=AblationFlags(scope_watch=False), baseline_id="B2b", strategy="B2b"
    )
    off_record = build_runner(BASELINE_REGISTRY["B2b"]).run_case(
        "unit_synth_001", make_context(off_config)
    )
    assert off_record.ablation_flags["scope_watch"] is False
    assert off_record.ablation_status == ABLATION_NOT_WIRED_STATUS
    assert off_record.ablation_status == "switch_declared_mechanism_not_wired"


# ---------------------------------------------------------------------------
# C05 完成率/未知率同时体现, 分母不删失败 case
# ---------------------------------------------------------------------------


def test_c05_both_rates_present_and_failed_case_stays_in_denominator() -> None:
    """同一 run 同时产出 completion/unknown/timeout 三率, 分母固定 case_count。"""
    context = make_context(make_config(), case_count=3)
    records = (
        make_record(context, "unit_synth_001", status="completed"),
        make_record(context, "unit_synth_002", status="partial"),
        make_record(
            context,
            "unit_synth_003",
            status="failed",
            error_code="wall_clock_budget_exceeded",
        ),
    )
    summary_metrics = summarize_run_metrics(records, 3)  # type: ignore[arg-type]
    assert summary_metrics["completion_rate"].numerator == 1
    assert summary_metrics["unknown_rate"].numerator == 1
    assert summary_metrics["timeout_rate"].numerator == 1
    for rate_name in ("completion_rate", "unknown_rate", "timeout_rate"):
        assert summary_metrics[rate_name].denominator == 3
        assert summary_metrics[rate_name].status == "computed_fixture_scale"

    summary = make_summary(records, 3)  # type: ignore[arg-type]
    assert set(summary.metrics) >= {"completion_rate", "unknown_rate"}

    with pytest.raises(MetricsContractError, match="single_metric_improvement_claim_rejected"):
        assert_metric_pair_present(
            {"improvement": {"completion_rate": 1.0}, "metrics": {"completion_rate": {}}}
        )
    assert_metric_pair_present(
        {
            "improvement": {"completion_rate": 1.0},
            "metrics": {"completion_rate": {}, "unknown_rate": {}},
        }
    )
    assert_metric_pair_present({"completion_rate": {}})


def test_c05_writer_rejects_single_rate_metric_summary(tmp_path: Path) -> None:
    """仅含其一的'提升声明'结构被 writer 拒绝: metrics 缺 unknown_rate 即拒。"""
    context = make_context(make_config(), case_count=1)
    records = (make_record(context, "unit_synth_001", status="completed"),)
    summary = make_summary(records, 1)  # type: ignore[arg-type]
    broken = summary.model_copy(
        update={
            "metrics": {
                "completion_rate": MetricTriple(
                    numerator=1, denominator=1, status="computed_fixture_scale"
                )
            }
        }
    )
    with pytest.raises(ReceiptWriteError, match="incomplete_metric_pair"):
        write_run_receipt(broken, records, tmp_path / "eval_single_rate")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# C06 缺模型明确阻塞, 不生成比较数字
# ---------------------------------------------------------------------------


def test_c06_missing_model_blocks_records_without_numbers() -> None:
    """凭据缺失 -> blocked_model_missing, 六指标分子全 null; 有凭据仍被费用上限=0 拦。"""
    real_model_config = make_config(
        model_config={
            "provider": "example-closed-model",
            "approved_model": "example-model-v1",
            "credential_env_var": "T47_EVAL_TEST_KEY",
        }
    )
    blocked = build_runner(BASELINE_REGISTRY["B2b"]).run_case(
        "unit_synth_001", make_context(real_model_config)
    )
    assert blocked.status == "blocked_model_missing"
    assert blocked.error_code == "model_credential_missing"
    assert blocked.model_calls == 0 and blocked.tool_calls == 0
    assert set(blocked.metrics) == {
        "accuracy",
        "critical_claim_accuracy",
        "evidence_support",
        "completion_rate",
        "unknown_rate",
        "timeout_rate",
    }
    assert all(metric.numerator is None for metric in blocked.metrics.values())

    context_with_credential = replace(
        make_context(real_model_config), environ={"T47_EVAL_TEST_KEY": "not-a-real-secret"}
    )
    budget_blocked = build_runner(BASELINE_REGISTRY["B2b"]).run_case(
        "unit_synth_001", context_with_credential
    )
    assert budget_blocked.status == "blocked_model_missing"
    assert budget_blocked.error_code == "model_budget_not_authorized"

    run_metrics = summarize_run_metrics((blocked,), 1)
    assert all(metric.numerator is None for metric in run_metrics.values())
    summary = make_summary((blocked,), 1)
    assert summary.cross_baseline_comparison == "not_generated"


# ---------------------------------------------------------------------------
# manifest 输入面
# ---------------------------------------------------------------------------


def test_manifest_missing_blocks_input(tmp_path: Path) -> None:
    """manifest 不存在: blocked_input_missing, 不空跑不伪造 case 集合。"""
    with pytest.raises(RuntimeError, match="blocked_input_missing"):
        load_dev_set_manifest(tmp_path / "absent.json", None)


def test_manifest_validation_rules(tmp_path: Path) -> None:
    """holdout 混入/金标声明/hash 不符/重复 case_id 分别显式拒绝; 合法 fixture 通过。"""
    manifest_path = write_fixture_manifest(tmp_path)

    loaded = load_dev_set_manifest(manifest_path, None)
    assert loaded.dev_set_id == "unit_dev_set_fixture_v1"
    assert loaded.hash_verified is False
    assert [case.case_id for case in loaded.cases] == ["unit_synth_001", "unit_synth_002"]

    verified = load_dev_set_manifest(
        manifest_path, hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    )
    assert verified.hash_verified is True

    with pytest.raises(RuntimeError, match="blocked_data_hash_mismatch"):
        load_dev_set_manifest(manifest_path, "e" * 64)

    holdout = {
        "dev_set_id": "bad",
        "cases": [{"case_id": "h1", "split": "holdout"}],
    }
    holdout_path = tmp_path / "holdout.json"
    holdout_path.write_text(json.dumps(holdout), encoding="utf-8")
    with pytest.raises(RuntimeError, match="blocked_holdout_split_detected"):
        load_dev_set_manifest(holdout_path, None)

    gold = {
        "dev_set_id": "bad",
        "cases": [{"case_id": "g1", "split": "dev"}],
        "gold": {"human_gold_count": 1},
    }
    gold_path = tmp_path / "gold.json"
    gold_path.write_text(json.dumps(gold), encoding="utf-8")
    with pytest.raises(RuntimeError, match="gold_scoring_not_implemented"):
        load_dev_set_manifest(gold_path, None)

    duplicate = {
        "dev_set_id": "bad",
        "cases": [{"case_id": "d1"}, {"case_id": "d1"}],
    }
    duplicate_path = tmp_path / "duplicate.json"
    duplicate_path.write_text(json.dumps(duplicate), encoding="utf-8")
    with pytest.raises(RuntimeError, match="blocked_input_invalid"):
        load_dev_set_manifest(duplicate_path, None)


# ---------------------------------------------------------------------------
# 配置 schema 与注册表
# ---------------------------------------------------------------------------


def test_config_schema_rejects_unknown_fields_and_bad_values(tmp_path: Path) -> None:
    """未知字段/cost_cap!=0/data_mode=live 全部 schema 级拒绝。"""
    with pytest.raises(ConfigContractError, match="config_schema_invalid"):
        load_experiment_config(_write_config(tmp_path / "cfg1", {"extra_field": 1}))
    with pytest.raises(ConfigContractError, match="config_schema_invalid"):
        load_experiment_config(
            _write_config(
                tmp_path / "cfg2",
                {"budget": {"max_model_calls": 1, "max_tool_calls": 1, "cost_cap": 1}},
            )
        )
    with pytest.raises(ConfigContractError, match="config_schema_invalid"):
        load_experiment_config(_write_config(tmp_path / "cfg3", {"data_mode": "live"}))


def test_registry_rejects_unknown_baseline_and_strategy_mismatch() -> None:
    """未注册基线与策略轴不一致都以固定错误码拒绝。"""
    with pytest.raises(ConfigContractError, match="baseline_unknown"):
        validate_config_against_registry(make_config(baseline_id="B9", strategy=None))
    with pytest.raises(ConfigContractError, match="strategy_mismatch"):
        validate_config_against_registry(make_config(baseline_id="B0", strategy="B2"))


def test_config_digest_stable_across_key_reorder(tmp_path: Path) -> None:
    """语义相同的配置重排版后 config_sha256 不变, 可比性绑定不受排版影响。"""
    reordered = {
        "hardware_note": "unit test workstation",
        "seed": 20261024,
        "budget": {"cost_cap": 0, "max_tool_calls": 8, "max_model_calls": 3},
        "model_config": {
            "credential_env_var": None,
            "approved_model": "fixture-provider",
            "provider": "fixture",
        },
        "data_ref": {"expected_sha256": None, "manifest_path": "fixture/manifest.json"},
        "data_mode": "fixture",
        "ablation": {
            "dynamic_dispatch": True,
            "scope_watch": True,
            "conflict_handling": True,
            "evidence_check": True,
            "condition_retention": True,
        },
        "strategy": "B2b",
        "title": "unit fixture config",
        "baseline_id": "B2b",
    }
    path = tmp_path / "reordered.json"
    path.write_text(json.dumps(reordered, ensure_ascii=False), encoding="utf-8")
    assert config_digest(load_experiment_config(path)) == config_digest(make_config())


# ---------------------------------------------------------------------------
# 复跑比较
# ---------------------------------------------------------------------------


def test_replay_identical_rerun_and_field_level_tamper_diff(tmp_path: Path) -> None:
    """同指纹重跑行为字段全同; 篡改单条记录状态后 diff 逐字段呈现且不丢 case。"""
    context = make_context(make_config(), case_count=2)
    records = tuple(
        make_record(context, case_id, status="completed")
        for case_id in ("unit_synth_001", "unit_synth_002")
    )
    run_a = write_run_receipt(make_summary(records, 2), records, tmp_path / "run_a")  # type: ignore[arg-type]
    records_b = tuple(
        make_record(replace(context, run_id="run-unit-0002"), case_id, status="completed")
        for case_id in ("unit_synth_001", "unit_synth_002")
    )
    run_b = write_run_receipt(make_summary(records_b, 2), records_b, tmp_path / "run_b")  # type: ignore[arg-type]

    identical = compare_runs(run_a, run_b)
    assert identical.behaviorally_identical
    assert identical.config_sha256_equal and identical.data_sha256_equal
    assert identical.code_sha256_equal

    tampered_dir = tmp_path / "run_tampered"
    tampered_dir.mkdir()
    lines = (run_a / "records.jsonl").read_text(encoding="utf-8").splitlines()
    mutated = [json.loads(line) for line in lines]
    mutated[0]["status"] = "failed"
    (tampered_dir / "records.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in mutated) + "\n",
        encoding="utf-8",
    )
    (tampered_dir / "run_summary.json").write_text(
        (run_a / "run_summary.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    diff = compare_runs(run_a, tampered_dir)
    assert not diff.behaviorally_identical
    assert diff.record_diffs["B2b::unit_synth_001"]["status"] == ["completed", "failed"]


# ---------------------------------------------------------------------------
# CLI 端到端 (fixture 数据真实可执行)
# ---------------------------------------------------------------------------


def test_cli_run_executes_fixture_manifest_end_to_end(tmp_path: Path) -> None:
    """CLI 对 fixture manifest 真跑: exit 0, 收据落盘, 全部输出显式 fixture-scale。"""
    manifest_path = write_fixture_manifest(tmp_path)
    config_path = write_cli_config(tmp_path, manifest_path)
    completed = run_cli(
        "run", "--config", str(config_path), "--output-root", str(tmp_path / "runs")
    )
    assert completed.returncode == 0, completed.stderr
    assert "fixture_scale=true" in completed.stdout
    assert RECEIPT_HEADER_NOTE in completed.stdout
    assert "case_count=2" in completed.stdout
    assert "accuracy_status=not_computable_no_gold" in completed.stdout

    receipt_dirs = list((tmp_path / "runs").glob("eval_*"))
    assert len(receipt_dirs) == 1
    records = [
        json.loads(line)
        for line in (receipt_dirs[0] / "records.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 2
    assert all(record["scale"] == "fixture" for record in records)
    assert all(record["status"] == "completed" for record in records)
    summary = json.loads((receipt_dirs[0] / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["data_hash_verified"] is True
    assert summary["metrics"]["accuracy"]["status"] == "not_computable_no_gold"
    assert summary["metrics"]["accuracy"]["numerator"] is None


def test_cli_missing_manifest_blocks_without_empty_run(tmp_path: Path) -> None:
    """manifest 缺失: exit 4 + blocked_input_missing, 不产生任何收据目录。"""
    config_payload = json.loads(
        write_cli_config(tmp_path, write_fixture_manifest(tmp_path)).read_text(encoding="utf-8")
    )
    config_payload["data_ref"]["manifest_path"] = str(tmp_path / "absent_manifest.json")
    config_path = tmp_path / "blocked_config.json"
    config_path.write_text(json.dumps(config_payload, ensure_ascii=False), encoding="utf-8")
    completed = run_cli(
        "run", "--config", str(config_path), "--output-root", str(tmp_path / "runs")
    )
    assert completed.returncode == 4, completed.stdout
    assert "blocked_input_missing" in completed.stderr
    assert not (tmp_path / "runs").exists() or not list((tmp_path / "runs").glob("eval_*"))


def test_cli_rejects_invalid_config_schema(tmp_path: Path) -> None:
    """配置含未知字段: exit 2 + config_schema_invalid, 不执行任何 case。"""
    config_path = write_cli_config(tmp_path, write_fixture_manifest(tmp_path))
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["unknown_field"] = True
    config_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    completed = run_cli(
        "run", "--config", str(config_path), "--output-root", str(tmp_path / "runs")
    )
    assert completed.returncode == 2, completed.stdout
    assert "config_schema_invalid" in completed.stderr


def test_cli_compare_reports_identical_reruns(tmp_path: Path) -> None:
    """同一 fixture 配置两次 run 的 compare: 行为字段全同, hash 门全部相等。"""
    manifest_path = write_fixture_manifest(tmp_path)
    config_path = write_cli_config(tmp_path, manifest_path)
    first = run_cli("run", "--config", str(config_path), "--output-root", str(tmp_path / "runs"))
    second = run_cli("run", "--config", str(config_path), "--output-root", str(tmp_path / "runs"))
    assert first.returncode == 0 and second.returncode == 0, first.stderr + second.stderr
    receipt_dirs = sorted((tmp_path / "runs").glob("eval_*"))
    assert len(receipt_dirs) == 2
    comparison = run_cli(
        "compare", "--run-a", str(receipt_dirs[0]), "--run-b", str(receipt_dirs[1])
    )
    assert comparison.returncode == 0, comparison.stderr
    diff = json.loads(comparison.stdout)
    assert diff["behaviorally_identical"] is True
    assert diff["config_sha256_equal"] is True
    assert diff["data_sha256_equal"] is True
    assert diff["summary_field_diffs"] == {}
    assert diff["record_diffs"] == {}


# ---------------------------------------------------------------------------
# 测试辅助
# ---------------------------------------------------------------------------


def _write_config(directory: Path, overrides: dict[str, object]) -> Path:
    """写一份带覆盖项的配置文件, 供 load_experiment_config 负例使用。"""
    base = make_config()
    payload = json.loads(base.model_dump_json(by_alias=True))
    payload.update(overrides)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "config.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path
