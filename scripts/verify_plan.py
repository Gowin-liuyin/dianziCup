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

REQUIREMENT_IDS = [
    "F1",
    "F2",
    "F3",
    "P1",
    "P2",
    "P3",
    "A1",
    "E1",
    "D1",
    "D2",
    "X1",
    "R1",
    "R2",
]
FINAL_SCORED_IDS = ["F1", "F2", "F3", "P1", "P2", "P3", "A1", "E1", "D1", "D2", "X1"]
PRELIM_TOTAL = 100
FINAL_TOTAL = 100
EXPECTED_TASK_COUNT = 60
EXPECTED_STAGES = ["G0", "G1", "G2", "G3", "G4", "G5", "G6"]
TASK_STATUS_VALUES = [
    "pending",
    "in_progress",
    "awaiting_review",
    "accepted",
    "blocked",
    "needs_changes",
]
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
RECOVERY_STAGES = ["G-A", "G-B", "G-C", "G-D", "G-E", "G-F", "G-G"]
RECOVERY_TASK_IDS = [f"R{number:02d}" for number in range(25)]
RECOVERY_WORK_PACKAGES = [f"R{number:02d}" for number in range(24)] + ["R24-A", "R24-B"]
VERIFICATION_SCOPES = [
    "unit",
    "contract",
    "integration",
    "security",
    "frontend",
    "e2e",
    "live",
    "manual",
]
SCENARIO_IDS = [f"U{number:02d}" for number in range(1, 15)]


def reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict:
    """Reject repeated keys in every JSON object, including nested history records."""
    document: dict = {}
    for key, value in pairs:
        if key in document:
            raise ValueError(f"重复JSON键: {key}")
        document[key] = value
    return document


def load_json(path: Path) -> dict:
    try:
        document = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_json_keys
        )
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from error
    if not isinstance(document, dict):
        raise ValueError(f"{path}: JSON根节点必须为对象")
    return document


def require_object(value: object, field: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{field}: 必须为JSON对象")
    return value


def require_string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field}: 必须为字符串数组")
    if len(value) != len(set(value)):
        raise ValueError(f"{field}: 数组包含重复值")
    return value


def check_file_reference(reference: object, label: str, root: Path, code: str) -> list[str]:
    """Check repository-local evidence references without reading their contents."""
    if not isinstance(reference, str) or not reference:
        return [f"{code}: {label} 缺文件路径"]
    candidate = (root / reference).resolve()
    if Path(reference).is_absolute() or not candidate.is_relative_to(root.resolve()):
        return [f"{code}: {label} 路径超出项目范围 {reference}"]
    if not candidate.is_file():
        return [f"{code}: {label} 引用的证据不存在 {reference}"]
    return []


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
        if (
            by_id[requirement_id].get("final_score") is not None
            or by_id[requirement_id].get("prelim_score") is not None
        ):
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
            violations.append(
                f"REQ_NO_INTERNAL_FIELD: {requirement_id} 缺内部目标字段（不得与官方档位混写）"
            )
        for evidence in item.get("planned_evidence", []):
            if evidence.get("status") != "planned" and not evidence.get("path"):
                violations.append(f"REQ_EVIDENCE_FIELD: {requirement_id} 证据项缺path")
    return violations


