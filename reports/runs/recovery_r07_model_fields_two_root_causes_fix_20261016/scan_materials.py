"""Apply the existing security patterns only to this bounded source and evidence package."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
from security_scan import PATTERNS

paths = [
    ROOT / "backend/src/ai_intel/enrichment/field_sources.py",
    ROOT / "backend/tests/unit/test_r07_model_fields.py",
    ROOT / "backend/tests/unit/test_r07_model_field_root_causes.py",
    ROOT / "reports/tasks/R07-model-fields-two-root-causes-fix.md",
    ROOT / ".gitattributes",
]
paths += [path for path in RUN.iterdir() if path.is_file()]
findings = [
    {"path": str(path.relative_to(ROOT)), "pattern_id": name}
    for path in paths
    for name, pattern in PATTERNS.items()
    if pattern.search(path.read_text(encoding="utf-8", errors="replace"))
]
print(json.dumps({"checked_files": len(paths), "findings": findings}))
sys.exit(1 if findings else 0)
