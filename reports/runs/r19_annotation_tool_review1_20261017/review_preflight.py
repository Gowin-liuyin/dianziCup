"""Bind public contracts, frozen source and prior failed evidence to this review."""

import hashlib
import json
import subprocess
from pathlib import Path

from scripts.verify_plan import load_json

root = Path(__file__).resolve().parents[3]
run = Path(__file__).parent
baseline = "9726363e0d9b33467ba40a06a8bde9548b46bccf"
source = "982532dd564f3eda5d85a6e252b2cf9ce16f98d1"
material = "3b001f288a63a336eb27cd8ef1b985745437cef4"
paths = [
    "AGENTS.md", "docs/plan/00_execution_map.md",
    "docs/plan/11_full_delivery_recovery_20261014.md",
    "docs/plan/12_recovery_task_cards_20261014.md",
    "docs/plan/06_testing_and_evaluation.md",
    "docs/tasks/T46_benchmark_dataset.md", "contracts/task_manifest.json",
    "benchmarks/schemas/candidate_case_v1.json", "progress/task_state.json",
    "progress/context_handoff.md", "scripts/verify_plan.py",
    "scripts/annotation/prepare.py", "scripts/annotation/tests/test_prepare.py",
    "scripts/annotation/tests/test_prepare_fix1.py",
    "scripts/annotation/tests/test_crash_recovery.py",
    "scripts/annotation/tests/test_fd_metadata_error.py",
    "reports/tasks/R19-qualified-root-integration.md",
]
state = load_json(root / "progress/task_state.json")
manifest = load_json(root / "contracts/task_manifest.json")
schema = load_json(root / "benchmarks/schemas/candidate_case_v1.json")
rows = []
for name in paths:
    raw = (root / name).read_bytes()
    ref = material if name.startswith("reports/") else source
    canonical = subprocess.check_output(["git", "show", f"{ref}:{name}"], cwd=root)
    rows.append({"path": name, "raw_sha256": hashlib.sha256(raw).hexdigest(),
                 "canonical_sha256": hashlib.sha256(canonical).hexdigest(),
                 "lf_equivalent": raw.replace(b"\r\n", b"\n") == canonical.replace(b"\r\n", b"\n")})
assert all(row["lf_equivalent"] for row in rows)
upstream = root / "reports/runs/r19_qualified_root_integration_20261017"
closure_raw = (upstream / "upstream_first_review/input_closure_receipt.json").read_bytes()
closure = json.loads(closure_raw)
closure_rows = []
for row in closure["restored"]:
    path = root / row["path"]
    actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    closure_rows.append({"path": row["path"], "expected": row["raw_sha256"],
                         "actual": actual, "matches": actual == row["raw_sha256"]})
diff = subprocess.check_output(["git", "diff", baseline, source, "--", "scripts/annotation"], cwd=root)
(run / "source.diff.patch").write_bytes(diff)
record = {"baseline": baseline, "source": source, "material": material,
          "inputs": rows, "source_diff_sha256": hashlib.sha256(diff).hexdigest(),
          "strict_duplicate_parser": True, "T46_state": state["tasks"]["T46"],
          "R19_card": manifest["recovery"]["work_packages"]["R19"],
          "schema_id": schema["$id"], "plan_closure_rows": closure_rows,
          "plan_closure_matches": sum(row["matches"] for row in closure_rows),
          "plan_closure_total": len(closure_rows), "holdout_answers_read": False}
(run / "input_inventory.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"inputs": len(rows), "plan_matches": record["plan_closure_matches"],
                  "plan_total": len(closure_rows), "source_diff_sha256": record["source_diff_sha256"]}))
