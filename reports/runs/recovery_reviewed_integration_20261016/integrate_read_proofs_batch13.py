"""Copy only frozen scoped integration blobs, retaining raw source identities."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
BASE = "9726363e0d9b33467ba40a06a8bde9548b46bccf"
SOURCES = {
    "0114779a2ebe3b39275b1a220ad6c13e531976ff": {
        "backend/src/ai_intel/investigation/graph.py",
        "backend/src/ai_intel/investigation/workflow_service.py",
        "backend/tests/contract/test_r14_shared_read_consumers_contract.py",
        "backend/tests/contract/test_r14_unknown_recovery_contract.py",
        "backend/tests/integration/test_r14_langgraph_workflow_pg.py",
        "backend/tests/integration/test_r14_shared_read_consumers_pg.py",
        "backend/tests/unit/test_r14_shared_read_consumers.py",
        "backend/tests/unit/test_r14_shared_read_consumers_fix1.py",
        "backend/tests/unit/test_r14_unknown_boundary_fix2.py",
        "backend/tests/unit/test_r14_unknown_incoming_fix3.py",
    },
    "ca17917fb14eebc7e2b228e51aa7ace9ba09ac5f": {
        "backend/src/ai_intel/enrichment/source_report_reader.py",
        "backend/src/ai_intel/investigation/source_report_node.py",
        "backend/src/ai_intel/knowledge/structured_fact_proofs.py",
        "backend/tests/contract/test_r07_structured_fact_proof_contract.py",
        "backend/tests/integration/test_r07_structured_fact_proofs_pg.py",
        "backend/tests/unit/test_r07_source_report_node.py",
        "backend/tests/unit/test_r07_source_report_reader.py",
        "backend/tests/unit/test_r07_structured_fact_proofs.py",
    },
}


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
head = git("rev-parse", "HEAD").decode().strip()
if head != BASE:
    raise RuntimeError("unexpected root baseline")
identities = []
for source, allowed in SOURCES.items():
    actual = set(git("diff-tree", "--no-commit-id", "--name-only", "-r", source).decode().splitlines())
    if actual != allowed:
        raise RuntimeError("frozen source file scope differs")
    for relative in sorted(allowed):
        target = ROOT / relative
        committed = subprocess.run(["git", "show", BASE + ":" + relative], cwd=ROOT, capture_output=True)
        if committed.returncode == 0:
            if not target.exists() or target.read_bytes().replace(b"\r\n", b"\n") != committed.stdout.replace(b"\r\n", b"\n"):
                raise RuntimeError("existing local edit protected: " + relative)
        elif target.exists():
            raise RuntimeError("unknown existing file protected: " + relative)
        payload = git("show", source + ":" + relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        identities.append({"path": relative, "source_sha": source, "source_git_blob": git("rev-parse", source + ":" + relative).decode().strip(), "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)})
ended = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
(RUN / "read_proofs_batch13_inputs.json").write_text(json.dumps({"started_at": started, "ended_at": ended, "baseline_sha": BASE, "files": identities, "new_default_validation": "not_run", "whole_task_accepted": False, "push": "not_run"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"files": len(identities), "started_at": started, "ended_at": ended, "default_validation": "not_run"}))
