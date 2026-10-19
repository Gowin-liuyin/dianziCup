"""Independent review receipts, source audit, and resource-only copies of frozen tests."""

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

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PYTHON = Path("D:/dianzi/backend/.venv/Scripts/python.exe")
CODE = "f316a7aa432d6f730fa49189814c2559be8b6db4"
MATERIALS = "a43d25e64dd00eaec63521c9457c7fa2228b8799"
DATABASE = "test_dianzi_r12_review1_20261016"
AUTHOR_RUN = ROOT / "reports/runs/recovery_r12_hybrid_retrieval_20261016"
SECRET_SOURCE = "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"
PROJECT = "dianzi-r12-hybrid-review1-backend"


def stamp() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()


def git(*arguments: str) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def execute(name: str, arguments: list[str], *, cwd: Path | None = None) -> int:
    started, clock = stamp(), time.perf_counter()
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT / "backend/src"), str(ROOT / "backend"), str(ROOT))))
    result = subprocess.run(arguments, cwd=cwd or ROOT / "backend", env=env, capture_output=True)
    output = result.stdout + result.stderr
    if env.get("TEST_DATABASE_URL"):
        output = output.replace(env["TEST_DATABASE_URL"].encode(), b"[redacted test connection]")
    credentials = []
    for key in ("R12_OPENSEARCH_PASSWORD",):
        if env.get(key):
            credentials.append(env[key])
    if env.get("TEST_DATABASE_URL"):
        from sqlalchemy.engine import make_url

        credentials.append(make_url(env["TEST_DATABASE_URL"]).password or "")
    for credential in credentials:
        if credential:
            output = output.replace(credential.encode(), b"[redacted]")
            for offset in range(max(0, len(credential) - 7)):
                output = output.replace(credential[offset : offset + 8].encode(), b"[redacted-fragment]")
    (RUN / f"{name}.log").write_bytes(output)
    receipt = dict(argv=arguments, cwd=str(cwd or ROOT / "backend"), started_at=started, ended_at=stamp(), elapsed_seconds=time.perf_counter() - clock, exit_code=result.returncode, code_sha=CODE, materials_sha=MATERIALS, head=git("rev-parse", "HEAD").decode().strip(), log=f"{name}.log")
    (RUN / f"{name}.command.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"name": name, "exit_code": result.returncode, "elapsed_seconds": receipt["elapsed_seconds"]}))
    print(output.decode(errors="replace")[-1200:])
    return result.returncode


def audit() -> None:
    manifest_path = AUTHOR_RUN / "materials_manifest.json"
    assert sha(manifest_path.read_bytes()) == "34fd3a94edf158944f5217caa1a28cec83d9cf70c09e3f21b91d57199a718b40"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checked_sources = []
    for source in manifest["source_blobs"]:
        path = source["path"]
        blob = git("show", f"{CODE}:{path}")
        current = (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
        assert sha(blob) == source["git_blob_sha256"]
        assert current == blob and git("show", f"{MATERIALS}:{path}") == blob
        checked_sources.append(dict(path=path, git_blob=git("rev-parse", f"{CODE}:{path}").decode().strip(), sha256=sha(blob)))
    checked_materials = []
    for item in manifest["materials"]:
        path = item["path"]
        raw = (ROOT / path).read_bytes()
        committed = git("show", f"{MATERIALS}:{path}")
        assert sha(raw) == item["sha256"] or sha(raw.replace(b"\r\n", b"\n")) == item["lf_sha256"]
        assert committed.replace(b"\r\n", b"\n") == raw.replace(b"\r\n", b"\n")
        checked_materials.append(dict(path=path, raw_sha256=sha(raw), git_sha256=sha(committed)))
    raw_entries = [json.loads(line) for line in (AUTHOR_RUN / "synthetic_source_blobs/raw_manifest.jsonl").read_text().splitlines()]
    originals = set()
    for item in raw_entries:
        raw = (AUTHOR_RUN / "synthetic_source_blobs" / (item["sha256"] + ".txt")).read_bytes()
        assert len(raw) == item["size_bytes"] and sha(raw) == item["sha256"] and item["data_mode"] == "synthetic"
        originals.add(item["sha256"])
    receipt = dict(checked_at=stamp(), head=git("rev-parse", "HEAD").decode().strip(), code_sha=CODE, materials_sha=MATERIALS, author_manifest_sha256=sha(manifest_path.read_bytes()), source_blobs=checked_sources, submitted_materials=checked_materials, synthetic_manifest_entries=len(raw_entries), synthetic_distinct_originals=len(originals), status="passed")
    (RUN / "freeze_materials_audit.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"status": "passed", "source_blobs": len(checked_sources), "submitted_materials": len(checked_materials), "raw_entries": len(raw_entries), "originals": len(originals)}))


def resource_copy() -> None:
    target = RUN / "resource_copy"
    target.mkdir(exist_ok=True)
    original = ROOT / "backend/tests/integration/test_t30_hybrid_retrieval.py"
    raw = original.read_bytes()
    (target / "original_test_t30_hybrid_retrieval.py.txt").write_bytes(raw)
    copied = raw.decode().replace("test_dianzi_r12_hybrid_20261016", DATABASE).replace("test_r12_hybrid_", "test_r12_review1_").replace("dianzi_test_r12_", "dianzi_test_r12_review1_")
    (target / "test_t30_hybrid_retrieval.py").write_text(copied, encoding="utf-8", newline="")
    (target / "conftest.py").write_text('"""Reuse frozen resource guards and failure redaction without changing original tests."""\npytest_plugins = ("tests.conftest",)\n', encoding="utf-8")
    (RUN / "resource_copy_audit.json").write_text(json.dumps(dict(original_sha256=sha(raw), copy_sha256=sha(copied.encode()), replacements={"test_dianzi_r12_hybrid_20261016": DATABASE, "test_r12_hybrid_": "test_r12_review1_", "dianzi_test_r12_": "dianzi_test_r12_review1_"}, business_assertions="unchanged"), indent=2), encoding="utf-8")


def services() -> None:
    import psycopg
    from psycopg import sql
    from sqlalchemy.engine import make_url

    captured = subprocess.run(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat", SECRET_SOURCE], capture_output=True, timeout=15)
    if captured.returncode:
        raise RuntimeError("authorized_connection_reference_unavailable")
    connection = json.loads(captured.stdout)
    url = make_url(connection["TEST_DATABASE_URL"])
    if (url.host, url.port, url.database) != ("127.0.0.1", 25432, "test_dianzi_r01_20261014"):
        raise RuntimeError("authorized_connection_identity_mismatch")
    parameters = dict(host=url.host, port=url.port, user=url.username, password=url.password, connect_timeout=5, options="-c statement_timeout=15000 -c lock_timeout=5000")
    with psycopg.connect(dbname=url.database, **parameters) as pg:
        pg.autocommit = True
        if pg.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DATABASE,)).fetchone() is None:
            pg.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DATABASE)))
    with psycopg.connect(dbname=DATABASE, **parameters) as pg:
        pg.execute("CREATE EXTENSION IF NOT EXISTS vector")
        assert pg.execute("SELECT current_database(), current_user").fetchone() == (DATABASE, url.username)
        version = pg.execute("SHOW server_version").fetchone()[0]
        vector = pg.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0]
    os.environ["TEST_DATABASE_URL"] = url.set(database=DATABASE).render_as_string(hide_password=False)
    os.environ["DIANZI_TEST_RUN_ID"] = "r12_review1_20261016"
    os.environ["R05_SEMANTIC_CACHE"] = "C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime"
    os.environ["R12_EVIDENCE_DIR"] = str(RUN / "synthetic_source_blobs")
    os.environ["R12_OPENSEARCH_URL"] = "http://127.0.0.1:29200"
    prior = json.loads((AUTHOR_RUN / "resource_probe.json").read_text())
    assert prior["opensearch_status"] == 200 and prior["opensearch_version"] == "2.17.0"
    versions = {name: __import__("importlib.metadata", fromlist=["version"]).version(name) for name in ("sqlalchemy", "psycopg", "pgvector", "httpx", "onnxruntime", "tokenizers", "numpy", "pytest", "ruff", "mypy")}
    (RUN / "resource_identity.json").write_text(json.dumps(dict(checked_at=stamp(), database=DATABASE, postgres_version=version, pgvector_version=vector, opensearch_version="2.17.0", opensearch_version_source="frozen_author_probe_no_second_root_GET", packages=versions, python=sys.version, resource_reference=SECRET_SOURCE), indent=2), encoding="utf-8")


