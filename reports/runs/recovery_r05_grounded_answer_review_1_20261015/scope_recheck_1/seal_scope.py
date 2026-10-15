"""Preserve initial red evidence and seal only the directed scope review."""

import hashlib
import inspect
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

from ai_intel.answering import grounding

run = Path(__file__).resolve().parent
initial_run = run.parent
report = Path("D:/dianzi/reports/reviews/recovery/G-B-R05-grounded-answer-review-1.md")
checkout = Path("C:/Users/yinha/.codex/worktrees/r05-grounded-answer-independent-review/dianzi")
sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout, text=True).strip()
status = subprocess.check_output(["git", "status", "--porcelain"], cwd=checkout, text=True)
assert sha == "b1511145d4e6c15c5b1f6595bb7c776781ecf2ab"
assert status == ""
initial_manifest = json.loads((initial_run / "seal_manifest.json").read_text(encoding="utf-8"))
report_text = report.read_text(encoding="utf-8")
initial_report = report_text.split("\n## 定向复核附录 · scope_recheck_1\n", 1)[0]
initial_report = re.sub(r"当前有限结论：[^\n]*\n\n", "", initial_report)
old_report_entry = next(entry for entry in initial_manifest["files"] if Path(entry["path"]) == report)
assert hashlib.sha256(initial_report.encode()).hexdigest() == old_report_entry["sha256"]
(run / "initial_review_c180.md").write_text(initial_report, encoding="utf-8")
for entry in initial_manifest["files"]:
    if Path(entry["path"]) != report:
        assert hashlib.sha256(Path(entry["path"]).read_bytes()).hexdigest() == entry["sha256"], entry["path"]
missing_links = [target for target in re.findall(r"\]\((D:/[^)]+)\)", report_text) if not Path(target).is_file()]
assert not missing_links, missing_links
counts = {}
for file in run.glob("*.xml"):
    root = ElementTree.parse(file).getroot()
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
    counts[file.name] = {key: sum(int(suite.attrib.get(key, 0)) for suite in suites) for key in ("tests", "failures", "errors", "skipped")}
assert counts["independent_scope.xml"]["tests"] == 47
assert counts["grounded_scope.xml"]["tests"] == 113
coverage = json.loads((run / "answering_coverage.json").read_text(encoding="utf-8"))
files = [report, *(file for file in run.iterdir() if file.is_file() and file.name not in {"scope_manifest.json", "seal_scope.log", "seal_scope.receipt.json"})]
manifest = {
    "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "code_sha": sha,
    "cwd": str(Path.cwd()),
    "import_origin": inspect.getfile(grounding),
    "checkout": str(checkout),
    "git_status_porcelain": status,
    "initial_red_artifact_hashes_preserved": True,
    "initial_report_reconstructed_sha256": old_report_entry["sha256"],
    "report_local_link_check": "passed",
    "tests": counts,
    "answering_coverage": coverage["totals"],
    "real_product_provider_calls": 0,
    "fee": "unknown",
    "files": [{"path": str(file), "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), "bytes": file.stat().st_size} for file in sorted(files)],
}
(run / "scope_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"code_sha": sha, "clean": status == "", "initial_red_preserved": True, "links": "passed", "tests": counts, "answering_coverage": coverage["totals"]}, ensure_ascii=False))
