"""Summarize real receipts and frozen component identities without rewriting outcomes."""

import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
components = {
    "b7817239022caed52ba6b8912b2d827c58a60181": ["backend/src/ai_intel/ingestion/source_jobs.py", "backend/src/ai_intel/ingestion/source_failure_receipts.py", "backend/migrations/versions/0016_source_response_receipts.py"],
    "cb34097898b412390ee7e119d0d5c2c90d090673": ["backend/src/ai_intel/domain/enrichment_values.py", "backend/src/ai_intel/knowledge/persistence.py"],
    "facf6cce653de318ac966e71ac62b479e562aa61": ["backend/src/ai_intel/enrichment/signals.py"],
    "ef24758bd8e9e3e1e8e24760d330a9ffe62af341": ["backend/src/ai_intel/enrichment/model_fields.py", "backend/src/ai_intel/enrichment/field_sources.py"],
    "df0faafb64327be190803089f0058f9b5dc2427b": ["backend/src/ai_intel/infrastructure/models/generation.py"],
    "6472d816471a8c8ff176745d199ae4a3ef73270f": ["frontend/src/features/events/events.css", "frontend/e2e/r17_event_detail_fixture.spec.ts"],
    "535c0a537bc24cb52c64511c72eeb4ea3ae5bc34": ["backend/src/ai_intel/infrastructure/process_limits.py", "backend/src/ai_intel/ingestion/parsing/_pdf_worker.py"],
    "8f5fe818774349b41b0b5aceb45d69ba81410678": ["backend/src/ai_intel/assessment/version_ranges.py"],
}
rows = []
for commit, paths in components.items():
    for path in paths:
        expected = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True, check=False)
        current = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=ROOT, capture_output=True, check=False)
        row = {"component": commit, "path": path, "expected_exists": expected.returncode == 0, "current_exists": current.returncode == 0}
        if expected.returncode == current.returncode == 0:
            row.update(exact_git_blob_bytes_equal=expected.stdout == current.stdout, expected_sha256=hashlib.sha256(expected.stdout).hexdigest(), current_sha256=hashlib.sha256(current.stdout).hexdigest(), checkout_sha256=hashlib.sha256((ROOT / path).read_bytes()).hexdigest())
        rows.append(row)
(RUN / "component_source_identity.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
receipts = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(RUN.glob("*.command.json"))]
(RUN / "command_index.json").write_text(json.dumps(receipts, indent=2), encoding="utf-8")
counts = {}
for filename in ("backend_full_pure.xml", "pg_selected.xml", "privacy_environment_recheck.xml", "shared_generation_boundary.xml", "frontend_unit.xml", "event_fixture.xml"):
    cases = ET.parse(RUN / filename).findall(".//testcase")
    groups = {}
    for case in cases:
        classname = case.get("classname", "")
        outcome = "failure" if case.find("failure") is not None else "error" if case.find("error") is not None else "skipped" if case.find("skipped") is not None else "passed"
        groups.setdefault(classname, {name: 0 for name in ("passed", "failure", "error", "skipped")})[outcome] += 1
    counts[filename] = groups
(RUN / "test_file_counts.json").write_text(json.dumps(counts, indent=2), encoding="utf-8")
print(json.dumps({"component_identities": rows, "commands": [{key: row.get(key) for key in ("label", "started_at", "ended_at", "exit_code")} for row in receipts], "pg_counts": counts["pg_selected.xml"]}, indent=2))
