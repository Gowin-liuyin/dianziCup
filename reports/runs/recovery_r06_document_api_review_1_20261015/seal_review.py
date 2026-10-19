"""Freeze source identities and exact artifact bytes for reviewer handoff."""
import hashlib
import json
import subprocess
from pathlib import Path
from review_runner import ROOT, RUN, now

PRODUCT = "49ee33f6a95099be619a59ff47c621713a089137"
BASE = "71e852ce4be147d30aa1bc824bf18afda99fb332"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


started = now()
paths = git("diff", "--name-only", BASE, PRODUCT).decode().splitlines()
sources = []
for name in paths:
    actual = (ROOT / name).read_bytes()
    product = git("show", PRODUCT + ":" + name)
    frozen = git("show", "HEAD:" + name)
    assert product == frozen, name
    normalized = actual.replace(b"\r\n", b"\n")
    assert normalized == product.replace(b"\r\n", b"\n"), name
    sources.append({"path": name, "product_blob_sha256": hashlib.sha256(product).hexdigest(), "working_file_sha256": hashlib.sha256(actual).hexdigest(), "bytes": len(actual)})
(RUN / "source_manifest.json").write_text(json.dumps({"baseline": BASE, "product": PRODUCT, "freeze": git("rev-parse", "HEAD").decode().strip(), "sources": sources}, indent=2) + "\n", encoding="utf-8")
(RUN / "reviewed_product.diff").write_bytes(git("diff", BASE, PRODUCT, "--", "backend"))
(RUN / "metadata_only_diff.txt").write_bytes(git("diff", "--name-status", PRODUCT, "HEAD"))
(RUN / "working_tree_status.txt").write_bytes(git("status", "--short"))
trace = subprocess.run(["rg", "-n", "_evidence_rows\\(|read_public_revision_evidence|lock_authenticated_scope|document_router", "backend/src/ai_intel"], cwd=ROOT, capture_output=True, check=False)
(RUN / "source_trace_rg.txt").write_bytes(trace.stdout)
(RUN / "seal.command.json").write_text(json.dumps({"argv": ["git diff/rev-parse/show/status; rg source callers; exact SHA256 manifests"], "cwd": str(ROOT), "started_at": started, "ended_at": now(), "exit_code": trace.returncode, "product_sources_unchanged": True}, indent=2) + "\n", encoding="utf-8")
files = []
for path in sorted(RUN.iterdir()):
    if path.is_file() and path.name != "artifact_manifest.json":
        raw = path.read_bytes()
        files.append({"path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
(RUN / "artifact_manifest.json").write_text(json.dumps({"created_at": now(), "hash_scope": "raw bytes; manifest excludes itself", "files": files}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"source_files": len(sources), "artifacts": len(files), "product_sources_unchanged": True}))
