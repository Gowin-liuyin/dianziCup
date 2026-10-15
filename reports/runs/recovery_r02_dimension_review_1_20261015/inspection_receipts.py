"""Keep source scope, cross-checks, test totals, and an artifact inventory without secret material."""

from pathlib import Path
import datetime as dt
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlsplit

ARTIFACTS = Path(__file__).resolve().parent
WORKTREE = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r02-dimensions-review\dianzi")
ZONE = dt.timezone(dt.timedelta(hours=8))
def now():
    return dt.datetime.now(ZONE).isoformat(timespec="seconds")

commands = [
    ("git_scope", ["git", "status", "--short"]),
    ("candidate_sha", ["git", "rev-parse", "HEAD"]),
    ("candidate_tree", ["git", "rev-parse", "HEAD^{tree}"]),
    ("base_sha", ["git", "rev-parse", "2be32ba"]),
    ("diff_stat", ["git", "diff", "--stat", "2be32ba", "a366c4e"]),
    ("diff_check", ["git", "diff", "--check", "2be32ba", "a366c4e"]),
    ("public_contract_unchanged", ["git", "diff", "--exit-code", "2be32ba", "a366c4e", "--",
                                    "backend/src/ai_intel/domain/enums.py", "contracts/schemas/public_api_v2.json",
                                    "contracts/task_manifest.json", "backend/pyproject.toml", "backend/uv.lock"]),
    ("rg_callers", ["rg", "-n", "DimensionRepository|DimensionSubmission|enrichment_results",
                      "backend/src", "backend/tests"]),
    ("rg_gateway_fact_calls", ["rg", "-n", "find_prior_publication|save_change_publication|knowledge_scope_key|publication_payload_digest",
                                 "backend/src/ai_intel/knowledge/persistence.py",
                                 "backend/src/ai_intel/enrichment/persistence.py",
                                 "backend/src/ai_intel/knowledge/event_linking.py"]),
]
for name, command in commands:
    start = now()
    result = subprocess.run(command, cwd=WORKTREE, capture_output=True, text=True, encoding="utf-8", errors="replace")
    (ARTIFACTS / (name + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
    (ARTIFACTS / (name + ".command.json")).write_text(json.dumps(
        {"start": start, "end": now(), "cwd": str(WORKTREE), "command": command,
         "exit_code": result.returncode}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(name, result.returncode)

files = subprocess.run(["git", "diff", "--name-only", "2be32ba", "a366c4e"], cwd=WORKTREE,
                       capture_output=True, text=True, check=True).stdout.splitlines()
source_files = [{"path": filename, "sha256": hashlib.sha256((WORKTREE / filename).read_bytes()).hexdigest(),
                 "size_bytes": (WORKTREE / filename).stat().st_size} for filename in files]
(ARTIFACTS / "candidate_files.json").write_text(json.dumps(source_files, indent=2), encoding="utf-8")
totals = {}
for filename in ("unit.xml", "pg.xml", "negative.xml", "negative_final.xml"):
    suites = ET.parse(ARTIFACTS / filename).getroot().findall("testsuite")
    totals[filename] = {field: sum(int(suite.attrib.get(field, 0)) for suite in suites)
                        for field in ("tests", "failures", "errors", "skipped")}
(ARTIFACTS / "test_totals.json").write_text(json.dumps(totals, indent=2), encoding="utf-8")
connection = json.loads(subprocess.run(["wsl", "-u", "root", "--", "cat",
    "/tmp/dianzi-r02_dimensions_20261015/connection.json"], capture_output=True, text=True, check=True).stdout)
connection_url = connection["TEST_DATABASE_URL"]
password = unquote(urlsplit(connection_url).password or "")
issues = []
for file in ARTIFACTS.iterdir():
    if file.is_file():
        content = file.read_bytes()
        if any(secret and secret.encode() in content for secret in (connection_url, password)):
            issues.append(file.name)
(ARTIFACTS / "secret_scan.json").write_text(json.dumps({"checked_at": now(), "matches": issues,
    "method": "exact current test DSN and decoded password bytes; values never emitted"}, indent=2), encoding="utf-8")
if issues:
    raise RuntimeError("secret artifact scan found matches")
manifest = [{"path": file.name, "size_bytes": file.stat().st_size,
             "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
            for file in sorted(ARTIFACTS.iterdir()) if file.is_file() and file.name != "artifact_manifest.json"]
(ARTIFACTS / "artifact_manifest.json").write_text(json.dumps({"generated_at": now(), "files": manifest},
    ensure_ascii=False, indent=2), encoding="utf-8")
print("totals", totals, "artifact_files", len(manifest), "secret_matches", len(issues))
