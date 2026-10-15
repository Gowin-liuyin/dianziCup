"""Verify independent candidate results, immutable inputs and original case identities."""

from __future__ import annotations

from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ElementTree


RUN_ROOT = Path(__file__).resolve().parent
WT = Path("C:/Users/yinha/.codex/worktrees/recovery-r01-vitest-candidate/dianzi")


def read_json(name: str) -> dict:
    return json.loads((RUN_ROOT / name).read_text(encoding="utf-8"))


def case_identities(name: str, replay: str) -> Counter:
    report = read_json(name)
    counts = [report[key] for key in ("numTotalTests", "numPassedTests", "numFailedTests", "numPendingTests", "numTodoTests")]
    assert counts == [30, 30, 0, 0, 0], (name, counts)
    assert report["success"] is True
    cases = Counter()
    for file in report["testResults"]:
        relative_file = Path(file["name"]).relative_to(RUN_ROOT / replay / "frontend").as_posix()
        for case in file["assertionResults"]:
            assert case["status"] == "passed"
            cases[(relative_file, case["fullName"])] += 1
    assert sum(cases.values()) == 30
    return cases


def lock_versions(lock: dict) -> dict[str, set[str]]:
    versions: dict[str, set[str]] = {}
    for path, package in lock["packages"].items():
        if not path:
            continue
        name = path.rsplit("node_modules/", 1)[1]
        if "version" in package:
            versions.setdefault(name, set()).add(package["version"])
    return versions


def main() -> None:
    inputs = read_json("inputs.json")
    assert inputs["changed_frontend_paths"] == ["frontend/package-lock.json", "frontend/package.json"]
    assert set(inputs["candidate_hashes"]) == set(inputs["baseline_hashes"])
    for replay, hashes in (("candidate_replay", inputs["candidate_hashes"]), ("baseline_replay", inputs["baseline_hashes"])):
        for path, expected in hashes.items():
            if path.endswith(".tsbuildinfo"):
                continue
            assert hashlib.sha256((RUN_ROOT / replay / path).read_bytes()).hexdigest() == expected, (replay, path)
    baseline_cases = case_identities("baseline_vitest.json", "baseline_replay")
    candidate_cases = case_identities("candidate_vitest.json", "candidate_replay")
    assert candidate_cases == baseline_cases
    test_files = Counter()
    for (path, _), count in candidate_cases.items():
        test_files[path] += count
    quality_path = RUN_ROOT / "candidate_replay/scripts/dev.py"
    assert hashlib.sha256(quality_path.read_bytes()).hexdigest() == inputs["quality_sha256"]
    specification = importlib.util.spec_from_file_location("independent_frozen_quality", quality_path)
    assert specification and specification.loader
    quality = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(quality)
    junit_counts = quality.read_test_report(RUN_ROOT / "candidate_junit.xml")
    assert junit_counts == {"tests": 30, "failed": 0, "errors": 0, "skipped": 0}
    assert quality._report_result("frontend", RUN_ROOT / "candidate_junit.xml", 0) == 0
    junit = ElementTree.parse(RUN_ROOT / "candidate_junit.xml").getroot()
    assert sum(int(suite.get("tests", "0")) for suite in junit.findall(".//testsuite")) == 30
    baseline_versions = read_json("baseline_versions.stdout.log")["dependencies"]
    candidate_versions = read_json("candidate_versions.stdout.log")["dependencies"]
    assert set(candidate_versions) == set(baseline_versions)
    direct_changes = {name: [baseline_versions[name]["version"], package["version"]] for name, package in candidate_versions.items() if package["version"] != baseline_versions[name]["version"]}
    assert direct_changes == {"vitest": ["3.2.7", "4.1.11"]}
    old_lock = read_json("baseline_replay/frontend/package-lock.json")
    new_lock = read_json("candidate_replay/frontend/package-lock.json")
    old_package = read_json("baseline_replay/frontend/package.json")
    new_package = read_json("candidate_replay/frontend/package.json")
    old_package["devDependencies"]["vitest"] = "4.1.11"
    assert old_package == new_package
    old_lock_versions, new_lock_versions = lock_versions(old_lock), lock_versions(new_lock)
    changed_packages = {name: {"before": sorted(old_lock_versions.get(name, [])), "after": sorted(new_lock_versions.get(name, []))} for name in sorted(old_lock_versions.keys() | new_lock_versions.keys()) if old_lock_versions.get(name) != new_lock_versions.get(name)}
    assert "tinypool" not in new_lock_versions and "vite-node" not in new_lock_versions
    before_audit = read_json("baseline_audit.stdout.log")
    after_audit = read_json("candidate_audit.stdout.log")
    assert before_audit["metadata"]["vulnerabilities"]["total"] == 3
    assert after_audit["metadata"]["vulnerabilities"]["total"] == 0
    assert after_audit["vulnerabilities"] == {}
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=WT).decode().strip() == inputs["candidate_sha"]
    status_after = subprocess.check_output(["git", "status", "--porcelain"], cwd=WT)
    assert status_after == (RUN_ROOT / "candidate_before.status.txt").read_bytes() == b""
    checkout_hashes = {path: hashlib.sha256((WT / path).read_bytes()).hexdigest() for path in inputs["candidate_hashes"]}
    for path in inputs["candidate_hashes"]:
        checkout_contents = (WT / path).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(checkout_contents).hexdigest() == inputs["candidate_hashes"][path], path
    summary = {
        "candidate_sha": inputs["candidate_sha"], "candidate_tree": inputs["candidate_tree"],
        "baseline_sha": inputs["baseline_sha"], "baseline_tree": inputs["baseline_tree"],
        "direct_version_changes": direct_changes,
        "direct_versions": {name: package["version"] for name, package in candidate_versions.items()},
        "lock_package_version_changes": changed_packages,
        "baseline_incomplete_lock_entries": sorted(path for path, package in old_lock["packages"].items() if path and "version" not in package),
        "candidate_incomplete_lock_entries": sorted(path for path, package in new_lock["packages"].items() if path and "version" not in package),
        "junit_counts": junit_counts,
        "json_cases_unchanged": True,
        "test_file_counts": dict(test_files),
        "case_identities": [{"file": path, "name": name, "count": count} for (path, name), count in sorted(candidate_cases.items())],
        "audit_before": before_audit["metadata"]["vulnerabilities"],
        "audit_after": after_audit["metadata"]["vulnerabilities"],
        "candidate_checkout_sha256": checkout_hashes,
        "candidate_status_unchanged": True,
        "quality_sha": inputs["quality_sha"], "quality_blob": inputs["quality_blob"], "quality_sha256": inputs["quality_sha256"],
    }
    (RUN_ROOT / "independent_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (RUN_ROOT / "candidate_after.status.txt").write_bytes(status_after)
    print(json.dumps({key: value for key, value in summary.items() if key not in {"case_identities", "candidate_checkout_sha256"}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
