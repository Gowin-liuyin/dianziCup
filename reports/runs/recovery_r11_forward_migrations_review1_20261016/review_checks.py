"""Record bounded independent review commands without exposing resource credentials."""

from __future__ import annotations

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
PWSH = Path(
    "C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe"
)
REFERENCE = Path("D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi")
RUN_ID = "r11_forward_review1_20261016"
DATABASE = "test_dianzi_" + RUN_ID
SCHEMA_PREFIX = "test_r11_forward_review1_"


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()


def database_reference() -> str:
    captured = subprocess.run(
        [
            str(PWSH),
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "(Get-Content -LiteralPath '"
            + str(REFERENCE)
            + "' -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText",
        ],
        capture_output=True,
        check=False,
        timeout=15,
    )
    if captured.returncode:
        raise RuntimeError("authorized_dpapi_reference_unavailable")
    configuration = json.loads(captured.stdout)
    value = configuration.get("TEST_DATABASE_URL")
    if not isinstance(value, str):
        raise RuntimeError("authorized_database_reference_missing")
    return value


def environment(resources: bool) -> tuple[dict[str, str], tuple[str, ...]]:
    result = os.environ.copy()
    result["PYTHONPATH"] = os.pathsep.join(
        (str(ROOT / "backend/src"), str(ROOT / "backend"), str(RUN))
    )
    if not resources:
        result.pop("TEST_DATABASE_URL", None)
        return result, ()
    if datetime.now(ZoneInfo("Asia/Shanghai")) >= datetime.fromisoformat(
        "2026-10-17T21:49:15+08:00"
    ):
        raise RuntimeError("authorized_resource_window_expired")
    if len(DATABASE) > 63 or len(RUN_ID) > 47:
        raise RuntimeError("owned_resource_name_too_long")
    base = make_url(database_reference())
    if (base.host, base.port, base.database) != ("127.0.0.1", 25432, "test_dianzi_r01_20261014"):
        raise RuntimeError("authorized_resource_reference_identity")
    if not base.username or not base.username.startswith("test_"):
        raise RuntimeError("authorized_resource_reference_username")
    parameters = dict(
        host=base.host,
        port=base.port,
        user=base.username,
        password=base.password,
        connect_timeout=5,
        options="-c statement_timeout=15000 -c lock_timeout=5000",
    )
    with psycopg.connect(dbname=base.database, **parameters) as connection:
        connection.autocommit = True
        if (
            connection.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DATABASE,)).fetchone()
            is None
        ):
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DATABASE)))
    with psycopg.connect(dbname=DATABASE, **parameters) as connection:
        actual_database, actual_user = connection.execute(
            "SELECT current_database(),current_user"
        ).fetchone()
        assert (actual_database, actual_user) == (DATABASE, base.username)
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
        version = connection.execute("SHOW server_version").fetchone()[0]
        vector = connection.execute(
            "SELECT extversion FROM pg_extension WHERE extname='vector'"
        ).fetchone()[0]
    own = base.set(database=DATABASE).render_as_string(hide_password=False)
    result["TEST_DATABASE_URL"] = own
    result["DIANZI_TEST_RUN_ID"] = RUN_ID
    result["R11_FORWARD_EVIDENCE_DIR"] = str(RUN)
    result["R12_OPENSEARCH_URL"] = "http://127.0.0.1:29200"
    result["R05_SEMANTIC_CACHE"] = "C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime"
    (RUN / "resource_receipt.json").write_text(
        json.dumps(
            {
                "database": DATABASE,
                "host": "loopback",
                "port": 25432,
                "username_prefix": "test_",
                "postgres_version": version,
                "vector_version": vector,
                "schema_prefix": SCHEMA_PREFIX,
                "source_reference": str(REFERENCE),
                "expires_at": "2026-10-17T21:49:15+08:00",
                "fixture_data": True,
                "paid_calls": 0,
                "third_party_scans": 0,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return result, (base.password or "", own, base.render_as_string(hide_password=False))


def execute(
    label: str, command: list[str], resources: bool = False, cwd: Path | None = None
) -> int:
    if not label.replace("_", "").isalnum() or (RUN / (label + ".json")).exists():
        raise RuntimeError("command_label_must_be_new")
    env, secrets = environment(resources)
    sys.path.insert(0, str(ROOT / "backend/src"))
    sys.path.insert(0, str(ROOT / "backend"))
    from tests.conftest import redact_test_connection_output

    started_at, started = now(), time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=cwd or ROOT / "backend",
            env=env,
            capture_output=True,
            timeout=300,
            check=False,
        )
        code, stdout, stderr, timed_out = result.returncode, result.stdout, result.stderr, False
    except subprocess.TimeoutExpired as error:
        code, stdout, stderr, timed_out = 124, error.stdout or b"", error.stderr or b"", True
    for stream, value in (("stdout", stdout), ("stderr", stderr)):
        output = redact_test_connection_output(value.decode("utf-8", errors="replace"), secrets)
        (RUN / (label + "." + stream + ".log")).write_text(output, encoding="utf-8", newline="")
    matched = []
    for path in RUN.rglob("*"):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix in {".xml", ".json", ".jsonl", ".log", ".txt", ".py"}
        ):
            raw = path.read_bytes()
            if any(secret and secret.encode() in raw for secret in secrets):
                matched.append(str(path.relative_to(ROOT)))
    record = {
        "label": label,
        "command": command,
        "cwd": str(cwd or ROOT / "backend"),
        "started_at": started_at,
        "finished_at": now(),
        "exit_code": code,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "timed_out": timed_out,
        "actual_secret_match_count": len(matched),
        "matched_paths": matched,
    }
    (RUN / (label + ".json")).write_text(json.dumps(record, indent=2), encoding="utf-8")
    with (RUN / "commands.jsonl").open("a", encoding="utf-8", newline="") as output:
        output.write(json.dumps(record) + "\n")
    if matched:
        raise RuntimeError("actual_sensitive_resource_value_detected")
    print(json.dumps(record))
    print((RUN / (label + ".stdout.log")).read_text(encoding="utf-8")[-2200:])
    print((RUN / (label + ".stderr.log")).read_text(encoding="utf-8")[-600:])
    return code


if __name__ == "__main__":
    label = sys.argv[1]
    resources = "--resources" in sys.argv[2:]
    arguments = [value for value in sys.argv[2:] if value != "--resources"]
    raise SystemExit(execute(label, arguments, resources))