def flatten_field_text(value: object) -> str:
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
            violations.append(
                f"INV_TARGET: {invariant.get('id')} 指向未知要求 {invariant.get('requirement_id')}"
            )
            continue
        field_value = requirement
        for part in invariant.get("field", "").split("."):
            field_value = field_value.get(part) if isinstance(field_value, dict) else None
        text = flatten_field_text(field_value)
        needle = invariant.get("value", "")
        if invariant.get("rule") == "must_contain" and needle not in text:
            violations.append(
                f"INV_VIOLATED: {invariant.get('id')} 字段 {invariant.get('field')} 不含 “{needle}”"
            )
        if invariant.get("rule") == "must_not_contain" and needle in text:
            violations.append(
                f"INV_VIOLATED: {invariant.get('id')} "
                f"字段 {invariant.get('field')} 不应含 “{needle}”"
            )
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

    staged_tasks = [
        task_id for stage_id in EXPECTED_STAGES for task_id in stages[stage_id].get("tasks", [])
    ]
    if sorted(staged_tasks) != sorted(tasks):
        violations.append("STAGE_PARTITION: 阶段任务划分与任务表不一致")

    execution_order = manifest.get("execution_order", [])
    if sorted(execution_order) != sorted(tasks) or len(execution_order) != len(
        set(execution_order)
    ):
        violations.append(
            f"EXEC_ORDER: execution_order 与任务集合不一致或有重复（len={len(execution_order)}）"
        )
    order_index = {task_id: position for position, task_id in enumerate(execution_order)}

    for task_id, task in tasks.items():
        for dependency in task.get("depends_on", []):
            if dependency not in tasks:
                violations.append(f"DEP_MISSING: {task_id} 依赖不存在的任务 {dependency}")
            elif (
                task_id in order_index
                and dependency in order_index
                and order_index[dependency] >= order_index[task_id]
            ):
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
        if (
            earlier in order_index
            and later in order_index
            and order_index[earlier] >= order_index[later]
        ):
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
            violations.append(f"DEP_CYCLE: 依赖成环 {' -> '.join([*trail[cycle_start:], task_id])}")
            return
        visiting.add(task_id)
        for dependency in tasks.get(task_id, {}).get("depends_on", []):
            if dependency in tasks:
                visit(dependency, [*trail, task_id])
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
        referenced = {
            task_id
            for task_id, task in tasks.items()
            if requirement_id in task.get("requirements", [])
        }
        for task_id in sorted(referenced - declared):
            violations.append(
                f"CONSISTENCY_REQ_TASK: 任务 {task_id} 声明映射 {requirement_id}，"
                "但 requirements.json 未列入"
            )
        for task_id in sorted(declared - referenced):
            violations.append(
                f"CONSISTENCY_TASK_REQ: requirements.json 将 {task_id} 列入 {requirement_id}，"
                "但任务表未声明"
            )
    return violations


