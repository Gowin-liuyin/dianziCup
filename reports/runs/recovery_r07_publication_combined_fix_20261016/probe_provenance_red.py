"""Restore an author-owned file after replaying the prior frozen publication implementation."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
target = ROOT / "backend/src/ai_intel/enrichment/publication.py"
assert target.resolve().is_relative_to(ROOT.resolve())
current = target.read_bytes()
old = subprocess.check_output(["git", "show", "20fb98541f9cc9035a2a2dad31e676b2a122e161:backend/src/ai_intel/enrichment/publication.py"], cwd=ROOT)
result = None
try:
    target.write_bytes(old)
    result = subprocess.run([str(ROOT / "backend/.venv/Scripts/python.exe"), str(RUN / "check_combination.py"), "provenance_red", "provenance"], cwd=ROOT, timeout=120)
finally:
    target.write_bytes(current)
    assert target.read_bytes() == current
receipt = {"original_source_code_sha": "20fb98541f9cc9035a2a2dad31e676b2a122e161", "old_blob_sha256": hashlib.sha256(old).hexdigest(), "restored_source_sha256": hashlib.sha256(current).hexdigest(), "wrapper_exit_code": result.returncode if result else None, "source_restored": True, "scope": "single owner temporary prior-code replay before any independent review; not product live"}
(RUN / "provenance_red_restoration.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))
