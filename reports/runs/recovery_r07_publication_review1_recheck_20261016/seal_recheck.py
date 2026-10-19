"""Seal exact reviewed blobs and directed evidence with a separate manifest hash."""

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
REPORT = ROOT / "reports/reviews/recovery/G-C-R07-publication-review-1-recheck.md"


def git(*arguments):
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, check=True).stdout.decode().strip()


summaries = {}
for path in RAW.glob("*.xml"):
    suite = ElementTree.parse(path).getroot().find("testsuite")
    summaries[path.name] = {key: suite.get(key) for key in ("tests", "failures", "errors", "skipped", "time", "timestamp")}
(RAW / "test_results_summary.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")
objects = {}
for line in git("ls-tree", "-r", "HEAD", "--", "backend/src", "backend/tests", "backend/uv.lock", "backend/pyproject.toml").splitlines():
    header, path = line.split("\t", 1)
    objects[path] = header.split()[2]
code = {"code_sha": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}"),
    "first_review_sha": "71e594cb958bd93d21fb7ed66574b3cba4cc47e1", "working_diff": git("diff", "--", "backend/src", "backend/tests"),
    "files": [{"path": path, "git_blob": blob, "sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest()} for path, blob in objects.items()]}
(RAW / "frozen_code_manifest.json").write_text(json.dumps(code, indent=2), encoding="utf-8")
(RAW / "runtime_versions.json").write_text(json.dumps({"python": sys.version, "executable": sys.executable,
    "packages": {name: importlib.metadata.version(name) for name in ("pytest", "pytest-cov", "pydantic", "psycopg", "sqlalchemy", "ruff", "mypy")},
    "lock_sha256": hashlib.sha256((ROOT / "backend/uv.lock").read_bytes()).hexdigest()}, indent=2), encoding="utf-8")
secret = json.loads(subprocess.run(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"], capture_output=True, text=True, check=True).stdout)
private_values = [secret.get(key, "") for key in ("postgres_password", "redis_password", "TEST_DATABASE_URL", "TEST_REDIS_URL")]
paths = [path for path in RAW.iterdir() if path.is_file() and path.name not in {"evidence_manifest.json", "evidence_manifest.sha256"}]
paths.append(REPORT)
for path in paths:
    content = path.read_bytes()
    if any(value and value.encode() in content for value in private_values):
        raise RuntimeError("Private connection value found in review artifact")
manifest = {"sealed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "code_sha": code["code_sha"], "tree": code["tree"],
    "review_result": "Ship: publication service slice only", "source_and_tests_unmodified": not code["working_diff"], "private_value_scan": "passed",
    "test_results": summaries, "artifacts": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(paths)]}
target = RAW / "evidence_manifest.json"
target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
digest = hashlib.sha256(target.read_bytes()).hexdigest()
(RAW / "evidence_manifest.sha256").write_text(digest + "  evidence_manifest.json\n", encoding="utf-8")
print(json.dumps({"code_sha": code["code_sha"], "tree": code["tree"], "artifact_count": len(paths), "source_test_lock_count": len(objects), "private_value_scan": "passed", "manifest_sha256": digest, "report_sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest()}))
