"""Seal reviewed source bytes, distinct JUnit nodes and instrument provenance."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

RUN = Path(__file__).parent
ROOT = RUN.parents[2]
SOURCE = "9fb558aaab4b1630eac62a88be7e2c5686243dab"
MATERIAL = "ccbbf3f5688bc57a81c881504a09ea5d18471387"
PATHS = [
    "sdk/python/ai_intel_client/mcp_adapter.py",
    "sdk/python/ai_intel_client/http_transport.py",
    "sdk/python/tests/test_http_transport.py",
    "sdk/python/README.md",
]

source_hashes = {}
for name in PATHS:
    committed = subprocess.run(["git", "show", SOURCE + ":" + name], cwd=ROOT,
                               capture_output=True, check=True).stdout
    current = (ROOT / name).read_bytes()
    filtered_blob = subprocess.run(["git", "hash-object", "--path=" + name, name],
                                   cwd=ROOT, capture_output=True, check=True).stdout.decode().strip()
    committed_blob = subprocess.run(["git", "rev-parse", SOURCE + ":" + name],
                                    cwd=ROOT, capture_output=True, check=True).stdout.decode().strip()
    assert filtered_blob == committed_blob, name
    source_hashes[name] = {
        "executed_checkout_sha256": hashlib.sha256(current).hexdigest(),
        "committed_sha256": hashlib.sha256(committed).hexdigest(),
        "git_blob": committed_blob,
        "checkout_filter": "core.autocrlf=true; Git-filtered blob must match frozen source",
    }

groups = {}
all_nodes = set()
for label in ["http_final", "regression_protocol", "native_regression", "independent_negatives", "native_http_final"]:
    cases = ET.parse(RUN / (label + ".xml")).getroot().findall(".//testcase")
    nodes = {(case.get("classname"), case.get("name")) for case in cases}
    assert len(nodes) == len(cases)
    assert not all_nodes.intersection(nodes)
    all_nodes.update(nodes)
    counts = {"tests": len(cases), "distinct_tests": len(nodes)}
    for kind in ["failure", "error", "skipped"]:
        counts[kind] = sum(case.find(kind) is not None for case in cases)
    assert counts["failure"] == counts["error"] == counts["skipped"] == 0
    groups[label] = counts

installed_paths = {
    name: str(Path(importlib.metadata.distribution(name).locate_file("")))
    for name in ["mcp", "mcp-types", "httpx", "anyio", "tiktoken"]
}
record = {
    "reviewer": "/root/r18_http_mcp_first_independent_review",
    "frozen_material_sha": MATERIAL,
    "source_sha": SOURCE,
    "source_hashes": source_hashes,
    "groups": groups,
    "distinct_test_nodes": len(all_nodes),
    "installed_versions": {name: importlib.metadata.version(name) for name in installed_paths},
    "installed_paths": installed_paths,
    "root_cr_sha256": hashlib.sha256(Path("D:/dianzi/docs/decisions/CR-R18_http_mcp_transport.md").read_bytes()).hexdigest(),
    "commands": {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in RUN.glob("*.command.json")},
    "request": "narrow SDK review; fixture-only ASGI/native loopback; no PG/provider credentials/paid calls",
}
cbm = {}
for label in ["index", "architecture", "schema", "transport_trace", "adapter_trace"]:
    payload = json.loads((RUN / ("cbm_" + label + ".raw.log")).read_text(encoding="utf-8"))
    assert not payload.get("isError"), label
    cbm[label] = payload.get("structuredContent") or payload.get("content")
record["cbm_results"] = cbm
record["official_source_hashes"] = {
    name: hashlib.sha256(Path("D:/dianzi/backend/.venv/Lib/site-packages", name).read_bytes()).hexdigest()
    for name in ["mcp/server/streamable_http_manager.py", "mcp/server/transport_security.py",
                 "mcp/server/_streamable_http_modern.py", "mcp/server/streamable_http.py",
                 "mcp/client/client.py", "mcp/client/streamable_http.py"]
}
(RUN / "review_seal.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"source_files_verified": len(source_hashes), "distinct_tests": len(all_nodes),
                  "installed_versions": record["installed_versions"]}))
