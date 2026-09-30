"""Validate the plan contracts of this repository without executing any product code.

Checks requirement coverage, task dependencies and ordering, synthetic case structure,
state/evidence consistency, and frozen-baseline drift. Exit codes: 0 valid, 1 violations,
2 usage or input error. Structural validity is not evidence of product correctness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REQUIREMENT_IDS = ["F1", "F2", "F3", "P1", "P2", "P3", "A1", "E1", "D1", "D2", "X1", "R1", "R2"]
FINAL_SCORED_IDS = ["F1", "F2", "F3", "P1", "P2", "P3", "A1", "E1", "D1", "D2", "X1"]
PRELIM_TOTAL = 100
FINAL_TOTAL = 100
EXPECTED_TASK_COUNT = 60
EXPECTED_STAGES = ["G0", "G1", "G2", "G3", "G4", "G5", "G6"]
TASK_STATUS_VALUES = ["pending", "in_progress", "awaiting_review", "accepted", "blocked", "needs_changes"]
IMPLEMENTATION_VALUES = ["not_started", "partial", "complete"]
VERIFICATION_VALUES = ["not_run", "passed", "failed", "blocked"]
CASE_REQUIRED_FIELDS = [
    "case_id",
    "scenario",
    "data_kind",
    "is_synthetic",
    "source_kind",
    "input",
    "expected_result",
    "expected_basis",
    "covers_requirements",
    "covers_tasks",
    "expected_status",
    "review_state",
]
CASE_ID_PREFIXES = ("SYN-", "DEMO-")
ORDER_RULES = [("T18", "T17"), ("T49", "T44")]
STAGE_MEMBERSHIP_RULES = {"T40": "G3", "T41": "G3", "T42": "G3"}
BASELINE_SCHEMA_VERSION = 1


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_requirements(requirements_doc: dict) -> list[str]:
    violations: list[str] = []
    requirements = requirements_doc.get("requirements", [])
    by_id = {item.get("id"): item for item in requirements}
    if sorted(by_id) != sorted(REQUIREMENT_IDS):
        violations.append(f"REQ_IDS: 要求ID集合不正确，实际={sorted(by_id)}")
        return violations
    if len(requirements) != len(by_id):
        violations.append("REQ_IDS: 存在重复要求ID")

    prelim_total = sum(item.get("prelim_score") or 0 for item in requirements)
    final_total = sum(item.get("final_score") or 0 for item in requirements)
    if prelim_total != PRELIM_TOTAL:
        violations.append(f"REQ_PRELIM_TOTAL: 初赛合计={prelim_total}，应为{PRELIM_TOTAL}")
    if final_total != FINAL_TOTAL:
        violations.append(f"REQ_FINAL_TOTAL: 决赛合计={final_total}，应为{FINAL_TOTAL}")

    for requirement_id in FINAL_SCORED_IDS:
        if by_id[requirement_id].get("final_score") is None:
            violations.append(f"REQ_FINAL_MISSING: {requirement_id} 缺决赛分值")
    for requirement_id in ["R1", "R2"]:
        if by_id[requirement_id].get("final_score") is not None or by_id[requirement_id].get("prelim_score") is not None:
            violations.append(f"REQ_R_SCORE: {requirement_id} 不应有独立分值")

    for item in requirements:
        requirement_id = item.get("id")
        if not item.get("implementation_tasks"):
            violations.append(f"REQ_NO_IMPL_TASK: {requirement_id} 缺实现任务映射")
        if not item.get("acceptance_tasks"):
            violations.append(f"REQ_NO_ACCEPTANCE_TASK: {requirement_id} 缺验收任务映射")
        if not item.get("planned_evidence"):
            violations.append(f"REQ_NO_EVIDENCE_PLAN: {requirement_id} 缺计划证明材料")
        reference = item.get("official_reference", {})
        if not reference.get("pdf_pages") or not reference.get("extract_lines"):
            violations.append(f"REQ_NO_OFFICIAL_REF: {requirement_id} 缺官方位置引用")
        if "internal_targets" not in item:
            violations.append(f"REQ_NO_INTERNAL_FIELD: {requirement_id} 缺内部目标字段（不得与官方档位混写）")
        for evidence in item.get("planned_evidence", []):
            if evidence.get("status") != "planned" and not evidence.get("path"):
                violations.append(f"REQ_EVIDENCE_FIELD: {requirement_id} 证据项缺path")
    return violations


def flatten_field_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(flatten_field_text(entry) for entry in value)
    if isinstance(value, dict):
        return " ".join(flatten_field_text(entry) for entry in value.values())
    return ""


def check_contract_invariants(requirements_doc: dict) -> list[str]:
    violations: list[str] = []
    by_id = {item.get("id"): item for item in requirements_doc.get("requirements", [])}
    for invariant in requirements_doc.get("contract_invariants", []):
        requirement = by_id.get(invariant.get("requirement_id"))
        if requirement is None:
            violations.append(f"INV_TARGET: {invariant.get('id')} 指向未知要求 {invariant.get('requirement_id')}")
            continue
        field_value = requirement
        for part in invariant.get("field", "").split("."):
            field_value = field_value.get(part) if isinstance(field_value, dict) else None
        text = flatten_field_text(field_value)
        needle = invariant.get("value", "")
        if invariant.get("rule") == "must_contain" and needle not in text:
            violations.append(f"INV_VIOLATED: {invariant.get('id')} 字段 {invariant.get('field')} 不含 “{needle}”")
        if invariant.get("rule") == "must_not_contain" and needle in text:
            violations.append(f"INV_VIOLATED: {invariant.get('id')} 字段 {invariant.get('field')} 不应含 “{needle}”")
    return violations


def check_manifest(manifest: dict) -> list[str]:
    violations: list[str] = []
    tasks = manifest.get("tasks", {})
    if len(tasks) != EXPECTED_TASK_COUNT or len(set(tasks)) != EXPECTED_TASK_COUNT:
        violations.append(f"TASK_COUNT: 任务数={len(tasks)}，应为{EXPECTED_TASK_COUNT}且ID唯一")

    stages = manifest.get("stages", {})
    if sorted(stages) != sorted(EXPECTED_STAGES):
        violations.append(f"STAGE_SET: 阶段集合={sorted(stages)}，应为{EXPECTED_STAGES}")
        return violations

    staged_tasks = [task_id for stage_id in EXPECTED_STAGES for task_id in stages[stage_id].get("tasks", [])]
    if sorted(staged_tasks) != sorted(tasks):
        violations.append("STAGE_PARTITION: 阶段任务划分与任务表不一致")

    execution_order = manifest.get("execution_order", [])
    if sorted(execution_order) != sorted(tasks) or len(execution_order) != len(set(execution_order)):
        violations.append(f"EXEC_ORDER: execution_order 与任务集合不一致或有重复（len={len(execution_order)}）")
    order_index = {task_id: position for position, task_id in enumerate(execution_order)}

    for task_id, task in tasks.items():
        for dependency in task.get("depends_on", []):
            if dependency not in tasks:
                violations.append(f"DEP_MISSING: {task_id} 依赖不存在的任务 {dependency}")
            elif task_id in order_index and dependency in order_index and order_index[dependency] >= order_index[task_id]:
                violations.append(f"DEP_ORDER: {task_id} 的依赖 {dependency} 未在其之前执行")
        if not task.get("requirements"):
            violations.append(f"TASK_NO_REQ: {task_id} 未映射任何评分要求")
        for requirement_id in task.get("requirements", []):
            if requirement_id not in REQUIREMENT_IDS:
                violations.append(f"TASK_REQ_UNKNOWN: {task_id} 映射未知要求 {requirement_id}")
        stage_id = task.get("stage")
        if stage_id not in stages or task_id not in stages.get(stage_id, {}).get("tasks", []):
            violations.append(f"TASK_STAGE: {task_id} 的stage字段与阶段表不一致")

    violations.extend(find_dependency_cycles(tasks))

    for earlier, later in ORDER_RULES:
        if earlier in order_index and later in order_index and order_index[earlier] >= order_index[later]:
            violations.append(f"ORDER_RULE: {earlier} 必须在 {later} 之前执行")
    for task_id, expected_stage in STAGE_MEMBERSHIP_RULES.items():
        if task_id in tasks and tasks[task_id].get("stage") != expected_stage:
            violations.append(f"STAGE_RULE: {task_id} 应属于 {expected_stage}")
    return violations


def find_dependency_cycles(tasks: dict) -> list[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    violations: list[str] = []

    def visit(task_id: str, trail: list[str]) -> None:
        if task_id in visited:
            return
        if task_id in visiting:
            cycle_start = trail.index(task_id) if task_id in trail else 0
            violations.append(f"DEP_CYCLE: 依赖成环 {' -> '.join(trail[cycle_start:] + [task_id])}")
            return
        visiting.add(task_id)
        for dependency in tasks.get(task_id, {}).get("depends_on", []):
            if dependency in tasks:
                visit(dependency, trail + [task_id])
        visiting.discard(task_id)
        visited.add(task_id)

    for task_id in tasks:
        visit(task_id, [])
    return violations


def check_requirements_manifest_consistency(requirements_doc: dict, manifest: dict) -> list[str]:
    violations: list[str] = []
    tasks = manifest.get("tasks", {})
    for item in requirements_doc.get("requirements", []):
        requirement_id = item.get("id")
        declared = set(item.get("implementation_tasks", [])) | set(item.get("acceptance_tasks", []))
        referenced = {task_id for task_id, task in tasks.items() if requirement_id in task.get("requirements", [])}
        for task_id in sorted(referenced - declared):
            violations.append(f"CONSISTENCY_REQ_TASK: 任务 {task_id} 声明映射 {requirement_id}，但 requirements.json 未列入")
        for task_id in sorted(declared - referenced):
            violations.append(f"CONSISTENCY_TASK_REQ: requirements.json 将 {task_id} 列入 {requirement_id}，但任务表未声明")
    return violations


def check_pilot_cases(cases_doc: dict) -> list[str]:
    violations: list[str] = []
    cases = cases_doc.get("cases", [])
    if not cases:
        return ["CASE_EMPTY: 合成案例集为空"]
    seen_ids: set[str] = set()
    for case in cases:
        case_id = case.get("case_id", "<missing>")
        for field in CASE_REQUIRED_FIELDS:
            if field not in case or case[field] in (None, "", [], {}):
                violations.append(f"CASE_FIELD: {case_id} 缺字段 {field}")
        if case.get("is_synthetic") is not True:
            violations.append(f"CASE_NOT_MARKED: {case_id} is_synthetic 必须为 true")
        if not str(case_id).startswith(CASE_ID_PREFIXES):
            violations.append(f"CASE_ID_PREFIX: {case_id} 需以 {'/'.join(CASE_ID_PREFIXES)} 开头")
        if case_id in seen_ids:
            violations.append(f"CASE_DUP: {case_id} 重复")
        seen_ids.add(case_id)
        for requirement_id in case.get("covers_requirements", []):
            if requirement_id not in REQUIREMENT_IDS:
                violations.append(f"CASE_REQ_UNKNOWN: {case_id} 引用未知要求 {requirement_id}")
    return violations


def check_task_state(state_doc: dict, manifest: dict, root: Path) -> list[str]:
    violations: list[str] = []
    tasks_state = state_doc.get("tasks", {})
    for task_id in manifest.get("tasks", {}):
        if task_id not in tasks_state:
            violations.append(f"STATE_MISSING_TASK: {task_id} 无状态记录")
    for task_id, entry in tasks_state.items():
        if task_id not in manifest.get("tasks", {}):
            violations.append(f"STATE_UNKNOWN_TASK: {task_id} 不在任务表中")
            continue
        if entry.get("status") not in TASK_STATUS_VALUES:
            violations.append(f"STATE_ENUM: {task_id}.status={entry.get('status')} 非合同枚举")
        if entry.get("implementation") not in IMPLEMENTATION_VALUES:
            violations.append(f"STATE_ENUM: {task_id}.implementation={entry.get('implementation')} 非合同枚举")
        verification = entry.get("verification", {})
        for scope, value in verification.items():
            if value not in VERIFICATION_VALUES:
                violations.append(f"STATE_ENUM: {task_id}.verification.{scope}={value} 非合同枚举")
        if "passed" in verification.values():
            evidence_paths = entry.get("evidence", [])
            if not evidence_paths:
                violations.append(f"EVIDENCE_MISSING: {task_id} 声明 passed 但无证据文件")
            for evidence_path in evidence_paths:
                if not (root / evidence_path).is_file():
                    violations.append(f"EVIDENCE_ABSENT: {task_id} passed 引用的证据不存在 {evidence_path}")
    return violations


def build_baseline(requirements_doc: dict, cases_doc: dict, contract_paths: dict[str, Path]) -> dict:
    return {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "purpose": "冻结评分门槛、合同不变量与合成案例集合，用于发现静默篡改；基线变更须走变更单",
        "source_hashes": {relative: sha256_of(path) for relative, path in contract_paths.items()},
        "thresholds": {
            item["id"]: {"prelim_score": item.get("prelim_score"), "final_score": item.get("final_score")}
            for item in requirements_doc.get("requirements", [])
        },
        "contract_invariants": requirements_doc.get("contract_invariants", []),
        "frozen_case_ids": [case["case_id"] for case in cases_doc.get("cases", [])],
    }


def check_source_hashes(baseline: dict, contract_paths: dict[str, Path]) -> list[str]:
    """Compare frozen source hashes with the current bytes of each contract file.

    Missing baseline entries and unreadable files are reported separately from changed
    hashes so that a silent content edit under an unchanged file name cannot pass.
    """
    violations: list[str] = []
    frozen_hashes = baseline.get("source_hashes", {})
    for relative in contract_paths:
        if relative not in frozen_hashes:
            violations.append(f"BASELINE_SOURCE_HASH_MISSING: {relative} 未在基线 source_hashes 中冻结")
    for relative, frozen_hash in frozen_hashes.items():
        path = contract_paths.get(relative)
        if path is None or not path.is_file():
            violations.append(f"BASELINE_SOURCE_HASH_MISSING: 基线冻结的 {relative} 当前不存在或不可读")
            continue
        current_hash = sha256_of(path)
        if current_hash != frozen_hash:
            violations.append(
                f"BASELINE_SOURCE_HASH_CHANGED: {relative} 内容哈希 {frozen_hash} -> {current_hash}，需变更单"
            )
    return violations


def compare_baseline(
    baseline: dict, requirements_doc: dict, cases_doc: dict, contract_paths: dict[str, Path]
) -> list[str]:
    violations: list[str] = check_source_hashes(baseline, contract_paths)
    current_thresholds = {
        item["id"]: {"prelim_score": item.get("prelim_score"), "final_score": item.get("final_score")}
        for item in requirements_doc.get("requirements", [])
    }
    for requirement_id, frozen in baseline.get("thresholds", {}).items():
        current = current_thresholds.get(requirement_id)
        if current is None:
            violations.append(f"BASELINE_REQ_DELETED: {requirement_id} 被删除")
        elif current != frozen:
            violations.append(f"BASELINE_THRESHOLD_CHANGED: {requirement_id} 分值 {frozen} -> {current}，需变更单")
    frozen_invariants = {item.get("id"): item for item in baseline.get("contract_invariants", [])}
    current_invariants = {item.get("id"): item for item in requirements_doc.get("contract_invariants", [])}
    for invariant_id, frozen in frozen_invariants.items():
        if invariant_id not in current_invariants:
            violations.append(f"BASELINE_INV_DELETED: 不变量 {invariant_id} 被删除，需变更单")
        elif current_invariants[invariant_id] != frozen:
            violations.append(f"BASELINE_INV_CHANGED: 不变量 {invariant_id} 被修改，需变更单")
    current_case_ids = {case.get("case_id") for case in cases_doc.get("cases", [])}
    for case_id in baseline.get("frozen_case_ids", []):
        if case_id not in current_case_ids:
            violations.append(f"BASELINE_CASE_DELETED: 已冻结案例 {case_id} 被删除，需变更单")
    return violations


def run_all_checks(root: Path, baseline_path: Path | None) -> tuple[list[str], dict]:
    contract_paths = {
        "contracts/requirements.json": root / "contracts" / "requirements.json",
        "contracts/task_manifest.json": root / "contracts" / "task_manifest.json",
        "fixtures/synthetic/pilot_cases.json": root / "fixtures" / "synthetic" / "pilot_cases.json",
    }
    requirements_doc = load_json(contract_paths["contracts/requirements.json"])
    manifest = load_json(contract_paths["contracts/task_manifest.json"])
    cases_doc = load_json(contract_paths["fixtures/synthetic/pilot_cases.json"])
    state_path = root / "progress" / "task_state.json"
    state_doc = load_json(state_path) if state_path.is_file() else {"tasks": {}}

    violations: list[str] = []
    violations.extend(check_requirements(requirements_doc))
    violations.extend(check_contract_invariants(requirements_doc))
    violations.extend(check_manifest(manifest))
    violations.extend(check_requirements_manifest_consistency(requirements_doc, manifest))
    violations.extend(check_pilot_cases(cases_doc))
    violations.extend(check_task_state(state_doc, manifest, root))
    if baseline_path is not None:
        violations.extend(compare_baseline(load_json(baseline_path), requirements_doc, cases_doc, contract_paths))

    context = {
        "requirements_doc": requirements_doc,
        "cases_doc": cases_doc,
        "contract_paths": contract_paths,
    }
    return violations, context


def main() -> int:
    parser = argparse.ArgumentParser(description="verify plan contracts (structure only, not product tests)")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--baseline", type=Path, help="compare current contracts against a saved baseline")
    parser.add_argument("--write-baseline", type=Path, help="freeze thresholds/invariants/case ids to a baseline file")
    args = parser.parse_args()

    root = args.root.resolve()
    try:
        violations, context = run_all_checks(root, args.baseline)
    except (OSError, json.JSONDecodeError) as error:
        print(f"INPUT_ERROR: {error}")
        return 2

    if args.write_baseline is not None:
        if violations:
            print("拒绝写入基线：当前合同存在校验失败项")
            for violation in violations:
                print(f" - {violation}")
            return 1
        baseline = build_baseline(context["requirements_doc"], context["cases_doc"], context["contract_paths"])
        args.write_baseline.parent.mkdir(parents=True, exist_ok=True)
        args.write_baseline.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"BASELINE_WRITTEN: {args.write_baseline}")
        return 0

    if violations:
        print(f"PLAN_INVALID: {len(violations)} 项不符合同")
        for violation in violations:
            print(f" - {violation}")
        return 1
    print("PLAN_OK: 需求/任务/顺序/案例/状态结构校验通过（不代表产品测试通过）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
