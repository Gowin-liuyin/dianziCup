"""Behavior tests for scripts/verify_plan.py against intact and deliberately corrupted plan copies."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify_plan.py"
FIXTURE_FILES = [
    "contracts/requirements.json",
    "contracts/task_manifest.json",
    "fixtures/synthetic/pilot_cases.json",
    "progress/task_state.json",
]


def copy_plan_root(destination: Path) -> Path:
    """Copy the plan contracts plus every evidence file the state index claims to reference."""
    for relative in FIXTURE_FILES:
        source = REPO_ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    state_doc = json.loads((destination / "progress" / "task_state.json").read_text(encoding="utf-8"))
    evidence_paths = {path for entry in state_doc.get("tasks", {}).values() for path in entry.get("evidence", [])}
    for relative in evidence_paths:
        source = REPO_ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return destination


def run_verify(root: Path, *extra_args: str) -> subprocess.CompletedProcess:
    command = [sys.executable, str(VERIFY_SCRIPT), "--root", str(root), *extra_args]
    return subprocess.run(command, capture_output=True, text=True, timeout=120)


def mutate_json(path: Path, mutate) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    mutate(doc)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return doc


class VerifyPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="verify_plan_test_"))
        self.addCleanup(shutil.rmtree, self.temp_dir, True)
        self.root = copy_plan_root(self.temp_dir / "plan_root")

    def test_valid_plan_passes(self) -> None:
        result = run_verify(self.root)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("PLAN_OK", result.stdout)

    def test_prelim_total_mismatch_fails(self) -> None:
        def lower_f1_prelim_score(doc: dict) -> None:
            next(item for item in doc["requirements"] if item["id"] == "F1")["prelim_score"] = 14

        mutate_json(self.root / "contracts" / "requirements.json", lower_f1_prelim_score)
        result = run_verify(self.root)
        self.assertNotEqual(result.returncode, 0, msg=result.stdout)
        self.assertIn("REQ_PRELIM_TOTAL", result.stdout)

    def test_missing_requirement_task_mapping_fails(self) -> None:
        mutate_json(
            self.root / "contracts" / "requirements.json",
            lambda doc: next(item for item in doc["requirements"] if item["id"] == "F3").update(
                {"implementation_tasks": [], "acceptance_tasks": []}
            ),
        )
        result = run_verify(self.root)
        self.assertNotEqual(result.returncode, 0, msg=result.stdout)
        self.assertIn("F3", result.stdout)

    def test_missing_dependency_fails(self) -> None:
        mutate_json(
            self.root / "contracts" / "task_manifest.json",
            lambda doc: doc["tasks"]["T05"]["depends_on"].append("T99"),
        )
        result = run_verify(self.root)
        self.assertNotEqual(result.returncode, 0, msg=result.stdout)
        self.assertIn("T99", result.stdout)

    def test_dependency_cycle_fails(self) -> None:
        mutate_json(
            self.root / "contracts" / "task_manifest.json",
            lambda doc: doc["tasks"]["T00"]["depends_on"].append("T59"),
        )
        result = run_verify(self.root)
        self.assertNotEqual(result.returncode, 0, msg=result.stdout)
        self.assertIn("DEP_CYCLE", result.stdout)

    def test_unmarked_synthetic_case_fails(self) -> None:
        mutate_json(
            self.root / "fixtures" / "synthetic" / "pilot_cases.json",
            lambda doc: doc["cases"][0].update({"is_synthetic": False}),
        )
        result = run_verify(self.root)
        self.assertNotEqual(result.returncode, 0, msg=result.stdout)
        self.assertIn("SYN-REV-001", result.stdout)

    def test_missing_case_field_fails(self) -> None:
        mutate_json(
            self.root / "fixtures" / "synthetic" / "pilot_cases.json",
            lambda doc: doc["cases"][1].pop("expected_basis"),
        )
        result = run_verify(self.root)
        self.assertNotEqual(result.returncode, 0, msg=result.stdout)
        self.assertIn("SYN-REV-002", result.stdout)
        self.assertIn("expected_basis", result.stdout)

    def test_passed_without_evidence_fails(self) -> None:
        def mark_passed_without_evidence(doc: dict) -> None:
            entry = doc["tasks"]["T01"]
            entry["verification"] = {"unit": "passed"}
            entry.pop("evidence", None)

        mutate_json(self.root / "progress" / "task_state.json", mark_passed_without_evidence)
        result = run_verify(self.root)
        self.assertNotEqual(result.returncode, 0, msg=result.stdout)
        self.assertIn("EVIDENCE_MISSING", result.stdout)
        self.assertIn("T01", result.stdout)

    def test_unknown_verification_enum_fails(self) -> None:
        mutate_json(
            self.root / "progress" / "task_state.json",
            lambda doc: doc["tasks"]["T00"]["verification"].update({"live": "blocked_live"}),
        )
        result = run_verify(self.root)
        self.assertNotEqual(result.returncode, 0, msg=result.stdout)
        self.assertIn("blocked_live", result.stdout)

    def test_execution_order_violation_fails(self) -> None:
        def swap_t18_and_t17(doc: dict) -> None:
            order = doc["execution_order"]
            index_18, index_17 = order.index("T18"), order.index("T17")
            order[index_18], order[index_17] = order[index_17], order[index_18]

        mutate_json(self.root / "contracts" / "task_manifest.json", swap_t18_and_t17)
        result = run_verify(self.root)
        self.assertNotEqual(result.returncode, 0, msg=result.stdout)
        self.assertTrue("ORDER_RULE" in result.stdout or "DEP_ORDER" in result.stdout, msg=result.stdout)

    def test_baseline_detects_threshold_change(self) -> None:
        baseline_path = self.temp_dir / "frozen_baseline.json"
        write_result = run_verify(self.root, "--write-baseline", str(baseline_path))
        self.assertEqual(write_result.returncode, 0, msg=write_result.stdout)

        def raise_f1_final_score(doc: dict) -> None:
            next(item for item in doc["requirements"] if item["id"] == "F1")["final_score"] = 12

        mutate_json(self.root / "contracts" / "requirements.json", raise_f1_final_score)
        result = run_verify(self.root, "--baseline", str(baseline_path))
        self.assertNotEqual(result.returncode, 0, msg=result.stdout)
        self.assertIn("BASELINE_THRESHOLD_CHANGED", result.stdout)
        self.assertIn("F1", result.stdout)

    def test_baseline_detects_removed_case(self) -> None:
        baseline_path = self.temp_dir / "frozen_baseline.json"
        write_result = run_verify(self.root, "--write-baseline", str(baseline_path))
        self.assertEqual(write_result.returncode, 0, msg=write_result.stdout)

        def drop_first_case(doc: dict) -> None:
            doc["cases"] = [case for case in doc["cases"] if case["case_id"] != "SYN-REV-001"]

        mutate_json(self.root / "fixtures" / "synthetic" / "pilot_cases.json", drop_first_case)
        result = run_verify(self.root, "--baseline", str(baseline_path))
        self.assertNotEqual(result.returncode, 0, msg=result.stdout)
        self.assertIn("BASELINE_CASE_DELETED", result.stdout)
        self.assertIn("SYN-REV-001", result.stdout)

    def test_baseline_detects_deleted_invariant(self) -> None:
        baseline_path = self.temp_dir / "frozen_baseline.json"
        write_result = run_verify(self.root, "--write-baseline", str(baseline_path))
        self.assertEqual(write_result.returncode, 0, msg=write_result.stdout)

        def drop_invariant(doc: dict) -> None:
            doc["contract_invariants"] = [item for item in doc["contract_invariants"] if item["id"] != "INV-P3-no-5s-in-excellent"]

        mutate_json(self.root / "contracts" / "requirements.json", drop_invariant)
        result = run_verify(self.root, "--baseline", str(baseline_path))
        self.assertNotEqual(result.returncode, 0, msg=result.stdout)
        self.assertIn("BASELINE_INV_DELETED", result.stdout)

    def test_baseline_detects_case_content_change_with_same_id(self) -> None:
        baseline_path = self.temp_dir / "frozen_baseline.json"
        write_result = run_verify(self.root, "--write-baseline", str(baseline_path))
        self.assertEqual(write_result.returncode, 0, msg=write_result.stdout)

        def weaken_syn_rev_001_expected_result(doc: dict) -> None:
            next(case for case in doc["cases"] if case["case_id"] == "SYN-REV-001")["expected_result"] = "被弱化的预期结果（案例ID不变）"

        mutate_json(self.root / "fixtures" / "synthetic" / "pilot_cases.json", weaken_syn_rev_001_expected_result)
        result = run_verify(self.root, "--baseline", str(baseline_path))
        self.assertNotEqual(result.returncode, 0, msg=result.stdout)
        self.assertIn("BASELINE_SOURCE_HASH_CHANGED", result.stdout)
        self.assertIn("fixtures/synthetic/pilot_cases.json", result.stdout)
        self.assertNotIn("BASELINE_CASE_DELETED", result.stdout)

    def test_baseline_detects_task_manifest_change(self) -> None:
        baseline_path = self.temp_dir / "frozen_baseline.json"
        write_result = run_verify(self.root, "--write-baseline", str(baseline_path))
        self.assertEqual(write_result.returncode, 0, msg=write_result.stdout)

        def restore_f1_on_t06(doc: dict) -> None:
            doc["tasks"]["T06"]["requirements"] = ["F1", "E1", "F3", "X1"]

        mutate_json(self.root / "contracts" / "task_manifest.json", restore_f1_on_t06)
        result = run_verify(self.root, "--baseline", str(baseline_path))
        self.assertNotEqual(result.returncode, 0, msg=result.stdout)
        self.assertIn("BASELINE_SOURCE_HASH_CHANGED", result.stdout)
        self.assertIn("contracts/task_manifest.json", result.stdout)

    def test_baseline_passes_on_unchanged_copy(self) -> None:
        baseline_path = self.temp_dir / "frozen_baseline.json"
        write_result = run_verify(self.root, "--write-baseline", str(baseline_path))
        self.assertEqual(write_result.returncode, 0, msg=write_result.stdout)
        result = run_verify(self.root, "--baseline", str(baseline_path))
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("PLAN_OK", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
