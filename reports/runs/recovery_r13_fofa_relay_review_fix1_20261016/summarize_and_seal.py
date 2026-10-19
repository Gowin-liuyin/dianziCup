"""汇总真实收据并封存新审查产物，不修改历史raw。"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
REPORT = ROOT / "reports/reviews/recovery/G-D-R13-fofa-relay-config-review-fix1.md"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if sys.argv[1:] == ["verify"]:
        manifest = json.loads((RUN / "artifact_manifest.json").read_text(encoding="utf-8"))
        for entry in manifest["artifacts"]:
            path = ROOT / entry["path"]
            assert len(path.read_bytes()) == entry["bytes"] and digest(path) == entry["sha256"]
        print(json.dumps({"artifacts": len(manifest["artifacts"]), "manifest_sha256": digest(RUN / "artifact_manifest.json"), "verified": True}))
        return
    receipts = []
    for path in sorted(RUN.glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict) and "argv" in value and "exit_code" in value:
            receipts.append(value)
    (RUN / "check_commands.json").write_text(json.dumps(receipts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tests = []
    for path in sorted(RUN.glob("*.xml")):
        suites = list(ET.parse(path).getroot().iter("testsuite"))
        counts = {name: sum(int(suite.attrib.get(name, "0")) for suite in suites) for name in ("tests", "failures", "errors", "skipped")}
        tests.append({"path": str(path.relative_to(ROOT)).replace("\\", "/"), **counts})
    total = sum(item["tests"] for item in tests)
    assert total == 235
    assert all(item[name] == 0 for item in tests for name in ("failures", "errors", "skipped"))
    evidence = json.loads((RUN / "author_artifact_verification_result.json").read_text(encoding="utf-8"))
    for original in evidence["previous_raw_read_only"]:
        path = Path(original["path"])
        assert len(path.read_bytes()) == original["bytes"] and digest(path) == original["sha256"]
    summary = {
        "task": "R13-fofa-relay-config-review-fix1", "component_verdict": "Ship",
        "head_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "tests": tests, "distinct_tests": total,
        "verification": {"unit": "passed", "contract": "passed", "security": "passed", "integration": "not_run", "frontend": "not_run", "e2e": "not_run", "live": "not_run", "manual": "not_run"},
        "external_operations_this_review": {"authenticated_requests": 0, "document_reads": 0, "asset_searches": 0, "scans": 0, "model_calls": 0, "secret_reads": 0},
        "previous_raw_unchanged": True,
        "failed_receipts": [item["name"] for item in receipts if item["exit_code"] != 0],
        "failure_explanation": "Initial verifier used final business blobs for historical manifest; corrected to each manifest code_sha. Preserved initial script and failure log.",
    }
    (RUN / "evidence_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths = sorted([path for path in RUN.rglob("*") if path.is_file() and path.name != "artifact_manifest.json"] + [REPORT])
    manifest = {
        "task": summary["task"], "recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "head_sha": summary["head_sha"], "byte_source": "New reviewer workspace bytes; no author raw normalized or overwritten",
        "self_exclusion": "artifact_manifest.json excluded to avoid recursive digest",
        "artifacts": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": len(path.read_bytes()), "sha256": digest(path)} for path in paths],
    }
    (RUN / "artifact_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"distinct_tests": total, "artifacts": len(paths), "manifest_sha256": digest(RUN / "artifact_manifest.json"), "head_sha": summary["head_sha"]}))


if __name__ == "__main__":
    main()
