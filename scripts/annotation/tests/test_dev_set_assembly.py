"""Synthetic fixtures exercise dev-set assembly; they are not human gold labels."""

from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from scripts.annotation.assemble_dev_set import (
    SCALE_STATEMENT,
    main as assemble_main,
    validate_dev_set_manifest,
)
from scripts.annotation.build_synthetic_seed import build_seed_document
from scripts.annotation.prepare import (
    ROOT,
    PreparationError,
    candidate_payload,
    digest,
    read_document,
    write_new,
)

REAL_BUNDLE = ROOT / "benchmarks/manifests/r19_public_dev_candidate_v1.json"
SEED_ARTIFACT = ROOT / "benchmarks/manifests/r19_synthetic_dev_seed_v1.json"
DEV_SET_ARTIFACT = ROOT / "benchmarks/manifests/r19_dev_set_assembly_v1.json"
PILOT_FIXTURES = ROOT / "fixtures/synthetic/pilot_cases.json"
REAL_FAMILY = "GHSA-6cxc-2vcg-w5qc"


def pilot_cases() -> list[dict[str, object]]:
    document = read_document(PILOT_FIXTURES)
    return document["cases"]


def write_bundle(document: dict[str, object], directory: Path, name: str) -> Path:
    path = directory / name
    write_new(path, document)
    return path


def resealed(bundle: dict[str, object]) -> dict[str, object]:
    """Recomputes candidate_sha256 so tampering reaches the check under test instead of the hash guard."""
    document = deepcopy(bundle)
    document["candidate_sha256"] = digest(candidate_payload(document))
    return document


def run_assemble(bundles: list[Path], output: Path) -> tuple[int, str]:
    stderr = io.StringIO()
    arguments: list[str] = []
    for bundle in bundles:
        arguments += ["--bundle", str(bundle)]
    arguments += ["--output", str(output)]
    with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
        code = assemble_main(arguments)
    return code, stderr.getvalue()


