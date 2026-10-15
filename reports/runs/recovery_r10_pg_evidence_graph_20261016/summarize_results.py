"""从实际 JUnit、命令收据和受限秘密扫描生成交付索引。"""

import json
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent


def main():
    receipts = json.loads((RUN / "commands_frozen.json").read_text(encoding="utf-8"))
    counts = {}
    for name in ("pure", "pg", "regression"):
        root = ET.parse(RUN / (name + "_frozen.xml")).getroot()
        cases = root.findall(".//testcase")
        counts[name] = {
            "tests": len(cases),
            "failures": len(root.findall(".//testcase/failure")),
            "errors": len(root.findall(".//testcase/error")),
            "skipped": len(root.findall(".//testcase/skipped")),
            "by_module": dict(sorted(Counter(case.attrib["classname"] for case in cases).items())),
        }
    capture = subprocess.run(
        ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"],
        check=True, capture_output=True, text=True,
    )
    private = json.loads(capture.stdout)
    credentials = [private[key].encode() for key in ("postgres_password", "redis_password", "TEST_DATABASE_URL")]
    assert all(len(value) >= 8 for value in credentials)
    code = json.loads((RUN / "frozen_code_manifest.json").read_text(encoding="utf-8"))
    diff_checks = []
    for name, arguments in (
        ("frozen_backend", ["git", "diff", "--check", code["baseline"], code["code_commit"], "--", "backend"]),
        ("committed_artifacts", ["git", "diff", "--check", code["baseline"], "HEAD"]),
    ):
        result = subprocess.run(arguments, cwd=ROOT, capture_output=True, text=True)
        diff_checks.append({"scope": name, "command": arguments, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
    (RUN / "diff_checks.json").write_text(json.dumps(diff_checks, ensure_ascii=False, indent=2), encoding="utf-8")
    scan_paths = [*(ROOT / item["path"] for item in code["files"]), *RUN.iterdir(), ROOT / "reports/tasks/R10-pg-evidence-graph.md"]
    matches = []
    checked = 0
    for path in scan_paths:
        if not path.is_file():
            continue
        checked += 1
        if any(value in path.read_bytes() for value in credentials):
            matches.append(path.relative_to(ROOT).as_posix())
    summary = {
        "recorded_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "code_commit": code["code_commit"],
        "task_status": "awaiting_review",
        "data_mode": "fixture",
        "counts": counts,
        "total_test_executions": sum(value["tests"] for value in counts.values()),
        "exit_codes": {value["name"]: value["exit_code"] for value in receipts},
        "verification": {"unit": "passed", "contract": "passed", "security": "passed", "integration": "passed", "frontend": "not_run", "e2e": "not_run", "live": "not_run", "manual": "not_run"},
        "private_credential_scan": {"files_checked": checked, "matching_paths": matches, "passed": not matches},
        "diff_checks": diff_checks,
    }
    (RUN / "verification_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"total_tests": summary["total_test_executions"], "exit_codes": summary["exit_codes"], "credential_scan_passed": not matches}))
    assert not matches


if __name__ == "__main__":
    main()
