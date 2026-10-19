"""新冻结版独立检查；仅独占测试库、资源副本及审查材料，日志写前脱敏。"""

import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PYTHON = ROOT / "backend/.venv/Scripts/python.exe"
OLD_RUN = Path(
    "D:/wt/r11-sbom-inventory-review1/reports/runs/recovery_r11_sbom_inventory_review1_20261016"
)
AUTHOR_OLD = ROOT / "reports/runs/recovery_r11_sbom_inventory_20261016"
SECRETS = []


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def load_private_literals():
    paths = [
        ROOT / "backend/tests/unit/test_r11_sbom_inventory_uri_privacy.py",
        ROOT / "backend/tests/integration/test_r11_sbom_inventory_uri_privacy.py",
        ROOT / "backend/tests/unit/test_r11_sbom_inventory_uri_privacy_followup.py",
        ROOT / "backend/tests/integration/test_r11_sbom_inventory_uri_privacy_followup.py",
    ]
    paths += list(RUN.glob("test_*.py"))
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value
                if len(value) >= 8 and (
                    "://" in value
                    or any(
                        word in value
                        for word in ("synthetic_password", "synthetic-password", "C:/private")
                    )
                ):
                    SECRETS.extend((value, unquote(value)))
    SECRETS.extend(("synthetic_password", "synthetic-password"))


def redact(value):
    for secret in sorted(set(SECRETS), key=len, reverse=True):
        if secret:
            value = value.replace(secret, "[redacted review value]")
    value = re.sub(
        r"postgresql(?:\+[A-Za-z0-9_]+)?://[^\s\"'<>\\]+", "[redacted test connection]", value
    )
    return value


def command(name, argv, *, cwd=None, environment=None):
    started = now()
    result = subprocess.run(
        argv,
        cwd=cwd or ROOT / "backend",
        env={**(environment or os.environ), "PYTHONIOENCODING": "utf-8"},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = redact(result.stdout.decode("utf-8", errors="replace"))
    (RUN / (name + ".log")).write_bytes(output.encode())
    receipt = {
        "name": name,
        "argv": argv,
        "cwd": str(cwd or ROOT / "backend"),
        "start": started,
        "end": now(),
        "exit_code": result.returncode,
        "log": name + ".log",
    }
    with (RUN / "commands.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    print(json.dumps(receipt, ensure_ascii=False), flush=True)
    print(output[-1800:], flush=True)
    return result.returncode


def approved_url():
    from sqlalchemy.engine import make_url

    try:
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
            timeout=12,
        )
        configuration = json.loads(result.stdout)
        source = "approved_wsl_reference"
    except (subprocess.SubprocessError, json.JSONDecodeError):
        code = (
            "$secured = ConvertTo-SecureString (Get-Content -Raw -LiteralPath "
            "'D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi'); "
            "ConvertFrom-SecureString -SecureString $secured -AsPlainText"
        )
        result = subprocess.run(
            ["pwsh.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", code],
            capture_output=True,
            check=True,
            timeout=15,
        )
        configuration = json.loads(result.stdout.decode("utf-8-sig"))
        source = "approved_test_reference_dpapi"
    url = make_url(configuration["TEST_DATABASE_URL"])
    assert url.host in {"127.0.0.1", "localhost"} and url.port == 25432
    assert url.database.startswith("test_dianzi_") and url.username.startswith("test_")
    SECRETS.extend(
        (
            url.render_as_string(hide_password=False),
            url.render_as_string(hide_password=True),
            url.password or "",
        )
    )
    return url, source


def prepare_copies():
    import difflib
    import hashlib

    resource = RUN / "resources"
    resource.mkdir(exist_ok=True)
    proofs = []
    for name in (
        "test_r11_sbom_inventory_postgres.py",
        "test_t24_asset_inventory.py",
        "test_r11_sbom_inventory_uri_privacy.py",
    ):
        path = ROOT / "backend/tests/integration" / name
        original = path.read_text(encoding="utf-8")
        changed = original
        if name != "test_r11_sbom_inventory_uri_privacy.py":
            old_prefix = (
                "r11_inventory_" if name == "test_t24_asset_inventory.py" else "r11_sbom_inventory_"
            )
            new_prefix = (
                "r11_inventory_review_fix1_"
                if name == "test_t24_asset_inventory.py"
                else "r11_sbom_review_fix1_"
            )
            changed = changed.replace(
                'startswith("test_dianzi_' + old_prefix + '")',
                'startswith("test_dianzi_' + new_prefix + '")',
            )
            changed = changed.replace(
                'startswith("' + old_prefix + '")', 'startswith("' + new_prefix + '")'
            )
        else:
            changed = changed.replace(
                "from tests.integration.test_r11_sbom_inventory_postgres",
                "from review_sbom_resource",
            )
        target = resource / name
        target.write_bytes(changed.encode())
        (RUN / (name + ".resource.patch")).write_text(
            "".join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True))),
            encoding="utf-8",
        )
        proofs.append(
            {
                "source": str(path),
                "copy": str(target),
                "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "copy_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "change": "resource_guards_or_fixture_import_only",
            }
        )
    for name in ("test_review_probes.py", "test_review_compatibility.py", "test_digest_binding.py"):
        original = (OLD_RUN / name).read_bytes()
        (RUN / name).write_bytes(original)
        proofs.append(
            {
                "source": str(OLD_RUN / name),
                "copy": str(RUN / name),
                "unchanged_bytes": True,
                "sha256": hashlib.sha256(original).hexdigest(),
            }
        )
    (RUN / "resource_copy_proof.json").write_text(json.dumps(proofs, indent=2), encoding="utf-8")


