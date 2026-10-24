"""Repo-level main-path smoke check against an isolated throwaway database.

The caller supplies ``DATABASE_URL`` pointing at a dated disposable database such
as ``story_smoke_YYYYMMDD`` and drops that database afterwards; this script never
creates or drops databases. ``ADMIN_USER_PASSWORD`` is the fixture analyst
password. Every child process is forced into ``DATA_MODE=fixture`` with a
temporary local content directory. Output is key=value lines on stdout; no
password or connection string is printed. Exit codes: 0 all assertions passed,
1 assertion or business failure, 2 environment configuration error.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import httpx
from sqlalchemy import Table, create_engine, insert, text
from sqlalchemy.engine import URL, Connection, Engine, make_url
from sqlalchemy.exc import SQLAlchemyError

if TYPE_CHECKING:
    from ai_intel.assessment.persistence_contracts import AssessmentReceipt

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SCRIPTS = ROOT / "scripts"
HEALTH_HOST = "127.0.0.1"
HEALTH_PATH = "/v1/health/live"
HEALTH_BODY_STATUS = "live"
STORY_RULE_FIELD = "rule_id"
STORY_ANALYST_USERNAME = "main-path-analyst"
ASSET_NAME_PREFIX = "主路径夹具资产 "
EXPECTED_RULE_STATUS = "published"
EXPECTED_RULE_VERSION = 1
EXPECTED_ASSESSMENT_STATUSES = {
    "1.4.1": "supported_applicability",
    "1.4.2": "excluded_with_evidence",
}
READY_POLL_INTERVAL_SECONDS = 0.5
API_STOP_TIMEOUT_SECONDS = 10


class EnvironmentConfigurationError(RuntimeError):
    """Caller-supplied environment is missing or unusable before any connection."""


@dataclass(frozen=True)
class SmokeArguments:
    port: int
    ready_timeout_seconds: int


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class StoryAsset:
    asset_id: str
    display_name: str
    snapshot_id: str
    component_version: str


def emit(line: str) -> None:
    print(line, flush=True)


def positive_integer(raw: str) -> int:
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="smoke_main_path.py",
        description=(
            "Main-path smoke check: migrate, load the fixture story, start the API, "
            "assert rule publication, asset assessments, idempotency and health."
        ),
        epilog=(
            "Requires DATABASE_URL pointing at a dated disposable database "
            "(for example story_smoke_YYYYMMDD) that the caller drops afterwards, "
            "plus ADMIN_USER_PASSWORD for the fixture analyst. "
            "Exit codes: 0 pass, 1 assertion failure, 2 environment configuration error."
        ),
    )
    parser.add_argument(
        "--port",
        type=positive_integer,
        required=True,
        help="TCP port for the uvicorn API process on 127.0.0.1",
    )
    parser.add_argument(
        "--ready-timeout-seconds",
        type=positive_integer,
        default=60,
        help="budget for API readiness polling (default 60)",
    )
    return parser.parse_args(argv)


def require_smoke_environment() -> tuple[str, str]:
    """Read caller inputs; neither value is ever printed."""
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise EnvironmentConfigurationError("DATABASE_URL is required and is not printed")
    analyst_password = os.environ.get("ADMIN_USER_PASSWORD", "")
    if not analyst_password:
        raise EnvironmentConfigurationError("ADMIN_USER_PASSWORD is required and is not printed")
    return database_url, analyst_password


def normalize_database_url(database_url: str) -> URL:
    """Keep the parsed URL object: rendering it to a string masks the password."""
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise EnvironmentConfigurationError("DATABASE_URL must use PostgreSQL")
    return url.set(drivername="postgresql+psycopg")


def redact_secret_text(value: str, database_url: str, analyst_password: str) -> str:
    """Scrub the connection string and password wherever embedded text could leak them."""
    redacted = value
    if database_url:
        redacted = redacted.replace(database_url, "[redacted-database-url]")
    if analyst_password:
        redacted = redacted.replace(analyst_password, "[redacted]")
    return redacted


def build_child_environment(
    database_url: str, analyst_password: str, raw_directory: Path
) -> dict[str, str]:
    """Fixture mode is forced; the caller's other environment variables propagate."""
    environment = os.environ.copy()
    environment.update(
        {
            "DATABASE_URL": database_url,
            "DATA_MODE": "fixture",
            "APP_ENV": "development",
            "ADMIN_USER_PASSWORD": analyst_password,
            "RAW_CONTENT_DIRECTORY": str(raw_directory),
            "CONTENT_STORE_BACKEND": "local",
        }
    )
    return environment