class DevSetAssemblyTests(unittest.TestCase):
    def test_assembles_real_and_synthetic_with_zero_gold(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            directory = Path(temporary_dir)
            seed_path = write_bundle(
                build_seed_document(pilot_cases()), directory, "seed.json"
            )
            output = directory / "dev_set.json"
            code, stderr = run_assemble([REAL_BUNDLE, seed_path], output)
            self.assertEqual(code, 0, stderr)
            manifest = read_document(output)
            summary = manifest["summary"]
            self.assertEqual(
                summary["counts"]["by_data_kind"],
                {"real": 1, "synthetic": 20, "redacted": 0, "replay": 0},
            )
            self.assertEqual(summary["counts"]["by_split"], {"dev": 21, "demo": 0})
            self.assertEqual(
                summary["label_status_counts"], {"awaiting_human_label": 21}
            )
            self.assertEqual(summary["gold"]["human_gold_count"], 0)
            self.assertEqual(summary["gold"]["formal_evaluation"]["status"], "not_run")
            self.assertIsNone(summary["gold"]["formal_evaluation"]["numerator"])
            self.assertIsNone(summary["gold"]["formal_evaluation"]["denominator"])
            self.assertEqual(summary["scale_statement"], SCALE_STATEMENT)
            self.assertEqual(
                [record["case_count"] for record in summary["source_bundles"]], [1, 20]
            )
            self.assertNotIn("annotations", manifest)
            for case in manifest["cases"]:
                self.assertEqual(case["label_status"], "awaiting_human_label")
                self.assertFalse(
                    any(key.startswith("expected") for key in case),
                    case["case_id"],
                )
            validate_dev_set_manifest(manifest)

    def test_cross_bundle_family_split_leak_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            directory = Path(temporary_dir)
            seed = build_seed_document(pilot_cases())
            seed["cases"][0]["split"] = "demo"
            seed["cases"][0]["family_aliases"] = [REAL_FAMILY]
            seed_path = write_bundle(resealed(seed), directory, "seed_leak.json")
            output = directory / "dev_set.json"
            code, stderr = run_assemble([REAL_BUNDLE, seed_path], output)
            self.assertEqual(code, 2)
            self.assertIn("FAMILY_SPLIT_LEAK", stderr)
            self.assertFalse(output.exists())

    def test_tampered_gold_count_rejected_by_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            directory = Path(temporary_dir)
            seed_path = write_bundle(
                build_seed_document(pilot_cases()), directory, "seed.json"
            )
            output = directory / "dev_set.json"
            code, stderr = run_assemble([REAL_BUNDLE, seed_path], output)
            self.assertEqual(code, 0, stderr)
            manifest = read_document(output)
            tampered = deepcopy(manifest)
            tampered["summary"]["gold"]["human_gold_count"] = 1
            with self.assertRaisesRegex(PreparationError, "DEV_SET_SCHEMA_INVALID"):
                validate_dev_set_manifest(tampered)
            self.assertEqual(
                read_document(output)["summary"]["gold"]["human_gold_count"], 0
            )

    def test_non_awaiting_label_status_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            directory = Path(temporary_dir)
            seed = build_seed_document(pilot_cases())
            seed["cases"][0]["label_status"] = "ready_for_manual_review"
            seed_path = write_bundle(resealed(seed), directory, "seed_labeled.json")
            output = directory / "dev_set.json"
            code, stderr = run_assemble([REAL_BUNDLE, seed_path], output)
            self.assertEqual(code, 2)
            self.assertIn("LABEL_STATUS_NOT_AWAITING", stderr)
            self.assertFalse(output.exists())

    def test_tampered_bundle_without_hash_update_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            directory = Path(temporary_dir)
            seed = build_seed_document(pilot_cases())
            seed["cases"][0]["candidate_task"] += " Tampered text."
            seed_path = write_bundle(seed, directory, "seed_stale_hash.json")
            output = directory / "dev_set.json"
            code, stderr = run_assemble([REAL_BUNDLE, seed_path], output)
            self.assertEqual(code, 2)
            self.assertIn("CANDIDATE_HASH_MISMATCH", stderr)
            self.assertFalse(output.exists())

    def test_holdout_bundle_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            directory = Path(temporary_dir)
            seed = build_seed_document(pilot_cases())
            seed["cases"][0]["split"] = "holdout"
            seed_path = write_bundle(seed, directory, "seed_holdout.json")
            output = directory / "dev_set.json"
            code, stderr = run_assemble([REAL_BUNDLE, seed_path], output)
            self.assertEqual(code, 2)
            self.assertIn("HOLDOUT_SPLIT_REFUSED", stderr)
            self.assertFalse(output.exists())

    def test_same_input_assembles_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            directory = Path(temporary_dir)
            seed_path = write_bundle(
                build_seed_document(pilot_cases()), directory, "seed.json"
            )
            first = directory / "first.json"
            second = directory / "second.json"
            first_code, first_stderr = run_assemble([REAL_BUNDLE, seed_path], first)
            second_code, second_stderr = run_assemble([REAL_BUNDLE, seed_path], second)
            self.assertEqual(first_code, 0, first_stderr)
            self.assertEqual(second_code, 0, second_stderr)
            first_manifest = read_document(first)
            second_manifest = read_document(second)
            self.assertEqual(
                first_manifest["summary"]["dev_set_sha256"],
                second_manifest["summary"]["dev_set_sha256"],
            )
            self.assertEqual(
                first_manifest["cases"], second_manifest["cases"]
            )

    def test_duplicate_empty_and_existing_output_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            directory = Path(temporary_dir)
            seed_path = write_bundle(
                build_seed_document(pilot_cases()), directory, "seed.json"
            )
            duplicate_output = directory / "duplicate.json"
            code, stderr = run_assemble([seed_path, seed_path], duplicate_output)
            self.assertEqual(code, 2)
            self.assertIn("DUPLICATE_CASE", stderr)
            self.assertFalse(duplicate_output.exists())
            empty_output = directory / "empty.json"
            code, stderr = run_assemble([], empty_output)
            self.assertEqual(code, 2)
            self.assertIn("BUNDLE_REQUIRED", stderr)
            self.assertFalse(empty_output.exists())
            existing = directory / "existing.json"
            code, stderr = run_assemble([REAL_BUNDLE, seed_path], existing)
            self.assertEqual(code, 0, stderr)
            code, stderr = run_assemble([REAL_BUNDLE, seed_path], existing)
            self.assertEqual(code, 2)
            self.assertIn("OUTPUT_EXISTS", stderr)

    def test_seed_and_dev_set_artifacts_pass_prepare_validate(self) -> None:
        for artifact in (SEED_ARTIFACT, DEV_SET_ARTIFACT):
            with self.subTest(artifact=artifact.name):
                completed = subprocess.run(
                    [
                        sys.executable,
                        "scripts/annotation/prepare.py",
                        "validate",
                        "--input",
                        str(artifact),
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
        manifest = read_document(DEV_SET_ARTIFACT)
        validate_dev_set_manifest(manifest)
        self.assertEqual(manifest["summary"]["gold"]["human_gold_count"], 0)

    def test_missing_license_or_snapshot_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            directory = Path(temporary_dir)
            for missing_field in ("license", "source_snapshot_time"):
                with self.subTest(field=missing_field):
                    seed = build_seed_document(pilot_cases())
                    del seed["cases"][0][missing_field]
                    seed_path = write_bundle(
                        seed, directory, f"seed_missing_{missing_field}.json"
                    )
                    output = directory / f"out_{missing_field}.json"
                    code, stderr = run_assemble([REAL_BUNDLE, seed_path], output)
                    self.assertEqual(code, 2)
                    self.assertIn("SCHEMA_INVALID", stderr)
                    self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
