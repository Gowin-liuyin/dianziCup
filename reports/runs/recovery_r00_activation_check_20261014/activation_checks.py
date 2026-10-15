"""Inspect only approval metadata and added evidence in the frozen activation commit."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, r"D:\dianzi\reports\runs\recovery_r00_review_1_20261014")
import run_commands as runner

ROOT = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r00-recheck-clean\dianzi")
OUT = Path(r"D:\dianzi\reports\runs\recovery_r00_activation_check_20261014")
OUT.mkdir(parents=True, exist_ok=True)
runner.OUTPUT = OUT
BASE = "15d0272bd2a9e25d19397d8147e9c3cbe6016f9b"
SHA = "69ecf16be7d95e839b18a4a40f03b3f9d86707f4"
LINUX = "/mnt/c/Users/yinha/.codex/worktrees/recovery-r00-recheck-clean/dianzi"


def run(name: str, argv: list[str]) -> dict:
    return runner.run(name, argv, ROOT)


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def blob(revision: str, relative: str) -> bytes:
    return git("show", revision + ":" + relative)


def diff_json(old: object, new: object, path: str = "") -> list[str]:
    if isinstance(old, dict) and isinstance(new, dict):
        changes = []
        for key in sorted(old.keys() | new.keys()):
            target = f"{path}.{key}" if path else key
            changes.extend(diff_json(old.get(key), new.get(key), target))
        return changes
    return [] if old == new else [path]


run("head", ["git", "rev-parse", "HEAD", "HEAD^{tree}"])
run("status", ["git", "status", "--short"])
run("metadata_diff_check", ["git", "diff", "--check", BASE, SHA, "--", ".gitattributes", "docs", "contracts", "progress", "reports/tasks", "reports/reviews"])
run("baseline_windows", ["python", "scripts/verify_plan.py", "--baseline", "contracts/baselines/plan_baseline_recovery_r00.json"])
run("baseline_wsl", ["wsl", "--cd", LINUX, "--exec", "python3", "scripts/verify_plan.py", "--baseline", "contracts/baselines/plan_baseline_recovery_r00.json"])
changed = git("diff", "--name-only", BASE, SHA).decode().splitlines()
forbidden = ("backend/", "frontend/", "scripts/", "tests/", "fixtures/", "benchmarks/", "experiments/", "config/", "infra/", ".github/")
state = json.loads(blob(SHA, "progress/task_state.json"))
old_state = json.loads(blob(BASE, "progress/task_state.json"))
manifest = json.loads(blob(SHA, "contracts/task_manifest.json"))
old_manifest = json.loads(blob(BASE, "contracts/task_manifest.json"))
baseline = json.loads(blob(SHA, "contracts/baselines/plan_baseline_recovery_r00.json"))
old_baseline = json.loads(blob(BASE, "contracts/baselines/plan_baseline_recovery_r00.json"))
accepted_slices = [slice_id for task in state["tasks"].values() for slice_id, entry in task["slice_acceptance"].items() if entry["status"] == "accepted"]
relative_links = []
for relative in changed:
    if not relative.endswith(".md"):
        continue
    diff = git("diff", "--unified=0", BASE, SHA, "--", relative).decode("utf-8")
    for line in diff.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", line):
            if target.startswith(("https:", "http:", "#", "app:", "codex:")):
                continue
            target_path = target.split("#", 1)[0].strip("<>")
            resolved = (ROOT / relative).parent / target_path
            relative_links.append({"source": relative, "target": target, "exists": resolved.is_file()})
source_trees = {relative: {"old": git("rev-parse", BASE + ":" + relative).decode().strip(), "new": git("rev-parse", SHA + ":" + relative).decode().strip()}
                for relative in ("backend", "frontend", "scripts", "tests", "fixtures", "benchmarks", "config", "infra")
                if git("ls-tree", SHA, relative).strip()}
hashes = [{"path": relative, "baseline": expected, "git": hashlib.sha256(blob(SHA, relative)).hexdigest(), "checkout": hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()}
          for relative, expected in baseline["source_hashes"].items()]
cr_headers = []
for number in range(1, 10):
    relative = f"docs/decisions/CR-R{number:02d}.md"
    lines = (ROOT / relative).read_text(encoding="utf-8").splitlines()
    cr_headers.append({"path": relative, "stale_status_header": "awaiting_review" in lines[2], "stale_review_header": "尚未发生" in lines[6] and "null" in lines[6],
                       "has_activated_record": "2026-10-14T22:19:34+08:00" in "\n".join(lines) and BASE in "\n".join(lines)})
secret_patterns = (rb"sk-(?:proj-|ant-)?[A-Za-z0-9_-]{32,}", rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
scan_count, forbidden_paths, match_paths = 0, [], []
for relative in changed:
    if "holdout" in relative.lower() or Path(relative).name.lower().startswith(".env") or "keys-and-usage" in relative.lower():
        forbidden_paths.append(relative)
        continue
    content = blob(SHA, relative)
    scan_count += 1
    if any(re.search(pattern, content) for pattern in secret_patterns):
        match_paths.append(relative)
record = {"candidate": SHA, "tree": git("rev-parse", "HEAD^{tree}").decode().strip(), "changed_count": len(changed), "changed_files": changed,
          "unexpected_product_files": [path for path in changed if path.startswith(forbidden)], "source_trees": source_trees,
          "manifest_changed_fields": diff_json(old_manifest, manifest), "baseline_changed_fields": diff_json(old_baseline, baseline),
          "state_changed_fields": diff_json(old_state, state), "accepted_original_tasks": [key for key, entry in state["tasks"].items() if entry["status"] == "accepted"],
          "accepted_recovery_tasks": [key for key, entry in state["recovery_tasks"].items() if entry["status"] == "accepted"],
          "accepted_slices": accepted_slices, "r01_status": state["recovery_tasks"]["R01"], "authority": manifest["recovery"]["authority"],
          "source_hashes": hashes, "relative_links": relative_links, "cr_headers": cr_headers,
          "stale_execution_order_source": "awaiting independent activation" in state["execution_order_source"],
          "r01_resource_report_in_frozen_tree": (ROOT / "reports/tasks/R01-resources.md").is_file(),
          "narrow_secret_scan": {"files": scan_count, "pattern_count": len(secret_patterns), "matching_paths": match_paths, "prohibited_unread_paths": forbidden_paths, "limitations": "Only API key/private key patterns, not a comprehensive secret or anonymization proof; no matched values printed."}}
(OUT / "activation_inventory.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: value for key, value in record.items() if key in ("candidate", "changed_count", "unexpected_product_files", "manifest_changed_fields", "baseline_changed_fields", "accepted_original_tasks", "accepted_recovery_tasks", "accepted_slices", "stale_execution_order_source", "r01_resource_report_in_frozen_tree", "narrow_secret_scan")}, ensure_ascii=False, indent=2))
