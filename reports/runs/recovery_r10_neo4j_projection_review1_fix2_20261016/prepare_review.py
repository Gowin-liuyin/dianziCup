"""Verify frozen input archives and adapt only this review's isolated resources."""

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PRIOR1 = Path("D:/wt/r10-neo4j-projection-review1/reports/runs/recovery_r10_neo4j_projection_review1_20261016")
PRIOR2 = Path("D:/wt/r10-neo4j-projection-review1-fix1/reports/runs/recovery_r10_neo4j_projection_review1_fix1_20261016")
CODE = "707331add19f3f8eed4ba530305113028d3caedb"
TIP = "e8e4086fccc2d9c3f2f582f85e185f5b6f395f0b"
BASE = "28a35f16ad1ebe08a49b63126b2c6fc828607333"
NAMESPACE = "r10_review1_fix2_"

def git(*arguments):
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, check=True).stdout

def verified_archive(directory, expected, member):
    manifest = json.loads((directory / "raw_evidence_manifest.json").read_text())
    archive_path = directory / "raw_evidence.zip"
    assert hashlib.sha256(archive_path.read_bytes()).hexdigest() == expected
    with zipfile.ZipFile(archive_path) as archive:
        for entry in manifest["files"]:
            raw = archive.read(entry["path"])
            assert hashlib.sha256(raw).hexdigest() == entry["raw_sha256"]
            assert len(raw) == entry["length_bytes"]
        raw = archive.read(member) if member else b""
    return raw, len(manifest["files"])

assert git("rev-parse", "HEAD").decode().strip() == TIP
assert git("rev-parse", TIP + "^{tree}").decode().strip() == "2a20e50bd91bf88c68ecf00a1938855e149cab34"
old11, count1 = verified_archive(PRIOR1, "02b0b1176f9b198d5a2ed19e6ad42f669bbd77f7fb690331563cb093ef7564d6",
    "reports/runs/recovery_r10_neo4j_projection_review1_20261016/adapted_tests/test_review_boundaries.py")
old2, count2 = verified_archive(PRIOR2, "ce2728db0520810676c5619fe1b2c43280332b9ea51ebdc9008809d0ce48c1c5",
    "reports/runs/recovery_r10_neo4j_projection_review1_fix1_20261016/adapted_tests/test_recheck_epoch_boundary.py")
assert hashlib.sha256(old11).hexdigest() == "6d8565c06cb64bd8bacbdb8aff81dfc3908842088cd0eec17094dc835b959cf1"
assert hashlib.sha256(old2).hexdigest() == "3e1e767d7c01ee18b02888c56509676dfa020c5b79d8a8506b7afc216b83ae09"
author = ROOT / "reports/runs/recovery_r10_neo4j_projection_fix2_20261016"
assert hashlib.sha256((author / "raw_evidence_manifest.json").read_bytes()).hexdigest() == "313ec07323e8aa2ea8e108c1bdbe97b36de4308310cad90c1a89371b43229e47"
_unused, count3 = verified_archive(author, "66804358f1a1db15ab6f7c65393c7ba9cb6a5ab93da5e3009ea079ac426d6216", None)
assert count3 == 55

runner = (PRIOR2 / "review_runner.py").read_text(encoding="utf-8")
for old, new in {
    'CODE = "9a6c8d66aaf163321c0d19339aa92637e31bcd31"': f'CODE = "{CODE}"',
    'TIP = "28a35f16ad1ebe08a49b63126b2c6fc828607333"': f'TIP = "{TIP}"',
    'BASE = "997d8cc9b3e0c220e88214d728cb9e7c45ee68a5"': f'BASE = "{BASE}"',
    "test_dianzi_r10_projection_review1_fix1_20261016": "test_dianzi_r10_projection_review1_fix2_20261016",
    "r10_projection_review1_fix1_20261016": "r10_projection_review1_fix2_20261016",
    "test_r10r1f1_": "test_r10r1f2_",
    '"r10_review1_fix1_"': f'"{NAMESPACE}"',
    'url.password, neo["NEO4J_TEST_PASSWORD"]': 'url.password, url.username, neo["NEO4J_TEST_PASSWORD"]',
}.items():
    runner = runner.replace(old, new)
