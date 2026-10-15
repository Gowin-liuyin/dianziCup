"""Bounded isolated checks with authorized DPAPI credentials captured only in memory."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PYTHON = Path("D:/dianzi/backend/.venv/Scripts/python.exe")
RUN_ID = "r11_forward_rules_sbom_20261016"
DATABASE = "test_dianzi_" + RUN_ID
PWSH = Path(
    "C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe"
)
SECRET_REFERENCE = "D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi"


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def credentials() -> dict[str, object]:
    captured = subprocess.run(
        [
            str(PWSH),
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "(Get-Content -LiteralPath '" + SECRET_REFERENCE + "' "
            "-Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText",
        ],
        capture_output=True,
        timeout=15,
        check=False,
    )
    if captured.returncode:
        raise RuntimeError("authorized_dpapi_reference_unavailable")
    configuration = json.loads(captured.stdout)
    if not isinstance(configuration, dict):
        raise RuntimeError("authorized_dpapi_reference_shape")
    return configuration


def environment() -> dict[str, str]:
    if datetime.now(ZoneInfo("Asia/Shanghai")) >= datetime.fromisoformat(
        "2026-10-17T21:49:15+08:00"
    ):
        raise RuntimeError("authorized_resource_window_expired")
    configuration = credentials()
    source_value = configuration.get("TEST_DATABASE_URL")
    if not isinstance(source_value, str):
        raise RuntimeError("authorized_database_reference_missing")
    url = make_url(source_value)
    if (
        (url.host, url.port, url.database) != ("127.0.0.1", 25432, "test_dianzi_r01_20261014")
        or not url.username
        or not url.username.startswith("test_")
    ):
        raise RuntimeError("authorized_database_reference_identity")
    parameters = dict(
        host=url.host,
        port=url.port,
        user=url.username,
        password=url.password,
        connect_timeout=5,
        options="-c statement_timeout=15000 -c lock_timeout=5000",
    )
    with psycopg.connect(dbname=url.database, **parameters) as connection:
        connection.autocommit = True
        if (
            connection.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DATABASE,)).fetchone()
            is None
        ):
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DATABASE)))
    with psycopg.connect(dbname=DATABASE, **parameters) as connection:
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
        version = connection.execute("SHOW server_version").fetchone()[0]
        vector = connection.execute(
            "SELECT extversion FROM pg_extension WHERE extname='vector'"
        ).fetchone()[0]
    result = os.environ.copy()
    result["PYTHONPATH"] = str(ROOT / "backend/src")
    result["TEST_DATABASE_URL"] = url.set(database=DATABASE).render_as_string(hide_password=False)
    result["DIANZI_TEST_RUN_ID"] = RUN_ID
    result["R11_FORWARD_EVIDENCE_DIR"] = str(RUN)
    result["R05_SEMANTIC_CACHE"] = "C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime"
    search_value = configuration.get("R12_OPENSEARCH_URL") or configuration.get(
        "TEST_OPENSEARCH_URL"
    )
    if isinstance(search_value, str):
        result["R12_OPENSEARCH_URL"] = search_value
    else:
        result["R12_OPENSEARCH_URL"] = "http://127.0.0.1:29200"
    (RUN / "resource_receipt.json").write_text(
        json.dumps(
            {
                "database": DATABASE,
                "host": "loopback",
                "port": 25432,
                "postgres_version": version,
                "vector_version": vector,
                "source_reference": SECRET_REFERENCE,
                "expires_at": "2026-10-17T21:49:15+08:00",
                "fixture_data": True,
                "paid_calls": 0,
                "third_party_scans": 0,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return result


def execute(label: str, command: list[str], *, resources: bool = True) -> int:
    if not label.replace("_", "").isalnum() or (RUN / f"{label}.stdout.log").exists():
        raise RuntimeError("label_must_be_new_and_bounded")
    started_at, started = now(), time.monotonic()
    current_env = environment() if resources else os.environ.copy()
    current_env["PYTHONPATH"] = str(ROOT / "backend/src")
    sys.path.insert(0, str(ROOT / "backend"))
    from tests.conftest import redact_test_connection_output

    private_url = make_url(current_env["TEST_DATABASE_URL"]) if resources else None
    dynamic = (private_url.password or "",) if private_url else ()
    previous_url = os.environ.get("TEST_DATABASE_URL")
    if resources:
        os.environ["TEST_DATABASE_URL"] = current_env["TEST_DATABASE_URL"]
    timed_out = False
    try:
        result = subprocess.run(
            command,
            cwd=ROOT / "backend",
            env=current_env,
            capture_output=True,
            timeout=300,
            check=False,
        )
        exit_code, stdout, stderr = result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as error:
        exit_code, stdout, stderr = 124, error.stdout or b"", error.stderr or b""
        timed_out = True
    for stream, value in (("stdout", stdout), ("stderr", stderr)):
        output = redact_test_connection_output(value.decode("utf-8", errors="replace"), dynamic)
        (RUN / f"{label}.{stream}.log").write_text(output, encoding="utf-8", newline="")
    if previous_url is None:
        os.environ.pop("TEST_DATABASE_URL", None)
    else:
        os.environ["TEST_DATABASE_URL"] = previous_url
    record = {
        "label": label,
        "command": command,
        "cwd": str(ROOT / "backend"),
        "started_at": started_at,
        "finished_at": now(),
        "exit_code": exit_code,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "timed_out": timed_out,
    }
    with (RUN / "commands.jsonl").open("a", encoding="utf-8", newline="") as log:
        log.write(json.dumps(record) + "\n")
    print(json.dumps(record))
    print((RUN / f"{label}.stdout.log").read_text(encoding="utf-8")[-2200:])
    return exit_code


def seal() -> None:
    configuration = credentials()
    url = make_url(str(configuration["TEST_DATABASE_URL"]))
    secret = (url.password or "").encode()
    files = sorted(
        path
        for path in RUN.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.name != "artifact_manifest.json"
    )
    source_manifest = json.loads((RUN / "source_manifest.json").read_text())
    scan_files = [
        *files,
        *(ROOT / entry["path"] for entry in source_manifest["entries"]),
        ROOT / "reports/tasks/R11-forward-rules-sbom.md",
    ]
    matches = [
        str(path.relative_to(ROOT)) for path in scan_files if secret and secret in path.read_bytes()
    ]
    (RUN / "credential_scan.json").write_text(
        json.dumps(
            {
                "actual_password_match_count": len(matches),
                "matched_paths": matches,
                "scanned_files": len(scan_files),
                "scanned_at": now(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    if matches:
        raise RuntimeError("actual_test_credential_detected")
    files = sorted(
        path
        for path in RUN.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.name != "artifact_manifest.json"
    )
    files.append(ROOT / "reports/tasks/R11-forward-rules-sbom.md")
    entries = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in files
    ]
    (RUN / "artifact_manifest.json").write_text(json.dumps(entries, indent=2), encoding="utf-8")
    print(json.dumps({"artifacts": len(entries), "actual_credential_matches": len(matches)}))


if __name__ == "__main__":
    if sys.argv[1] == "seal":
        seal()
    else:
        use_resources = sys.argv[1] != "local"
        label_index = 2 if not use_resources else 1
        try:
            raise SystemExit(
                execute(
                    sys.argv[label_index],
                    [str(PYTHON), *sys.argv[label_index + 1 :]],
                    resources=use_resources,
                )
            )
        except Exception as error:
            print(json.dumps({"status": "blocked_harness", "error_type": type(error).__name__}))
            raise SystemExit(4) from None