def build_assertion_engine(normalized_url: URL) -> Engine:
    return create_engine(
        normalized_url,
        hide_parameters=True,
        connect_args={"connect_timeout": 5},
    )


def probe_database(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def run_script(script_name: str, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script_name)],
        cwd=BACKEND,
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


def start_api(port: int, environment: dict[str, str]) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "ai_intel.api.app:app",
            "--host",
            HEALTH_HOST,
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=BACKEND,
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def stop_api(process: subprocess.Popen[str]) -> tuple[str, str]:
    """Terminate the API process and drain captured output for redacted diagnostics."""
    if process.poll() is None:
        process.terminate()
    try:
        stdout, stderr = process.communicate(timeout=API_STOP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
    return stdout or "", stderr or ""


def fetch_live_health(base_url: str) -> tuple[int, str] | None:
    """Return (status code, body status), or None while the listener is not accepting."""
    try:
        with httpx.Client(trust_env=False, timeout=2.0) as client:
            response = client.get(base_url + HEALTH_PATH)
    except httpx.HTTPError:
        return None
    try:
        payload = response.json()
    except ValueError:
        return (response.status_code, "unparseable")
    if not isinstance(payload, dict) or not isinstance(payload.get("status"), str):
        return (response.status_code, "missing")
    return (response.status_code, payload["status"])


def wait_for_live_health(
    base_url: str, process: subprocess.Popen[str], timeout_seconds: int
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        health = fetch_live_health(base_url)
        if health is not None and health[0] == 200:
            return True
        time.sleep(READY_POLL_INTERVAL_SECONDS)
    return False


def story_field(stdout: str, field: str) -> str | None:
    """Read one identifier from the story public lines."""
    for line in stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator and key == field:
            return value.strip()
    return None


def parse_story_state(stdout: str) -> str:
    """Read the load state word from the first public story line."""
    lines = stdout.strip().splitlines()
    if not lines:
        return "missing"
    prefix = "main-path story "
    if not lines[0].startswith(prefix):
        return "unexpected"
    state = lines[0][len(prefix) :]
    return state if state in {"created", "already-present"} else "unexpected"


def read_component_version(payload: object) -> str:
    """Read the first manifest component version; psycopg returns JSONB as a dict."""
    if not isinstance(payload, dict):
        return "missing"
    components = payload.get("components", [])
    if not isinstance(components, list) or not components:
        return "missing"
    first = components[0]
    if not isinstance(first, dict) or "version" not in first:
        return "missing"
    return str(first["version"])


def load_story_assets(connection: Connection) -> list[StoryAsset]:
    rows = connection.execute(
        text(
            "SELECT assets.asset_id::text AS asset_id, assets.display_name AS display_name, "
            "asset_snapshots.snapshot_id::text AS snapshot_id, "
            "asset_snapshots.canonical_payload AS canonical_payload "
            "FROM assets JOIN asset_snapshots ON assets.asset_id = asset_snapshots.asset_id "
            "WHERE assets.display_name LIKE :name_pattern "
            "ORDER BY assets.display_name"
        ),
        {"name_pattern": ASSET_NAME_PREFIX + "%"},
    ).all()
    return [
        StoryAsset(
            asset_id=row.asset_id,
            display_name=row.display_name,
            snapshot_id=row.snapshot_id,
            component_version=read_component_version(row.canonical_payload),
        )
        for row in rows
    ]


def record_published_rule_check(
    connection: Connection, rule_id: str, record: Callable[[CheckResult], None]
) -> None:
    row = connection.execute(
        text("SELECT status, version FROM condition_rule_versions WHERE rule_id = :rule_id"),
        {"rule_id": rule_id},
    ).one_or_none()
    if row is None:
        emit("rule_status=missing")
        record(CheckResult("rule_published", False, "rule row missing"))
        return
    evidence = f"rule_status={row.status} rule_version={int(row.version)}"
    emit(evidence)
    passed = row.status == EXPECTED_RULE_STATUS and int(row.version) == EXPECTED_RULE_VERSION
    record(CheckResult("rule_published", passed, evidence))


def story_assets_complete(assets: list[StoryAsset], record: Callable[[CheckResult], None]) -> bool:
    versions = sorted(asset.component_version for asset in assets)
    passed = len(assets) == len(EXPECTED_ASSESSMENT_STATUSES) and versions == sorted(
        EXPECTED_ASSESSMENT_STATUSES
    )
    record(
        CheckResult(
            "story_assets_present",
            passed,
            f"count={len(assets)} versions={','.join(versions) or 'none'}",
        )
    )
    return passed


def insert_assertion_session(engine: Engine, auth_sessions: Table) -> str:
    """Create a short-lived analyst session so the in-process service authenticates."""
    unused_csrf = "smoke-unused"
    token = f"smoke-{uuid4().hex}"
    now = datetime.now(UTC)
    with engine.begin() as connection:
        user_id = connection.execute(
            text("SELECT user_id FROM users WHERE username = :username"),
            {"username": STORY_ANALYST_USERNAME},
        ).scalar_one()
        connection.execute(
            insert(auth_sessions).values(
                session_hash=hashlib.sha256(token.encode()).hexdigest(),
                user_id=user_id,
                csrf_token=unused_csrf,
                issued_at=now,
                expires_at=now + timedelta(minutes=10),
            )
        )
    return token


def record_assessment_check(
    asset: StoryAsset,
    receipt: AssessmentReceipt,
    record: Callable[[CheckResult], None],
) -> None:
    status_value = receipt.status.value
    expected_status = EXPECTED_ASSESSMENT_STATUSES[asset.component_version]
    missing = ",".join(receipt.missing_requirements) or "none"
    conflicts = ",".join(receipt.conflicts) or "none"
    emit(
        f"asset={asset.display_name} component_version={asset.component_version} "
        f"assessment={status_value} missing={missing} conflicts={conflicts}"
    )
    check_name = "asset_assessment_" + asset.component_version.replace(".", "_")
    record(
        CheckResult(
            check_name,
            status_value == expected_status,
            f"assessment_status={status_value} expected={expected_status}",
        )
    )


def run_database_assertions(
    engine: Engine,
    rule_id: str,
    raw_directory: Path,
    record: Callable[[CheckResult], None],
) -> None:
    """Assert fixture rule publication and both asset assessment statuses."""
    try:
        from ai_intel.api.auth_state import auth_sessions
        from ai_intel.assessment.assessment_service import AssessmentService
        from ai_intel.infrastructure.content_store import ContentStore
    except ImportError as import_error:
        raise EnvironmentConfigurationError(
            f"run inside backend venv: {import_error}"
        ) from import_error
    with engine.connect() as connection:
        record_published_rule_check(connection, rule_id, record)
        assets = load_story_assets(connection)
    if not story_assets_complete(assets, record):
        return
    token = insert_assertion_session(engine, auth_sessions)
    service = AssessmentService(engine, token, ContentStore(raw_directory))
    for asset in assets:
        prepared = service.prepare(
            asset.asset_id, asset.snapshot_id, rule_id, EXPECTED_RULE_VERSION
        )
        receipt = service.commit(prepared)
        record_assessment_check(asset, receipt, record)


def emit_summary(checks: list[CheckResult]) -> int:
    failed = [check.name for check in checks if not check.passed]
    emit("failures=" + (",".join(failed) if failed else "none"))
    emit("smoke_result=" + ("pass" if not failed else "fail"))
    return 0 if not failed else 1


def run_smoke(arguments: SmokeArguments) -> int:
    try:
        database_url, analyst_password = require_smoke_environment()
        engine = build_assertion_engine(normalize_database_url(database_url))
    except EnvironmentConfigurationError as failure:
        print(f"ERROR {failure}", file=sys.stderr)
        return 2
    except SQLAlchemyError as failure:
        print(
            f"ERROR DATABASE_URL is not a usable SQLAlchemy URL: {type(failure).__name__}",
            file=sys.stderr,
        )
        return 2
    raw_directory = tempfile.TemporaryDirectory(prefix="main_path_smoke_raw_")
    child_environment = build_child_environment(
        database_url, analyst_password, Path(raw_directory.name)
    )
    process: subprocess.Popen[str] | None = None
    checks: list[CheckResult] = []

    def record(check: CheckResult) -> None:
        checks.append(check)
        emit(
            f"check={check.name} result={'pass' if check.passed else 'fail'} detail={check.detail}"
        )

    emit("smoke=main_path")
    emit("data_mode=fixture")
    try:
        try:
            probe_database(engine)
        except SQLAlchemyError as failure:
            raise EnvironmentConfigurationError(
                f"database unreachable: {type(failure).__name__}"
            ) from failure
        emit("database_probe=reachable")

        migration = run_script("migrate.py", child_environment)
        emit(f"migrate_exit={migration.returncode}")
        emit(
            "migrate_stdout="
            + redact_secret_text(migration.stdout.strip(), database_url, analyst_password)
        )
        emit(
            "migrate_stderr="
            + redact_secret_text(migration.stderr.strip(), database_url, analyst_password)
        )
        if migration.returncode != 0:
            return migration.returncode

        story = run_script("load_main_path_story.py", child_environment)
        emit(f"story_exit={story.returncode}")
        emit(redact_secret_text(story.stdout.strip(), database_url, analyst_password))
        if story.stderr.strip():
            emit(
                "story_stderr="
                + redact_secret_text(story.stderr.strip(), database_url, analyst_password)
            )
        if story.returncode != 0:
            return story.returncode
        rule_id = story_field(story.stdout, STORY_RULE_FIELD)
        if rule_id is None:
            record(CheckResult("story_output_parseable", False, "rule_id line missing"))
            return 1
        record(CheckResult("story_output_parseable", True, f"rule_id={rule_id}"))

        base_url = f"http://{HEALTH_HOST}:{arguments.port}"
        process = start_api(arguments.port, child_environment)
        ready = wait_for_live_health(base_url, process, arguments.ready_timeout_seconds)
        emit(f"api_host={HEALTH_HOST}")
        emit(f"api_port={arguments.port}")
        emit(f"api_ready={'true' if ready else 'false'}")
        record(
            CheckResult("api_ready", ready, "" if ready else "readiness timeout or process exited")
        )
        if not ready:
            _, api_stderr = stop_api(process)
            process = None
            tail = "\n".join(api_stderr.strip().splitlines()[-10:])
            emit("api_stderr_tail=" + redact_secret_text(tail, database_url, analyst_password))

        run_database_assertions(engine, rule_id, Path(raw_directory.name), record)

        rerun = run_script("load_main_path_story.py", child_environment)
        rerun_state = parse_story_state(rerun.stdout)
        rerun_rule_id = story_field(rerun.stdout, STORY_RULE_FIELD)
        emit(f"rerun_exit={rerun.returncode}")
        emit(redact_secret_text(rerun.stdout.strip(), database_url, analyst_password))
        if rerun.stderr.strip():
            emit(
                "rerun_stderr="
                + redact_secret_text(rerun.stderr.strip(), database_url, analyst_password)
            )
        idempotent = (
            rerun.returncode == 0 and rerun_state == "already-present" and rerun_rule_id == rule_id
        )
        record(
            CheckResult(
                "story_idempotent",
                idempotent,
                f"rerun_state={rerun_state} rule_id_matches={rerun_rule_id == rule_id}",
            )
        )

        if ready:
            health = fetch_live_health(base_url)
            if health is None:
                emit(f"health_path={HEALTH_PATH} health_status=unreachable")
                record(CheckResult("health_live", False, "request failed"))
            else:
                status_code, body_status = health
                emit(
                    f"health_path={HEALTH_PATH} health_status={status_code} "
                    f"body_status={body_status}"
                )
                record(
                    CheckResult(
                        "health_live",
                        status_code == 200 and body_status == HEALTH_BODY_STATUS,
                        f"health_status={status_code} body_status={body_status}",
                    )
                )
        else:
            record(CheckResult("health_live", False, "api not ready"))
        return emit_summary(checks)
    except EnvironmentConfigurationError as failure:
        print(f"ERROR {failure}", file=sys.stderr)
        emit("smoke_result=config_error")
        return 2
    except Exception as failure:
        emit(f"error_type={type(failure).__name__}")
        return emit_summary(checks)
    finally:
        if process is not None:
            stop_api(process)
        engine.dispose()
        raw_directory.cleanup()


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    return run_smoke(
        SmokeArguments(port=arguments.port, ready_timeout_seconds=arguments.ready_timeout_seconds)
    )


if __name__ == "__main__":
    sys.exit(main())
