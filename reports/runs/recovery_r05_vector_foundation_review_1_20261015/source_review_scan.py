"""Persist frozen contract and source inspection, never reading vault or holdout resources."""

import subprocess
from pathlib import Path

WORKTREE = Path('C:/Users/yinha/.codex/worktrees/recovery-r05-vector-foundation-review-1/dianzi')
FILES = (
    'AGENTS.md', 'docs/plan/00_execution_map.md', 'docs/plan/12_recovery_task_cards_20261014.md',
    'docs/tasks/T18_model_clients.md', 'docs/tasks/T30_hybrid_retrieval.md', 'docs/tasks/T31_grounded_qa_baseline.md',
    'docs/plan/03_data_contracts.md', 'docs/plan/04_workflows_and_algorithms.md',
    'docs/plan/05_api_and_tool_contracts.md', 'docs/plan/06_testing_and_evaluation.md',
    'backend/src/ai_intel/infrastructure/models/clients.py',
    'backend/migrations/versions/0014_grounded_answer_vectors.py',
    'backend/src/ai_intel/retrieval/persistence_models.py',
)
for name in FILES:
    print({'frozen_source': name})
    print((WORKTREE / name).read_text(encoding='utf-8'))
result = subprocess.run(['rg', '-n', 'LocalSemanticModels|retrieval_chunks|grounded_answers|validate_embedding_batch|bound_process_resources',
                         'backend/src', 'backend/tests', 'backend/migrations'], cwd=WORKTREE, capture_output=True,
                        text=True, encoding='utf-8', check=True)
print(result.stdout)
