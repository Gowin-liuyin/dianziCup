"""核对742冻结源和原97证据；报告计数来自独立XML，不使用作者通过声明。"""

import gzip
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from review_runner import OLD_RUN, ROOT, RUN, now

CODE = "7428515366804d92d692e6989994a716ca1c7d26"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def main():
    started = now()
    old_manifest_raw = (OLD_RUN / "artifact_manifest.json").read_bytes()
    assert sha(old_manifest_raw) == "0cc00f729e88152ccf4f527f6861f21c19709be303c8e73bd30844414a77f5a7"
    old_manifest = json.loads(old_manifest_raw)
    old_root = OLD_RUN.parents[2]
    for entry in old_manifest["entries"]:
        assert sha((old_root / entry["path"]).read_bytes()) == entry["sha256"]
    changes = git("diff", "--name-only", "c0369e6b", CODE).decode().splitlines()
    kept = ["backend/src/ai_intel/assets/sbom_parser.py", "backend/src/ai_intel/assets/manifest_parser.py",
            "backend/src/ai_intel/assets/inventory_models.py", "backend/src/ai_intel/assets/sbom_persistence_models.py",
            "backend/src/ai_intel/assets/inventory_routes.py", "backend/src/ai_intel/assets/inventory_contracts.py",
            "backend/src/ai_intel/infrastructure/models/json_output.py", "backend/tests/conftest.py",
            "backend/pyproject.toml", "backend/uv.lock", "progress/task_state.json"]
    output = RUN / "source_blobs"
    output.mkdir(exist_ok=True)
    sources = []
    for index, name in enumerate(changes + kept):
        frozen = git("show", CODE + ":" + name)
        if name in kept:
            assert frozen == git("show", "c0369e6b:" + name)
        expected_blob = git("rev-parse", CODE + ":" + name).decode().strip()
        actual_blob = git("hash-object", "--path=" + name, name).decode().strip()
        assert expected_blob == actual_blob
        target = output / (f"{index:02d}_" + Path(name).name + ".gz")
        target.write_bytes(gzip.compress(frozen, mtime=0))
        sources.append({"path": name, "code_sha256": sha(frozen), "git_blob": actual_blob,
                        "unchanged_from_c036": name in kept, "blob_copy": target.relative_to(ROOT).as_posix()})
    summary = {}
    for name in ("pure", "pg_sbom", "pg_legacy", "pg_old", "pg_new", "pg_corrected", "pg_nullmeta"):
        cases = list(ET.parse(RUN / (name + ".xml")).getroot().iter("testcase"))
        result = {kind: sum(case.find(kind) is not None for case in cases) for kind in ("failure", "error", "skipped")}
        result.update(tests=len(cases), passed=len(cases) - sum(result.values()))
        result["groups"] = {group: sum(group in case.attrib.get("classname", "") for case in cases)
                            for group in ("unit", "contract", "security")}
        summary[name] = result
    receipt = {"start": started, "end": now(), "code_commit": CODE, "old_manifest_sha256": sha(old_manifest_raw),
               "old_verified_entries": len(old_manifest["entries"]), "changed_paths": changes, "sources": sources,
               "independent_junit": summary, "current_head": git("rev-parse", "HEAD").decode().strip()}
    (RUN / "source_audit.json").write_bytes(json.dumps(receipt, indent=2, ensure_ascii=False).encode())
    print(json.dumps({key: receipt[key] for key in ("code_commit", "old_verified_entries", "changed_paths", "independent_junit")}, indent=2))


if __name__ == "__main__":
    main()
