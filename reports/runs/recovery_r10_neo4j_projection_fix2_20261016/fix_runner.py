"""Independent frozen review runner; decrypt resource references only in memory."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PYTHON = Path("D:/dianzi/backend/.venv/Scripts/python.exe")
PWSH = Path("C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe")
DATABASE = "test_dianzi_r10_projection_fix2_20261016"
RUN_ID = "r10_projection_fix2_20261016"
MARKER = "dianzi:r10_projection_fix2_20261016:owned-test-only"
CODE = "9a6c8d66aaf163321c0d19339aa92637e31bcd31"
TIP = "28a35f16ad1ebe08a49b63126b2c6fc828607333"
BASE = "b502b7ea4a2ffdeca24b8edc7fa8a33cc0980457"
ZONE = timezone(timedelta(hours=8))


def now():
    return datetime.now(ZONE).isoformat()


def decrypt(path):
    assert path in (
        "D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi",
        "D:/dianzi-private/r10-neo4j-test-20261016.dpapi",
    )
    fields = (
        "TEST_DATABASE_URL" if "test-runtime-resource-reference" in path else
        "NEO4J_TEST_BOLT_URL,NEO4J_TEST_USERNAME,NEO4J_TEST_PASSWORD,resource_id,deadline"
    )
    result = subprocess.run(
        [str(PWSH), "-NoProfile", "-NonInteractive", "-Command",
         "$ErrorActionPreference='Stop'; $reviewProtected=Get-Content -LiteralPath '" + path +
         "' -Raw; $reviewValue=($reviewProtected.Trim() | ConvertTo-SecureString | "
         "ConvertFrom-SecureString -AsPlainText | ConvertFrom-Json); "
         "[Console]::Write(($reviewValue | Select-Object " + fields + " | ConvertTo-Json -Compress))"],
        capture_output=True, text=True, encoding="utf-8", timeout=20, check=False,
    )
    if result.returncode:
        raise RuntimeError("private reference decryption failed")
    return json.loads(result.stdout)


def resources():
    pg = decrypt("D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi")
    neo = decrypt("D:/dianzi-private/r10-neo4j-test-20261016.dpapi")
    url = make_url(pg["TEST_DATABASE_URL"])
    assert url.host == "127.0.0.1" and url.port == 25432
    assert url.database == "test_dianzi_r01_20261014"
    assert url.username and url.username.startswith("test_")
    assert neo["NEO4J_TEST_BOLT_URL"] == "bolt://127.0.0.1:27687"
    assert neo["resource_id"] == "dianzi-r10-neo4j-test-20261016"
    assert neo["deadline"] == "2026-10-16T19:35:43.312788+08:00"
    assert datetime.fromisoformat(neo["deadline"]) > datetime.now(UTC)
    return url, neo


def prepare_pg(url):
    engine = create_engine(url, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            actual = connection.execute(text("SELECT current_database(),current_user")).one()
            assert actual == (url.database, url.username)
            row = connection.execute(text(
                "SELECT pg_get_userbyid(datdba), shobj_description(oid,'pg_database') "
                "FROM pg_database WHERE datname=:name"), {"name": DATABASE}).first()
            if row is None:
                connection.execute(text('CREATE DATABASE "test_dianzi_r10_projection_fix2_20261016"'))
                connection.execute(text(
                    "COMMENT ON DATABASE test_dianzi_r10_projection_fix2_20261016 "
                    "IS 'dianzi:r10_projection_fix2_20261016:owned-test-only'"))
            else:
                assert row == (url.username, MARKER)
    finally:
        engine.dispose()
    return url.set(database=DATABASE).render_as_string(hide_password=False)


def adapt_fixtures():
    adapted = RUN / "adapted_tests"
    adapted.mkdir(exist_ok=True)
    changes = {}
    for name in ("test_r10_projection_pg.py", "test_r10_neo4j_projection.py", "test_r10_projection_fix1_markers.py"):
        original = ROOT / "backend/tests/integration" / name
        value = original.read_text(encoding="utf-8")
        replacements = {
            "test_dianzi_r10_projection_20261016": DATABASE,
            "dianzi:r10_projection_20261016:owned-test-only": MARKER,
            '"test_r10_projection_"': '"test_r10fix2_"',
            '"r10-real-"': '"r10_fix2_"',
            '"r10_fix1_"': '"r10_fix2_"',
        }
        applied = {old: new for old, new in replacements.items() if old in value}
        for old, new in applied.items():
            value = value.replace(old, new)
        (adapted / name).write_text(value, encoding="utf-8", newline="\n")
        changes[name] = {"original_blob": git("rev-parse", TIP + ":backend/tests/integration/" + name).strip(),
                         "replacements": applied}
    source = ROOT / "backend/tests/conftest.py"
    hook = source.read_text(encoding="utf-8").replace(
        "PROJECT_ROOT = Path(__file__).resolve().parents[2]", "PROJECT_ROOT = Path(" + repr(str(ROOT)) + ")")
    hook += '\n@pytest.fixture(autouse=True)\ndef review_register_resources(register_sensitive_failure_value):\n    register_sensitive_failure_value(SecretStr(unquote(urlsplit(os.environ["TEST_DATABASE_URL"]).password or "")))\n'
    hook += '    register_sensitive_failure_value(SecretStr(os.environ["TEST_DATABASE_URL"]))\n'
    (adapted / "conftest.py").write_text(hook, encoding="utf-8", newline="\n")
    (RUN / "fixture_adaptations.json").write_text(json.dumps(changes, indent=2), encoding="utf-8")
    probe = RUN / "original_review_probes.py"
    archive_path = RUN / "raw_evidence.zip"
    if archive_path.is_file():
        with zipfile.ZipFile(archive_path) as archive:
            raw = archive.read(probe.relative_to(ROOT).as_posix())
    else:
        raw = probe.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "6d8565c06cb64bd8bacbdb8aff81dfc3908842088cd0eec17094dc835b959cf1"
    (adapted / "test_review_boundaries.py").write_bytes(raw.replace(b"r10_review1_", b"r10_fix2_"))
    probe = RUN / "original_epoch_probe.py"
    if archive_path.is_file():
        with zipfile.ZipFile(archive_path) as archive:
            raw = archive.read(probe.relative_to(ROOT).as_posix())
    else:
        raw = probe.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "3e1e767d7c01ee18b02888c56509676dfa020c5b79d8a8506b7afc216b83ae09"
    (adapted / "test_recheck_epoch_boundary.py").write_bytes(raw.replace(b"r10_review1_fix1_", b"r10_fix2_"))
    return adapted


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8", timeout=30, check=True)
    return result.stdout


def receipt(name, command, cwd, environment, timeout=180, sensitive=()):
    start = now()
    input_hashes = {}
    for argument in command:
        path = Path(argument)
        if not path.is_absolute():
            path = cwd / path
        if path.is_file():
            input_hashes[str(path.resolve())] = hashlib.sha256(path.read_bytes()).hexdigest()
    timer = time.monotonic()
    result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True,
                            text=True, encoding="utf-8", timeout=timeout, check=False)
    output = result.stdout + result.stderr
    for value in sensitive:
        if value:
            output = output.replace(value, "[redacted resource value]")
    (RUN / (name + ".log")).write_text(output, encoding="utf-8", newline="\n")
    record = {"argv": command, "cwd": str(cwd), "started_at": start, "finished_at": now(),
              "exit_code": result.returncode, "elapsed_seconds": time.monotonic() - timer,
              "code_sha": CODE, "materials_sha": TIP, "base_sha": BASE,
              "data_mode": "isolated_synthetic", "log": name + ".log",
              "input_file_sha256": input_hashes,
              "output_sha256": hashlib.sha256(output.encode()).hexdigest()}
    record["source_head"] = git("rev-parse", "HEAD").strip()
    record["source_file_sha256"] = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in ("backend/src/ai_intel/knowledge/graph_projection.py",
                     "backend/src/ai_intel/knowledge/graph_projection_models.py",
                     "backend/src/ai_intel/infrastructure/neo4j_projection.py")
    }
    (RUN / (name + ".json")).write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps({"name": name, "exit_code": result.returncode}))
    print(output[-2200:])
    return result.returncode


def verify_delivery():
    paths = git("diff", "--name-only", BASE, TIP).splitlines()
    assert git("diff", "--name-only", CODE, TIP).splitlines() == [
        "reports/runs/recovery_r10_neo4j_projection_20261016/code_commit_receipt.json"]
    record = json.loads((ROOT / "reports/runs/recovery_r10_neo4j_projection_20261016/code_commit_receipt.json").read_text())
    blobs = {}
    for path in record["business_source_paths"]:
        blob = git("rev-parse", TIP + ":" + path).strip()
        assert blob == record["business_source_git_blobs"][path]
        raw = (ROOT / path).read_bytes()
        normalized = raw.replace(b"\r\n", b"\n")
        disk_blob = hashlib.sha1(b"blob " + str(len(normalized)).encode() + b"\0" + normalized).hexdigest()
        assert disk_blob == blob
        blobs[path] = {"blob": blob, "raw_sha256": hashlib.sha256(raw).hexdigest(),
                       "git_lf_sha256": hashlib.sha256(normalized).hexdigest(), "disk_lf_git_blob": disk_blob}
    manifest_path = ROOT / "reports/runs/recovery_r10_neo4j_design_20261016/raw_evidence_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    archive = manifest_path.parent / manifest["archive"]
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest["archive_sha256"]
    with zipfile.ZipFile(archive) as opened:
        for entry in manifest["archive_files"]:
            value = opened.read(entry["path"])
            assert hashlib.sha256(value).hexdigest() == entry["sha256"]
            assert len(value) == entry["length_bytes"]
    allowed = set(record["diff_paths"]) | {"reports/runs/recovery_r10_neo4j_projection_20261016/code_commit_receipt.json"}
    assert set(paths) == allowed
    historical = [path for path in paths if path.startswith("reports/runs/recovery_r10_neo4j_design_20261016/")
                  or path in ("docs/design/recovery/R10-neo4j-projection-proposal.md", "reports/tasks/R10-neo4j-design.md")]
    for path in historical:
        assert git("rev-parse", "d274018abf2791733d7e9e278aa9ae553cb173e0:" + path).strip() == git("rev-parse", TIP + ":" + path).strip()
    value = {"observed_at": now(), "code_sha": CODE, "materials_sha": TIP,
             "base_sha": BASE, "changed_paths": paths, "source_blobs": blobs,
             "historical_archive_hash_passed": True, "archive_member_count": len(manifest["archive_files"]),
             "historical_design_exact_blob_count": len(historical),
             "business_unchanged_since_code_sha": True}
    (RUN / "frozen_delivery_verification.json").write_text(json.dumps(value, indent=2), encoding="utf-8")
    print(json.dumps({"delivery_verified": True, "changed_files": len(paths)}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.name == "verify_delivery":
        verify_delivery()
        return 0
    environment = dict(os.environ)
    adapted = adapt_fixtures()
    environment["PYTHONPATH"] = os.pathsep.join(str(path) for path in (
        adapted, RUN, ROOT / "backend/src", ROOT,
        ROOT / "backend/tests/integration", ROOT / "backend/tests/unit",
        ROOT / "backend/tests/contract", ROOT / "backend/tests/security"))
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["RUFF_CACHE_DIR"] = "C:/Users/yinha/AppData/Local/Temp/dianzi-r10-fix2-ruff"
    environment["COVERAGE_FILE"] = "C:/Users/yinha/AppData/Local/Temp/dianzi-r10-fix2-coverage"
    sensitive = []
    if args.name.startswith(("pg", "neo", "regression", "probes", "secret")):
        url, neo = resources()
        environment["TEST_DATABASE_URL"] = prepare_pg(url)
        environment["DIANZI_TEST_RUN_ID"] = RUN_ID
        sensitive = [environment["TEST_DATABASE_URL"], url.render_as_string(hide_password=False),
                     url.password, neo["NEO4J_TEST_PASSWORD"], neo["NEO4J_TEST_USERNAME"]]
    code = receipt(args.name, [str(PYTHON), "-B", *args.arguments], ROOT / "backend", environment,
                   sensitive=sensitive)
    if sensitive:
        findings = []
        for path in RUN.rglob("*"):
            if path.is_file():
                raw = path.read_bytes()
                for value in sensitive:
                    if value and len(value) >= 8 and value.encode() in raw:
                        findings.append(path.relative_to(RUN).as_posix())
        scan = {"observed_at": now(), "scanned_directory": str(RUN),
                "actual_value_leak_count": len(findings), "paths": sorted(set(findings))}
        (RUN / (args.name + "_secret_scan.json")).write_text(json.dumps(scan, indent=2), encoding="utf-8")
        assert not findings, "actual private resource value detected in review artifacts"
    return code


if __name__ == "__main__":
    raise SystemExit(main())
