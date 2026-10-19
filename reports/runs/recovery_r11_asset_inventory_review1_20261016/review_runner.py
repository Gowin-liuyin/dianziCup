"""Independent review evidence; only a new loopback test database is mutated."""

import ast
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from ai_intel.assets.inventory_models import ASSET_TABLES
from ai_intel.infrastructure.database import run_migrations
from ai_intel.knowledge.models import metadata
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
BACKEND = ROOT / "backend"
PYTHON = BACKEND / ".venv/Scripts/python.exe"
AUTHOR = ROOT / "reports/runs/recovery_r11_asset_inventory_20261016"


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def archive_check():
    manifest_bytes = git(
        "show",
        "HEAD:reports/runs/recovery_r11_asset_inventory_20261016/artifact_manifest.json",
    )
    manifest = json.loads(manifest_bytes)
    records = []
    for row in manifest["artifacts"]:
        blob = git("show", "HEAD:" + row["path"])
        assert len(blob) == row["bytes"]
        assert hashlib.sha256(blob).hexdigest() == row["sha256"]
        raw = gzip.decompress(blob)
        records.append(
            {
                "path": row["path"],
                "blob_sha256": hashlib.sha256(blob).hexdigest(),
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "raw_bytes": len(raw),
            }
        )
    raw_entries = manifest["raw_evidence_archives"]
    for row in raw_entries:
        raw = gzip.decompress(git("show", "HEAD:" + row["archive_path"]))
        assert len(raw) == row["bytes"]
        assert hashlib.sha256(raw).hexdigest() == row["sha256"]
    for row in manifest["source_proofs"]:
        blob = git("show", "HEAD:" + row["path"])
        assert hashlib.sha256(blob).hexdigest() == row["git_blob_sha256"]
        assert blob == git(
            "show", "6f82c68075dde808da9c92e3a49ad2e605e6b5a8:" + row["path"]
        )
    receipt = {
        "recorded_at": now(),
        "material_commit": git("rev-parse", "HEAD").decode().strip(),
        "code_commit": "6f82c68075dde808da9c92e3a49ad2e605e6b5a8",
        "manifest_git_blob_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "gzip_entries": len(records),
        "raw_entries_key": [k for k in manifest if "raw" in k],
        "raw_entries_type": type(raw_entries).__name__,
        "records": records,
    }
    (RUN / "archive_verification.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in receipt.items() if k != "records"}), flush=True)


def main():
    archive_check()
    config = json.loads(
        subprocess.check_output(
            [
                "wsl",
                "-d",
                "Ubuntu-22.04",
                "-u",
                "root",
                "--exec",
                "cat",
                "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
            ]
        )
    )
    original_url = make_url(config["TEST_DATABASE_URL"])
    assert config["postgres_port"] == 25432
    assert (
        original_url.host in {"127.0.0.1", "localhost"} and original_url.port == 25432
    )
    assert original_url.database.startswith("test_")
    suffix = uuid4().hex[:14]
    run_id = "r11_inventory_review1_" + suffix
    database = "test_dianzi_r11_inventory_review1_" + suffix
    assert re.fullmatch(r"test_dianzi_r11_inventory_review1_[0-9a-f]{14}", database)
    admin_url = original_url.set(
        drivername="postgresql+psycopg", host="127.0.0.1", database="postgres", query={}
    )
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT", hide_parameters=True)
    with admin.connect() as connection:
        connection.execute(text('CREATE DATABASE "' + database + '"'))
    admin.dispose()
    url = admin_url.set(database=database)
    started = now()
    run_migrations(
        url.render_as_string(hide_password=False), "0016_source_response_receipts"
    )
    engine = create_engine(url, hide_parameters=True)
    with engine.begin() as connection:
        metadata.create_all(connection, tables=list(ASSET_TABLES))
    with engine.connect() as connection:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        pg_version = connection.scalar(text("SHOW server_version"))
    engine.dispose()
    (RUN / "database_receipt.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "database": database,
                "host": "127.0.0.1",
                "port": 25432,
                "started_at": started,
                "finished_at": now(),
                "postgres_version": pg_version,
                "base_migration": revision,
                "asset_tables_action": "create_tables_not_production_migration",
                "asset_tables": [table.name for table in ASSET_TABLES],
                "cleanup": "not_deleted_no_downgrade",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    environment = {
        **os.environ,
        "TEST_DATABASE_URL": url.render_as_string(hide_password=False),
        "DIANZI_TEST_RUN_ID": run_id,
        "PYTHONPATH": str(BACKEND / "src"),
        "PYTHONIOENCODING": "utf-8",
    }
    tree = ast.parse((AUTHOR / "run_checks.py").read_text(encoding="utf-8"))
    checks = next(
        ast.literal_eval(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "checks"
            for target in node.targets
        )
    )
    if (RUN / "review_probes.py").exists():
        checks.append(
            (
                "independent_probes",
                ["-m", "pytest", str(RUN / "review_probes.py"), "--no-cov", "-q"],
            )
        )
    checks.append(
        (
            "default_coverage_gate",
            [
                "-m",
                "pytest",
                "tests/unit/test_r11_inventory.py",
                "tests/contract/test_r11_inventory_contracts.py",
                "tests/security/test_r11_inventory_boundary.py",
                "-q",
            ],
        )
    )
    receipts = []
    for label, args in checks:
        if "pytest" in args:
            args.append("--junitxml=" + str(RUN / (label + ".xml")))
        command = [str(PYTHON), *args]
        started = now()
        result = subprocess.run(
            command,
            cwd=BACKEND,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
            check=False,
        )
        output = result.stdout + result.stderr
        for secret in [environment["TEST_DATABASE_URL"], original_url.password or ""]:
            if secret:
                output = output.replace(secret, "[redacted test connection]")
        (RUN / (label + ".log")).write_text(output, encoding="utf-8")
        receipts.append(
            {
                "label": label,
                "argv": command,
                "cwd": str(BACKEND),
                "started_at": started,
                "finished_at": now(),
                "exit_code": result.returncode,
            }
        )
        (RUN / "commands.json").write_text(
            json.dumps(receipts, indent=2), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "label": label,
                    "exit_code": result.returncode,
                    "summary": output.splitlines()[-1] if output else "",
                }
            ),
            flush=True,
        )
    return int(
        any(
            row["exit_code"]
            for row in receipts
            if row["label"] != "default_coverage_gate"
        )
    )


if __name__ == "__main__":
    sys.exit(main())