def main() -> int:
    mode = sys.argv[1]
    if mode == "audit":
        audit()
        resource_copy()
        return 0
    if mode == "cbm":
        assert (RUN / "freeze_materials_audit.json").exists()
        prefix = ["wsl", "--exec", "/usr/bin/env", "CBM_CACHE_DIR=/tmp/dianzi-cbm-r12-review1-20261016", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
        commands = [("cbm_index", ["index_repository", "--repo-path", "/mnt/d/wt/r12-hybrid-review1/backend/src", "--name", PROJECT, "--mode", "fast"]), ("cbm_schema", ["get_graph_schema", "--project", PROJECT]), ("cbm_architecture", ["get_architecture", "--project", PROJECT, "--path", "ai_intel/retrieval", "--aspects", "overview", "--format", "json"])]
        for method in ("hybrid.HybridRetriever.retrieve", "indexing.HybridIndexer.refresh_scope", "indexing.HybridIndexer.prepare_generation"):
            commands.append(("cbm_trace_" + method.split(".")[-1], ["trace_path", "--project", PROJECT, "--function-name", PROJECT + ".ai_intel.retrieval." + method, "--direction", "outbound", "--depth", "3", "--include-tests", "false", "--format", "json"]))
        codes = [execute(name, prefix + arguments, cwd=ROOT) for name, arguments in commands]
        codes.append(execute("rg_callers", ["rg", "-n", "HybridRetriever|HybridIndexer|facts_query|SemanticModels|scope_epoch|hybrid_metadata", "backend/src"], cwd=ROOT))
        return int(any(codes))
    if mode == "fixture":
        return execute("fixture_regression", [str(PYTHON), "-m", "pytest", "tests/unit/test_r12_hybrid.py", "tests/contract/test_r12_hybrid_contracts.py", "tests/security/test_r12_retrieval_boundaries.py", "tests/unit/test_r05_evidence_chunks.py", "tests/unit/test_r05_embedding_boundaries.py", "tests/contract/test_r05_semantic_contract.py", "-o", "addopts=", "-q", "--junitxml=" + str(RUN / "fixture_regression.xml")])
    if mode == "integration" or mode.startswith("negative") or mode == "legal_publication":
        services()
        target = RUN / "resource_copy" / ("test_t30_hybrid_retrieval.py" if mode == "integration" else "test_legal_publication_window.py" if mode == "legal_publication" else "test_review_negative.py")
        return execute(mode, [str(PYTHON), "-m", "pytest", str(target), "-o", "addopts=", "-q", "-s", "--tb=short", "--junitxml=" + str(RUN / (mode + ".xml"))])
    if mode == "command":
        return execute(sys.argv[2], [str(PYTHON), *sys.argv[3:]])
    raise ValueError("unknown review mode")


if __name__ == "__main__":
    raise SystemExit(main())
