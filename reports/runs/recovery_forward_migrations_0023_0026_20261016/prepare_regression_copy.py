"""Preserve original tests; adapt only the historical head guard in a test-only copy."""

from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
original = ROOT / "backend/tests/contract/test_r11_r08_forward_migrations.py"
raw = original.read_bytes()
source = raw.decode("utf-8").replace("\r\n", "\n")
adapted = source.replace(
    'MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"',
    'MIGRATIONS = Path(__file__).resolve().parents[4] / "backend/migrations"',
).replace(
    'assert scripts.get_heads() == ["0019_aggregate_observations"]',
    'assert scripts.get_heads() == ["0026_api_key_credentials"]',
).replace(
    '== [\n        "0019_aggregate_observations",',
    '== [\n        "0026_api_key_credentials",\n        "0025_graph_projection",\n'
    '        "0024_conversation_context",\n        "0023_enrichment_input_audit",\n'
    '        "0022_sbom_sidecars",\n        "0021_condition_assessments",\n'
    '        "0020_hybrid_retrieval",\n        "0019_aggregate_observations",',
)
assert source != adapted
(RUN / "testcopy").mkdir(exist_ok=True)
(RUN / "prior_forward_contract.original.snapshot").write_bytes(raw)
copy = RUN / "testcopy/test_previous_forward_contract.py"
copy.write_text(adapted, encoding="utf-8", newline="\n")
(RUN / "prior_forward_contract.adaptation.diff").write_text(
    "".join(difflib.unified_diff(source.splitlines(keepends=True),
                                 adapted.splitlines(keepends=True),
                                 fromfile=str(original), tofile=str(copy))),
    encoding="utf-8", newline="\n",
)
(RUN / "prior_forward_contract.adaptation.json").write_text(
    json.dumps({"original": str(original), "original_raw_sha256": hashlib.sha256(raw).hexdigest(),
                "adapted": str(copy), "adapted_raw_sha256": hashlib.sha256(copy.read_bytes()).hexdigest(),
                "changes": ["copy path", "head0026", "complete forward revision list"],
                "original_modified": False}, indent=2) + "\n",
    encoding="utf-8", newline="\n",
)
print(json.dumps({"original_modified": False, "copy": copy.name}))