runner = runner.replace("hook += '\\n@pytest.fixture", "hook += '\\n@pytest.fixture")
needle = "    (adapted / \"conftest.py\").write_text(hook, encoding=\"utf-8\", newline=\"\\n\")"
runner = runner.replace(needle, "    hook += '    register_sensitive_failure_value(SecretStr(unquote(urlsplit(os.environ[\"TEST_DATABASE_URL\"]).username or \"\")))\\n'\n" + needle)
runner = runner.replace('raw = path.read_bytes()\n                for value in sensitive:',
    'raw = path.read_bytes()\n                if path.name in ("review_runner.py", "prepare_review.py"):\n                    raw = raw.replace(b"test_dianzi_r01_20261014", b"[public isolated base database identifier]")\n                for value in sensitive:')
(RUN / "review_runner.py").write_text(runner, encoding="utf-8", newline="\n")
adapted = RUN / "adapted_tests"
adapted.mkdir(exist_ok=True)
(RUN / "original_review_probes.py").write_bytes(old11)
(RUN / "original_epoch_probe.py").write_bytes(old2)
(adapted / "test_review_boundaries.py").write_bytes(old11.replace(b"r10_review1_", NAMESPACE.encode()))
(adapted / "test_recheck_epoch_boundary.py").write_bytes(old2.replace(b"r10_review1_fix1_", NAMESPACE.encode()))
for name, prefix in (("test_r10_projection_fix1_markers.py", b"r10_fix1_"), ("test_r10_projection_fix2_empty_reads.py", b"r10_fix2_")):
    original = ROOT / "backend/tests/integration" / name
    (adapted / name).write_bytes(original.read_bytes().replace(prefix, NAMESPACE.encode()))

frozen = json.loads((author / "frozen_code_verification.json").read_text())
facts = {}
for name, fact in frozen["source"].items():
    raw = (ROOT / name).read_bytes()
    normalized = raw.replace(b"\r\n", b"\n")
    blob = git("rev-parse", TIP + ":" + name).decode().strip()
    assert blob == fact["frozen_blob"]
    assert hashlib.sha256(normalized).hexdigest() == fact["git_lf_sha256"]
    assert hashlib.sha1(b"blob " + str(len(normalized)).encode() + b"\0" + normalized).hexdigest() == blob
    facts[name] = {"blob": blob, "raw_sha256": hashlib.sha256(raw).hexdigest(), "git_lf_sha256": hashlib.sha256(normalized).hexdigest()}
before = dict(line.decode().split("\t", 1)[::-1] for line in git("ls-tree", "-r", BASE).splitlines())
after = dict(line.decode().split("\t", 1)[::-1] for line in git("ls-tree", "-r", TIP).splitlines())
protected = {path: value for path, value in before.items() if path != "backend/src/ai_intel/knowledge/graph_projection.py"}
assert len(protected) == 13005 and all(after[path] == value for path, value in protected.items())
assert not git("diff", "--name-only", CODE, TIP, "--", "backend/src", "backend/tests")
(RUN / "input_verification.json").write_text(json.dumps({"code_sha": CODE, "materials_sha": TIP,
    "material_tree": "2a20e50bd91bf88c68ecf00a1938855e149cab34", "base_sha": BASE,
    "prior_review_archive_members": count1, "fix1_review_archive_members": count2,
    "author_fix2_archive_members": count3, "all_archive_hashes_verified": True,
    "protected_original_objects": len(protected), "source": facts,
    "old11_probe_sha256": hashlib.sha256(old11).hexdigest(), "old2_probe_sha256": hashlib.sha256(old2).hexdigest(),
    "only_probe_adaptation": "owned namespace prefix", "old_raw_files_changed": False}, indent=2), encoding="utf-8")
print(json.dumps({"verified": True, "archive_members": [count1, count2, count3], "protected": len(protected)}))