def pg(mode):
    from sqlalchemy import create_engine, text

    from ai_intel.assets.sbom_persistence_models import asset_snapshot_sbom_sidecars
    from ai_intel.infrastructure.database import run_migrations

    url, source = approved_url()
    prefix = "r11_inventory_review_fix1_" if mode == "legacyfinal" else "r11_sbom_review_fix1_"
    database_mode = {"legacyfinal": "lf", "sbomfinal": "sf", "oldfinal": "of", "newfinal": "nf", "edgesfinal": "ef", "edgescorrected": "ec"}[mode]
    run_id = prefix + database_mode + "_" + datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d_%H%M%S")
    database = "test_dianzi_" + run_id
    assert len(database) <= 63
    assert re.fullmatch(
        r"test_dianzi_r11_(inventory|sbom)_review_fix1_[a-z]+_[0-9]{8}_[0-9]{6}", database
    )
    started = now()
    admin = create_engine(url, isolation_level="AUTOCOMMIT", hide_parameters=True)
    with admin.connect() as connection:
        assert not connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": database}
        )
        connection.execute(text(f'CREATE DATABASE "{database}"'))
    admin.dispose()
    target = url.set(database=database, query={})
    dsn = target.render_as_string(hide_password=False)
    SECRETS.extend((dsn, target.render_as_string(hide_password=True)))
    run_migrations(
        dsn, "0018_asset_inventory" if mode == "legacyfinal" else "0019_aggregate_observations"
    )
    engine = create_engine(target, hide_parameters=True)
    with engine.begin() as connection:
        asset_snapshot_sbom_sidecars.create(connection)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == database
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        version = connection.scalar(text("SHOW server_version"))
    engine.dispose()
    receipt = {
        "mode": mode,
        "database": database,
        "resource": source,
        "start": started,
        "prepared": now(),
        "forward_revision": revision,
        "postgres_version": version,
        "sidecar_action": "test_table_create_not_production_0022",
        "drop_or_downgrade": False,
    }
    (RUN / (mode + "_database.json")).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    resource = RUN / "resources"
    files = {
        "sbomfinal": [
            str(resource / "test_r11_sbom_inventory_postgres.py"),
            str(resource / "test_r11_sbom_inventory_uri_privacy.py"),
            str(resource / "test_r11_sbom_inventory_uri_privacy_followup.py"),
        ],
        "legacyfinal": [str(resource / "test_t24_asset_inventory.py")],
        "oldfinal": [
            str(RUN / "test_review_probes.py"),
            str(RUN / "test_review_compatibility.py"),
            str(RUN / "test_digest_binding.py"),
        ],
        "newfinal": [str(RUN / "test_fix1_probes.py")],
        "edgesfinal": [str(RUN / "test_final_edges.py")],
        "edgescorrected": [str(RUN / "test_final_edges.py"), "-k", "test_duplicate_graph"],
    }
    environment = {
        **os.environ,
        "TEST_DATABASE_URL": dsn,
        "DIANZI_TEST_RUN_ID": run_id,
        "DIANZI_ENV": "test",
        "PYTHONPATH": str(ROOT / "backend/src"),
    }
    return command(
        "pg_" + mode,
        [
            str(PYTHON),
            str(__file__),
            "external",
            *files[mode],
            "--no-cov",
            "-q",
            f"--junitxml={RUN / ('pg_' + mode + '.xml')}",
        ],
        environment=environment,
    )


