"""Save fixed source-flow crosschecks and provenance without accessing private runtime inputs."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
commands = [
    ["git", "status", "--porcelain", "--", "backend/src", "backend/tests", "contracts", "docs", "progress"],
    ["git", "diff", "--name-only", "ce1da8811495f1ea1de538c67cb12b16e6d8a280", "cb34097898b412390ee7e119d0d5c2c90d090673", "--", "backend/src", "backend/tests", "contracts"],
    ["git", "diff", "--check"],
    ["rg", "-n", "LiteratureReferenceValue|VersionInterval|KnowledgeRepository\\(.*|\\.publish\\(|_claim_display_value|_claim_from_row", "backend/src/ai_intel/knowledge/persistence.py", "backend/src/ai_intel/domain/enrichment_values.py", "backend/src/ai_intel/ingestion/source_documents.py", "backend/src/ai_intel/api/knowledge_read_service.py"],
    ["rg", "-n", "revision scope does not match document scope|begin_nested|find_prior_publication|_validate_submission|_save_claim|enforce_visible|reference target scope", "backend/src/ai_intel/knowledge/persistence.py", "backend/src/ai_intel/knowledge/revisions.py"],
]
receipts = []
for index, argv in enumerate(commands):
    command_started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    result = subprocess.run(argv, cwd=ROOT, capture_output=True)
    output_file = RUN / ("static_trace_" + str(index) + ".log")
    output_file.write_bytes(result.stdout + result.stderr)
    receipts.append({"argv": argv, "cwd": str(ROOT), "started_at": command_started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "exit_code": result.returncode, "log": output_file.name})
input_paths = [ROOT / "docs/plan/07_sources_and_resources.md", Path("D:/wt/r07-core-review-1/reports/reviews/recovery/G-C-R07-core-review-1.md"), Path("C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md")]
inputs = [{"path": str(path), "bytes": len(path.read_bytes()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in input_paths]
result = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "commands": receipts, "additional_inputs": inputs, "fresh_worktree": str(ROOT), "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(), "code_sha": "ce1da8811495f1ea1de538c67cb12b16e6d8a280", "full_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
(RUN / "static_trace_receipts.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"commands": len(receipts), "all_exit_zero": all(item["exit_code"] == 0 for item in receipts)}))
