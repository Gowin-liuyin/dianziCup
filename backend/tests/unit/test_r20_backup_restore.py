"""Explicit synthetic backup boundaries, separate from real PostgreSQL rehearsal."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr
from scripts.backup_restore import (
    BackupManifest,
    DatabaseTarget,
    NativePgTools,
    RehearsalError,
    controlled_path,
    file_hash,
    guard_database,
    require_operator,
    restore_backup,
    verify_backup,
)
from sqlalchemy.engine import make_url

from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role
from ai_intel.infrastructure.content_store import ContentStore

MARKER = "dianzi-rehearsal:r20_unit_synthetic_20261016"


def target() -> DatabaseTarget:
    return DatabaseTarget(
        host="127.0.0.1",
        port=25432,
        database="test_r20_unit",
        database_oid=123,
        marker=MARKER,
        schema_name="r20_backup_data",
        schema_oid=None,
    )


def bundle(root: Path) -> tuple[Path, str]:
    root.mkdir()
    (root / ".rehearsal-owner").write_text(MARKER, encoding="utf-8")
    backup = root / "backup"
    backup.mkdir()
    (backup / "database.dump").write_bytes(b"synthetic-not-pg-archive")
    saved = ContentStore(backup / "objects").store_bytes(b"synthetic original")
    manifest = BackupManifest(
        started_at="2026-10-16T00:00:00+00:00",
        ended_at="2026-10-16T00:00:01+00:00",
        server_version="synthetic",
        schema_name="r20_backup_data",
        schema_revision="synthetic",
        code_version="a" * 40,
        dump_sha256=file_hash(backup / "database.dump"),
        tables={},
        objects={saved.content_hash: saved.size_bytes},
        derived_tables_excluded=[
            "retrieval_chunks",
            "hybrid_chunks",
            "hybrid_index_generations",
            "hybrid_index_watermarks",
            "hybrid_index_receipts",
        ],
    )
    (backup / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    return backup, file_hash(backup / "manifest.json")


@pytest.mark.parametrize("role", [Role.VIEWER, Role.ANALYST, Role.TENANT_ADMIN])
def test_whole_backup_refuses_tenant_principals(role: Role) -> None:
    with pytest.raises(PermissionDeniedError, match="system operator"):
        require_operator(AccessScope.for_authenticated_user("synthetic-user", "tenant_b", role))


def test_owned_absolute_child_path_and_wrong_marker(tmp_path: Path) -> None:
    root = tmp_path / "owned"
    root.mkdir()
    (root / ".rehearsal-owner").write_text(MARKER)
    assert controlled_path(root, root / "backup", MARKER) == root / "backup"
    for path in (tmp_path / "other", root, root / ".." / "escape", Path("relative")):
        with pytest.raises(RehearsalError):
            controlled_path(root, path, MARKER)
    with pytest.raises(RehearsalError, match="ownership"):
        controlled_path(root, root / "backup", MARKER + "wrong")


@pytest.mark.parametrize("change", ["dump", "object", "missing", "partial", "manifest", "failure"])
def test_pinned_backup_rejects_tampered_partial_and_failed_files(
    tmp_path: Path, change: str
) -> None:
    backup, pin = bundle(tmp_path / "owned")
    manifest = verify_backup(backup, pin)
    digest = next(iter(manifest.objects))
    object_path = backup / "objects" / digest[:2] / digest
    if change == "dump":
        (backup / "database.dump").write_bytes(b"tampered")
    elif change == "object":
        object_path.write_bytes(b"tampered")
    elif change == "missing":
        object_path.unlink()
    elif change == "partial":
        (backup / "database.dump.partial").write_bytes(b"incomplete")
    elif change == "failure":
        (backup / "FAILED").write_text("incomplete")
    else:
        value = json.loads((backup / "manifest.json").read_text())
        value["dump_sha256"] = hashlib.sha256(b"tampered").hexdigest()
        (backup / "manifest.json").write_text(json.dumps(value))
    with pytest.raises((RehearsalError, ValueError, FileNotFoundError)):
        verify_backup(backup, pin)


@pytest.mark.parametrize("bad", ["host", "oid", "comment", "port", "schema", "occupied"])
def test_target_guard_checks_actual_identity_and_empty_schema(bad: str) -> None:
    connection = MagicMock()
    connection.engine.url = make_url("postgresql://127.0.0.1:25432/test_r20_unit")
    database = MagicMock()
    database.one.return_value = (
        999 if bad == "oid" else 123,
        "unexpected" if bad == "comment" else MARKER,
        999 if bad == "port" else 25432,
    )
    schemas = MagicMock()
    schemas.all.return_value = (
        [(2200, "public", None), (9999, "unexpected", MARKER)]
        if bad == "schema"
        else [(2200, "public", None)]
    )
    connection.execute.side_effect = [database, schemas]
    connection.scalar.return_value = bad == "occupied"
    guarded = target()
    if bad == "host":
        guarded = guarded.model_copy(update={"host": "production.invalid"})
    with pytest.raises(RehearsalError):
        guard_database(connection, guarded, empty=True)


def test_native_tools_keep_credentials_and_output_out_of_argv_and_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / ("pg_restore.exe" if os.name == "nt" else "pg_restore")
    executable.write_bytes(b"synthetic tool path")
    captured: list[tuple[list[str], dict[str, str]]] = []
    synthetic_password = "unit-private-secret"

    def completed(arguments: list[str], **options: object) -> subprocess.CompletedProcess[bytes]:
        environment = options["env"]
        assert isinstance(environment, dict)
        captured.append((arguments, environment))
        return subprocess.CompletedProcess(arguments, 1, b"", synthetic_password.encode())

    monkeypatch.setattr(subprocess, "run", completed)
    tools = NativePgTools(
        tmp_path,
        SecretStr("postgresql://unit:" + synthetic_password + "@127.0.0.1:25432/test_r20_unit"),
    )
    with pytest.raises(RehearsalError, match="postgres_tool_failed") as failure:
        tools.restore(tmp_path / "database.dump")
    assert synthetic_password not in str(failure.value)
    arguments, environment = captured[0]
    assert all(
        synthetic_password not in value and "postgresql://" not in value for value in arguments
    )
    assert environment["PGPASSWORD"] == synthetic_password
    assert "--single-transaction" in arguments and "--exit-on-error" in arguments
    assert "--clean" not in arguments and "--create" not in arguments


@pytest.mark.parametrize("failure", ["database", "index"])
def test_restore_failure_retains_truthful_incomplete_or_degraded_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    root = tmp_path / "owned"
    backup, pin = bundle(root)
    tools = MagicMock()
    tools.database_identity = ("127.0.0.1", 25432, "test_r20_unit")
    if failure == "database":
        tools.restore.side_effect = RuntimeError("synthetic failure")
    monkeypatch.setattr("scripts.backup_restore.guard_database", lambda *args, **kwargs: None)
    monkeypatch.setattr("scripts.backup_restore.table_digests", lambda *args, **kwargs: {})

    def rebuild() -> None:
        raise RuntimeError("synthetic failed projection")

    scope = AccessScope.for_authenticated_user("synthetic-admin", None, Role.SYSTEM_ADMIN)
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value.scalar.side_effect = [True, 999]
    with pytest.raises(RehearsalError, match="incomplete_or_degraded"):
        restore_backup(
            engine,
            target(),
            scope,
            tools,
            root,
            backup,
            root / "restored",
            pin,
            rebuild,
        )
    receipt = json.loads((root / "restored.restore.json").read_text())
    assert receipt["content"] == "verified"
    assert receipt["database"] == ("incomplete" if failure == "database" else "verified")
    assert receipt["indexes"] == ("rebuild_required" if failure == "database" else "failed")


def test_restore_existing_content_or_mismatched_tool_target_causes_no_mutation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "owned"
    backup, pin = bundle(root)
    tools = MagicMock()
    tools.database_identity = ("127.0.0.1", 25432, "test_r20_unit")
    destination = root / "existing"
    destination.mkdir()
    sentinel = destination / "user-file"
    sentinel.write_text("preserve")
    scope = AccessScope.for_authenticated_user("synthetic-admin", None, Role.SYSTEM_ADMIN)
    with pytest.raises(RehearsalError, match="already_exists"):
        restore_backup(MagicMock(), target(), scope, tools, root, backup, destination, pin)
    assert sentinel.read_text() == "preserve"
    tools.restore.assert_not_called()
    tools.database_identity = ("127.0.0.1", 25432, "different")
    with pytest.raises(RehearsalError, match="target_mismatch"):
        restore_backup(MagicMock(), target(), scope, tools, root, backup, root / "fresh", pin)
    assert not (root / "fresh").exists()


def test_backup_cannot_write_sensitive_dump_inside_a_git_checkout(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    root.mkdir()
    (root / ".git").write_text("synthetic git worktree marker")
    (root / ".rehearsal-owner").write_text(MARKER)
    with pytest.raises(RehearsalError, match="inside_git"):
        controlled_path(root, root / "backup", MARKER)
    assert not (root / "backup").exists()


def test_concurrent_restore_guard_causes_no_content_or_tool_mutation(tmp_path: Path) -> None:
    root = tmp_path / "owned"
    backup, pin = bundle(root)
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value.scalar.return_value = False
    tools = MagicMock()
    tools.database_identity = ("127.0.0.1", 25432, "test_r20_unit")
    scope = AccessScope.for_authenticated_user("synthetic-admin", None, Role.SYSTEM_ADMIN)
    with pytest.raises(RehearsalError, match="incomplete_or_degraded"):
        restore_backup(engine, target(), scope, tools, root, backup, root / "restored", pin)
    assert not (root / "restored").exists()
    tools.restore.assert_not_called()
    receipt = json.loads((root / "restored.restore.json").read_text())
    assert receipt["database"] == "incomplete" and receipt["content"] == "incomplete"