def check_recovery_manifest(manifest: dict, root: Path) -> list[str]:
    """Validate recovery execution separately from the original final acceptance DAG."""
    if "recovery" not in manifest:
        return []
    violations: list[str] = []
    recovery = require_object(manifest["recovery"], "recovery")
    if recovery.get("schema_version") != 1:
        violations.append("RECOVERY_SCHEMA: recovery.schema_version 必须为1")
    packages = require_object(recovery.get("work_packages", {}), "recovery.work_packages")
    stages = require_object(recovery.get("stages", {}), "recovery.stages")
    slices = require_object(recovery.get("capability_slices", {}), "recovery.capability_slices")
    aggregation = require_object(
        recovery.get("original_task_aggregation", {}), "recovery.original_task_aggregation"
    )
    if set(packages) != set(RECOVERY_WORK_PACKAGES):
        violations.append("RECOVERY_PACKAGE_SET: 必须含26个执行节点R00–R23及R24-A/B，不含聚合R24")
    if set(stages) != set(RECOVERY_STAGES):
        violations.append("RECOVERY_STAGE_SET: 必须含G-A至G-G七个阶段")
    staged_packages: list[str] = []
    for stage_id, stage_value in stages.items():
        stage = require_object(stage_value, f"recovery.stages.{stage_id}")
        staged_packages.extend(
            require_string_list(stage.get("work_packages", []), f"{stage_id}.work_packages")
        )
    if sorted(staged_packages) != sorted(packages):
        violations.append("RECOVERY_STAGE_PARTITION: 恢复阶段必须唯一划分全部执行节点")
    order = require_string_list(recovery.get("execution_order", []), "recovery.execution_order")
    if set(order) != set(packages):
        violations.append("RECOVERY_EXEC_ORDER: 执行顺序与工作包集合不一致")
    order_index = {package_id: position for position, package_id in enumerate(order)}
    if not all(
        package_id in order_index for package_id in ("R22", "R24-A", "R23", "R24-B")
    ) or not (
        order_index["R22"] < order_index["R24-A"] < order_index["R23"] < order_index["R24-B"]
    ):
        violations.append("RECOVERY_FINAL_ORDER: 必须保持R22→R24-A→R23→R24-B")
    required_tasks = {f"T{number:02d}" for number in range(EXPECTED_TASK_COUNT)}
    if set(aggregation) != required_tasks or set(manifest.get("tasks", {})) != required_tasks:
        violations.append("RECOVERY_TASK_MAP: 原T00–T59必须全部且唯一映射，不得删除或替换")

    covered_requirements: set[str] = set()
    covered_scenarios: set[str] = set()
    output_slices: list[str] = []
    for package_id, package_value in packages.items():
        package = require_object(package_value, f"recovery.work_packages.{package_id}")
        stage_id = package.get("stage")
        if not isinstance(stage_id, str):
            raise ValueError(f"{package_id}.stage: 必须为字符串")
        if stage_id not in stages or package_id not in stages[stage_id].get("work_packages", []):
            violations.append(f"RECOVERY_PACKAGE_STAGE: {package_id}阶段字段与划分不一致")
        dependencies = require_string_list(
            package.get("depends_on", []), f"{package_id}.depends_on"
        )
        for dependency in dependencies:
            if dependency not in packages:
                violations.append(f"RECOVERY_DEP_MISSING: {package_id}依赖未知节点{dependency}")
            elif (
                dependency in order_index
                and package_id in order_index
                and order_index[dependency] >= order_index[package_id]
            ):
                violations.append(f"RECOVERY_DEP_ORDER: {package_id}依赖{dependency}未先执行")
        requirement_ids = require_string_list(
            package.get("requirements", []), f"{package_id}.requirements"
        )
        scenario_ids = require_string_list(package.get("scenarios", []), f"{package_id}.scenarios")
        if not requirement_ids or not set(requirement_ids).issubset(REQUIREMENT_IDS):
            violations.append(f"RECOVERY_PACKAGE_REQ: {package_id}要求映射为空或含未知ID")
        if not set(scenario_ids).issubset(SCENARIO_IDS):
            violations.append(f"RECOVERY_PACKAGE_SCENARIO: {package_id}含未知U场景")
        covered_requirements.update(requirement_ids)
        covered_scenarios.update(scenario_ids)
        output_slices.extend(
            require_string_list(package.get("output_slices", []), f"{package_id}.output_slices")
        )
    if covered_requirements != set(REQUIREMENT_IDS):
        violations.append("RECOVERY_REQ_COVERAGE: 恢复工作包未覆盖全部13个要求")
    if covered_scenarios != set(SCENARIO_IDS):
        violations.append("RECOVERY_SCENARIO_COVERAGE: 恢复工作包未覆盖U01–U14")
    if sorted(output_slices) != sorted(slices):
        violations.append("RECOVERY_SLICE_PARTITION: 各工作包输出必须唯一覆盖所有能力切片")
    violations.extend(
        message.replace("DEP_CYCLE:", "RECOVERY_DEP_CYCLE:", 1)
        for message in find_dependency_cycles(packages)
    )

    def dependency_owners(package_id: str) -> set[str]:
        visited: set[str] = set()
        pending = list(packages[package_id].get("depends_on", []))
        while pending:
            dependency = pending.pop()
            if dependency in visited or dependency not in packages:
                continue
            visited.add(dependency)
            pending.extend(packages[dependency].get("depends_on", []))
        return visited

    for slice_id, slice_value in slices.items():
        capability = require_object(slice_value, f"capability_slices.{slice_id}")
        owner = capability.get("work_package")
        original_task = capability.get("original_task")
        if not isinstance(owner, str) or not isinstance(original_task, str):
            raise ValueError(f"{slice_id}: work_package/original_task必须为字符串")
        if (
            owner not in packages
            or original_task not in required_tasks
            or slice_id != f"{owner}:{original_task}"
            or slice_id not in packages.get(owner, {}).get("output_slices", [])
        ):
            violations.append(f"RECOVERY_SLICE_OWNER: {slice_id}归属、ID或输出声明不一致")
        if not isinstance(capability.get("description"), str) or not capability["description"]:
            violations.append(f"RECOVERY_SLICE_DESCRIPTION: {slice_id}缺能力验收描述")
        violations.extend(
            check_file_reference(
                capability.get("acceptance_contract"), slice_id, root, "RECOVERY_CONTRACT"
            )
        )
    for package_id, package in packages.items():
        for slice_id in require_string_list(
            package.get("requires_slices", []), f"{package_id}.requires_slices"
        ):
            if slice_id not in slices:
                violations.append(f"RECOVERY_SLICE_MISSING: {package_id}引用不存在切片{slice_id}")
                continue
            owner = slices[slice_id].get("work_package")
            if owner == package_id or owner not in dependency_owners(package_id):
                violations.append(
                    f"RECOVERY_SLICE_DEP: {package_id}未声明切片{slice_id}所属节点的前置依赖"
                )
    for task_id, aggregate_value in aggregation.items():
        aggregate = require_object(aggregate_value, f"original_task_aggregation.{task_id}")
        declared_slices = require_string_list(
            aggregate.get("required_slices", []), f"{task_id}.required_slices"
        )
        actual_slices = {
            slice_id
            for slice_id, capability in slices.items()
            if capability.get("original_task") == task_id
        }
        if not declared_slices or set(declared_slices) != actual_slices:
            violations.append(f"RECOVERY_TASK_SLICES: {task_id}合并验收未包含全部所属切片")
        dependencies = require_string_list(
            aggregate.get("final_dependencies", []), f"{task_id}.final_dependencies"
        )
        if set(dependencies) != set(
            manifest.get("tasks", {}).get(task_id, {}).get("depends_on", [])
        ):
            violations.append(f"RECOVERY_FINAL_DEPS: {task_id}改变了原任务最终验收前置")
        if (
            not isinstance(aggregate.get("acceptance_rule"), str)
            or not aggregate["acceptance_rule"]
        ):
            violations.append(f"RECOVERY_ACCEPTANCE_RULE: {task_id}缺合并验收规则")
        violations.extend(
            check_file_reference(
                aggregate.get("acceptance_contract"), task_id, root, "RECOVERY_CONTRACT"
            )
        )
    for task_id in ("T59",):
        required = {f"R24-A:{task_id}", f"R24-B:{task_id}"}
        if not required.issubset(set(aggregation.get(task_id, {}).get("required_slices", []))):
            violations.append(f"RECOVERY_R24_SLICES: {task_id}必须分别包含R24-A与R24-B切片")
    change_records = require_string_list(
        recovery.get("change_records", []), "recovery.change_records"
    )
    if len(change_records) != 9:
        violations.append("RECOVERY_CHANGE_RECORDS: CR-R01–CR-R09须各有正式变更记录")
    for reference in change_records:
        violations.extend(
            check_file_reference(
                reference, "recovery.change_records", root, "RECOVERY_CHANGE_RECORDS"
            )
        )
    preparations = recovery.get("independent_preparation", [])
    if not isinstance(preparations, list):
        raise ValueError("recovery.independent_preparation: 必须为数组")
    preparation_ids: set[str] = set()
    for preparation_value in preparations:
        preparation = require_object(preparation_value, "recovery.independent_preparation entry")
        preparation_id = preparation.get("id")
        if (
            not isinstance(preparation_id, str)
            or not preparation_id
            or preparation_id in preparation_ids
        ):
            violations.append("RECOVERY_PREPARATION_ID: 独立准备必须有唯一非空ID")
        else:
            preparation_ids.add(preparation_id)
        target = preparation.get("work_package")
        if not isinstance(target, str):
            raise ValueError(f"{preparation_id}.work_package: 必须为字符串")
        target_node = "R24-A" if target == "R24" else target
        if target_node not in packages:
            violations.append(f"RECOVERY_PREPARATION_TARGET: {preparation_id}目标工作包不存在")
        after = require_string_list(preparation.get("after", []), f"{preparation_id}.after")
        satisfied_owners: set[str] = set()
        if not after:
            violations.append(f"RECOVERY_PREPARATION_DEP: {preparation_id}必须声明准备前置")
        for dependency in after:
            if dependency not in packages:
                violations.append(
                    f"RECOVERY_PREPARATION_DEP: {preparation_id}前置{dependency}不存在"
                )
                continue
            satisfied_owners.update({dependency, *dependency_owners(dependency)})
            if (
                target_node in order_index
                and order_index.get(dependency, -1) >= order_index[target_node]
            ):
                violations.append(
                    f"RECOVERY_PREPARATION_DEP_ORDER: {preparation_id}准备前置不能晚于正式工作包"
                )
        for slice_id in require_string_list(
            preparation.get("requires_slices", []), f"{preparation_id}.requires_slices"
        ):
            if slice_id not in slices:
                violations.append(
                    f"RECOVERY_PREPARATION_SLICE: {preparation_id}引用未知切片{slice_id}"
                )
            elif slices[slice_id].get("work_package") not in satisfied_owners:
                violations.append(
                    f"RECOVERY_PREPARATION_SLICE: {preparation_id}切片{slice_id}不在准备前置链上"
                )
        if (
            not isinstance(preparation.get("allows"), str)
            or not preparation["allows"]
            or not isinstance(preparation.get("final_gate"), str)
            or not preparation["final_gate"]
        ):
            violations.append(
                f"RECOVERY_PREPARATION_BOUNDARY: {preparation_id}必须说明允许范围与正式验收门"
            )
    authority = require_object(recovery.get("authority", {}), "recovery.authority")
    if authority.get("status") not in TASK_STATUS_VALUES:
        violations.append("RECOVERY_AUTHORITY: 变更生效状态不属于合同枚举")
    if authority.get("status") == "accepted":
        violations.extend(
            check_file_reference(
                authority.get("review_ref"), "recovery.authority", root, "STATE_REVIEW_MISSING"
            )
        )
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


