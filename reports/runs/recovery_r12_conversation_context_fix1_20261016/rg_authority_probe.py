"""Capture the current shared callers and publisher locks from this isolated checkout."""

import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[3]
commands = [
    ["rg", "-n", "ConversationContextService|resolve_question_context|build_question_evidence|acknowledge_completed_turn", "backend/src", "backend/tests"],
    ["rg", "-n", "with_for_update|lock_authenticated_scope|scope_epochs|advisory_xact_lock|def publish|def merge_events", "backend/src/ai_intel/api/auth_state.py", "backend/src/ai_intel/knowledge/persistence.py", "backend/src/ai_intel/knowledge/revisions.py", "backend/src/ai_intel/knowledge/event_linking.py", "backend/src/ai_intel/enrichment/publication.py", "backend/src/ai_intel/ingestion/source_documents.py", "backend/src/ai_intel/ingestion/catalog_documents.py", "backend/src/ai_intel/retrieval/hybrid.py", "backend/src/ai_intel/assets/inventory.py"],
    ["rg", "-n", "build_question|GroundedQuestionService|read_grounded_answer|_lock_answer_scope|response|reservation", "backend/src/ai_intel/api/question_routes.py", "backend/src/ai_intel/answering/service.py"],
]
for command in commands:
    print(json.dumps(dict(command=command, cwd=str(root)), ensure_ascii=False))
    result = subprocess.run(command, cwd=root, capture_output=True)
    print(result.stdout.decode("utf-8", errors="replace"))
    print(result.stderr.decode("utf-8", errors="replace"))
    assert result.returncode == 0
