"""Owned default API/PG/Edge execution; credentials remain in inherited memory only."""

import hashlib
import ctypes
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
RUN_ID = "r17_real_review1_20261016"
PYTHON = Path("D:/dianzi/backend/.venv/Scripts/python.exe")
SECRETS = []
PHASE = "initialize"


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()


def redact(value):
    for sensitive in sorted(SECRETS, key=len, reverse=True):
        value = value.replace(sensitive.get_secret_value(), "[redacted owned test secret]")
    return value


def configure_database():
    captured = subprocess.run(["C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe", "-NoProfile", "-Command", "$r17Protected=Get-Content -LiteralPath 'D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi' -Raw; $r17Clear=$r17Protected | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText; [Console]::Write($r17Clear)"], capture_output=True, timeout=15, check=True)
    original = make_url(json.loads(captured.stdout)["TEST_DATABASE_URL"])
    assert (original.host, original.port, original.database) == ("127.0.0.1", 25432, "test_dianzi_r01_20261014")
    assert original.username.startswith("test_")
    configured = original.set(database="test_dianzi_" + RUN_ID)
    SECRETS.extend([SecretStr(configured.render_as_string(hide_password=False)), SecretStr(original.password)])
    marker = RUN / "owned_database.json"
    engine = create_engine(original, isolation_level="AUTOCOMMIT", hide_parameters=True, poolclass=NullPool, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            exists = connection.scalar(text("SELECT 1 FROM pg_database WHERE datname=:database"), {"database": configured.database})
            if exists:
                assert marker.exists() and json.loads(marker.read_text())["database"] == configured.database
            else:
                connection.exec_driver_sql('CREATE DATABASE "' + configured.database + '"')
                marker.write_text(json.dumps({"database": configured.database, "created_at": now(), "run_id": RUN_ID}) + "\n", encoding="utf8")
    finally:
        engine.dispose()
    return configured


def run(label):
    global PHASE
    PHASE = "port guard"
    for port in (26873, 28873):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    configured = configure_database()
    PHASE = "migrate and seed"
    environment = os.environ.copy()
    environment.update(PYTHONPATH=str(ROOT / "backend/src"), PYTHONIOENCODING="utf-8", TEST_DATABASE_URL=configured.render_as_string(hide_password=False), DIANZI_TEST_RUN_ID=RUN_ID, API_PROXY_TARGET="http://127.0.0.1:28873", R17_EDGE_LABEL=label, R17_BOOT_NONCE=uuid4().hex)
    sys.path.insert(0, environment["PYTHONPATH"])
    from ai_intel.api.auth_state import PgAuthenticationStateStore
    from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
    from ai_intel.domain.access import Role
    migration = subprocess.run([str(PYTHON), "-c", "import os; from ai_intel.infrastructure.database import run_migrations; run_migrations(os.environ['TEST_DATABASE_URL'])"], cwd=ROOT, env=environment, capture_output=True, timeout=60)
    (RUN / (label + "_migration.log")).write_text(redact((migration.stdout + migration.stderr).decode("utf8", errors="replace")), encoding="utf8")
    assert migration.returncode == 0
    seed_engine = create_engine(configured, hide_parameters=True, poolclass=NullPool, connect_args={"connect_timeout": 5})
    try:
        with seed_engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0022_sbom_sidecars"
        bootstrap = AuthenticationSessionService(DatabaseUserDirectory(seed_engine), ("http://127.0.0.1:26873",), False, state_store=PgAuthenticationStateStore(seed_engine))
        accounts = []
        for _ in range(11):
            username = "r17-synthetic-browser-" + uuid4().hex
            password = secrets.token_urlsafe(32)
            SECRETS.append(SecretStr(password))
            bootstrap.create_precreated_user(username, password, "r17-synthetic-tenant-" + uuid4().hex, Role.TENANT_ADMIN)
            accounts.append({"username": username, "password": password})
        environment["R17_BROWSER_ACCOUNTS"] = json.dumps(accounts)
    finally:
        seed_engine.dispose()
    started = now()
    PHASE = "default API boot"
    api = subprocess.Popen([str(PYTHON), str(RUN / "api_server.py")], cwd=ROOT, env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
    argv = ["C:/Program Files/nodejs/node.exe", "node_modules/@playwright/test/cli.js", "test", "--config=../reports/runs/recovery_r17_integrated_sbom_browser_review1_20261016/playwright.actual.cjs"]
    result = None
    try:
        for _ in range(150):
            if api.poll() is not None:
                raise RuntimeError("owned default API stopped before readiness")
            boot_path = RUN / "api_boot.json"
            if boot_path.exists():
                boot = json.loads(boot_path.read_text())
                if api.pid in (boot["pid"], boot.get("parent_pid")) and boot["nonce"] == environment["R17_BOOT_NONCE"] and boot["started"]:
                    break
            time.sleep(0.1)
        else:
            raise RuntimeError("owned default API readiness deadline exceeded")
        assert Path(boot["default_factory"]).is_relative_to(ROOT / "backend/src")
        parent_session = ctypes.c_ulong()
        ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(parent_session))
        assert boot["session_id"] == parent_session.value
        (RUN / (label + "_api_boot.json")).write_text(json.dumps(boot, indent=2) + "\n", encoding="utf8")
        PHASE = "actual Edge tests"
        result = subprocess.run(argv, cwd=ROOT / "frontend", env=environment, capture_output=True, timeout=420)
        (RUN / (label + ".log")).write_text(redact((result.stdout + result.stderr).decode("utf8", errors="replace")), encoding="utf8")
    finally:
        PHASE = "owned API shutdown"
        api_out, api_error = api.communicate(input=b"stop\n", timeout=20)
        (RUN / (label + "_api.log")).write_text(redact((api_out + api_error).decode("utf8", errors="replace")), encoding="utf8")
        (RUN / (label + "_api_shutdown.json")).write_bytes((RUN / "api_shutdown.json").read_bytes())
        PHASE = "owned PostgreSQL cleanup"
        audit_engine = create_engine(configured, hide_parameters=True, poolclass=NullPool, connect_args={"connect_timeout": 5})
        try:
            with audit_engine.connect() as connection:
                renamed_sidecar = connection.scalar(text("SELECT to_regclass('r17_owned_unavailable_sbom_sidecars')"))
                current_sidecar = connection.scalar(text("SELECT to_regclass('asset_snapshot_sbom_sidecars')"))
                remaining_history = []
                for _ in range(50):
                    connection.execute(text("SELECT pg_stat_clear_snapshot()"))
                    remaining = connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=:database AND pid<>pg_backend_pid()"), {"database": configured.database})
                    remaining_history.append(remaining)
                    if remaining == 0:
                        break
                    time.sleep(0.1)
                (RUN / (label + "_cleanup.json")).write_text(json.dumps({"current_sidecar": current_sidecar, "renamed_sidecar": renamed_sidecar, "remaining_history": remaining_history, "api_exit_code": api.returncode}) + "\n", encoding="utf8")
                assert renamed_sidecar is None and current_sidecar is not None and remaining == 0
        finally:
            audit_engine.dispose()
        scan_files = [file for file in RUN.rglob("*") if file.is_file() and file.suffix in {".json", ".log", ".md", ".xml", ".txt"}]
        hits = []
        for file in scan_files:
            value = file.read_text(encoding="utf8", errors="replace")
            if any(sensitive.get_secret_value() in value for sensitive in SECRETS):
                hits.append(str(file.relative_to(RUN)))
                file.write_text(redact(value), encoding="utf8")
        assert not hits
        assert api.returncode == 0
        PHASE = "port and secret audit"
        for port in (26873, 28873):
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", port))
        receipt = {"argv": argv, "cwd": str(ROOT / "frontend"), "started_at": started, "ended_at": now(), "exit_code": None if result is None else result.returncode, "api_exit_code": api.returncode, "api_pid": api.pid, "boot_nonce": environment["R17_BOOT_NONCE"], "own_pg_connections_after_shutdown": remaining, "port_listeners_after_shutdown": 0, "exact_secret_scan_hits": len(hits), "scanned_text_files": len(scan_files), "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "main_buildinfo_sha256": hashlib.sha256(Path("D:/dianzi/frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest()}
        (RUN / (label + "_command.json")).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"label": label, "exit_code": result.returncode, "api_exit_code": api.returncode, "own_pg_connections": remaining}), flush=True)
    return result.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(run(sys.argv[1]))
    except Exception as failure:
        failure_receipt = {"error_type": type(failure).__name__, "phase": PHASE, "observed_at": now(), "label": sys.argv[1]}
        (RUN / (sys.argv[1] + "_runner_failure.json")).write_text(json.dumps(failure_receipt) + "\n", encoding="utf8")
        print(json.dumps(failure_receipt), file=sys.stderr)
        raise SystemExit(1) from None
