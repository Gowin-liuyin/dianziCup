"""Protect predecessor evidence and freeze actual code and raw evidence without reading caches."""

import hashlib
import io
import json
import subprocess
from pathlib import Path
from checks import ROOT, RUN, now

BASE = "014de585413c8a82a04d00b1ff2fbd1ff62d733b"
CODE = "0c57b559fe2f0d93f8a5359383f1db6cc7abc6f5"
PRIOR_RUN = "reports/runs/recovery_r07_input_audit_20261016"
PRIOR_ROOT = Path("D:/wt/r07-input-audit")
BLOBS = {}

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def blob(revision, path):
    if (revision, path) in BLOBS:
        return BLOBS[(revision, path)]
    return subprocess.check_output(["git", "show", revision + ":" + path], cwd=ROOT)

def row(path):
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "size_bytes": len(raw), "raw_sha256": digest(raw), "lf_sha256": digest(raw.replace(b"\r\n", b"\n"))}

started = now()
prior = json.loads(blob(BASE, PRIOR_RUN + "/forbidden_files_hash_proof.json"))
material_paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASE, PRIOR_RUN], cwd=ROOT, text=True).splitlines()
material_paths += ["docs/decisions/CR-R07_input_audit_fingerprint.md", "reports/tasks/R07-input-audit.md"]
changed = subprocess.check_output(["git", "diff", "--name-only", BASE, CODE], cwd=ROOT, text=True).splitlines()
owned_unchanged = ["backend/src/ai_intel/enrichment/" + name for name in ("job_contracts.py", "job_models.py", "job_types.py")]
old_paths = sorted(set([entry["path"] for entry in prior["rows"]] + material_paths + owned_unchanged))
references = [(BASE, path) for path in old_paths] + [(CODE, path) for path in sorted(set(old_paths + changed))]
stream = io.BytesIO(subprocess.check_output(["git", "cat-file", "--batch"], cwd=ROOT, input="".join(revision + ":" + path + "\n" for revision, path in references).encode()))
for reference in references:
    header = stream.readline().decode().split()
    assert len(header) == 3 and header[1] == "blob"
    BLOBS[reference] = stream.read(int(header[2]))
    assert stream.read(1) == b"\n"
protected = []
for entry in prior["rows"]:
    path = entry["path"]
    original = blob(BASE, path)
    current = blob(CODE, path)
    assert current == original
    protected.append({"path": path, "original_git_blob_sha256": digest(original), "fix1_git_blob_sha256": digest(current), "match": True})
protected_materials = []
for path in material_paths:
    original = blob(BASE, path)
    raw = (ROOT / path).read_bytes()
    original_raw = (PRIOR_ROOT / path).read_bytes()
    assert original_raw == original
    assert raw == original or raw.replace(b"\r\n", b"\n") == original
    assert blob(CODE, path) == original
    protected_materials.append({"path": path, "original_worktree_raw_sha256": digest(original_raw), "original_git_blob_sha256": digest(original), "fresh_checkout_raw_sha256": digest(raw), "fresh_checkout_raw_identical": raw == original, "original_bytes_and_git_unchanged": True})
assert len(protected) == 408 and len(protected_materials) == 93
unchanged_owned = []
for name in ("job_contracts.py", "job_models.py", "job_types.py"):
    path = "backend/src/ai_intel/enrichment/" + name
    assert blob(BASE, path) == blob(CODE, path)
    unchanged_owned.append({"path": path, "git_blob_sha256": digest(blob(CODE, path)), "match": True})
proposal = PRIOR_RUN + "/0023_input_audit_proposal.sql"
assert blob(BASE, proposal) == blob(CODE, proposal)
proof = {"started_at": started, "ended_at": now(), "exit_code": 0, "base_sha": BASE, "code_sha": CODE, "protected_existing_files": len(protected), "protected_predecessor_materials": len(protected_materials), "rows": protected, "materials": protected_materials, "unchanged_owned_contract_metadata_types": unchanged_owned, "unchanged_0023_proposal_sha256": digest(blob(CODE, proposal)), "cache_policy": "excluded; no cache content read"}
(RUN / "predecessor_protection.json").write_bytes(json.dumps(proof, indent=2).encode())
sources = []
snapshot = RUN / "frozen_sources"
snapshot.mkdir(exist_ok=True)
assert len(changed) == 2
for name in changed:
    content = blob(CODE, name)
    (snapshot / Path(name).name).write_bytes(content)
    source = row(ROOT / name)
    source["code_git_blob_sha256"] = digest(content)
    assert source["lf_sha256"] == source["code_git_blob_sha256"]
    sources.append(source)
report = ROOT / "reports/tasks/R07-input-audit-fix1.md"
materials = [path for path in sorted(RUN.rglob("*")) if path.is_file() and "__pycache__" not in path.parts and path.name not in {"raw_manifest.json", "material_fingerprint.json", "index_blob_verification.json", "post_commit_verification.json"}]
materials.append(report)
manifest = {"created_at": now(), "base_sha": BASE, "code_sha": CODE, "code_tree_sha": subprocess.check_output(["git", "rev-parse", CODE + "^{tree}"], cwd=ROOT, text=True).strip(), "changed_source": sources, "materials": [row(path) for path in materials], "cache_policy": "excluded; no cache content read", "task_status": "awaiting_review", "nvd_original_case": "failed, not_closed", "original_review_third": {"passed": 13, "business_red": 3, "codec_instrument_red": 1}, "private_values_or_their_hashes": "excluded"}
raw = json.dumps(manifest, indent=2).encode()
(RUN / "raw_manifest.json").write_bytes(raw)
(RUN / "material_fingerprint.json").write_bytes(json.dumps({"created_at": now(), "code_sha": CODE, "raw_manifest_sha256": digest(raw)}, indent=2).encode())
print(json.dumps({"code_sha": CODE, "protected_files": len(protected), "protected_materials": len(protected_materials), "new_materials": len(materials), "raw_manifest_sha256": digest(raw)}))
