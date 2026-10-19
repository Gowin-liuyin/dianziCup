"""Trace code and caller gaps from fixed repositories, without trusting graph absence alone."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
EXECUTION = Path("D:/wt/r07-enrichment-execution")
SHA = "595e42a91a830f78fd11d0e4fc7a79a1aaf767cb"
files = {}
for name in ("job_service.py", "job_contracts.py", "job_types.py", "job_models.py"):
    relative = "backend/src/ai_intel/enrichment/" + name
    raw = subprocess.check_output(["git", "show", SHA + ":" + relative], cwd=EXECUTION)
    lines = raw.decode().splitlines()
    matches = [{"line": index, "text": line} for index, line in enumerate(lines, 1) if any(term in line for term in ("extract_model_dimension", "generated.", "execution_policy_sha256", "result_payload=encoded", "MODEL_TRACE_ADAPTER", "input_selections", "selection_version", "prompt_version", "class EnrichmentExecutionPolicy"))]
    files[relative] = {"git_blob_sha256": hashlib.sha256(raw).hexdigest(), "matches": matches, "contains_selection_version": "selection_version" in raw.decode(), "contains_prompt_version": "prompt_version" in raw.decode(), "contains_input_selections": "input_selections" in raw.decode()}
commands = [
    ["rg", "-n", "select_field_evidence|load_taxonomy_catalogue|input_selections|extract_model_dimension", "backend/src"],
    ["rg", "-n", "validate_field_candidate|limitations", "backend/src/ai_intel/enrichment/publication.py", "backend/src/ai_intel/enrichment/field_sources.py"],
]
results = []
for command in commands:
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    results.append({"command": command, "cwd": str(ROOT), "exit_code": completed.returncode, "output": completed.stdout + completed.stderr})
result = {"recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "reviewed_tree_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "fixed_external_execution_sha": SHA, "external_files": files, "caller_searches": results, "scope_limit": "Caller gaps block whole R07/default App acceptance and require separate controlled integration. This review covers the isolated pure parser/selection and PG loader only."}
(RUN / ("caller_audit_" + result["reviewed_tree_head"][:8] + ".json")).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"fixed_external_execution_sha": SHA, "external_files": len(files), "caller_searches": len(results)}))