def external(args):
    import pytest
    from sqlalchemy.engine import make_url

    spec = importlib.util.spec_from_file_location(
        "shared_review_redaction", ROOT / "backend/tests/conftest.py"
    )
    shared = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shared)
    url = make_url(os.environ["TEST_DATABASE_URL"])
    SECRETS.extend(
        (
            url.render_as_string(hide_password=False),
            url.render_as_string(hide_password=True),
            url.password or "",
        )
    )
    load_private_literals()
    resource_spec = importlib.util.spec_from_file_location(
        "review_sbom_resource", RUN / "resources/test_r11_sbom_inventory_postgres.py"
    )
    resource = importlib.util.module_from_spec(resource_spec)
    sys.modules["review_sbom_resource"] = resource
    resource_spec.loader.exec_module(resource)
    privacy_spec = importlib.util.spec_from_file_location(
        "review_privacy_resource", RUN / "resources/test_r11_sbom_inventory_uri_privacy.py"
    )
    privacy_resource = importlib.util.module_from_spec(privacy_spec)
    sys.modules["review_privacy_resource"] = privacy_resource
    privacy_spec.loader.exec_module(privacy_resource)
    original_redaction = shared.redact_test_connection_output

    def enhanced_redaction(output, dynamic_credentials=()):
        return redact(original_redaction(output, dynamic_credentials))

    shared.redact_test_connection_output = enhanced_redaction
    return pytest.main(args, plugins=[shared])


def pure():
    entries = [
        json.loads(line) for line in (AUTHOR_OLD / "commands.jsonl").read_text().splitlines()
    ]
    original = next(item for item in entries if item["name"] == "pure_final")["argv"][1:]
    arguments = [value for value in original if not value.startswith("--junitxml=")]
    arguments += [
        "tests/unit/test_r11_sbom_inventory_uri_privacy.py",
        "tests/unit/test_r11_sbom_inventory_uri_privacy_followup.py",
        f"--junitxml={RUN / 'pure_final.xml'}",
    ]
    return command("pure_final", [str(PYTHON), *arguments])


def cbm():
    prefix = [
        "wsl.exe",
        "-e",
        "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp",
        "cli",
        "--json",
    ]
    for suffix, path in (("src", "backend/src"), ("assets", "backend/src/ai_intel/assets")):
        project = "r11-sbom-review1-fix1-final-" + suffix + "-20261016"
        code = command(
            "cbm_final_" + suffix + "_index",
            [
                *prefix,
                "index_repository",
                json.dumps(
                    {
                        "repo_path": "/mnt/d/wt/r11-sbom-inventory-review1-fix1/" + path,
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
            command(
                "cbm_final_" + suffix + "_" + tool,
                [*prefix, tool, json.dumps({"project": project, "format": "json"})],
                cwd=ROOT,
            )
        if suffix == "assets":
            for function in (
                "get_snapshot",
                "read_asset",
                "list_assets",
                "list_snapshots",
                "get_snapshot_sbom",
                "import_manifest",
                "safe_sbom_sidecar",
                "safe_sbom_snapshot",
            ):
                command(
                    "cbm_final_trace_" + function,
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
    return 0


if __name__ == "__main__":
    load_private_literals()
    try:
        mode, *arguments = sys.argv[1:]
        if mode == "prepare":
            prepare_copies()
            result = 0
        elif mode == "pure":
            result = pure()
        elif mode == "cbm":
            result = cbm()
        elif mode == "external":
            result = external(arguments)
        elif mode in {"sbomfinal", "legacyfinal", "oldfinal", "newfinal", "edgesfinal", "edgescorrected"}:
            result = pg(mode)
        else:
            raise ValueError("unsupported review mode")
    except Exception:
        error = redact(traceback.format_exc())
        (RUN / (mode + "_runner_error.log")).write_bytes(error.encode())
        print(error)
        result = 1
    raise SystemExit(result)
