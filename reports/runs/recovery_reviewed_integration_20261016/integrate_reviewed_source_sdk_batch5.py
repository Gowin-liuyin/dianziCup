"""按冻结 Git blob 集成独审通过的来源证据与 SDK 入口，核查依赖闭包。"""

import ast
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent


def git(directory, *arguments):
    return subprocess.check_output(["git", *arguments], cwd=directory)


started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
head = git(ROOT, "rev-parse", "HEAD").decode().strip()
assert not git(ROOT, "diff", "--cached", "--name-only").strip()
protected = ROOT / "frontend/tsconfig.tsbuildinfo"
protected_hash = hashlib.sha256(protected.read_bytes()).hexdigest()
assert protected_hash == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
packages = [
    (Path("D:/wt/r06-source-excerpt-event-proof"), "8355adbd9521e0dec99374b3bbb28bb6449e0fbc", "source_proof"),
    (Path("D:/wt/r18-sdk-canonical-verification-integration"), "02ce8d6b8072253c26a5df1a49e1b574f2668498", "sdk_tests"),
]
entries = []
for directory, source, label in packages:
    files = git(directory, "diff-tree", "--no-commit-id", "--name-only", "-r", source).decode().splitlines()
    assert len(files) == (3 if label == "source_proof" else 16)
    for relative in files:
        assert relative.startswith("backend/") if label == "source_proof" else relative.startswith("sdk/python/tests/")
        assert not git(ROOT, "diff", "--", relative).strip(), "pre-existing modification: " + relative
        target = ROOT / relative
        raw = git(directory, "show", source + ":" + relative)
        if target.exists():
            old = git(directory, "show", source + "^:" + relative)
            assert target.read_bytes().replace(b"\r\n", b"\n") == old, "baseline divergence: " + relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        assert git(ROOT, "hash-object", "--path", relative, str(target)).decode().strip() == git(directory, "rev-parse", source + ":" + relative).decode().strip()
        entries.append({"path": relative, "source_sha": source, "canonical_sha256": hashlib.sha256(raw).hexdigest()})

closure = []
for entry in entries:
    tree = ast.parse((ROOT / entry["path"]).read_bytes())
    for node in ast.walk(tree):
        modules = []
        if isinstance(node, ast.Import):
            modules = [item.name for item in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules = [node.module]
        for module in modules:
            if module.startswith("ai_intel."):
                base = ROOT / "backend/src" / Path(*module.split("."))
            elif module.startswith("ai_intel_client"):
                base = ROOT / "sdk/python" / Path(*module.split("."))
            elif module == "r18_test_paths":
                base = ROOT / "sdk/python/tests/r18_test_paths"
            else:
                continue
            assert base.with_suffix(".py").exists() or (base / "__init__.py").exists() or base.is_dir(), "missing import: " + module
            closure.append({"consumer": entry["path"], "module": module})
assert hashlib.sha256(protected.read_bytes()).hexdigest() == protected_hash
receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "baseline_sha": head, "files": entries, "internal_imports_checked": closure, "protected_buildinfo_unchanged": True, "test_status": "not_run", "stage_gate": "not_accepted"}
(RUN / "reviewed_source_sdk_batch5.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"files_integrated": len(entries), "internal_imports_checked": len(closure), "protected_buildinfo_unchanged": True}))