def check_state_entry(entry: dict, label: str, root: Path, require_all_scopes: bool) -> list[str]:
    violations: list[str] = []
    if entry.get("status") not in TASK_STATUS_VALUES:
        violations.append(f"STATE_ENUM: {label}.status={entry.get('status')} 非合同枚举")
    if entry.get("implementation") not in IMPLEMENTATION_VALUES:
        violations.append(
            f"STATE_ENUM: {label}.implementation={entry.get('implementation')} 非合同枚举"
        )
    verification = require_object(entry.get("verification", {}), f"{label}.verification")
    if require_all_scopes and set(verification) != set(VERIFICATION_SCOPES):
        violations.append(f"STATE_VERIFICATION_SCOPES: {label}必须分别登记八层验证状态")
    for scope, value in verification.items():
        if value not in VERIFICATION_VALUES:
            violations.append(f"STATE_ENUM: {label}.verification.{scope}={value} 非合同枚举")
    if "passed" in verification.values() or (
        require_all_scopes and entry.get("status") == "accepted"
    ):
        evidence_paths = require_string_list(entry.get("evidence", []), f"{label}.evidence")
        if not evidence_paths:
            violations.append(f"EVIDENCE_MISSING: {label}声明passed或accepted但无证据文件")
        for evidence_path in evidence_paths:
            violations.extend(check_file_reference(evidence_path, label, root, "EVIDENCE_ABSENT"))
    if require_all_scopes and entry.get("status") == "accepted":
        if entry.get("implementation") != "complete":
            violations.append(f"STATE_ACCEPTED_IMPLEMENTATION: {label}未完整实现不得accepted")
        if "failed" in verification.values() or "blocked" in verification.values():
            violations.append(f"STATE_ACCEPTED_VERIFICATION: {label}存在failed/blocked不得accepted")
        violations.extend(
            check_file_reference(entry.get("review_ref"), label, root, "STATE_REVIEW_MISSING")
        )
    return violations


