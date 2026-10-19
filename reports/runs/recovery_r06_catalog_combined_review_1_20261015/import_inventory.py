"""Verify the independent interpreter imports the frozen worktree modules."""

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
names = ["ai_intel", "ai_intel.knowledge.revisions", "ai_intel.knowledge.models", "ai_intel.ingestion.catalog_documents", "ai_intel.ingestion.source_catalog", "ai_intel.ingestion.source_documents", "ai_intel.api.document_contracts"]
paths = {name: str(Path(importlib.import_module(name).__file__).resolve()) for name in names}
assert all(Path(value).is_relative_to(ROOT / "backend/src") for value in paths.values())
print(json.dumps({"interpreter": sys.executable, "modules": paths}, indent=2))
