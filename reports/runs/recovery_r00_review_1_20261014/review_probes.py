"""Independent negative probes on bounded copies of the frozen plan contract."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from run_commands import run, REVIEW, OUTPUT


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def read(relative: str) -> dict:
    return json.loads((REVIEW / relative).read_text(encoding="utf-8"))


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


manifest, state = read("contracts/task_manifest.json"), read("progress/task_state.json")
recovery = manifest["recovery"]
copy_paths = {"contracts/requirements.json", "contracts/task_manifest.json", "fixtures/synthetic/pilot_cases.json", "progress/task_state.json"}
copy_paths.update(recovery["change_records"])
for entry in [*recovery["capability_slices"].values(), *recovery["original_task_aggregation"].values()]:
    copy_paths.add(entry["acceptance_contract"])
for entry in [*state["tasks"].values(), *state["recovery_tasks"].values()]:
    copy_paths.update(entry.get("evidence", []))
    if entry.get("review_ref"):
        copy_paths.add(entry["review_ref"])
    for child in [*entry.get("slice_acceptance", {}).values(), *entry.get("slices", {}).values()]:
        copy_paths.update(child.get("evidence", []))
        if child.get("review_ref"):
            copy_paths.add(child["review_ref"])


def make_copy(name: str) -> Path:
    root = OUTPUT / "temporary_copies" / name
    for relative in copy_paths:
        source = (REVIEW / relative).resolve()
        if not source.is_relative_to(REVIEW.resolve()) or ".env" in source.name.lower() or "holdout" in relative.lower():
            raise ValueError("Unexpected prohibited reference")
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return root


results = []
for name in ("deep_duplicate", "partial_r01_t06", "passed_without_evidence", "r24_reverse", "accepted_r02_missing_slices"):
    root = make_copy(name)
    changed_state, changed_manifest = copy.deepcopy(state), copy.deepcopy(manifest)
    if name == "deep_duplicate":
        payload = json.dumps(changed_state, ensure_ascii=False)[:-1] + ',"probe":[{"nested":{"x":1,"x":2}}]}'
        (root / "progress/task_state.json").write_text(payload, encoding="utf-8")
    elif name == "partial_r01_t06":
        entry = changed_state["tasks"]["T06"]
        entry.update(status="accepted", implementation="complete", review_ref="reports/reviews/R-T00.md")
        entry["slice_acceptance"]["R01:T06"].update(status="accepted", evidence=["reports/tasks/R00.md"], review_ref="reports/reviews/R-T00.md")
        save(root / "progress/task_state.json", changed_state)
    elif name == "passed_without_evidence":
        changed_state["recovery_tasks"]["R01"]["verification"]["unit"] = "passed"
        changed_state["recovery_tasks"]["R01"]["evidence"] = []
        save(root / "progress/task_state.json", changed_state)
    elif name == "r24_reverse":
        order = changed_manifest["recovery"]["execution_order"]
        left, right = order.index("R24-A"), order.index("R24-B")
        order[left], order[right] = order[right], order[left]
        save(root / "contracts/task_manifest.json", changed_manifest)
    elif name == "accepted_r02_missing_slices":
        ref = "reports/reviews/R-T00.md"
        changed_manifest["recovery"]["authority"].update(status="accepted", review_ref=ref)
        for package in ("R00", "R01", "R02"):
            entry = changed_state["recovery_tasks"][package]
            entry.update(status="accepted", implementation="complete", review_ref=ref, evidence=[ref])
            entry["verification"] = dict.fromkeys(entry["verification"], "passed")
        save(root / "progress/task_state.json", changed_state)
        save(root / "contracts/task_manifest.json", changed_manifest)
    record = run(name, [sys.executable, str(REVIEW / "scripts/verify_plan.py"), "--root", str(root)])
    results.append({"probe": name, "exit_code": record["exit_code"], "stdout": (OUTPUT / record["stdout"]).read_text(encoding="utf-8")})

schema = read("contracts/schemas/public_api_v2.json")
examples = read("contracts/schemas/public_api_v2_examples.json")


def valid(definition: str, value: dict) -> bool:
    return Draft202012Validator({**schema, "$ref": f"#/$defs/{definition}"}, format_checker=FormatChecker()).is_valid(value)


for status in ("clean", "excluded_with_evidence", "insufficient_evidence"):
    result = copy.deepcopy(examples["invalid"]["StackCheckResult"][0])
    result["results"][0].update(reason_code="no_match", status=status)
    results.append({"probe": "no_match_" + status, "valid": valid("StackCheckResult", result)})
answer = copy.deepcopy(examples["valid"]["AskResult"][1])
answer["claims"] = [{"text": "Synthetic unsupported claim", "kind": "source_fact", "support_ids": []}]
results.append({"probe": "source_fact_empty_support", "valid": valid("AskResult", answer)})
answer["claims"][0]["support_ids"] = ["00000000-0000-4000-8000-000000000077"]
answer["citations"] = []
results.append({"probe": "source_fact_orphan_support", "valid": valid("AskResult", answer), "note": "JSON Schema format does not prove evidence visibility, existence or support; R18 runtime adapter remains required."})

hash_results = []
for relative in ("fixtures/synthetic/pilot_cases.json", "progress/history/task_state_pre_recovery_8e265dc.json.txt", "reports/runs/plan_audit_20261014/nvd-response.json", "backend/uv.lock", "backend/pyproject.toml"):
    blob = subprocess.check_output(["git", "show", "d752fe0c8f14dd4c35b39863cfba0d1c902fffae:" + relative], cwd=REVIEW)
    candidate = (REVIEW / relative).read_bytes()
    main = (Path(r"D:\dianzi") / relative).read_bytes()
    hash_results.append({"path": relative, "git_blob": digest(blob), "review_bytes": digest(candidate), "integration_bytes": digest(main), "review_lf_normalized": digest(candidate.replace(b"\r\n", b"\n")), "review_crlf": digest(candidate.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")), "byte_equal_git_review": blob == candidate})

original = json.loads(subprocess.check_output(["git", "show", "b8199ce5dd0a7920ce5770e4f580fe23e0fe9f6b:contracts/task_manifest.json"], cwd=REVIEW))
old_baseline = read("contracts/baselines/plan_baseline_t01.json")
new_baseline = read("contracts/baselines/plan_baseline_recovery_r00.json")
preserved_fields = {field: old_baseline[field] == new_baseline[field] for field in ("schema_version", "purpose", "thresholds", "contract_invariants", "frozen_case_ids")}
cards = []
for task_id, task in manifest["tasks"].items():
    relative = recovery["original_task_aggregation"][task_id]["acceptance_contract"]
    baseline_card = subprocess.check_output(["git", "show", "b8199ce5dd0a7920ce5770e4f580fe23e0fe9f6b:" + relative], cwd=REVIEW).decode("utf-8").replace("\r\n", "\n")
    current = (REVIEW / relative).read_text(encoding="utf-8")
    cards.append({"task": task_id, "path": relative, "original_body_preserved": current.startswith(baseline_card), "all_six_ids": all(f"{task_id}-C{number:02d}" in current for number in range(1, 7)), "final_dependencies_preserved": recovery["original_task_aggregation"][task_id]["final_dependencies"] == original["tasks"][task_id]["depends_on"], "slices": recovery["original_task_aggregation"][task_id]["required_slices"]})
summary = {"negative_probes": results, "hashes": hash_results, "frozen_fields": preserved_fields, "original_manifest_preserved": {field: manifest[field] == original[field] for field in ("tasks", "stages", "execution_order")}, "task_count": len(cards), "slice_count": len(recovery["capability_slices"]), "package_count": len(recovery["work_packages"]), "cards": cards, "current_task_states": {key: {field: entry.get(field) for field in ("status", "implementation", "verification", "reopen_reason")} for key, entry in state["tasks"].items()}, "preparation": recovery["independent_preparation"], "authority": recovery["authority"]}
save(OUTPUT / "independent_probes.json", summary)
print(json.dumps({"negative_probes": results, "hashes": hash_results, "frozen_fields": preserved_fields, "card_preserved_count": sum(card["original_body_preserved"] for card in cards), "six_case_count": sum(card["all_six_ids"] for card in cards), "dependency_preserved_count": sum(card["final_dependencies_preserved"] for card in cards), "slices": len(recovery["capability_slices"])}, ensure_ascii=False, indent=2))