def check_task_state(state_doc: dict, manifest: dict, root: Path) -> list[str]:
    """Validate accepted slice evidence before recovery nodes consume or publish it."""
    violations: list[str] = []
    tasks_state = require_object(state_doc.get("tasks", {}), "tasks")
    recovery = manifest.get("recovery")
    for task_id in manifest.get("tasks", {}):
        if task_id not in tasks_state:
            violations.append(f"STATE_MISSING_TASK: {task_id}无状态记录")
    for task_id, entry_value in tasks_state.items():
        if task_id not in manifest.get("tasks", {}):
            violations.append(f"STATE_UNKNOWN_TASK: {task_id}不在任务表中")
            continue
        entry = require_object(entry_value, task_id)
        violations.extend(check_state_entry(entry, task_id, root, recovery is not None))
        if recovery is None:
            continue
        required_slices = (
            recovery.get("original_task_aggregation", {})
            .get(task_id, {})
            .get("required_slices", [])
        )
        declared_slices = require_string_list(
            entry.get("required_slices", []), f"{task_id}.required_slices"
        )
        slice_acceptance = require_object(
            entry.get("slice_acceptance", {}), f"{task_id}.slice_acceptance"
        )
        if set(declared_slices) != set(required_slices) or set(slice_acceptance) != set(
            required_slices
        ):
            violations.append(f"STATE_SLICE_SET: {task_id}状态切片与合同合并验收集合不一致")
        for slice_id, slice_value in slice_acceptance.items():
            slice_entry = require_object(slice_value, f"{task_id}.slice_acceptance.{slice_id}")
            if slice_entry.get("status") not in TASK_STATUS_VALUES:
                violations.append(f"STATE_ENUM: {slice_id}.status非合同枚举")
            if slice_entry.get("status") == "accepted":
                evidence_paths = require_string_list(
                    slice_entry.get("evidence", []), f"{slice_id}.evidence"
                )
                if not evidence_paths:
                    violations.append(f"EVIDENCE_MISSING: {slice_id}accepted但缺证据")
                for reference in evidence_paths:
                    violations.extend(
                        check_file_reference(reference, slice_id, root, "EVIDENCE_ABSENT")
                    )
                violations.extend(
                    check_file_reference(
                        slice_entry.get("review_ref"), slice_id, root, "STATE_REVIEW_MISSING"
                    )
                )
        if entry.get("status") != "accepted":
            continue
        for slice_id in required_slices:
            if slice_acceptance.get(slice_id, {}).get("status") != "accepted":
                violations.append(
                    f"STATE_SLICE_INCOMPLETE: {task_id}所需切片{slice_id}尚未独立验收"
                )
        for dependency in (
            recovery.get("original_task_aggregation", {})
            .get(task_id, {})
            .get("final_dependencies", [])
        ):
            if tasks_state.get(dependency, {}).get("status") != "accepted":
                violations.append(
                    f"STATE_FINAL_DEP_INCOMPLETE: {task_id}原最终前置{dependency}未验收"
                )
    if recovery is None:
        return violations
    recovery_states = require_object(state_doc.get("recovery_tasks", {}), "recovery_tasks")
    if set(recovery_states) != set(RECOVERY_TASK_IDS):
        violations.append("STATE_RECOVERY_SET: 状态必须登记25张聚合R00–R24卡")
    for task_id, entry_value in recovery_states.items():
        entry = require_object(entry_value, f"recovery_tasks.{task_id}")
        violations.extend(check_state_entry(entry, task_id, root, True))
    r24 = require_object(recovery_states.get("R24", {}), "recovery_tasks.R24")
    r24_slices = require_object(r24.get("slices", {}), "recovery_tasks.R24.slices")
    if set(r24_slices) != {"A", "B"}:
        violations.append("STATE_R24_SLICES: R24聚合必须分别登记A/B状态")
    for label, entry_value in r24_slices.items():
        violations.extend(
            check_state_entry(
                require_object(entry_value, f"R24-{label}"), f"R24-{label}", root, True
            )
        )
    if r24.get("status") == "accepted" and any(
        r24_slices.get(label, {}).get("status") != "accepted" for label in ("A", "B")
    ):
        violations.append("STATE_R24_INCOMPLETE: R24-A就绪不等于R24整卡验收，须完成A/B")
    for package_id, package in recovery.get("work_packages", {}).items():
        if package_id.startswith("R24-"):
            entry = r24_slices.get(package_id[-1], {})
        else:
            entry = recovery_states.get(package_id, {})
        if entry.get("status") != "accepted":
            continue
        for field, error_code in (
            ("requires_slices", "STATE_RECOVERY_REQUIRED_SLICE"),
            ("output_slices", "STATE_RECOVERY_OUTPUT_SLICE"),
        ):
            for slice_id in package.get(field, []):
                original_task = (
                    recovery.get("capability_slices", {}).get(slice_id, {}).get("original_task")
                )
                slice_entry = (
                    tasks_state.get(original_task, {}).get("slice_acceptance", {}).get(slice_id, {})
                )
                if slice_entry.get("status") != "accepted":
                    violations.append(
                        f"{error_code}: {package_id}的{field}切片{slice_id}尚未独立验收"
                    )
        for dependency in package.get("depends_on", []):
            dependency_entry = (
                r24_slices.get(dependency[-1], {})
                if dependency.startswith("R24-")
                else recovery_states.get(dependency, {})
            )
            if dependency_entry.get("status") != "accepted":
                violations.append(
                    f"STATE_RECOVERY_DEP_INCOMPLETE: {package_id}前置{dependency}未验收"
                )
        if recovery.get("authority", {}).get("status") != "accepted":
            violations.append(f"STATE_RECOVERY_AUTHORITY: {package_id}验收前恢复变更需独立审查生效")
    return violations


