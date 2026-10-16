"""Synthetic local filesystem probes; no human labels or holdout answers are read."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO
from unittest.mock import patch

from scripts.annotation import prepare

CHILD = """
import json
import sys
import time
from pathlib import Path
from scripts.annotation import prepare
from scripts.annotation.tests.test_prepare import fixture_bundle

mode, output, ready = sys.argv[1:]
document = fixture_bundle()
document['candidate_sha256'] = prepare.digest(prepare.candidate_payload(document))
document['summary'] = prepare.summarize(prepare.validate_candidates(document), None)

def pause():
    Path(ready).write_text('synthetic-ready', encoding='utf-8')
    time.sleep(60)

if mode == 'partial':
    def interrupted_dump(document, stream, **kwargs):
        stream.write('{"synthetic":')
        stream.flush()
        pause()
    prepare.json.dump = interrupted_dump
else:
    original_link = prepare.os.link
    def interrupted_link(source, target):
        if mode == 'before_publish':
            pause()
        original_link(source, target)
        if mode == 'after_publish':
            pause()
    prepare.os.link = interrupted_link

prepare.write_new(Path(output), document)
"""


class AtomicWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="r19-crash-synthetic-")
        self.directory = Path(self.temporary.name)
        self.output = self.directory / "output.json"
        self.document: dict[str, object] = {"data_mode": "fixture", "value": "𠮷安全"}

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_complete_json_bytes_and_hash_match_before_publication(self) -> None:
        expected = (
            json.dumps(self.document, ensure_ascii=False, indent=2) + "\n"
        ).encode()
        prepare.write_new(self.output, self.document)
        self.assertEqual(self.output.read_bytes(), expected)
        self.assertEqual(
            hashlib.sha256(self.output.read_bytes()).digest(),
            hashlib.sha256(expected).digest(),
        )
        self.assertEqual(list(self.directory.glob(".r19-pending-*")), [])

    def test_existing_regular_file_is_never_modified(self) -> None:
        previous = b'{"previous":"synthetic"}\n'
        self.output.write_bytes(previous)
        with self.assertRaisesRegex(prepare.PreparationError, "OUTPUT_EXISTS"):
            prepare.write_new(self.output, self.document)
        self.assertEqual(self.output.read_bytes(), previous)
        self.assertEqual(list(self.directory.glob(".r19-pending-*")), [])

    def test_existing_directory_is_never_modified(self) -> None:
        self.output.mkdir()
        marker = self.output / "synthetic.txt"
        marker.write_bytes(b"previous")
        with self.assertRaisesRegex(prepare.PreparationError, "OUTPUT_EXISTS"):
            prepare.write_new(self.output, self.document)
        self.assertEqual(marker.read_bytes(), b"previous")

    def test_invalid_json_never_creates_final_output(self) -> None:
        with self.assertRaises(ValueError):
            prepare.write_new(self.output, {"fixture": float("nan")})
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.directory.glob(".r19-pending-*")), [])

    def test_file_fsync_failure_never_publishes(self) -> None:
        with (
            patch.object(prepare.os, "fsync", side_effect=OSError("synthetic-fsync")),
            self.assertRaises(OSError),
        ):
            prepare.write_new(self.output, self.document)
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.directory.glob(".r19-pending-*")), [])

    def test_stream_creation_failure_closes_owned_descriptor(self) -> None:
        original_close = os.close
        with (
            patch.object(
                prepare.os, "fdopen", side_effect=OSError("synthetic-open-stream")
            ),
            patch.object(prepare.os, "close", wraps=original_close) as closed,
            self.assertRaises(OSError),
        ):
            prepare.write_new(self.output, self.document)
        self.assertEqual(closed.call_count, 1)
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.directory.glob(".r19-pending-*")), [])

    def test_unsupported_hard_link_fails_closed(self) -> None:
        with (
            patch.object(prepare.os, "link", side_effect=OSError("synthetic-no-link")),
            self.assertRaises(OSError),
        ):
            prepare.write_new(self.output, self.document)
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.directory.glob(".r19-pending-*")), [])

    def test_competing_target_created_before_link_is_not_overwritten(self) -> None:
        original_link = os.link
        previous = b'{"winner":"synthetic-other-writer"}\n'

        def competing_link(source: Path, target: Path) -> None:
            target.write_bytes(previous)
            original_link(source, target)

        with (
            patch.object(prepare.os, "link", side_effect=competing_link),
            self.assertRaisesRegex(prepare.PreparationError, "OUTPUT_EXISTS"),
        ):
            prepare.write_new(self.output, self.document)
        self.assertEqual(self.output.read_bytes(), previous)
        self.assertEqual(list(self.directory.glob(".r19-pending-*")), [])

    def test_unrelated_pending_files_are_never_removed(self) -> None:
        unrelated = self.directory / ".r19-pending-other-instance.json"
        unrelated.write_bytes(b"synthetic-unrelated")
        prepare.write_new(self.output, self.document)
        self.assertEqual(unrelated.read_bytes(), b"synthetic-unrelated")

    def test_replaced_temporary_identity_is_not_published_or_deleted(self) -> None:
        replacement: list[Path] = []

        def replacing_link(source: Path, target: Path) -> None:
            source.unlink()
            source.write_bytes(b"synthetic-other-owner")
            replacement.append(source)
            raise OSError("synthetic-replacement")

        with (
            patch.object(prepare.os, "link", side_effect=replacing_link),
            self.assertRaises(OSError),
        ):
            prepare.write_new(self.output, self.document)
        self.assertFalse(self.output.exists())
        self.assertEqual(replacement[0].read_bytes(), b"synthetic-other-owner")

    def test_temporary_replaced_before_publication_fails_identity_check(self) -> None:
        original_fdopen = os.fdopen
        replacement: list[Path] = []

        @contextmanager
        def replaced_stream(
            descriptor: int, mode: str, encoding: str, newline: str
        ) -> Iterator[IO[str]]:
            with original_fdopen(
                descriptor, mode, encoding=encoding, newline=newline
            ) as stream:
                yield stream
            pending = next(self.directory.glob(".r19-pending-*"))
            pending.unlink()
            pending.write_bytes(b"synthetic-replaced-before-publish")
            replacement.append(pending)

        with (
            patch.object(prepare.os, "fdopen", side_effect=replaced_stream),
            self.assertRaisesRegex(prepare.PreparationError, "OUTPUT_PATH_CHANGED"),
        ):
            prepare.write_new(self.output, self.document)
        self.assertFalse(self.output.exists())
        self.assertEqual(
            replacement[0].read_bytes(), b"synthetic-replaced-before-publish"
        )

    def test_cleanup_failure_reports_error_with_complete_final_file(self) -> None:
        with (
            patch.object(
                prepare,
                "remove_owned_pending",
                side_effect=OSError("synthetic-cleanup"),
            ),
            self.assertRaises(OSError),
        ):
            prepare.write_new(self.output, self.document)
        self.assertEqual(json.loads(self.output.read_bytes()), self.document)
        with self.assertRaisesRegex(prepare.PreparationError, "OUTPUT_EXISTS"):
            prepare.write_new(self.output, self.document)

    def test_symlink_parent_is_refused_before_temporary_creation(self) -> None:
        with (
            patch.object(Path, "is_symlink", return_value=True),
            self.assertRaisesRegex(prepare.PreparationError, "OUTPUT_PATH_UNSAFE"),
        ):
            prepare.write_new(self.output, self.document)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_windows_junction_parent_is_refused_before_temporary_creation(self) -> None:
        with (
            patch.object(Path, "is_junction", return_value=True),
            self.assertRaisesRegex(prepare.PreparationError, "OUTPUT_PATH_UNSAFE"),
        ):
            prepare.write_new(self.output, self.document)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_directory_sync_failure_keeps_only_complete_published_file(self) -> None:
        with (
            patch.object(
                prepare,
                "sync_output_directory",
                side_effect=OSError("synthetic-dir-sync"),
            ),
            self.assertRaises(OSError),
        ):
            prepare.write_new(self.output, self.document)
        self.assertEqual(json.loads(self.output.read_bytes()), self.document)
        self.assertEqual(list(self.directory.glob(".r19-pending-*")), [])

    def test_recovery_does_not_bypass_holdout_export_boundary(self) -> None:
        from scripts.annotation.tests.test_prepare import fixture_bundle

        document = fixture_bundle()
        document["cases"][0]["split"] = "holdout"
        pending = self.directory / ".r19-pending-synthetic-holdout.json"
        pending.write_text(json.dumps(document), encoding="utf-8")
        result = prepare.main(
            [
                "export",
                "--input",
                str(pending),
                "--output",
                str(self.output),
                "--purpose",
                "prompt",
            ]
        )
        self.assertEqual(result, 2)
        self.assertFalse(self.output.exists())
        self.assertTrue(pending.exists())

    def test_recovery_does_not_bypass_external_annotation_boundary(self) -> None:
        from scripts.annotation.tests.test_prepare import (
            fixture_annotations,
            fixture_bundle,
        )

        document = fixture_bundle()
        labels = fixture_annotations()
        document["annotations"] = labels
        document["annotation_sha256"] = prepare.digest(labels)
        pending = self.directory / ".r19-pending-synthetic-annotations.json"
        pending.write_text(json.dumps(document), encoding="utf-8")
        forbidden = prepare.ROOT / "benchmarks/manifests/r19-crash-forbidden.json"
        self.assertFalse(forbidden.exists())
        result = prepare.main(
            ["export", "--input", str(pending), "--output", str(forbidden)]
        )
        self.assertEqual(result, 2)
        self.assertFalse(forbidden.exists())
        self.assertTrue(pending.exists())

    def test_recovery_rejects_tampered_candidate_hash(self) -> None:
        from scripts.annotation.tests.test_prepare import fixture_bundle

        document = fixture_bundle()
        document["candidate_sha256"] = "0" * 64
        pending = self.directory / ".r19-pending-synthetic-tampered.json"
        pending.write_text(json.dumps(document), encoding="utf-8")
        result = prepare.main(
            ["export", "--input", str(pending), "--output", str(self.output)]
        )
        self.assertEqual(result, 2)
        self.assertFalse(self.output.exists())
        self.assertTrue(pending.exists())

    def test_real_local_junction_parent_is_refused(self) -> None:
        target = self.directory / "synthetic-target"
        target.mkdir()
        link = self.directory / "synthetic-junction"
        if os.name == "nt":
            created = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True,
                timeout=10,
                check=False,
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            self.assertTrue(link.is_junction())
        else:
            link.symlink_to(target, target_is_directory=True)
        try:
            with self.assertRaisesRegex(prepare.PreparationError, "OUTPUT_PATH_UNSAFE"):
                prepare.write_new(link / "output.json", self.document)
            self.assertEqual(list(target.iterdir()), [])
        finally:
            self.assertEqual(link.resolve(), target)
            if os.name == "nt":
                link.rmdir()
            else:
                link.unlink()


class ProcessInterruptionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="r19-native-synthetic-")
        self.directory = Path(self.temporary.name)
        self.output = self.directory / "output.json"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def interrupt(self, mode: str) -> list[Path]:
        ready = self.directory / "ready.txt"
        process = subprocess.Popen(
            [sys.executable, "-c", CHILD, mode, str(self.output), str(ready)],
            cwd=prepare.ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            deadline = time.monotonic() + 8
            while (
                not ready.exists()
                and process.poll() is None
                and time.monotonic() < deadline
            ):
                time.sleep(0.01)
            if not ready.exists():
                if process.poll() is None:
                    process.kill()
                stdout, stderr = process.communicate(timeout=5)
                self.fail(
                    f"Synthetic child did not reach barrier: {stdout!r}, {stderr!r}"
                )
            process.kill()
            process.communicate(timeout=5)
            self.assertIsNotNone(process.returncode)
            self.assertNotEqual(process.returncode, 0)
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
        return list(self.directory.glob(".r19-pending-*"))

    def cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(prepare.ROOT / "scripts/annotation/prepare.py"),
                *arguments,
            ],
            cwd=prepare.ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
            check=False,
        )

    def test_interrupted_partial_write_never_exposes_final_file(self) -> None:
        pending = self.interrupt("partial")
        self.assertFalse(self.output.exists())
        self.assertEqual(len(pending), 1)
        result = self.cli("validate", "--input", str(pending[0]))
        self.assertEqual(result.returncode, 2)
        self.assertIn("JSON_INPUT_INVALID", result.stderr)
        self.assertEqual(pending[0].read_bytes(), b'{"synthetic":')

    def test_interrupted_before_publish_can_be_validated_and_reexported(self) -> None:
        pending = self.interrupt("before_publish")
        self.assertFalse(self.output.exists())
        self.assertEqual(len(pending), 1)
        self.assertEqual(self.cli("validate", "--input", str(pending[0])).returncode, 0)
        recovered = self.directory / "recovered.json"
        result = self.cli(
            "export", "--input", str(pending[0]), "--output", str(recovered)
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(recovered.read_bytes()), json.loads(pending[0].read_bytes())
        )
        self.assertTrue(pending[0].exists())
        self.assertEqual(json.loads(result.stdout)["human_gold_count"], 0)

    def test_interrupted_after_publish_keeps_complete_final_file(self) -> None:
        pending = self.interrupt("after_publish")
        self.assertEqual(len(pending), 1)
        self.assertEqual(self.output.read_bytes(), pending[0].read_bytes())
        self.assertEqual(
            self.cli("validate", "--input", str(self.output)).returncode, 0
        )
        previous = self.output.read_bytes()
        result = self.cli(
            "export", "--input", str(pending[0]), "--output", str(self.output)
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("OUTPUT_EXISTS", result.stderr)
        self.assertEqual(self.output.read_bytes(), previous)


if __name__ == "__main__":
    unittest.main()
