"""Recovery plan contract tests use explicit synthetic state and corrupted copies."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from test_verify_plan import copy_plan_root, mutate_json, run_verify

VERIFICATION_SCOPES = (
    "unit",
    "contract",
    "integration",
    "security",
    "frontend",
    "e2e",
    "live",
    "manual",
)
RECOVERY_ORDER = [f"R{number:02d}" for number in range(23)] + ["R24-A", "R23", "R24-B"]
STAGE_PACKAGES = {
    "G-A": ["R00", "R01", "R02", "R03"],
    "G-B": ["R04", "R05"],
    "G-C": ["R06", "R07", "R08", "R09", "R10"],
    "G-D": ["R11", "R12", "R13", "R14"],
    "G-E": ["R15", "R16", "R17", "R18"],
    "G-F": ["R19", "R20", "R21"],
    "G-G": ["R22", "R24-A", "R23", "R24-B"],
}
ORIGINAL_WORK_PACKAGES = {
    "T00": ["R00"],
    "T01": ["R00", "R19"],
    "T02": ["R01"],
    "T03": ["R01", "R20"],
    "T04": ["R00", "R02", "R18"],
    "T05": ["R02"],
    "T06": ["R01", "R02", "R20"],
    "T07": ["R03", "R20"],
    "T08": ["R03", "R06", "R08"],
    "T09": ["R04", "R09"],
    "T10": ["R04"],
    "T11": ["R06", "R11"],
    "T12": ["R04", "R06"],
    "T13": ["R06", "R07"],
    "T14": ["R06", "R09"],
    "T15": ["R06", "R09"],
    "T16": ["R03", "R06"],
    "T17": ["R02", "R04", "R10"],
    "T18": ["R05"],
    "T19": ["R02", "R07", "R08"],
    "T20": ["R05", "R07"],
    "T21": ["R02", "R10"],
    "T22": ["R07", "R09", "R10"],
    "T23": ["R07", "R08", "R10"],
    "T24": ["R11"],
    "T25": ["R13"],
    "T26": ["R11"],
    "T27": ["R11"],
    "T28": ["R11", "R16"],
    "T29": ["R11"],
    "T30": ["R05", "R12"],
    "T31": ["R05", "R12"],
    "T32": ["R14", "R18"],
    "T33": ["R14"],
    "T34": ["R14"],
    "T35": ["R12", "R14", "R18"],
    "T36": ["R16"],
    "T37": ["R16"],
    "T38": ["R16"],
    "T39": ["R15", "R16"],
    "T40": ["R01", "R04", "R17"],
    "T41": ["R04", "R07", "R10", "R17"],
    "T42": ["R11", "R13", "R17"],
    "T43": ["R05", "R12", "R14", "R15", "R17"],
    "T44": ["R16", "R17", "R20"],
    "T45": ["R20"],
    "T46": ["R19"],
    "T47": ["R21"],
    "T48": ["R21"],
    "T49": ["R06", "R20"],
    "T50": ["R20"],
    "T51": ["R18", "R20"],
    "T52": ["R22"],
    "T53": ["R22"],
    "T54": ["R06", "R22"],
    "T55": ["R24-A"],
    "T56": ["R24-A"],
    "T57": ["R23"],
    "T58": ["R23"],
    "T59": ["R24-A", "R24-B"],
}
REQUIREMENTS = ["F1", "F2", "F3", "P1", "P2", "P3", "A1", "E1", "D1", "D2", "X1", "R1", "R2"]


def install_recovery_fixture(root: Path) -> None:
    """Build an isolated document-only recovery contract, never product or gold data."""
    manifest_path = root / "contracts" / "task_manifest.json"
    state_path = root / "progress" / "task_state.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    contract_path = "docs/tasks/synthetic_acceptance.md"
    (root / contract_path).parent.mkdir(parents=True, exist_ok=True)
    (root / contract_path).write_text(
        "Synthetic acceptance contract for validator tests.\n", encoding="utf-8"
    )
    recovery = {
        "schema_version": 1,
        "stages": {
            stage: {"work_packages": packages} for stage, packages in STAGE_PACKAGES.items()
        },
        "execution_order": RECOVERY_ORDER.copy(),
        "work_packages": {},
        "capability_slices": {},
        "original_task_aggregation": {},
        "independent_preparation": [],
        "change_records": [],
        "authority": {"status": "awaiting_review", "review_ref": None},
    }
    for position, package_id in enumerate(RECOVERY_ORDER):
        recovery["work_packages"][package_id] = {
            "stage": next(
                stage for stage, packages in STAGE_PACKAGES.items() if package_id in packages
            ),
            "depends_on": RECOVERY_ORDER[position - 1 : position] if position else [],
            "requires_slices": [],
            "output_slices": [],
            "requirements": REQUIREMENTS.copy() if package_id == "R00" else ["E1"],
            "scenarios": [f"U{number:02d}" for number in range(1, 15)]
            if package_id == "R00"
            else [],
        }
    for task_id, packages in ORIGINAL_WORK_PACKAGES.items():
        slice_ids = [f"{package_id}:{task_id}" for package_id in packages]
        recovery["original_task_aggregation"][task_id] = {
            "required_slices": slice_ids,
            "final_dependencies": manifest["tasks"][task_id]["depends_on"].copy(),
            "acceptance_contract": contract_path,
            "acceptance_rule": "All slices and dependencies require independent acceptance.",
        }
        for package_id, slice_id in zip(packages, slice_ids, strict=True):
            recovery["capability_slices"][slice_id] = {
                "original_task": task_id,
                "work_package": package_id,
                "description": f"Synthetic {package_id} capability slice of {task_id}.",
                "acceptance_contract": contract_path,
            }
            recovery["work_packages"][package_id]["output_slices"].append(slice_id)
        state["tasks"][task_id].update(
            {
                "status": "pending",
                "implementation": "not_started",
                "verification": dict.fromkeys(VERIFICATION_SCOPES, "not_run"),
                "evidence": [],
                "review_ref": None,
                "required_slices": slice_ids,
                "slice_acceptance": {
                    slice_id: {"status": "pending", "evidence": [], "review_ref": None}
                    for slice_id in slice_ids
                },
            }
        )
    state["recovery_tasks"] = {
        f"R{number:02d}": {
            "status": "pending",
            "implementation": "not_started",
            "verification": dict.fromkeys(VERIFICATION_SCOPES, "not_run"),
            "evidence": [],
            "review_ref": None,
        }
        for number in range(25)
    }
    state["recovery_tasks"]["R24"]["slices"] = {
        label: {
            "status": "pending",
            "implementation": "not_started",
            "verification": dict.fromkeys(VERIFICATION_SCOPES, "not_run"),
            "evidence": [],
            "review_ref": None,
        }
        for label in ("A", "B")
    }
    for number in range(1, 10):
        relative = f"docs/decisions/CR-R{number:02d}.md"
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(f"Synthetic CR-R{number:02d}.\n", encoding="utf-8")
        recovery["change_records"].append(relative)
    manifest["recovery"] = recovery
    for path, document in ((manifest_path, manifest), (state_path, state)):
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class RecoveryPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="recovery_plan_test_"))
        self.addCleanup(shutil.rmtree, self.temp_dir, True)
        self.root = copy_plan_root(self.temp_dir / "plan_root")
        install_recovery_fixture(self.root)
        self.manifest_path = self.root / "contracts" / "task_manifest.json"
        self.state_path = self.root / "progress" / "task_state.json"

    def assert_violation(self, code: str) -> None:
        result = run_verify(self.root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(code, result.stdout)

    def accept_recovery_packages(self, package_ids: list[str]) -> None:
        """Approve synthetic slices without accepting their larger original T cards."""
        reference = "reports/reviews/synthetic_package_acceptance.md"
        (self.root / reference).parent.mkdir(parents=True, exist_ok=True)
        (self.root / reference).write_text(
            "Synthetic independent review evidence for validator tests only.\n", encoding="utf-8"
        )
        manifest = mutate_json(
            self.manifest_path,
            lambda doc: doc["recovery"]["authority"].update(
                {"status": "accepted", "review_ref": reference}
            ),
        )

        def accept_packages(doc: dict) -> None:
            for package_id in package_ids:
                entry = (
                    doc["recovery_tasks"]["R24"]["slices"][package_id[-1]]
                    if package_id.startswith("R24-")
                    else doc["recovery_tasks"][package_id]
                )
                entry.update(
                    {
                        "status": "accepted",
                        "implementation": "complete",
                        "verification": dict.fromkeys(VERIFICATION_SCOPES, "passed"),
                        "evidence": [reference],
                        "review_ref": reference,
                    }
                )
                for slice_id in manifest["recovery"]["work_packages"][package_id]["output_slices"]:
                    task_id = manifest["recovery"]["capability_slices"][slice_id]["original_task"]
                    doc["tasks"][task_id]["slice_acceptance"][slice_id].update(
                        {"status": "accepted", "evidence": [reference], "review_ref": reference}
                    )

        mutate_json(self.state_path, accept_packages)

    def test_recovery_plan_passes(self) -> None:
        result = run_verify(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_independently_accepted_original_task_can_pass(self) -> None:
        reference = "reports/reviews/synthetic.md"
        (self.root / reference).parent.mkdir(parents=True, exist_ok=True)
        (self.root / reference).write_text(
            "Synthetic review for state validation.\n", encoding="utf-8"
        )

        def accept_t00(doc: dict) -> None:
            entry = doc["tasks"]["T00"]
            entry.update(
                {
                    "status": "accepted",
                    "implementation": "complete",
                    "evidence": [reference],
                    "review_ref": reference,
                }
            )
            entry["slice_acceptance"]["R00:T00"].update(
                {"status": "accepted", "evidence": [reference], "review_ref": reference}
            )

        mutate_json(self.state_path, accept_t00)
        result = run_verify(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_duplicate_json_keys_fail_at_any_depth(self) -> None:
        for payload in (
            '{"tasks": {}, "tasks": {}}',
            '{"tasks": {"T00": {"status": "pending", "status": "accepted"}}}',
            '{"history": [{"status": "pending", "status": "accepted"}]}',
        ):
            with self.subTest(payload=payload):
                self.state_path.write_text(payload, encoding="utf-8")
                result = run_verify(self.root)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("INPUT_ERROR", result.stdout)
                self.assertIn("重复JSON键", result.stdout)

    def test_original_mapping_cannot_omit_task(self) -> None:
        mutate_json(
            self.manifest_path, lambda doc: doc["recovery"]["original_task_aggregation"].pop("T59")
        )
        self.assert_violation("RECOVERY_TASK_MAP")

    def test_recovery_dependency_must_exist(self) -> None:
        mutate_json(
            self.manifest_path,
            lambda doc: doc["recovery"]["work_packages"]["R03"]["depends_on"].append("R99"),
        )
        self.assert_violation("RECOVERY_DEP_MISSING")

    def test_recovery_dependency_cycle_fails(self) -> None:
        mutate_json(
            self.manifest_path,
            lambda doc: doc["recovery"]["work_packages"]["R00"]["depends_on"].append("R03"),
        )
        self.assert_violation("RECOVERY_DEP_CYCLE")

    def test_final_candidate_reproduction_freeze_order_is_enforced(self) -> None:
        def reverse_final_steps(doc: dict) -> None:
            order = doc["recovery"]["execution_order"]
            left, right = order.index("R24-A"), order.index("R24-B")
            order[left], order[right] = order[right], order[left]

        mutate_json(self.manifest_path, reverse_final_steps)
        self.assert_violation("RECOVERY_FINAL_ORDER")

    def test_requirement_and_scenario_coverage_cannot_be_removed(self) -> None:
        mutate_json(
            self.manifest_path,
            lambda doc: doc["recovery"]["work_packages"]["R00"].update(
                {"requirements": ["E1"], "scenarios": []}
            ),
        )
        self.assert_violation("RECOVERY_REQ_COVERAGE")
        self.assert_violation("RECOVERY_SCENARIO_COVERAGE")

    def test_required_slice_must_exist(self) -> None:
        mutate_json(
            self.manifest_path,
            lambda doc: doc["recovery"]["work_packages"]["R03"]["requires_slices"].append(
                "R02:missing"
            ),
        )
        self.assert_violation("RECOVERY_SLICE_MISSING")

    def test_slice_dependency_owner_must_be_declared(self) -> None:
        mutate_json(
            self.manifest_path,
            lambda doc: doc["recovery"]["work_packages"]["R03"].update(
                {"requires_slices": ["R01:T06"], "depends_on": []}
            ),
        )
        self.assert_violation("RECOVERY_SLICE_DEP")

    def test_slice_cannot_be_assigned_to_another_owner(self) -> None:
        mutate_json(
            self.manifest_path,
            lambda doc: doc["recovery"]["capability_slices"]["R01:T06"].update(
                {"work_package": "R20"}
            ),
        )
        self.assert_violation("RECOVERY_SLICE_OWNER")

    def test_all_eight_verification_layers_are_required(self) -> None:
        mutate_json(
            self.state_path,
            lambda doc: doc["recovery_tasks"]["R01"]["verification"].pop("security"),
        )
        self.assert_violation("STATE_VERIFICATION_SCOPES")

    def test_recovery_passed_requires_existing_evidence(self) -> None:
        mutate_json(
            self.state_path,
            lambda doc: doc["recovery_tasks"]["R01"]["verification"].update({"unit": "passed"}),
        )
        self.assert_violation("EVIDENCE_MISSING")
        mutate_json(
            self.state_path,
            lambda doc: doc["recovery_tasks"]["R01"].update({"evidence": ["missing.log"]}),
        )
        self.assert_violation("EVIDENCE_ABSENT")

    def test_passed_checks_every_evidence_reference(self) -> None:
        mutate_json(
            self.state_path,
            lambda doc: doc["recovery_tasks"]["R01"].update(
                {
                    "verification": dict.fromkeys(VERIFICATION_SCOPES, "passed"),
                    "evidence": ["docs/tasks/synthetic_acceptance.md", "missing.log"],
                }
            ),
        )
        self.assert_violation("EVIDENCE_ABSENT")

    def test_evidence_reference_cannot_escape_project(self) -> None:
        outside = self.temp_dir / "outside.log"
        outside.write_text("External file is not project evidence.\n", encoding="utf-8")
        mutate_json(
            self.state_path,
            lambda doc: doc["recovery_tasks"]["R01"].update(
                {
                    "verification": dict.fromkeys(VERIFICATION_SCOPES, "passed"),
                    "evidence": ["../outside.log"],
                }
            ),
        )
        self.assert_violation("EVIDENCE_ABSENT")

    def test_recovery_state_cannot_omit_card(self) -> None:
        mutate_json(self.state_path, lambda doc: doc["recovery_tasks"].pop("R24"))
        self.assert_violation("STATE_RECOVERY_SET")

    def test_malformed_recovery_object_is_input_error(self) -> None:
        mutate_json(self.manifest_path, lambda doc: doc.update({"recovery": []}))
        result = run_verify(self.root)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("INPUT_ERROR", result.stdout)

    def test_independent_preparation_keeps_final_dependencies(self) -> None:
        preparation = {
            "id": "synthetic-r19-candidates",
            "work_package": "R19",
            "after": ["R04"],
            "requires_slices": ["R04:T10", "R03:T08"],
            "allows": "Prepare synthetic candidate tool.",
            "final_gate": "Original formal acceptance remains required.",
        }
        mutate_json(
            self.manifest_path,
            lambda doc: doc["recovery"].update({"independent_preparation": [preparation]}),
        )
        result = run_verify(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_independent_preparation_cannot_depend_on_later_final_node(self) -> None:
        preparation = {
            "id": "synthetic-r19-candidates",
            "work_package": "R19",
            "after": ["R24-B"],
            "requires_slices": [],
            "allows": "Prepare synthetic candidate tool.",
            "final_gate": "Original formal acceptance remains required.",
        }
        mutate_json(
            self.manifest_path,
            lambda doc: doc["recovery"].update({"independent_preparation": [preparation]}),
        )
        self.assert_violation("RECOVERY_PREPARATION_DEP_ORDER")

    def test_independent_preparation_requires_available_slice(self) -> None:
        preparation = {
            "id": "synthetic-r19-candidates",
            "work_package": "R19",
            "after": ["R04"],
            "requires_slices": ["R20:T06"],
            "allows": "Prepare synthetic candidate tool.",
            "final_gate": "Original formal acceptance remains required.",
        }
        mutate_json(
            self.manifest_path,
            lambda doc: doc["recovery"].update({"independent_preparation": [preparation]}),
        )
        self.assert_violation("RECOVERY_PREPARATION_SLICE")

    def test_accepted_recovery_requires_independent_review(self) -> None:
        mutate_json(
            self.state_path,
            lambda doc: doc["recovery_tasks"]["R01"].update(
                {"status": "accepted", "implementation": "complete"}
            ),
        )
        self.assert_violation("STATE_REVIEW_MISSING")

    def test_accepted_recovery_package_requires_its_output_slices(self) -> None:
        self.accept_recovery_packages(["R00", "R01"])
        mutate_json(
            self.state_path,
            lambda doc: doc["tasks"]["T06"]["slice_acceptance"]["R01:T06"].update(
                {"status": "pending"}
            ),
        )
        self.assert_violation("STATE_RECOVERY_OUTPUT_SLICE")

    def test_accepted_recovery_package_requires_consumed_slices(self) -> None:
        self.accept_recovery_packages(["R00", "R01", "R02"])
        mutate_json(
            self.manifest_path,
            lambda doc: doc["recovery"]["work_packages"]["R02"].update(
                {"requires_slices": ["R01:T06"]}
            ),
        )
        mutate_json(
            self.state_path,
            lambda doc: doc["tasks"]["T06"]["slice_acceptance"]["R01:T06"].update(
                {"status": "pending"}
            ),
        )
        self.assert_violation("STATE_RECOVERY_REQUIRED_SLICE")

    def test_accepted_consumed_slice_needs_evidence_and_review(self) -> None:
        self.accept_recovery_packages(["R00", "R01", "R02"])
        mutate_json(
            self.manifest_path,
            lambda doc: doc["recovery"]["work_packages"]["R02"].update(
                {"requires_slices": ["R01:T06"]}
            ),
        )
        mutate_json(
            self.state_path,
            lambda doc: doc["tasks"]["T06"]["slice_acceptance"]["R01:T06"].update(
                {"evidence": [], "review_ref": None}
            ),
        )
        result = run_verify(self.root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("EVIDENCE_MISSING: R01:T06", result.stdout)
        self.assertIn("STATE_REVIEW_MISSING: R01:T06", result.stdout)

    def test_accepted_slices_allow_recovery_while_original_task_stays_pending(self) -> None:
        self.accept_recovery_packages(["R00", "R01", "R02"])
        mutate_json(
            self.manifest_path,
            lambda doc: doc["recovery"]["work_packages"]["R02"].update(
                {"requires_slices": ["R01:T06"]}
            ),
        )
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["tasks"]["T06"]["status"], "pending")
        self.assertEqual(state["tasks"]["T06"]["slice_acceptance"]["R20:T06"]["status"], "pending")
        result = run_verify(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_r24_a_requires_original_task_output_slice_acceptance(self) -> None:
        self.accept_recovery_packages(RECOVERY_ORDER[: RECOVERY_ORDER.index("R24-A") + 1])
        mutate_json(
            self.state_path,
            lambda doc: doc["tasks"]["T59"]["slice_acceptance"]["R24-A:T59"].update(
                {"status": "pending"}
            ),
        )
        self.assert_violation("STATE_RECOVERY_OUTPUT_SLICE")

    def test_r24_b_requires_candidate_slice_acceptance(self) -> None:
        self.accept_recovery_packages(RECOVERY_ORDER)
        mutate_json(
            self.manifest_path,
            lambda doc: doc["recovery"]["work_packages"]["R24-B"].update(
                {"requires_slices": ["R24-A:T59"]}
            ),
        )
        mutate_json(
            self.state_path,
            lambda doc: doc["tasks"]["T59"]["slice_acceptance"]["R24-A:T59"].update(
                {"status": "pending"}
            ),
        )
        self.assert_violation("STATE_RECOVERY_REQUIRED_SLICE")

    def test_r24_a_accepted_preserves_partial_aggregate(self) -> None:
        self.accept_recovery_packages(RECOVERY_ORDER[: RECOVERY_ORDER.index("R24-A") + 1])
        mutate_json(
            self.state_path,
            lambda doc: doc["recovery_tasks"]["R24"].update(
                {"status": "in_progress", "implementation": "partial"}
            ),
        )
        result = run_verify(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_t06_cannot_be_accepted_with_only_r01_slice(self) -> None:
        review_path = "reports/reviews/synthetic.md"
        (self.root / review_path).parent.mkdir(parents=True, exist_ok=True)
        (self.root / review_path).write_text(
            "Synthetic reviewer evidence, not product approval.\n", encoding="utf-8"
        )

        def accept_only_r01(doc: dict) -> None:
            entry = doc["tasks"]["T06"]
            entry.update(
                {"status": "accepted", "implementation": "complete", "review_ref": review_path}
            )
            entry["slice_acceptance"]["R01:T06"].update(
                {"status": "accepted", "evidence": [review_path], "review_ref": review_path}
            )

        mutate_json(self.state_path, accept_only_r01)
        self.assert_violation("STATE_SLICE_INCOMPLETE")

    def test_original_final_dependencies_cannot_be_reduced(self) -> None:
        mutate_json(
            self.manifest_path,
            lambda doc: doc["recovery"]["original_task_aggregation"]["T06"].update(
                {"final_dependencies": []}
            ),
        )
        self.assert_violation("RECOVERY_FINAL_DEPS")

    def test_r24_a_alone_cannot_accept_aggregate(self) -> None:
        mutate_json(
            self.state_path,
            lambda doc: doc["recovery_tasks"]["R24"].update(
                {"status": "accepted", "implementation": "complete"}
            ),
        )
        self.assert_violation("STATE_R24_INCOMPLETE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
