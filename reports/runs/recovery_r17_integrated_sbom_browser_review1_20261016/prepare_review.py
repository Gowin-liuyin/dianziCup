"""Verify frozen source and mount only the exact missing original test resource."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
BASE = "17ab90e0a6b100530a3078dd525f9086813c9728"
SOURCE = "4a17fa3fb7357a8c2b9d647f62c875958a24a27d"
MATERIAL = "f1f2bc49ccd33be7e0b150482b253399a4ad7c64"
ORIGINAL = "5587deb124f06b9aa14fb7feb22cdc9493ae4883"

def git(*argv):
    return subprocess.check_output(["git", *argv], cwd=ROOT)

paths = git("ls-tree", "-r", "--name-only", BASE, "frontend").decode().splitlines()
tests = [path for path in paths if re.search(r"\.(test|spec)\.[cm]?[jt]sx?$", path)]
original_tests = [path for path in git("ls-tree", "-r", "--name-only", ORIGINAL, "frontend").decode().splitlines() if re.search(r"\.(test|spec)\.[cm]?[jt]sx?$", path)]
protected = []
for path in tests:
    values = {revision: git("rev-parse", revision + ":" + path).decode().strip() for revision in (BASE, SOURCE, MATERIAL, ORIGINAL)}
    assert len(set(values.values())) == 1, path
    protected.append({"path": path, "blob": values[BASE]})
assert tests == original_tests
changed = git("diff", "--name-only", BASE, SOURCE).decode().splitlines()
assert len(changed) == 5
source_files = []
for path in changed:
    assert git("rev-parse", SOURCE + ":" + path) == git("rev-parse", MATERIAL + ":" + path)
    source_files.append({"path": path, "blob": git("rev-parse", SOURCE + ":" + path).decode().strip(), "raw_sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest()})
fixture_path = "reports/runs/recovery_r17_sbom_workbench_20261016/backend_contract_samples.json"
target = ROOT / fixture_path
assert not target.exists()
fixture = git("show", ORIGINAL + ":" + fixture_path)
assert hashlib.sha256(fixture).hexdigest() == "92f5a0cac56ccd97c63af16bd14418cbc1c42cf4803c3ab6627f419235a6e331"
assert git("rev-parse", ORIGINAL + ":" + fixture_path).decode().strip() == "82c40263274fb65517037ab5e3f2d3982f151d67"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(fixture)
(RUN / "backend_contract_samples.original.json").write_bytes(fixture)
receipt = {"base": BASE, "source": SOURCE, "material": MATERIAL, "original": ORIGINAL, "protected_test_count": len(tests), "protected_tests": protected, "source_files": source_files, "changed": changed, "fresh_fixture_present": False, "resource_adapter": {"path": fixture_path, "original_blob": "82c40263274fb65517037ab5e3f2d3982f151d67", "raw_sha256": hashlib.sha256(fixture).hexdigest(), "bytes": len(fixture), "temporary_only": True}, "main_buildinfo_sha256": hashlib.sha256(Path("D:/dianzi/frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest()}
(RUN / "source_resource_audit.json").write_text(json.dumps(receipt, indent=2), encoding="utf8")
print(json.dumps({"protected_test_count": len(tests), "changed_count": len(changed), "resource_adapter_bytes": len(fixture)}))
