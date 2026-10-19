"""Explicit local DPAPI opt-in runner; the collected fixtures only consume CI environment."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--dpapi-resource-reference", type=Path, required=True)
    parser.add_argument("--powershell", type=Path, required=True)
    parser.add_argument("--label", default="pg20")
    parser.add_argument("--probe-script", type=Path)
    parser.add_argument("--new-pg-tests", action="store_true")
    parser.add_argument("--baseline", action="store_true")
    arguments = parser.parse_args()
    if os.name != "nt":
        parser.error("DPAPI opt-in is supported only by this Windows evidence runner")
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,47}", arguments.label):
        parser.error("evidence label must be a lowercase test identifier")
    log_path, receipt_path, junit_path = (
        RUN / (arguments.label + suffix) for suffix in (".log", ".json", ".xml")
    )
    if any(path.exists() for path in (log_path, receipt_path, junit_path)):
        raise RuntimeError("PG evidence label already recorded")
    started = datetime.now().astimezone().isoformat()
    source_paths = (
        "backend/src/ai_intel/api/credentials.py",
        "backend/tests/integration/test_r18_api_key_credentials_pg.py",
        "backend/tests/contract/test_r18_api_key_pg_fixture_entry.py",
        "backend/tests/unit/test_r18_api_key_post_lock_time.py",
        "backend/tests/integration/test_r18_api_key_post_lock_time_pg.py",
    )
    source_hashes = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source_paths
    }
    source_root = ROOT / "backend/src"
    baseline_root = Path("D:/wt/r18-api-key-ci-fix1")
    if arguments.baseline:
        assert (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=baseline_root, text=True
            ).strip()
            == "c0428cb9801549c3bc778060153899e4b72028a2"
        )
        baseline_credentials = baseline_root / "backend/src/ai_intel/api/credentials.py"
        assert baseline_credentials.read_bytes().replace(b"\r\n", b"\n") == subprocess.check_output(
            ["git", "show", "c0428cb9:backend/src/ai_intel/api/credentials.py"], cwd=ROOT
        )
        source_root = baseline_root / "backend/src"
    sys.path.insert(0, str(source_root))
    reference = str(arguments.dpapi_resource_reference.resolve())
    if "'" in reference:
        raise ValueError("DPAPI resource reference contains an unsupported quote")
    protected = subprocess.run(
        [
            str(arguments.powershell),
            "-NoProfile",
            "-Command",
            "$r18Protected=Get-Content -LiteralPath '" + reference + "' -Raw; "
            "$r18Clear=$r18Protected | ConvertTo-SecureString | "
            "ConvertFrom-SecureString -AsPlainText; [Console]::Write($r18Clear)",
        ],
        capture_output=True,
        timeout=15,
        check=True,
    )
    original_secret = SecretStr(json.loads(protected.stdout)["TEST_DATABASE_URL"])
    original = make_url(original_secret.get_secret_value())
    if (
        original.host != "127.0.0.1"
        or original.port != 25432
        or not original.database
        or not original.database.startswith("test_")
        or not original.username
        or not re.fullmatch(r"test_[a-z0-9_]+", original.username)
        or not original.password
    ):
        raise RuntimeError("explicitly authorized local test resource identity rejected")
    run_id = "r18_expiry_fix2_" + uuid4().hex
    database_name = "test_dianzi_" + run_id
    configured = original.set(database=database_name)
    database_secret = SecretStr(configured.render_as_string(hide_password=False))
    admin_url = original.set(database="postgres")
    admin_secret = SecretStr(admin_url.render_as_string(hide_password=False))
    sensitive = (
        original_secret,
        database_secret,
        admin_secret,
        SecretStr(original.password),
    )
    admin = create_engine(
        admin_url,
        isolation_level="AUTOCOMMIT",
        hide_parameters=True,
        poolclass=NullPool,
        connect_args={"connect_timeout": 5, "options": "-c statement_timeout=12000"},
    )
    saved_environment = {
        name: os.environ.get(name)
        for name in ("TEST_DATABASE_URL", "DIANZI_TEST_RUN_ID", "PYTHONPATH")
    }
    created = dropped = False
    schema_count = sessions = None
    result = 1
    output = io.StringIO()
    try:
        with admin.connect() as connection:
            assert connection.scalar(text("SELECT current_user")) == original.username
            assert (
                connection.scalar(
                    text("SELECT 1 FROM pg_database WHERE datname=:name"),
                    {"name": database_name},
                )
                is None
            )
            connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
            created = True
        os.environ["DIANZI_TEST_RUN_ID"] = run_id
        os.environ["TEST_DATABASE_URL"] = database_secret.get_secret_value()
        os.environ["PYTHONPATH"] = str(source_root)
        os.chdir(ROOT / "backend")
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            if arguments.probe_script:
                probe_script = arguments.probe_script.resolve()
                if probe_script != RUN / "independent_pg_probe.py":
                    raise ValueError("only the exact frozen reviewer probe is authorized")
                current = datetime.now().astimezone()
                if current.second >= 55:
                    time.sleep(60 - current.second - current.microsecond / 1_000_000 + 0.1)
                execution = subprocess.run(
                    [sys.executable, str(probe_script)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=90,
                )
                output.write(execution.stdout + execution.stderr)
                result = execution.returncode
                observation_path = RUN / "independent_pg_observation.json"
                if observation_path.exists():
                    target = RUN / (arguments.label + "_observation.json")
                    assert not target.exists()
                    observation_path.replace(target)
            else:
                test_target = "tests/integration/test_r18_api_key_credentials_pg.py"
                if arguments.new_pg_tests:
                    test_target = "tests/integration/test_r18_api_key_post_lock_time_pg.py"
                result = int(
                    pytest.main(
                        ["-o", "addopts=", test_target, "-q", "--junitxml=" + str(junit_path)]
                    )
                )
        probe = create_engine(
            configured,
            hide_parameters=True,
            poolclass=NullPool,
            connect_args={
                "connect_timeout": 5,
                "options": "-c statement_timeout=12000",
            },
        )
        try:
            with probe.connect() as connection:
                schema_count = connection.scalar(
                    text("SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'r18c_%'")
                )
                sessions = connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE datname=current_database() AND pid<>pg_backend_pid()"
                    )
                )
                assert schema_count == 0 and sessions == 0
        finally:
            probe.dispose()
    except Exception as failure:
        output.write("runner failure type: " + type(failure).__name__ + "\n")
        result = 1
    finally:
        for name, saved_value in saved_environment.items():
            if saved_value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = saved_value
        try:
            if created:
                with admin.connect() as connection:
                    remaining = connection.scalar(
                        text("SELECT count(*) FROM pg_stat_activity WHERE datname=:name"),
                        {"name": database_name},
                    )
                    if remaining != 0:
                        output.write("owned database still has sessions; no forced termination\n")
                        result = 1
                    else:
                        connection.exec_driver_sql(f'DROP DATABASE "{database_name}"')
                        dropped = True
        finally:
            admin.dispose()
    raw = output.getvalue()
    leaked = any(value.get_secret_value() in raw for value in sensitive)
    for value in sensitive:
        raw = raw.replace(value.get_secret_value(), "[redacted test credential]")
    log_path.write_text(raw, encoding="utf-8", newline="\n")
    counts = None
    junit_leaked = False
    if junit_path.exists():
        junit_text = junit_path.read_text(encoding="utf-8")
        junit_leaked = any(value.get_secret_value() in junit_text for value in sensitive)
        for value in sensitive:
            junit_text = junit_text.replace(value.get_secret_value(), "[redacted test credential]")
        if junit_leaked:
            junit_path.write_text(junit_text, encoding="utf-8", newline="\n")
        cases = ElementTree.fromstring(junit_text).findall(".//testcase")
        counts = {
            "tests": len(cases),
            "failures": sum(case.find("failure") is not None for case in cases),
            "errors": sum(case.find("error") is not None for case in cases),
            "skipped": sum(case.find("skipped") is not None for case in cases),
        }
    receipt = {
        "started_at": started,
        "ended_at": datetime.now().astimezone().isoformat(),
        "cwd": str(ROOT / "backend"),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "code_tree": subprocess.check_output(
            ["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True
        ).strip(),
        "source_raw_sha256_at_start": source_hashes,
        "source_raw_bytes_unchanged_during_run": all(
            hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
            for path, digest in source_hashes.items()
        ),
        "runner_argv": sys.argv,
        "source_root": str(source_root),
        "baseline_source": arguments.baseline,
        "pytest_or_probe_target": str(arguments.probe_script)
        if arguments.probe_script
        else (
            "tests/integration/test_r18_api_key_post_lock_time_pg.py"
            if arguments.new_pg_tests
            else "tests/integration/test_r18_api_key_credentials_pg.py"
        ),
        "pytest_exit_code": result,
        "counts": counts,
        "run_id": run_id,
        "owned_database": database_name,
        "created": created,
        "dropped": dropped,
        "schemas_after_tests": schema_count,
        "other_owned_database_sessions_after_tests": sessions,
        "connection_policy": "NullPool, one serial pytest, no forced session termination",
        "credential_transport": "explicit DPAPI opt-in; TEST_DATABASE_URL in process memory only",
        "exact_dsn_or_password_in_raw": leaked,
        "exact_dsn_or_password_in_junit": junit_leaked,
        "log_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest(),
    }
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "pytest_exit_code": result,
                "counts": counts,
                "schemas_after_tests": schema_count,
                "other_sessions_after_tests": sessions,
                "owned_database_dropped": dropped,
                "credential_match": leaked or junit_leaked,
            }
        )
    )
    return result or int(leaked or junit_leaked) or int(not dropped)


if __name__ == "__main__":
    raise SystemExit(main())
