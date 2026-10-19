"""独立评审只读源码，在专用库验证；凭据只在内存中传给子进程。"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PYTHON = ROOT / "backend/.venv/Scripts/python.exe"
AUTHOR_RUN = ROOT / "reports/runs/recovery_r11_sbom_inventory_20261016"
CBM = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
SECRETS: list[str] = []


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def redact(value):
    for secret in sorted(set(SECRETS), key=len, reverse=True):
        if secret:
            value = value.replace(secret, "[redacted test credential]")
    return value


def command(name, argv, *, cwd=None, environment=None):
    start = now()
    result = subprocess.run(
        argv,
        cwd=cwd or ROOT / "backend",
        env={**(environment or os.environ), "PYTHONIOENCODING": "utf-8"},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = redact(result.stdout.decode("utf-8", errors="replace"))
    (RUN / (name + ".log")).write_text(output, encoding="utf-8")
    receipt = {
        "name": name,
        "argv": argv,
        "cwd": str(cwd or ROOT / "backend"),
        "start": start,
        "end": now(),
        "exit_code": result.returncode,
        "log": name + ".log",
    }
    with (RUN / "commands.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    print(json.dumps(receipt, ensure_ascii=False), flush=True)
    print(output[-2000:], flush=True)
    return result.returncode


def original(mode):
    entries = [
        json.loads(line) for line in (AUTHOR_RUN / "commands.jsonl").read_text().splitlines()
    ]
    mapping = {
        "pure": "pure_final",
        "mypy": "mypy_first",
        "ruff": "ruff_final2",
        "format": "format_final2",
    }
    item = next(entry for entry in entries if entry["name"] == mapping[mode])
    arguments = item["argv"][1:]
    arguments = [value for value in arguments if not value.startswith("--junitxml=")]
    if mode == "pure":
        arguments.append(f"--junitxml={RUN / 'pure.xml'}")
    if mode in {"ruff", "format"}:
        arguments.append("src/ai_intel/assets/sbom_persistence_models.py")
    return command(mode, [str(PYTHON), *arguments])


def pg(mode):
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    from ai_intel.assets.sbom_persistence_models import asset_snapshot_sbom_sidecars
    from ai_intel.infrastructure.database import run_migrations

    result = subprocess.run(
        [
            "wsl.exe",
            "-d",
            "Ubuntu-22.04",
            "-u",
            "root",
            "--exec",
            "cat",
            "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
        ],
        capture_output=True,
        check=True,
    )
    parsed = make_url(json.loads(result.stdout)["TEST_DATABASE_URL"])
    assert parsed.host in {"127.0.0.1", "localhost"} and parsed.port == 25432
    assert parsed.database.startswith("test_dianzi_") and parsed.username.startswith("test_")
    SECRETS.extend([parsed.render_as_string(hide_password=False), parsed.password or ""])
    run_id = ("r11_sbom_review_" if mode != "legacy" else "r11_inventory_review_") + datetime.now(
        ZoneInfo("Asia/Shanghai")
    ).strftime("%Y%m%d_%H%M%S")
    database = "test_dianzi_" + run_id
    assert re.fullmatch(
        r"test_dianzi_r11_(sbom_review|inventory_review)_[0-9]{8}_[0-9]{6}", database
    )
    start = now()
    admin = create_engine(parsed, isolation_level="AUTOCOMMIT", hide_parameters=True)
    with admin.connect() as connection:
        assert not connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": database}
        )
        connection.execute(text(f'CREATE DATABASE "{database}"'))
    admin.dispose()
    url = parsed.set(database=database, query={})
    dsn = url.render_as_string(hide_password=False)
    SECRETS.append(dsn)
    run_migrations(
        dsn, "0018_asset_inventory" if mode == "legacy" else "0019_aggregate_observations"
    )
    engine = create_engine(url, hide_parameters=True)
    with engine.begin() as connection:
        asset_snapshot_sbom_sidecars.create(connection)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == database
        version = connection.scalar(text("SHOW server_version"))
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
    engine.dispose()
    resource = RUN / "resources"
    resource.mkdir(exist_ok=True)
    source = (
        ROOT
        / "backend/tests/integration"
        / (
            "test_t24_asset_inventory.py"
            if mode == "legacy"
            else "test_r11_sbom_inventory_postgres.py"
        )
    )
    old_prefix = "r11_inventory_" if mode == "legacy" else "r11_sbom_inventory_"
    new_prefix = "r11_inventory_review_" if mode == "legacy" else "r11_sbom_review_"
    original_text = source.read_text(encoding="utf-8")
    copy_text = original_text.replace(
        'startswith("test_dianzi_' + old_prefix + '")',
        'startswith("test_dianzi_' + new_prefix + '")',
    )
    copy_text = copy_text.replace(
        'startswith("' + old_prefix + '")', 'startswith("' + new_prefix + '")'
    )
    assert copy_text != original_text
    copied = resource / source.name
    copied.write_text(copy_text, encoding="utf-8")
    (RUN / (mode + "_resource_guard.patch")).write_text(
        "".join(
            __import__("difflib").unified_diff(
                original_text.splitlines(True),
                copy_text.splitlines(True),
                fromfile=str(source),
                tofile=str(copied),
            )
        ),
        encoding="utf-8",
    )
    environment = {
        **os.environ,
        "TEST_DATABASE_URL": dsn,
        "DIANZI_TEST_RUN_ID": run_id,
        "PYTHONPATH": str(ROOT / "backend/src"),
        "DIANZI_ENV": "test",
    }
    receipt = {
        "mode": mode,
        "database": database,
        "start": start,
        "prepared": now(),
        "host": "127.0.0.1",
        "port": 25432,
        "server_version": version,
        "forward_revision": revision,
        "sidecar_action": "test_table_create_not_production_0022",
        "deletion": False,
        "resource_copy": str(copied),
        "guard_only": True,
    }
    (RUN / (mode + "_database.json")).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    tests = [str(RUN / "test_review_probes.py")] if mode == "probes" else [str(copied)]
    if mode == "compatibility":
        tests = [str(RUN / "test_review_compatibility.py")]
    if mode == "targeted":
        tests = [
            str(RUN / "test_digest_binding.py"),
            str(RUN / "test_review_probes.py"),
            "-k",
            "test_real_sbom_identity or test_10000_components",
        ]
    label = "pg_" + mode + ("_second" if mode == "probes" else "")
    return command(
        label,
        [
            str(PYTHON),
            str(__file__),
            "pytest_external",
            *tests,
            "--no-cov",
            "-q",
            f"--junitxml={RUN / (label + '.xml')}",
        ],
        environment=environment,
    )


def pytest_external(args):
    import pytest

    spec = importlib.util.spec_from_file_location(
        "shared_review_redaction", ROOT / "backend/tests/conftest.py"
    )
    plugin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin)
    return pytest.main(args, plugins=[plugin])


def cbm():
    for suffix, path in (("src", "/backend/src"), ("assets", "/backend/src/ai_intel/assets")):
        project = "r11-sbom-review1-" + suffix + "-20261016"
        prefix = ["wsl.exe", "-e", CBM, "cli", "--json"]
        code = command(
            "cbm_" + suffix + "_index",
            [
                *prefix,
                "index_repository",
                json.dumps(
                    {
                        "repo_path": "/mnt/d/wt/r11-sbom-inventory-review1" + path,
                        "name": project,
                        "mode": "fast",
                    }
                ),
            ],
            cwd=ROOT,
        )
        if code:
            return code
        for tool in ("get_graph_schema", "get_architecture"):
            code = command(
                "cbm_" + suffix + "_" + tool,
                [*prefix, tool, json.dumps({"project": project, "format": "json"})],
                cwd=ROOT,
            )
            if code:
                return code
        if suffix == "assets":
            for function in (
                "parse_manifest",
                "parse_inventory_input",
                "import_manifest",
                "get_snapshot_sbom",
            ):
                code = command(
                    "cbm_trace_" + function,
                    [
                        *prefix,
                        "trace_path",
                        json.dumps(
                            {
                                "project": project,
                                "function_name": function,
                                "direction": "both",
                                "depth": 3,
                            }
                        ),
                    ],
                    cwd=ROOT,
                )
                if code:
                    return code
    return 0


if __name__ == "__main__":
    mode, *args = sys.argv[1:]
    try:
        if mode in {"pure", "mypy", "ruff", "format"}:
            result = original(mode)
        elif mode in {"sbom", "legacy", "probes", "compatibility", "targeted"}:
            result = pg(mode)
        elif mode == "pytest_external":
            result = pytest_external(args)
        elif mode == "cbm":
            result = cbm()
        elif mode == "audit":
            result = command("audit_final", [str(PYTHON), str(RUN / "audit_evidence.py")])
        else:
            raise ValueError("unsupported review action")
    except Exception:
        failure = redact(traceback.format_exc())
        (RUN / (mode + "_runner_error.log")).write_text(failure, encoding="utf-8")
        print(failure)
        result = 1
    raise SystemExit(result)
