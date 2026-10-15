"""Regression tests for the three independent review Musts, using only synthetic records."""

import itertools
import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from scripts.annotation.prepare import (
    ROOT,
    PreparationError,
    inspect_annotations,
    protected_roots,
    require_external,
    validate_candidates,
)
from scripts.annotation.tests.test_prepare import (
    fixture_annotations,
    fixture_bundle,
    fixture_decision,
    fixture_identity,
    fixture_label,
)


def separate_case(stem: str, split: str) -> dict:
    case = fixture_bundle()["cases"][0]
    case.update(
        case_id=stem + "-CASE",
        event_family_id=stem + "-FAMILY",
        family_aliases=[],
        split=split,
    )
    source = case["source_refs"][0]
    source.update(
        uri="urn:synthetic:" + stem,
        document_id=stem + "-DOC",
        revision_id=stem + "-REV",
    )
    evidence = case["evidence"][0]
    evidence.update(
        source_uri=source["uri"],
        revision_id=source["revision_id"],
        span_id=stem + "-SPAN",
        block_id=stem + "-BLOCK",
    )
    case["input_refs"][0]["ref_id"] = evidence["span_id"]
    return case


class FamilyIdentityRegressionTests(unittest.TestCase):
    def test_alias_and_primary_family_share_identity_domain(self) -> None:
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                document = fixture_bundle()
                first, second = (
                    separate_case("SYN-A", "dev"),
                    separate_case("SYN-B", "holdout"),
                )
                second["family_aliases"] = [first["event_family_id"]]
                document["cases"] = [second, first] if reverse else [first, second]
                with self.assertRaisesRegex(PreparationError, "FAMILY_SPLIT_LEAK"):
                    validate_candidates(document)

    def test_family_alias_document_and_uri_use_one_identifier_domain(self) -> None:
        for key in ("family", "alias", "document", "uri"):
            with self.subTest(key=key):
                document = fixture_bundle()
                first, second = (
                    separate_case("SYN-A", "dev"),
                    separate_case("SYN-B", "holdout"),
                )
                identity = {
                    "family": first["event_family_id"],
                    "alias": "SYN-A-ALIAS",
                    "document": first["source_refs"][0]["document_id"],
                    "uri": first["source_refs"][0]["uri"],
                }[key]
                if key == "alias":
                    first["family_aliases"] = [identity]
                second["family_aliases"] = [identity]
                document["cases"] = [first, second]
                with self.assertRaisesRegex(PreparationError, "FAMILY_SPLIT_LEAK"):
                    validate_candidates(document)

    def test_document_uri_cross_field_match_cannot_bypass_split(self) -> None:
        document = fixture_bundle()
        first, second = separate_case("SYN-A", "dev"), separate_case("SYN-B", "holdout")
        first["source_refs"][0]["document_id"] = second["source_refs"][0]["uri"]
        document["cases"] = [first, second]
        with self.assertRaisesRegex(PreparationError, "FAMILY_SPLIT_LEAK"):
            validate_candidates(document)

    def test_transitive_and_cyclic_declared_relations_are_order_independent(
        self,
    ) -> None:
        first, bridge, last = (
            separate_case("SYN-A", "dev"),
            separate_case("SYN-B", "dev"),
            separate_case("SYN-C", "holdout"),
        )
        bridge["family_aliases"] = [first["event_family_id"], last["event_family_id"]]
        last["family_aliases"] = [first["event_family_id"]]
        for cases in itertools.permutations([first, bridge, last]):
            with self.subTest(order=[case["case_id"] for case in cases]):
                document = fixture_bundle()
                document["cases"] = list(cases)
                with self.assertRaisesRegex(PreparationError, "FAMILY_SPLIT_LEAK"):
                    validate_candidates(document)
        last["split"] = "dev"
        document["cases"] = [first, bridge, last]
        self.assertEqual(len(validate_candidates(document)), 3)

    def test_unrelated_identical_quote_does_not_imply_family_identity(self) -> None:
        document = fixture_bundle()
        document["cases"] = [
            separate_case("SYN-A", "dev"),
            separate_case("SYN-B", "demo"),
        ]
        self.assertEqual(len(validate_candidates(document)), 2)


class ReviewRecordRegressionTests(unittest.TestCase):
    def test_zero_or_one_label_cannot_have_adjudication_or_identity_record(
        self,
    ) -> None:
        cases = validate_candidates(fixture_bundle())
        records = [fixture_label("fixture-a"), fixture_label("fixture-b", "conflict")]
        for count, kind in itertools.product(
            (0, 1), ("adjudication", "identity_checks")
        ):
            with self.subTest(count=count, kind=kind):
                annotations = fixture_annotations()
                annotations["annotators"] = records[:count]
                annotations[kind] = [
                    fixture_decision(records)
                    if kind == "adjudication"
                    else fixture_identity(records)
                ]
                with self.assertRaisesRegex(
                    PreparationError, "REVIEW_REQUIRES_TWO_CURRENT_LABELS"
                ):
                    inspect_annotations(cases, annotations)

    def test_orphan_duplicate_reviews_are_rejected_before_pending_state(self) -> None:
        for kind in ("adjudication", "identity_checks"):
            with self.subTest(kind=kind):
                annotations = fixture_annotations()
                records = [fixture_label("fixture-a"), fixture_label("fixture-b")]
                annotations["annotators"] = records[:1]
                review = (
                    fixture_decision(records)
                    if kind == "adjudication"
                    else fixture_identity(records)
                )
                annotations[kind] = [review, deepcopy(review)]
                with self.assertRaisesRegex(
                    PreparationError, "DUPLICATE_REVIEW_RECORD"
                ):
                    inspect_annotations(
                        validate_candidates(fixture_bundle()), annotations
                    )

    def test_pending_adjudication_still_validates_identity_record(self) -> None:
        annotations = fixture_annotations()
        records = [fixture_label("fixture-a"), fixture_label("fixture-b", "conflict")]
        annotations["annotators"] = records
        identity = fixture_identity(records)
        identity["label_sha256s"] = ["0" * 64, "1" * 64]
        annotations["identity_checks"] = [identity]
        with self.assertRaisesRegex(
            PreparationError, "IDENTITY_ATTESTATION_INVALID_OR_STALE"
        ):
            inspect_annotations(validate_candidates(fixture_bundle()), annotations)


class CliRegistryRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(
            prefix="r19-fix1-synthetic-regression-"
        )
        self.directory = Path(self.temporary.name).resolve()
        self.input = self.directory / "synthetic_candidates.json"
        self.input.write_text(json.dumps(fixture_bundle()), encoding="utf-8")
        self.labels = self.directory / "synthetic_labels.json"
        self.labels.write_text(json.dumps(fixture_annotations()), encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts/annotation/prepare.py"), *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )

    def test_alias_primary_validate_and_export_refused(self) -> None:
        document = fixture_bundle()
        first, second = separate_case("SYN-A", "dev"), separate_case("SYN-B", "holdout")
        second["family_aliases"] = [first["event_family_id"]]
        document["cases"] = [first, second]
        self.input.write_text(json.dumps(document), encoding="utf-8")
        for action in ("validate", "export"):
            with self.subTest(action=action):
                output = self.directory / "forbidden_alias_export.json"
                result = self.cli(
                    action, "--input", str(self.input), "--output", str(output)
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("FAMILY_SPLIT_LEAK", result.stderr)
                self.assertFalse(output.exists())

    def test_new_registered_worktree_and_resolved_junction_are_protected(self) -> None:
        linked = self.directory / "registered worktree 注记"
        previous = protected_roots([])
        self.assertNotIn(linked, previous)
        subprocess.run(
            [
                "git",
                "worktree",
                "add",
                "--detach",
                "--no-checkout",
                str(linked),
                "HEAD",
            ],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        junction = self.directory / "junction"
        try:
            self.assertIn(linked.resolve(), protected_roots([]))
            if os.name == "nt":
                subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(junction), str(linked)],
                    capture_output=True,
                    check=True,
                )
            else:
                junction.symlink_to(linked, target_is_directory=True)
            for target in (linked, junction):
                for payload in ("labels", "holdout"):
                    with self.subTest(target=target.name, payload=payload):
                        output = target / (
                            "synthetic_" + payload + "_must_not_exist.json"
                        )
                        arguments = [
                            "export",
                            "--input",
                            str(self.input),
                            "--output",
                            str(output),
                        ]
                        if payload == "labels":
                            arguments.extend(["--labels", str(self.labels)])
                        else:
                            holdout = fixture_bundle()
                            holdout["cases"][0]["split"] = "holdout"
                            self.input.write_text(json.dumps(holdout), encoding="utf-8")
                        result = self.cli(*arguments)
                        self.assertEqual(result.returncode, 2, result.stderr)
                        self.assertIn(
                            "HUMAN_OR_HOLDOUT_PATH_MUST_BE_EXTERNAL", result.stderr
                        )
                        self.assertFalse(output.exists())
                        self.input.write_text(
                            json.dumps(fixture_bundle()), encoding="utf-8"
                        )
        finally:
            if junction.exists():
                self.assertTrue(junction.resolve().is_relative_to(self.directory))
                if os.name == "nt":
                    junction.rmdir()
                else:
                    junction.unlink()
            self.assertTrue(linked.resolve().is_relative_to(self.directory))
            self.assertEqual({entry.name for entry in linked.iterdir()}, {".git"})
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(linked)],
                cwd=ROOT,
                capture_output=True,
                check=True,
            )

    def test_missing_git_registry_fails_closed_with_fixed_error(self) -> None:
        with (
            patch("scripts.annotation.prepare.ROOT", self.directory),
            self.assertRaisesRegex(
                PreparationError, "REPOSITORY_WORKTREE_REGISTRY_UNAVAILABLE"
            ),
        ):
            protected_roots([])
        script = (
            "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
            "import scripts.annotation.prepare as prepare; prepare.ROOT=Path(sys.argv[2]); "
            "raise SystemExit(prepare.main(['validate', '--input', sys.argv[3]]))"
        )
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
                str(ROOT),
                str(self.directory),
                str(self.input),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=30,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("REPOSITORY_WORKTREE_REGISTRY_UNAVAILABLE", result.stderr)

    def test_registered_product_root_and_resolved_path_refused(self) -> None:
        mount = self.directory / "synthetic_product_mount"
        mount.mkdir()
        with self.assertRaisesRegex(
            PreparationError, "HUMAN_OR_HOLDOUT_PATH_MUST_BE_EXTERNAL"
        ):
            require_external(mount / "labels.json", protected_roots([mount]))

    def test_orphan_export_never_creates_signed_annotation_artifact(self) -> None:
        records = [fixture_label("fixture-a"), fixture_label("fixture-b", "conflict")]
        annotations = fixture_annotations()
        annotations["annotators"] = records[:1]
        annotations["adjudication"] = [fixture_decision(records)]
        self.labels.write_text(json.dumps(annotations), encoding="utf-8")
        output = self.directory / "orphan_must_not_exist.json"
        result = self.cli(
            "export",
            "--input",
            str(self.input),
            "--labels",
            str(self.labels),
            "--output",
            str(output),
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("REVIEW_REQUIRES_TWO_CURRENT_LABELS", result.stderr)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
