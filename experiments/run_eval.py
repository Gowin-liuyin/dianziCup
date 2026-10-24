"""T47/R21 评测骨架 CLI: 读配置 -> 注册表校验 -> 逐 case 产出记录 -> 收据落盘。

用法:
    python experiments/run_eval.py run --config experiments/configs/b2b_nine_roles.json \
        [--output-root reports/runs] [--repo-root .]
    python experiments/run_eval.py compare --run-a <receipt_dir> --run-b <receipt_dir>

退出码 (仿 scripts/dev.py 合同): 0 通过(含如实登记的 blocked/registration 记录, 见
status_counts); 1 失败(存在 failed 记录或收据合同拒绝); 2 参数/配置/注册表错误;
3 未建设(manifest 声明金标, 骨架无金标评分路径); 4 输入阻塞(dev-set manifest
缺失/无效/hash 不符或模型门阻塞)。

一切输出显式标注 fixture-scale, 非正式指标; 0 gold 下 accuracy 恒
not_computable_no_gold, 不产出准确率数字, 不做跨基线比较。
真实模型调用禁止: 费用上限=0, 非 fixture provider 一律 blocked_model_missing。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = REPO_ROOT / "backend" / "src"

try:
    from ai_intel.evaluation.configs import (
        ConfigContractError,
        config_digest,
        load_dev_set_manifest,
        load_experiment_config,
        resolve_manifest_path,
    )
    from ai_intel.evaluation.metrics import coverage_matrix, summarize_run_metrics
    from ai_intel.evaluation.records import (
        BEIJING_FIXED_OFFSET,
        CodeFingerprintError,
        beijing_timestamp,
        compute_code_fingerprint,
    )
    from ai_intel.evaluation.registry import validate_config_against_registry
    from ai_intel.evaluation.replay import compare_runs
    from ai_intel.evaluation.runners import (
        DEFAULT_EVALUATION_ENVIRONMENT,
        CaseRunContext,
        build_runner,
    )
    from ai_intel.evaluation.writers import (
        RECEIPT_HEADER_NOTE,
        ReceiptWriteError,
        RunSummary,
        write_run_receipt,
    )
except ModuleNotFoundError:  # 仓库根直跑时补 backend/src, prepare.py:19-20 同例
    if str(BACKEND_SRC) not in sys.path:
        sys.path.insert(0, str(BACKEND_SRC))
    from ai_intel.evaluation.configs import (
        ConfigContractError,
        config_digest,
        load_dev_set_manifest,
        load_experiment_config,
        resolve_manifest_path,
    )
    from ai_intel.evaluation.metrics import coverage_matrix, summarize_run_metrics
    from ai_intel.evaluation.records import (
        BEIJING_FIXED_OFFSET,
        CodeFingerprintError,
        beijing_timestamp,
        compute_code_fingerprint,
    )
    from ai_intel.evaluation.registry import validate_config_against_registry
    from ai_intel.evaluation.replay import compare_runs
    from ai_intel.evaluation.runners import (
        DEFAULT_EVALUATION_ENVIRONMENT,
        CaseRunContext,
        build_runner,
    )
    from ai_intel.evaluation.writers import (
        RECEIPT_HEADER_NOTE,
        ReceiptWriteError,
        RunSummary,
        write_run_receipt,
    )

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_ARGUMENT_ERROR = 2
EXIT_NOT_BUILT = 3
EXIT_INPUT_BLOCKED = 4

GOLD_SCORING_CODE = "gold_scoring_not_implemented"


def _fail(error_code: str, detail: str = "") -> int:
    print(f"error_code={error_code}" + (f" detail={detail}" if detail else ""), file=sys.stderr)
    return EXIT_ARGUMENT_ERROR


def run_command(args: argparse.Namespace) -> int:
    """run 子命令: 配置 -> manifest -> 逐 case 记录 -> 收据。"""
    repo_root = Path(args.repo_root).resolve()
    output_root = Path(args.output_root)
    if not output_root.is_absolute():
        output_root = repo_root / output_root
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path

    try:
        config = load_experiment_config(config_path)
    except ConfigContractError as error:
        return _fail(error.error_code, str(error))
    try:
        spec = validate_config_against_registry(config)
    except ConfigContractError as error:
        return _fail(error.error_code, str(error))

    manifest_path = resolve_manifest_path(repo_root, config.data_ref.manifest_path)
    try:
        manifest = load_dev_set_manifest(manifest_path, config.data_ref.expected_sha256)
    except RuntimeError as error:
        error_code = getattr(error, "error_code", "blocked_input_invalid")
        print(f"error_code={error_code} detail={error}", file=sys.stderr)
        return EXIT_NOT_BUILT if error_code == GOLD_SCORING_CODE else EXIT_INPUT_BLOCKED

    try:
        fingerprint = compute_code_fingerprint(repo_root)
    except CodeFingerprintError as error:
        return _fail("code_fingerprint_unavailable", str(error))
    expected_head = config.code_ref.expected_head
    if expected_head is not None and not fingerprint.code_sha256.startswith(expected_head):
        return _fail(
            "code_head_mismatch",
            f"expected {expected_head}, got {fingerprint.code_sha256}",
        )

    run_started_at = beijing_timestamp()
    # 微秒级 run_id: 同一秒内重复 run 不冲突, 收据目录独占创建
    timestamp = datetime.now(BEIJING_FIXED_OFFSET).strftime("%Y%m%dT%H%M%S%f+0800")
    run_id = f"{timestamp}-{config.baseline_id}"
    context = CaseRunContext(
        run_id=run_id,
        config=config,
        config_sha256=config_digest(config),
        data_sha256=manifest.sha256,
        data_hash_verified=manifest.hash_verified,
        code_sha256=fingerprint.code_sha256,
        code_dirty=fingerprint.code_dirty,
        case_count=len(manifest.cases),
        environment_name=DEFAULT_EVALUATION_ENVIRONMENT,
    )
    runner = build_runner(spec)
    records = tuple(runner.run_case(case.case_id, context) for case in manifest.cases)
    run_ended_at = beijing_timestamp()

    status_counts: dict[str, int] = {}
    for record in records:
        status_counts[record.status] = status_counts.get(record.status, 0) + 1
    if any(record.status == "failed" for record in records):
        run_exit_code = EXIT_FAILED
    elif any(record.status == "blocked_model_missing" for record in records):
        run_exit_code = EXIT_INPUT_BLOCKED
    else:
        run_exit_code = EXIT_OK

    summary = RunSummary(
        run_id=run_id,
        baseline_id=config.baseline_id,
        strategy=config.strategy,
        title=config.title,
        config_sha256=context.config_sha256,
        data_sha256=context.data_sha256,
        data_ref_path=config.data_ref.manifest_path,
        data_hash_verified=context.data_hash_verified,
        code_sha256=context.code_sha256,
        code_dirty=context.code_dirty,
        model_provider=config.model_configuration.provider,
        model_name=config.model_configuration.approved_model,
        budget=config.budget.model_dump(),
        seed=config.seed,
        hardware_note=config.hardware_note,
        ablation_flags=config.ablation.model_dump(),
        ablation_status=records[0].ablation_status,
        command=f"run_eval.py run --config {args.config}",
        cwd=str(Path.cwd()),
        started_at=run_started_at,
        ended_at=run_ended_at,
        exit_code=run_exit_code,
        case_count=len(manifest.cases),
        data_kind_counts=manifest.data_kind_counts,
        status_counts=status_counts,
        metrics=summarize_run_metrics(records, len(manifest.cases)),
        coverage=coverage_matrix(records),
        scale="fixture",
        data_mode="fixture",
        disclaimer=records[0].disclaimer,
    )

    receipt_dir = output_root / f"eval_{run_id}"
    try:
        write_run_receipt(summary, records, receipt_dir)
    except ReceiptWriteError as error:
        print(f"error_code={error}", file=sys.stderr)
        return EXIT_FAILED

    print(RECEIPT_HEADER_NOTE)
    print("fixture_scale=true")
    print(f"run_id={run_id}")
    print(f"baseline_id={config.baseline_id}")
    print(f"strategy={config.strategy}")
    print(f"case_count={len(manifest.cases)}")
    print(f"data_kind_counts={json.dumps(manifest.data_kind_counts, ensure_ascii=False)}")
    print(f"status_counts={json.dumps(status_counts, ensure_ascii=False)}")
    accuracy_metric = summary.metrics.get("accuracy")
    accuracy_status = accuracy_metric.status if accuracy_metric else "no_metrics_declared"
    print(f"accuracy_status={accuracy_status}")
    print(f"data_hash_verified={str(manifest.hash_verified).lower()}")
    print(f"receipt_dir={receipt_dir}")
    print(f"exit_code={run_exit_code}")
    return run_exit_code


def compare_command(args: argparse.Namespace) -> int:
    """compare 子命令: 两次 run 收据的字段级 diff, 不产出比较数字声明。"""
    try:
        diff = compare_runs(Path(args.run_a), Path(args.run_b))
    except RuntimeError as error:
        return _fail("receipt_read_error", str(error))
    print(json.dumps(diff.to_json_dict(), ensure_ascii=False, indent=2))
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="T47/R21 evaluation skeleton CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="执行单基线评测骨架 run")
    run_parser.add_argument("--config", required=True, help="实验配置 JSON 路径")
    run_parser.add_argument(
        "--output-root", default="reports/runs", help="收据根目录 (默认 reports/runs)"
    )
    run_parser.add_argument("--repo-root", default=str(REPO_ROOT), help="仓库根 (相对路径解析基准)")
    run_parser.set_defaults(handler=run_command)

    compare_parser = subparsers.add_parser("compare", help="比较两次 run 收据")
    compare_parser.add_argument("--run-a", required=True, help="收据目录 A")
    compare_parser.add_argument("--run-b", required=True, help="收据目录 B")
    compare_parser.set_defaults(handler=compare_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    sys.exit(main())
