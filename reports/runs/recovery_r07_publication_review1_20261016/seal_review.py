"""Seal reviewed code and independent evidence without changing business or progress files."""

import hashlib
import importlib.metadata
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

RAW = Path(__file__).resolve().parent
ROOT = RAW.parents[2]
REPORT = ROOT / "reports/reviews/recovery/G-C-R07-publication-review-1.md"


def git(*arguments):
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


summaries = {}
for xml in RAW.glob("*.xml"):
    suite = ElementTree.parse(xml).getroot().find("testsuite")
    summaries[xml.name] = {key: suite.get(key) for key in ("tests", "errors", "failures", "skipped", "time", "timestamp")}
    if xml.name == "full_pure_regression.xml":
        native = [{"classname": node.get("classname"), "name": node.get("name"), "passed": len(node) == 0, "seconds": node.get("time")} for node in suite.findall("testcase") if "native_cpu_guard" in node.get("classname", "")]
        (RAW / "strict_cpu_case_results.json").write_text(json.dumps(native, indent=2), encoding="utf-8")
(RAW / "test_results_summary.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")

tracked = git("ls-files", "backend/src", "backend/tests", "backend/uv.lock", "backend/pyproject.toml").splitlines()
code_files = [{"path": name, "sha256": hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), "git_object": git("rev-parse", "HEAD:" + name)} for name in tracked]
code = {"code_sha": git("rev-parse", "HEAD"), "code_tree": git("rev-parse", "HEAD^{tree}"),
    "base_sha": git("rev-parse", "cb340978"), "publication_base_sha": git("rev-parse", "23f5186^"),
    "scope": "Immutable backend source/tests and original lock; no production, holdout, report or secret indexing",
    "changed_from_base": git("diff", "--name-status", "cb340978...HEAD"),
    "changed_publication_only": git("diff", "--name-status", "23f5186^...HEAD"),
    "source_test_working_diff": git("diff", "--", "backend/src", "backend/tests"), "files": code_files}
(RAW / "frozen_code_manifest.json").write_text(json.dumps(code, ensure_ascii=False, indent=2), encoding="utf-8")
(RAW / "runtime_versions.json").write_text(json.dumps({"python": sys.version, "executable": sys.executable,
    "packages": {name: importlib.metadata.version(name) for name in ("pytest", "pytest-cov", "sqlalchemy", "psycopg", "pydantic", "ruff", "mypy")},
    "lock_sha256": hashlib.sha256((ROOT / "backend/uv.lock").read_bytes()).hexdigest()}, indent=2), encoding="utf-8")

private = json.loads(subprocess.run(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"], capture_output=True, text=True, check=True).stdout)
secrets = [private[key] for key in ("postgres_password", "redis_password", "TEST_DATABASE_URL", "TEST_REDIS_URL") if private.get(key)]
targets = [path for path in RAW.iterdir() if path.is_file() and path.name != "evidence_manifest.json"]
if REPORT.exists():
    targets.append(REPORT)
for path in targets:
    body = path.read_bytes()
    if any(value.encode() in body for value in secrets):
        raise RuntimeError("Private connection material was found in evidence; do not publish")
manifest = {"recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "review_status": "needs_changes",
    "code_sha": code["code_sha"], "code_tree": code["code_tree"], "business_source_and_tests_unmodified": code["source_test_working_diff"] == "",
    "private_values_scan": "passed", "files": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "size_bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(targets)]}
(RAW / "evidence_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"code_sha": code["code_sha"], "code_tree": code["code_tree"], "raw_file_count": len(targets), "source_and_test_files": len(code_files), "private_values_scan": "passed", "test_results": summaries}, indent=2))
