"""Bind unchanged R17 source/tests and the restored exact fixture to fresh HEAD."""
import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
HEAD = "8514ebb16fedfe026cc280b78fced993af1dc5e8"
SOURCE = "4a17fa3fb7357a8c2b9d647f62c875958a24a27d"
BASE = "17ab90e0a6b100530a3078dd525f9086813c9728"
ORIGINAL = "5587deb124f06b9aa14fb7feb22cdc9493ae4883"
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)

assert git("rev-parse", "HEAD").decode().strip() == HEAD
sources = git("diff", "--name-only", BASE, SOURCE).decode().splitlines()
tests = [path for path in git("ls-tree", "-r", "--name-only", BASE, "frontend").decode().splitlines() if re.search(r"\.(test|spec)\.[cm]?[jt]sx?$", path)]
assert len(sources) == 5 and len(tests) == 58
assert tests == [path for path in git("ls-tree", "-r", "--name-only", ORIGINAL, "frontend").decode().splitlines() if re.search(r"\.(test|spec)\.[cm]?[jt]sx?$", path)]
source_proof = []
for path in sources:
    source_blob = git("rev-parse", SOURCE + ":" + path).decode().strip()
    assert git("rev-parse", HEAD + ":" + path).decode().strip() == source_blob
    source_proof.append({"path": path, "blob": source_blob, "checkout_sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest()})
test_proof = []
for path in tests:
    blobs = {revision: git("rev-parse", revision + ":" + path).decode().strip() for revision in (BASE, ORIGINAL, HEAD)}
    assert len(set(blobs.values())) == 1, path
    test_proof.append({"path": path, "blob": blobs[HEAD]})
fixture_path = "reports/runs/recovery_r17_sbom_workbench_20261016/backend_contract_samples.json"
attrs_path = "reports/runs/recovery_r17_sbom_workbench_20261016/.gitattributes"
assert git("rev-parse", HEAD + ":" + fixture_path).decode().strip() == "82c40263274fb65517037ab5e3f2d3982f151d67"
original_fixture = git("show", ORIGINAL + ":" + fixture_path)
assert (ROOT / fixture_path).read_bytes() == original_fixture
assert hashlib.sha256(original_fixture).hexdigest() == "92f5a0cac56ccd97c63af16bd14418cbc1c42cf4803c3ab6627f419235a6e331"
assert git("show", HEAD + ":" + attrs_path) == git("show", ORIGINAL + ":" + attrs_path) == (ROOT / attrs_path).read_bytes()
unchanged_scope = ["backend/src/ai_intel/assets", "backend/migrations/versions/0018_asset_inventory.py", "backend/migrations/versions/0022_sbom_sidecars.py", "backend/src/ai_intel/api/app.py", "backend/src/ai_intel/api/authentication.py", "backend/src/ai_intel/domain/access.py", "frontend/src/features/assets", "frontend/package.json", "frontend/package-lock.json"]
scope_diff = git("diff", "--name-status", SOURCE, HEAD, "--", *unchanged_scope).decode()
assert not scope_diff, scope_diff
auth_state_diff = git("diff", SOURCE, HEAD, "--", "backend/src/ai_intel/api/auth_state.py").decode()
(RUN / "auth_state_scope_diff.patch").write_text(auth_state_diff, encoding="utf8")
migration_diff = git("diff", "--name-status", SOURCE, HEAD, "--", "backend/migrations", "backend/src/ai_intel/assets/inventory_models.py", "backend/src/ai_intel/assets/sbom_persistence_models.py").decode()
(RUN / "migration_model_scope_diff.log").write_text(migration_diff, encoding="utf8")
receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "exit_code": 0, "head": HEAD, "source": SOURCE, "base": BASE, "original": ORIGINAL, "source_files": source_proof, "old_tests": test_proof, "original_test_count": len(tests), "fixture_blob": "82c40263274fb65517037ab5e3f2d3982f151d67", "fixture_raw_sha256": hashlib.sha256(original_fixture).hexdigest(), "fixture_bytes": len(original_fixture), "attrs_original_git_and_raw_equal": True, "attrs_blob": git("rev-parse", HEAD + ":" + attrs_path).decode().strip(), "unchanged_scope": unchanged_scope, "scope_diff_empty": True, "resource_adapter": False, "main_buildinfo_sha256": hashlib.sha256(Path("D:/dianzi/frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest()}
assert receipt["main_buildinfo_sha256"] == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
(RUN / "fresh_source_audit.json").write_text(json.dumps(receipt, indent=2), encoding="utf8")
print(json.dumps({"source_files": len(sources), "old_test_files": len(tests), "fixture_bytes": len(original_fixture), "resource_adapter": False, "scope_diff_empty": True}))
