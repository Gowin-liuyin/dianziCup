"""Offline operator backup and empty, marked PostgreSQL rehearsal restoration.

Callers supply trusted deployment paths, authenticated scope and exact database identities.
This module is deliberately not an HTTP, model, arbitrary SQL or shell tool.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.exc import SQLAlchemyError

from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role
from ai_intel.infrastructure.content_store import ContentStorage, ContentStore

IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
DERIVED_TABLES = frozenset(
    {
        "retrieval_chunks",
        "hybrid_chunks",
        "hybrid_index_generations",
        "hybrid_index_watermarks",
        "hybrid_index_receipts",
    }
)


class RehearsalError(RuntimeError):
    """Sanitized operational failure; underlying connection/output stays private."""


class DatabaseTarget(BaseModel):
    """An operator-observed identity, independent of a database's naming convention."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    host: str
    port: int = Field(ge=1, le=65535)
    database: str
    database_oid: int = Field(gt=0)
    marker: str
    schema_name: str
    schema_oid: int | None


class TableDigest(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    row_count: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class BackupManifest(BaseModel):
    """Private metadata without row values, account names, DSNs or original text."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    format_version: int = 1
    scope: str = "whole_marked_database_and_registered_content_objects"
    started_at: str
    ended_at: str
    server_version: str
    schema_name: str
    schema_revision: str
    code_version: str = Field(pattern=r"^[0-9a-f]{40}$")
    dump_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tables: dict[str, TableDigest]
    objects: dict[str, int]
    derived_tables_excluded: list[str]
    index_status: str = "rebuild_required"


class PgTools(Protocol):
    @property
    def database_identity(self) -> tuple[str, int, str]: ...

    def dump(self, destination: Path, snapshot: str, excluded: tuple[str, ...]) -> None: ...

    def restore(self, archive: Path) -> None: ...


class NativePgTools:
    """Fixed native pg_dump/pg_restore executables, credentials only in child environment."""

    def __init__(
        self,
        bin_directory: Path,
        database_url: SecretStr,
        timeout_seconds: int = 90,
    ) -> None:
        self._directory = bin_directory.resolve(strict=True)
        self._url = make_url(database_url.get_secret_value())
        self._timeout = timeout_seconds
        if self._url.get_backend_name() != "postgresql" or not 1 <= timeout_seconds <= 120:
            raise RehearsalError("postgres_tools_configuration_rejected")

    @property
    def database_identity(self) -> tuple[str, int, str]:
        return self._url.host or "", self._url.port or 5432, self._url.database or ""

    def _run(self, tool: str, arguments: list[str]) -> None:
        executable = self._directory / (tool + (".exe" if os.name == "nt" else ""))
        if not executable.is_file() or executable.is_symlink():
            raise RehearsalError("postgres_tool_missing")
        environment = {
            key: value
            for key, value in os.environ.items()
            if key in {"PATH", "SYSTEMROOT", "TEMP", "TMP", "LANG"}
        }
        environment.update(
            PGHOST=self._url.host or "",
            PGPORT=str(self._url.port or 5432),
            PGDATABASE=self._url.database or "",
            PGUSER=self._url.username or "",
            PGPASSWORD=self._url.password or "",
            PGCONNECT_TIMEOUT="5",
            PGOPTIONS="-c statement_timeout=90000 -c lock_timeout=5000",
        )
        try:
            completed = subprocess.run(
                [str(executable), *arguments],
                env=environment,
                capture_output=True,
                timeout=self._timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise RehearsalError("postgres_tool_unavailable_or_timed_out") from None
        if completed.returncode:
            raise RehearsalError("postgres_tool_failed")

    def dump(self, destination: Path, snapshot: str, excluded: tuple[str, ...]) -> None:
        self._run(
            "pg_dump",
            [
                "--format=custom",
                "--no-owner",
                "--no-acl",
                "--snapshot=" + snapshot,
                "--file=" + str(destination),
                *("--exclude-table-data=" + name for name in excluded),
            ],
        )

    def restore(self, archive: Path) -> None:
        self._run(
            "pg_restore",
            [
                "--single-transaction",
                "--exit-on-error",
                "--no-owner",
                "--no-acl",
                "--dbname=" + (self._url.database or ""),
                str(archive),
            ],
        )


def timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def require_operator(scope: AccessScope) -> None:
    if scope.role != Role.SYSTEM_ADMIN or scope.tenant_id is not None:
        raise PermissionDeniedError("system operator required for whole-database rehearsal")
    scope.requires("manage:users")


def controlled_path(root: Path, candidate: Path, marker: str) -> Path:
    """Reject traversal and symlink/junction ancestors before any backup or object write."""
    if not root.is_absolute() or not candidate.is_absolute():
        raise RehearsalError("absolute_owned_paths_required")
    if not marker.startswith("dianzi-rehearsal:") or len(marker) < 25:
        raise RehearsalError("ownership_marker_rejected")
    for path in (root, candidate):
        if ".." in path.parts:
            raise RehearsalError("path_traversal_rejected")
        for ancestor in (path, *path.parents):
            if ancestor.is_symlink() or ancestor.is_junction():
                raise RehearsalError("linked_path_rejected")
            if (ancestor / ".git").exists():
                raise RehearsalError("backup_inside_git_checkout_rejected")
    resolved_root = root.resolve(strict=True)
    resolved = candidate.resolve()
    if resolved == resolved_root or not resolved.is_relative_to(resolved_root):
        raise RehearsalError("path_outside_owned_root")
    marker_path = resolved_root / ".rehearsal-owner"
    if marker_path.is_symlink() or marker_path.is_junction():
        raise RehearsalError("linked_ownership_marker_rejected")
    if marker_path.read_text(encoding="utf-8") != marker:
        raise RehearsalError("path_ownership_rejected")
    return resolved


def guard_database(connection: Connection, target: DatabaseTarget, *, empty: bool) -> None:
    """Require actual address, database OID/comment and allowed schema, never drop/create."""
    url = connection.engine.url
    if (url.host, url.port or 5432, url.database) != (
        target.host,
        target.port,
        target.database,
    ):
        raise RehearsalError("connection_target_rejected")
    if target.host not in {"127.0.0.1", "::1"} or not target.database.startswith("test_"):
        raise RehearsalError("non_test_database_rejected")
    if not target.marker.startswith("dianzi-rehearsal:") or len(target.marker) < 25:
        raise RehearsalError("database_marker_rejected")
    if not IDENTIFIER.fullmatch(target.schema_name):
        raise RehearsalError("schema_identifier_rejected")
    row = connection.execute(
        text(
            "SELECT oid, shobj_description(oid, 'pg_database'), inet_server_port() "
            "FROM pg_database WHERE datname=current_database()"
        )
    ).one()
    if (row[0], row[1], row[2]) != (target.database_oid, target.marker, target.port):
        raise RehearsalError("database_identity_rejected")
    namespaces = connection.execute(
        text(
            "SELECT oid, nspname, obj_description(oid, 'pg_namespace') FROM pg_namespace "
            "WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema'"
        )
    ).all()
    expected_schemas = {"public"} if empty else {"public", target.schema_name}
    if {str(row[1]) for row in namespaces} != expected_schemas:
        raise RehearsalError("database_schema_scope_rejected")
    if empty:
        if target.schema_oid is not None:
            raise RehearsalError("restore_schema_must_be_absent")
        occupied = connection.scalar(
            text(
                "SELECT EXISTS (SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema') OR "
                "EXISTS (SELECT FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema') OR "
                "EXISTS (SELECT FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace "
                "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema') OR "
                "EXISTS (SELECT FROM pg_extension WHERE extname<>'plpgsql') OR "
                "EXISTS (SELECT FROM pg_event_trigger)"
            )
        )
        if occupied:
            raise RehearsalError("restore_database_not_empty")
    else:
        schema_rows = [row for row in namespaces if row[1] == target.schema_name]
        if len(schema_rows) != 1 or (schema_rows[0][0], schema_rows[0][2]) != (
            target.schema_oid,
            target.marker,
        ):
            raise RehearsalError("source_schema_identity_rejected")
        if connection.scalar(text("SELECT count(*) FROM pg_tables WHERE schemaname='public'")):
            raise RehearsalError("source_public_tables_outside_scope")


def table_digests(
    connection: Connection,
    schema: str,
    *,
    include_derived: bool = False,
) -> dict[str, TableDigest]:
    tables = [
        str(row[0])
        for row in connection.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname=:schema ORDER BY tablename"),
            {"schema": schema},
        )
    ]
    result: dict[str, TableDigest] = {}
    for table in tables:
        name = str(table)
        if not IDENTIFIER.fullmatch(name):
            raise RehearsalError("table_identifier_rejected")
        digest = hashlib.sha256()
        count = 0
        if include_derived or name not in DERIVED_TABLES:
            rows = connection.execute(
                text(
                    f'SELECT to_jsonb(r)::text FROM "{schema}"."{name}" r '
                    "ORDER BY to_jsonb(r)::text"
                ),
                execution_options={"stream_results": True},
            )
            for row in rows:
                encoded = str(row[0]).encode("utf-8")
                digest.update(len(encoded).to_bytes(8, "big"))
                digest.update(encoded)
                count += 1
        result[name] = TableDigest(row_count=count, sha256=digest.hexdigest())
    return result


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def create_backup(
    engine: Engine,
    target: DatabaseTarget,
    scope: AccessScope,
    storage: ContentStorage,
    tools: PgTools,
    owned_root: Path,
    destination: Path,
    code_version: str,
) -> str:
    """Export one PG snapshot plus every registered immutable content object; seal last."""
    require_operator(scope)
    if tools.database_identity != (target.host, target.port, target.database):
        raise RehearsalError("postgres_tools_target_mismatch")
    backup = controlled_path(owned_root, destination, target.marker)
    if backup.exists():
        raise RehearsalError("backup_destination_already_exists")
    started = timestamp()
    backup.mkdir(mode=0o700)
    try:
        with (
            engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection,
            connection.begin(),
        ):
            guard_database(connection, target, empty=False)
            connection.execute(
                text(f'LOCK TABLE "{target.schema_name}".content_objects IN SHARE MODE')
            )
            snapshot = str(connection.scalar(text("SELECT pg_export_snapshot()")))
            tables = table_digests(connection, target.schema_name)
            objects = {
                str(row[0]): int(row[1])
                for row in connection.execute(
                    text(
                        f"SELECT content_hash, size_bytes FROM "
                        f'"{target.schema_name}".content_objects'
                    )
                )
            }
            object_store = ContentStore(backup / "objects")
            for digest, size in objects.items():
                payload = storage.read_verified(digest)
                if len(payload) != size or hashlib.sha256(payload).hexdigest() != digest:
                    raise RehearsalError("source_content_integrity_failed")
                object_store.store_bytes(payload)
            archive = backup / "database.dump"
            excluded = tuple(f"{target.schema_name}.{name}" for name in sorted(DERIVED_TABLES))
            tools.dump(archive, snapshot, excluded)
            if not archive.is_file() or archive.stat().st_size == 0:
                raise RehearsalError("database_archive_missing")
            version = str(connection.scalar(text("SHOW server_version")))
            revision = str(
                connection.scalar(
                    text(f'SELECT version_num FROM "{target.schema_name}".alembic_version')
                )
            )
            manifest = BackupManifest(
                started_at=started,
                ended_at=timestamp(),
                server_version=version,
                schema_name=target.schema_name,
                schema_revision=revision,
                code_version=code_version,
                dump_sha256=file_hash(archive),
                tables=tables,
                objects=objects,
                derived_tables_excluded=sorted(DERIVED_TABLES),
            )
            manifest_file = backup / "manifest.json"
            manifest_file.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
            return file_hash(manifest_file)
    except (OSError, ValueError, RuntimeError, SQLAlchemyError, subprocess.SubprocessError):
        (backup / "FAILED").write_text("backup_incomplete", encoding="utf-8")
        raise RehearsalError("backup_failed_incomplete") from None


def verify_backup(backup: Path, manifest_sha256: str) -> BackupManifest:
    """Pinned manifest hash is kept outside the backup, detecting manifest replacement too."""
    if not re.fullmatch(r"[0-9a-f]{64}", manifest_sha256):
        raise RehearsalError("manifest_pin_rejected")
    for path in backup.rglob("*"):
        if path.is_symlink() or path.is_junction():
            raise RehearsalError("backup_link_rejected")
    manifest_file = backup / "manifest.json"
    if (backup / "FAILED").exists() or file_hash(manifest_file) != manifest_sha256:
        raise RehearsalError("backup_manifest_integrity_failed")
    manifest = BackupManifest.model_validate_json(manifest_file.read_bytes())
    if manifest.format_version != 1 or manifest.index_status != "rebuild_required":
        raise RehearsalError("backup_format_rejected")
    if not IDENTIFIER.fullmatch(manifest.schema_name):
        raise RehearsalError("backup_schema_rejected")
    if set(manifest.derived_tables_excluded) != DERIVED_TABLES:
        raise RehearsalError("derived_scope_rejected")
    expected = {"manifest.json", "database.dump"}
    store = ContentStore(backup / "objects")
    for digest, size in manifest.objects.items():
        if size < 0 or len(store.read_verified(digest)) != size:
            raise RehearsalError("backup_object_integrity_failed")
        expected.add("objects/" + digest[:2] + "/" + digest)
    actual = set()
    for path in backup.rglob("*"):
        if path.is_symlink() or path.is_junction():
            raise RehearsalError("backup_link_rejected")
        if path.is_file():
            actual.add(path.relative_to(backup).as_posix())
    if actual != expected or file_hash(backup / "database.dump") != manifest.dump_sha256:
        raise RehearsalError("backup_file_integrity_failed")
    return manifest


def restore_backup(
    engine: Engine,
    target: DatabaseTarget,
    scope: AccessScope,
    tools: PgTools,
    owned_root: Path,
    backup_directory: Path,
    destination: Path,
    manifest_sha256: str,
    rebuild_indexes: Callable[[], None] | None = None,
) -> dict[str, str]:
    """Restore only into an exact empty marked DB and a fresh owned content directory."""
    require_operator(scope)
    if tools.database_identity != (target.host, target.port, target.database):
        raise RehearsalError("postgres_tools_target_mismatch")
    backup = controlled_path(owned_root, backup_directory, target.marker)
    content = controlled_path(owned_root, destination, target.marker)
    if content == backup or content.is_relative_to(backup) or backup.is_relative_to(content):
        raise RehearsalError("restore_paths_overlap")
    if content.exists():
        raise RehearsalError("restore_content_destination_already_exists")
    manifest = verify_backup(backup, manifest_sha256)
    if manifest.schema_name != target.schema_name:
        raise RehearsalError("restore_schema_mismatch")
    receipt = {
        "database": "incomplete",
        "content": "incomplete",
        "indexes": "rebuild_required",
    }
    receipt_file = content.parent / (content.name + ".restore.json")
    controlled_path(owned_root, receipt_file, target.marker)
    if receipt_file.exists():
        raise RehearsalError("restore_receipt_already_exists")
    try:
        with engine.begin() as connection:
            acquired = connection.scalar(
                text(
                    "SELECT pg_try_advisory_xact_lock("
                    "hashtextextended('dianzi-restore-rehearsal',0))"
                )
            )
            if acquired is not True:
                raise RehearsalError("restore_rehearsal_already_running")
            guard_database(connection, target, empty=True)
            content.mkdir(mode=0o700)
            source_store = ContentStore(backup / "objects")
            restored_store = ContentStore(content)
            for digest in manifest.objects:
                restored_store.store_bytes(source_store.read_verified(digest))
            receipt["content"] = "verified"
            guard_database(connection, target, empty=True)
            tools.restore(backup / "database.dump")
            schema_oid = connection.scalar(
                text("SELECT oid FROM pg_namespace WHERE nspname=:schema"),
                {"schema": target.schema_name},
            )
            if not isinstance(schema_oid, int):
                raise RehearsalError("restored_schema_missing")
            guard_database(
                connection, target.model_copy(update={"schema_oid": schema_oid}), empty=False
            )
            restored = table_digests(connection, target.schema_name, include_derived=True)
            if restored != manifest.tables:
                raise RehearsalError("restored_records_integrity_failed")
        receipt["database"] = "verified"
        if rebuild_indexes is not None:
            receipt["indexes"] = "failed"
            rebuild_indexes()
            receipt["indexes"] = "rebuilt"
        return receipt
    except (OSError, ValueError, RuntimeError, SQLAlchemyError, subprocess.SubprocessError):
        raise RehearsalError("restore_failed_incomplete_or_degraded") from None
    finally:
        receipt_file.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