def build_baseline(
    requirements_doc: dict, cases_doc: dict, contract_paths: dict[str, Path]
) -> dict:
    return {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "purpose": "冻结评分门槛、合同不变量与合成案例集合，用于发现静默篡改；基线变更须走变更单",
        "source_hashes": {relative: sha256_of(path) for relative, path in contract_paths.items()},
        "thresholds": {
            item["id"]: {
                "prelim_score": item.get("prelim_score"),
                "final_score": item.get("final_score"),
            }
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
            violations.append(
                f"BASELINE_SOURCE_HASH_MISSING: {relative} 未在基线 source_hashes 中冻结"
            )
    for relative, frozen_hash in frozen_hashes.items():
        path = contract_paths.get(relative)
        if path is None or not path.is_file():
            violations.append(
                f"BASELINE_SOURCE_HASH_MISSING: 基线冻结的 {relative} 当前不存在或不可读"
            )
            continue
        current_hash = sha256_of(path)
        if current_hash != frozen_hash:
            violations.append(
                f"BASELINE_SOURCE_HASH_CHANGED: {relative} 内容哈希 "
                f"{frozen_hash} -> {current_hash}，需变更单"
            )
    return violations


def compare_baseline(
    baseline: dict,
    requirements_doc: dict,
    cases_doc: dict,
    contract_paths: dict[str, Path],
) -> list[str]:
    violations: list[str] = check_source_hashes(baseline, contract_paths)
    current_thresholds = {
        item["id"]: {
            "prelim_score": item.get("prelim_score"),
            "final_score": item.get("final_score"),
        }
        for item in requirements_doc.get("requirements", [])
    }
    for requirement_id, frozen in baseline.get("thresholds", {}).items():
        current = current_thresholds.get(requirement_id)
        if current is None:
            violations.append(f"BASELINE_REQ_DELETED: {requirement_id} 被删除")
        elif current != frozen:
            violations.append(
                f"BASELINE_THRESHOLD_CHANGED: {requirement_id} 分值 {frozen} -> {current}，需变更单"
            )
    frozen_invariants = {item.get("id"): item for item in baseline.get("contract_invariants", [])}
    current_invariants = {
        item.get("id"): item for item in requirements_doc.get("contract_invariants", [])
    }
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
    violations.extend(check_recovery_manifest(manifest, root))
    violations.extend(check_requirements_manifest_consistency(requirements_doc, manifest))
    violations.extend(check_pilot_cases(cases_doc))
    violations.extend(check_task_state(state_doc, manifest, root))
    if baseline_path is not None:
        violations.extend(
            compare_baseline(load_json(baseline_path), requirements_doc, cases_doc, contract_paths)
        )

    context = {
        "requirements_doc": requirements_doc,
        "cases_doc": cases_doc,
        "contract_paths": contract_paths,
    }
    return violations, context


def main() -> int:
    parser = argparse.ArgumentParser(
        description="verify plan contracts (structure only, not product tests)"
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--baseline",
        type=Path,
        help="compare current contracts against a saved baseline",
    )
    parser.add_argument(
        "--write-baseline",
        type=Path,
        help="freeze thresholds/invariants/case ids to a baseline file",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    try:
        violations, context = run_all_checks(root, args.baseline)
    except (OSError, ValueError) as error:
        print(f"INPUT_ERROR: {error}")
        return 2

    if args.write_baseline is not None:
        if violations:
            print("拒绝写入基线：当前合同存在校验失败项")
            for violation in violations:
                print(f" - {violation}")
            return 1
        baseline = build_baseline(
            context["requirements_doc"], context["cases_doc"], context["contract_paths"]
        )
        args.write_baseline.parent.mkdir(parents=True, exist_ok=True)
        args.write_baseline.write_text(
            json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
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
