"""Seal exact candidate hashes and audit only authorized public fixture/report artifacts."""

import hashlib
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
BASE = "7b8103e6d91a7274bcfb661d8e6f1d5b7180be17"
candidate_files = (
    "backend/tests/integration/test_r05_vector_persistence.py",
    "fixtures/recorded/r05_legacy_0013_vllm_public_v1.json",
)
changed = subprocess.check_output(
    ["git", "diff", "--name-only", BASE, "HEAD"], cwd=ROOT, text=True
).splitlines()
assert set(changed) == set(candidate_files)
connection_url = os.environ["TEST_DATABASE_URL"]
credentials = (connection_url, unquote(urlsplit(connection_url).password or ""))
artifacts = [ROOT / name for name in candidate_files]
artifacts.extend(path for path in RUN.iterdir() if path.is_file())
for path in artifacts:
    content = path.read_bytes()
    assert all(not value or value.encode() not in content for value in credentials)
for path in RUN.glob("*.json"):
    metadata = json.loads(path.read_bytes())
    if "public_before" in metadata:
        assert metadata["public_before"] == metadata["public_after"]
        assert metadata["public_unchanged"] is True
old_root = Path("D:/wt/gb-stage-final")
old_chain = (
    "ai_intel.ingestion.source_documents",
    "ai_intel.knowledge.revisions",
    "ai_intel.knowledge.event_linking",
    "ai_intel.knowledge.persistence",
    "ai_intel.knowledge.models",
)
chain_script = """
import hashlib, importlib, json
from pathlib import Path
modules = __MODULES__
chain = {}
for name in modules:
    path = Path(importlib.import_module(name).__file__).resolve()
    assert str(path).startswith('D:\\\\wt\\\\gb-stage-final\\\\backend\\\\src\\\\')
    chain[name] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
print(json.dumps(chain))
""".replace("__MODULES__", repr(old_chain))
old_env = {**os.environ, "PYTHONPATH": str(old_root / "backend/src")}
old_imports = json.loads(
    subprocess.check_output(
        [str(old_root / "backend/.venv/Scripts/python.exe"), "-c", chain_script],
        cwd=old_root,
        env=old_env,
        text=True,
    )
)
manifest = {
    "base_sha": BASE,
    "code_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "files": {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in candidate_files
    },
    "original_writer_import_chain": old_imports,
    "credential_scan_passed": True,
    "public_mutation_guards_passed": True,
    "artifact_count": len(artifacts),
}
(RUN / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps(manifest))
