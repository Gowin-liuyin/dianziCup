"""Single-variable, in-memory probes; no source files or original responses are edited."""

import json
import os
import sys
from pathlib import Path

from ai_intel.infrastructure.models.json_output import strict_json_object
from ai_intel.ingestion import catalog_pages
from ai_intel.ingestion.sources import github_releases

from replay_originals import RUN, current_time, failure_summary, static_messages


def structure_counts(value):
    pending = [(value, 0)]
    count = 0
    depth_max = 0
    while pending:
        current, depth = pending.pop()
        count += 1
        depth_max = max(depth_max, depth)
        if isinstance(current, dict):
            pending.extend((key, depth + 1) for key in current)
            pending.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            pending.extend((child, depth + 1) for child in current)
    return {"node_count_including_keys": count, "maximum_depth": depth_max}


def verdict(call):
    try:
        result = call()
        return {"verdict": "passed", "record_count": len(result) if isinstance(result, tuple) else None}
    except Exception as error:
        return {"verdict": "failed", **failure_summary(error, static_messages())}


started_at = current_time()
entry = json.loads((RUN / "initial_manifest.json").read_text(encoding="utf-8"))[0]
body = Path(entry["original_path"]).read_bytes()
entries = json.loads(body)
wrapped = b'{"releases":' + body + b'}'
probes = {
    "default_strict_json": verdict(lambda: strict_json_object(wrapped, 2 * 1024 * 1024 + 13)),
    "explicit_50000_nodes_strict_json": verdict(lambda: strict_json_object(
        wrapped, 2 * 1024 * 1024 + 13, maximum_nodes=50000)),
    "per_record_parser": [verdict(lambda item=item: github_releases.parse_github_releases(
        json.dumps([item]).encode())) for item in entries],
    "without_assets_in_memory": verdict(lambda: github_releases.parse_github_releases(json.dumps([
        {key: value for key, value in item.items() if key != "assets"} for item in entries
    ]).encode())),
}
prefix_results = []
for count in range(1, len(entries) + 1):
    subset = entries[:count]
    result = verdict(lambda subset=subset: github_releases.parse_github_releases(json.dumps(subset).encode()))
    prefix_results.append({"records": count, **structure_counts({"releases": subset}), **result})
    if result["verdict"] == "failed":
        break
probes["minimal_prefix"] = prefix_results[-2:]


def source_budget(raw, maximum_bytes=262144, *, maximum_nodes=10000):
    return strict_json_object(raw, maximum_bytes, maximum_nodes=50000)


saved_release_json = github_releases.strict_json_object
saved_catalog_json = catalog_pages.strict_json_object
try:
    github_releases.strict_json_object = source_budget
    probes["parser_with_source_budget_only"] = verdict(lambda: github_releases.parse_github_releases(body))
    probes["catalog_with_parser_source_budget_only"] = verdict(lambda: catalog_pages.normalize_catalog_page(
        "ollama_releases", body, {}))
    catalog_pages.strict_json_object = source_budget
    source_diagnosis = json.loads(Path("D:/dianzi/reports/runs/recovery_r06_integrated_live_20261015/source_diagnosis.json").read_text(encoding="utf-8"))
    headers = source_diagnosis["diagnosis"][0]["responses"][0]["redacted_headers"]
    page = catalog_pages.normalize_catalog_page("ollama_releases", body, {}, headers)
    probes["catalog_with_both_source_budgets"] = {
        "verdict": "passed", "documents": len(page.documents), "next_cursor": page.next_cursor,
        "all_parsed": all(member.parsed.status == "parsed" for member in page.documents),
    }
finally:
    github_releases.strict_json_object = saved_release_json
    catalog_pages.strict_json_object = saved_catalog_json

output = {"source_sha": "1156b2ed6616e3a4297215c2893d2cbe633f5215", "argv": sys.argv,
          "cwd": os.getcwd(), "started_at": started_at, "finished_at": current_time(),
          "network_requests": 0, "database_calls": 0,
          "response_type": type(entries).__name__, "release_count": len(entries),
          "structure": structure_counts({"releases": entries}), "probes": probes,
          "classification": "diagnostic in-memory substitution, not implemented or live validation",
          "exit_code": 0}
(RUN / "release_structure_probes.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
print(json.dumps(output, indent=2))
