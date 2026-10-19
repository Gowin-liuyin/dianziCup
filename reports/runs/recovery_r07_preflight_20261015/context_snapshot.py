"""Capture only task contracts and public capability evidence, with strict JSON keys."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from preflight_probe import ROOT, RUN, now


def unique_pairs(entries: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in entries:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


files = [
    "AGENTS.md", "docs/plan/00_execution_map.md",
    "docs/plan/11_full_delivery_recovery_20261014.md",
    "docs/plan/12_recovery_task_cards_20261014.md",
    "docs/plan/03_data_contracts.md", "docs/plan/04_workflows_and_algorithms.md",
    "docs/plan/05_api_and_tool_contracts.md", "docs/plan/06_testing_and_evaluation.md",
    "docs/plan/07_sources_and_resources.md",
    "reports/tasks/R02.md", "reports/tasks/R02-dimensions.md",
    "reports/tasks/R05.md", "reports/tasks/R06.md", "reports/tasks/R06-document-live.md",
    "reports/reviews/recovery/G-A-R02-dimension-review-1.md",
    "reports/reviews/recovery/G-B-checkpoint-review-1.md",
    "progress/context_handoff.md", "progress/blockers.md",
]
files += [f"docs/decisions/CR-R0{index}.md" for index in range(1, 10)]
files += ["docs/tasks/" + name for name in (
    "T13_community_repository_connectors.md", "T19_structured_enrichment.md",
    "T20_claim_extraction.md", "T22_research_and_document_links.md",
    "T23_poc_scores_impact.md", "T41_sources_events_ui.md")]
records = []
for relative in files:
    raw = (ROOT / relative).read_bytes()
    raw.decode("utf-8-sig")
    records.append({"path": relative, "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)})
manifest = json.loads((ROOT / "contracts/task_manifest.json").read_text(encoding="utf-8-sig"), object_pairs_hook=unique_pairs)
state = json.loads((ROOT / "progress/task_state.json").read_text(encoding="utf-8-sig"), object_pairs_hook=unique_pairs)
requirements = json.loads((ROOT / "contracts/requirements.json").read_text(encoding="utf-8-sig"), object_pairs_hook=unique_pairs)
recovery = manifest["recovery"]
payload = {
    "recorded_at": now(), "read_files": records, "json_duplicate_keys": "strictly rejected",
    "R07": recovery["work_packages"]["R07"],
    "requires_slices": {key: recovery["capability_slices"][key] for key in recovery["work_packages"]["R07"]["requires_slices"]},
    "original_aggregation": {key: recovery["original_task_aggregation"][key] for key in ("T13", "T19", "T20", "T22", "T23", "T41")},
    "state_top_keys": list(state), "requirements_top_keys": list(requirements),
    "state": {key: state["recovery_tasks"][key] for key in ("R02", "R05", "R06", "R07")},
}
(RUN / "contract_snapshot.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"read_count": len(records), "R07": payload["R07"], "state_top_keys": list(state)}, ensure_ascii=False))
