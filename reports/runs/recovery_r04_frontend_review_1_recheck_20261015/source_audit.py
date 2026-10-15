"""Record fixed source, test identity and dependency boundaries for this review."""

import base64
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
WORKTREE = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r04-frontend-recheck\dianzi")
CANDIDATE = "7f9b6f14e3c7c5ff451fab183f959a11d8daf114"


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=WORKTREE)


package_pair = {}
for relative in ["frontend/package.json", "frontend/package-lock.json"]:
    current = git("show", f"{CANDIDATE}:{relative}")
    security = git("show", f"497740a771e7cb2d719ab22ebad34bd30539e20d:{relative}")
    package_pair[relative] = {"candidate_sha256": hashlib.sha256(current).hexdigest(), "security_candidate_sha256": hashlib.sha256(security).hexdigest(), "identical_bytes": current == security}
test_paths = git("ls-tree", "-r", "--name-only", "471c54760e8fe016fcd26aca89d17a334d7b0303", "frontend").decode().splitlines()
preservation = []
for relative in test_paths:
    if ".test." not in relative and not relative.endswith(".spec.ts"):
        continue
    original = git("show", f"471c54760e8fe016fcd26aca89d17a334d7b0303:{relative}")
    current = git("show", f"{CANDIDATE}:{relative}")
    preservation.append({"path": relative, "identical_bytes": current == original, "original_sha256": hashlib.sha256(original).hexdigest(), "candidate_sha256": hashlib.sha256(current).hexdigest()})
test_diff = git("diff", "471c54760e8fe016fcd26aca89d17a334d7b0303", CANDIDATE, "--", "frontend/src/App.test.tsx").decode()
(RUN / "original-test-identity.diff").write_text(test_diff, encoding="utf-8")
xml = ET.parse(RUN / "test.xml").getroot()
tests = [{"file": suite.attrib["name"], "name": case.attrib["name"]} for suite in xml.findall("testsuite") for case in suite.findall("testcase")]
initial_xml = ET.parse(RUN.parent / "recovery_r04_frontend_review_1_20261015/test.xml").getroot()
initial_ids = Counter((suite.attrib["name"], case.attrib["name"]) for suite in initial_xml.findall("testsuite") for case in suite.findall("testcase"))
current_ids = Counter((item["file"], item["name"]) for item in tests)
(RUN / "test-identity-delta.json").write_text(json.dumps({"initial_count": sum(initial_ids.values()), "current_count": sum(current_ids.values()), "comparison": "multiset; duplicate parameterized names preserve occurrence counts", "removed": sorted((initial_ids-current_ids).elements()), "added": sorted((current_ids-initial_ids).elements())}, ensure_ascii=False, indent=2), encoding="utf-8")
(RUN / "fix-scope.diff").write_bytes(git("diff", "5e0699d", CANDIDATE, "--", "frontend/src"))
source_paths = ["AGENTS.md", "docs/plan/00_execution_map.md", "docs/plan/03_data_contracts.md", "docs/plan/05_api_and_tool_contracts.md", "docs/plan/06_testing_and_evaluation.md", "docs/plan/12_recovery_task_cards_20261014.md", "docs/tasks/T40_frontend_shell.md", "docs/tasks/T41_sources_events_ui.md", "docs/decisions/CR-R04-R04_read_api_projection.md", "docs/decisions/CR-R10_vitest_security_upgrade.md", "backend/src/ai_intel/api/knowledge_contracts.py", "contracts/schemas/public_api_v2.json"]
receipt = {"checked_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"), "candidate": CANDIDATE, "tree": git("rev-parse", f"{CANDIDATE}^{{tree}}").decode().strip(), "diff_baseline": "3465b47ce618bed6fa45cfecccd88b2b595e04b9", "package_pair": package_pair, "original_106_test_source": "471c54760e8fe016fcd26aca89d17a334d7b0303", "test_file_preservation": preservation, "current_junit": xml.attrib, "current_test_identities": tests, "frozen_sources": [{"path": relative, "sha256": hashlib.sha256(git("show", f"{CANDIDATE}:{relative}")).hexdigest()} for relative in source_paths], "root_report_sources": [{"path": relative, "sha256": hashlib.sha256((Path(r"D:\dianzi") / relative).read_bytes()).hexdigest()} for relative in ["reports/tasks/R17-frontend-preparation.md", "reports/reviews/recovery/G-A-CR-R10-scope-check.md"]]}
receipt["diff_baseline"] = git("rev-parse", "5e0699d").decode().strip()
receipt["frontend_fix_files"] = git("diff", "--name-only", "0b983349e0468a4c75a1adf9f050ac3e7dd00686", CANDIDATE, "--", "frontend").decode().splitlines()
diff_check = subprocess.run(["git", "diff", "--check", "5e0699d", CANDIDATE, "--", "frontend"], cwd=WORKTREE, capture_output=True)
receipt["diff_check"] = {"exit_code": diff_check.returncode, "stdout": diff_check.stdout.decode(), "stderr": diff_check.stderr.decode()}
(RUN / "source-audit.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"test_cases": len(tests), "original_test_files": len(preservation), "changed_original_test_files": [item["path"] for item in preservation if not item["identical_bytes"]], "security_package_pair_identical": all(item["identical_bytes"] for item in package_pair.values())}))

