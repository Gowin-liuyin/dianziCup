"""Reuse the unchanged security patterns on this bounded source and evidence package."""

import json
import sys
from pathlib import Path

RUN_ROOT = Path(__file__).resolve().parent
WORKTREE = RUN_ROOT.parents[2]
sys.path.insert(0, str(WORKTREE / "scripts"))
from security_scan import PATTERNS

paths = [
    WORKTREE / "backend/src/ai_intel/enrichment/model_fields.py",
    WORKTREE / "backend/tests/unit/test_r07_single_model_dimension.py",
    WORKTREE / "backend/tests/contract/test_r07_single_model_dimension_contract.py",
    WORKTREE / "backend/tests/security/test_r07_single_model_dimension_security.py",
    WORKTREE / "reports/tasks/R07-single-model-dimension.md",
]
paths += [path for path in RUN_ROOT.iterdir() if path.is_file()]
findings = [
    {"path": str(path.relative_to(WORKTREE)), "pattern_id": name}
    for path in paths
    for name, pattern in PATTERNS.items()
    if pattern.search(path.read_text(encoding="utf-8", errors="replace"))
]
print(json.dumps({"checked_files": len(paths), "findings": findings}))
sys.exit(1 if findings else 0)
