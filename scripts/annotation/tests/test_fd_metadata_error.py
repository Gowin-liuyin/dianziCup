"""Synthetic metadata faults verify owned FD closure without deleting unidentified files."""

from __future__ import annotations

import errno
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.annotation import prepare


class FileMetadataLifetimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(
            prefix="r19-fd-metadata-synthetic-"
        )
        self.directory = Path(self.temporary.name)
        self.output = self.directory / "output.json"
        self.foreign = self.directory / ".r19-pending-foreign-marker.json"
        self.foreign.write_bytes(b"synthetic-foreign-file")
        self.descriptor: int | None = None
        self.pending: Path | None = None
        self.original_fstat = os.fstat
        self.original_mkstemp = tempfile.mkstemp

    def tearDown(self) -> None:
        if self.descriptor is not None:
            try:
                self.original_fstat(self.descriptor)
            except OSError as error:
                self.assertEqual(error.errno, errno.EBADF)
            else:
                os.close(self.descriptor)
        self.temporary.cleanup()

    def create_pending(self, *, dir: Path, prefix: str, suffix: str) -> tuple[int, str]:
        descriptor, name = self.original_mkstemp(dir=dir, prefix=prefix, suffix=suffix)
        self.descriptor = descriptor
        self.pending = Path(name)
        return descriptor, name

    def assert_descriptor_closed(self) -> None:
        self.assertIsNotNone(self.descriptor)
        if self.descriptor is None:
            self.fail("synthetic descriptor was not created")
        with self.assertRaises(OSError) as captured:
            self.original_fstat(self.descriptor)
        self.assertEqual(captured.exception.errno, errno.EBADF)

    def test_fstat_failure_closes_fd_and_keeps_unknown_identity_residue(self) -> None:
        original_close = os.close
        with (
            patch.object(prepare.tempfile, "mkstemp", side_effect=self.create_pending),
            patch.object(
                prepare.os, "fstat", side_effect=OSError(errno.EIO, "synthetic-fstat")
            ),
            patch.object(prepare.os, "close", wraps=original_close) as closed,
            patch.object(prepare, "remove_owned_pending") as cleanup,
            self.assertRaises(OSError) as captured,
        ):
            prepare.write_new(self.output, {"data_mode": "fixture"})
        self.assertEqual(captured.exception.errno, errno.EIO)
        closed.assert_called_once_with(self.descriptor)
        cleanup.assert_not_called()
        self.assert_descriptor_closed()
        self.assertFalse(self.output.exists())
        self.assertIsNotNone(self.pending)
        if self.pending is None:
            self.fail("synthetic pending path was not created")
        self.assertEqual(self.pending.read_bytes(), b"")
        self.assertEqual(self.foreign.read_bytes(), b"synthetic-foreign-file")

    def test_pending_path_constructor_failure_still_closes_fd(self) -> None:
        original_path = Path
        original_close = os.close

        def pending_path(value: str) -> Path:
            if Path(value).name.startswith(".r19-pending-"):
                raise OSError(errno.EIO, "synthetic-pending-path")
            return original_path(value)

        with (
            patch.object(prepare.tempfile, "mkstemp", side_effect=self.create_pending),
            patch.object(prepare, "Path", side_effect=pending_path),
            patch.object(prepare.os, "close", wraps=original_close) as closed,
            patch.object(prepare, "remove_owned_pending") as cleanup,
            self.assertRaises(OSError) as captured,
        ):
            prepare.write_new(self.output, {"data_mode": "fixture"})
        self.assertEqual(captured.exception.errno, errno.EIO)
        closed.assert_called_once_with(self.descriptor)
        cleanup.assert_not_called()
        self.assert_descriptor_closed()
        self.assertFalse(self.output.exists())
        self.assertEqual(self.foreign.read_bytes(), b"synthetic-foreign-file")

    def test_metadata_base_exception_closes_fd_without_unproven_cleanup(self) -> None:
        original_close = os.close
        with (
            patch.object(prepare.tempfile, "mkstemp", side_effect=self.create_pending),
            patch.object(
                prepare.os, "fstat", side_effect=KeyboardInterrupt("synthetic-only")
            ),
            patch.object(prepare.os, "close", wraps=original_close) as closed,
            patch.object(prepare, "remove_owned_pending") as cleanup,
            self.assertRaises(KeyboardInterrupt),
        ):
            prepare.write_new(self.output, {"data_mode": "fixture"})
        closed.assert_called_once_with(self.descriptor)
        cleanup.assert_not_called()
        self.assert_descriptor_closed()
        self.assertFalse(self.output.exists())
        self.assertEqual(self.foreign.read_bytes(), b"synthetic-foreign-file")

    def test_stream_constructor_failure_closes_fd_with_proven_identity_cleanup(
        self,
    ) -> None:
        original_close = os.close
        with (
            patch.object(prepare.tempfile, "mkstemp", side_effect=self.create_pending),
            patch.object(
                prepare.os, "fdopen", side_effect=OSError(errno.EIO, "synthetic-fdopen")
            ),
            patch.object(prepare.os, "close", wraps=original_close) as closed,
            self.assertRaises(OSError) as captured,
        ):
            prepare.write_new(self.output, {"data_mode": "fixture"})
        self.assertEqual(captured.exception.errno, errno.EIO)
        closed.assert_called_once_with(self.descriptor)
        self.assert_descriptor_closed()
        self.assertFalse(self.output.exists())
        self.assertIsNotNone(self.pending)
        if self.pending is None:
            self.fail("synthetic pending path was not created")
        self.assertFalse(self.pending.exists())
        self.assertEqual(self.foreign.read_bytes(), b"synthetic-foreign-file")

    def test_normal_writer_closes_fd_and_preserves_foreign_file(self) -> None:
        with patch.object(prepare.tempfile, "mkstemp", side_effect=self.create_pending):
            prepare.write_new(self.output, {"data_mode": "fixture", "value": "安全"})
        self.assert_descriptor_closed()
        self.assertEqual(
            json.loads(self.output.read_bytes()),
            {"data_mode": "fixture", "value": "安全"},
        )
        self.assertEqual(self.foreign.read_bytes(), b"synthetic-foreign-file")

    def test_preexisting_output_refuses_before_fd_allocation(self) -> None:
        self.output.write_bytes(b'{"previous":"synthetic"}\n')
        with (
            patch.object(prepare.tempfile, "mkstemp") as allocate,
            self.assertRaisesRegex(prepare.PreparationError, "OUTPUT_EXISTS"),
        ):
            prepare.write_new(self.output, {"data_mode": "fixture"})
        allocate.assert_not_called()
        self.assertEqual(self.output.read_bytes(), b'{"previous":"synthetic"}\n')
        self.assertEqual(self.foreign.read_bytes(), b"synthetic-foreign-file")

    def test_allocation_error_does_not_close_unowned_descriptor(self) -> None:
        with (
            patch.object(
                prepare.tempfile,
                "mkstemp",
                side_effect=OSError(errno.ENOSPC, "synthetic-full"),
            ),
            patch.object(prepare.os, "close") as closed,
            self.assertRaises(OSError) as captured,
        ):
            prepare.write_new(self.output, {"data_mode": "fixture"})
        self.assertEqual(captured.exception.errno, errno.ENOSPC)
        closed.assert_not_called()
        self.assertFalse(self.output.exists())
        self.assertEqual(self.foreign.read_bytes(), b"synthetic-foreign-file")
