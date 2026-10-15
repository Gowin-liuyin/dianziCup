"""Pin raw evidence attributes and verify exact staged or committed artifact bytes."""

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
REPORT = ROOT / "reports/tasks/R07-model-fields-two-root-causes-fix.md"
CODE = "696b1d88045ee862db1af3aaf569574ad361feaf"
ZONE = ZoneInfo("Asia/Shanghai")
SOURCE_PATHS = (
    "backend/src/ai_intel/enrichment/field_sources.py",
    "backend/tests/unit/test_r07_model_fields.py",
    "backend/tests/unit/test_r07_model_field_root_causes.py",
)


def digest(content):
    return hashlib.sha256(content).hexdigest()


def relative(path):
    return path.relative_to(ROOT).as_posix()


def git_blob(ref, path):
    return subprocess.check_output(["git", "show", ref + ":" + path], cwd=ROOT)


def artifact_entry(path):
    content = path.read_bytes()
    return {"path": relative(path), "sha256": digest(content), "bytes": len(content)}


if sys.argv[1] == "attributes":
    paths = {path for path in RUN.iterdir() if path.is_file()}
    paths.add(REPORT)
    for name in ("artifact_manifest.json", "material_integrity.json"):
        paths.add(RUN / name)
    for label in ("package_diff_check", "package_diff_check_final", "scope_secret_scan_final", "scope_secret_scan_sealed", "fixed_identity", "changed_paths", "public_contract_unchanged"):
        for suffix in ("stdout.log", "stderr.log", "command.json"):
            paths.add(RUN / f"{label}.{suffix}")
    attributes = ROOT / ".gitattributes"
    existing = attributes.read_bytes().replace(b"\r\n", b"\n").decode()
    original = "\n".join(
        line for line in existing.splitlines()
        if not line.startswith(relative(RUN) + "/") and not line.startswith(relative(REPORT) + " ")
    ).encode()
    entries = []
    for path in sorted(paths):
        extra = " -diff" if path.suffix in {".log", ".xml"} else ""
        if path.suffix in {".json", ".py"}:
            extra += " whitespace=trailing-space,space-before-tab,cr-at-eol"
        entries.append(relative(path) + " -text" + extra)
    attributes.write_bytes(original.rstrip(b"\r\n") + b"\n" + "\n".join(entries).encode() + b"\n")
    print(json.dumps({"exact_paths": len(entries), "scope": relative(RUN)}))
elif sys.argv[1] == "seal":
    started = datetime.now(ZONE).isoformat()
    paths = [path for path in RUN.iterdir() if path.is_file() and path.name not in {"artifact_manifest.json", "material_integrity.json"}]
    paths += [REPORT, ROOT / ".gitattributes"]
    staged = [{**artifact_entry(path), "staged_equals_raw": git_blob("", relative(path)) == path.read_bytes()} for path in sorted(paths)]
    assert all(item["staged_equals_raw"] for item in staged)
    integrity = {
        "argv": sys.argv, "cwd": str(ROOT), "started_at_shanghai": started,
        "ended_at_shanghai": datetime.now(ZONE).isoformat(), "exit_code": 0,
        "code_sha": CODE, "verified_artifacts": len(staged), "artifacts": staged,
    }
    (RUN / "material_integrity.json").write_text(json.dumps(integrity, indent=2), encoding="utf-8")
    paths.append(RUN / "material_integrity.json")
    sources = [{"path": path, "git_blob_sha256": digest(git_blob(CODE, path)), "worktree_sha256": digest((ROOT / path).read_bytes())} for path in SOURCE_PATHS]
    manifest = {
        "status": "awaiting_review", "code_sha": CODE,
        "base_material_sha": "6199ad193d36da17c6597ee286aae40af887d425",
        "sealed_at_shanghai": datetime.now(ZONE).isoformat(), "cwd": str(ROOT),
        "source_files": sources, "artifacts": [artifact_entry(path) for path in sorted(paths)],
    }
    (RUN / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"artifacts": len(manifest["artifacts"]), "code_sha": CODE, "manifest_sha256": digest((RUN / "artifact_manifest.json").read_bytes())}))
elif sys.argv[1] == "verify":
    manifest_path = RUN / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["artifacts"]:
        path = ROOT / item["path"]
        assert path.stat().st_size == item["bytes"]
        assert digest(path.read_bytes()) == item["sha256"]
        assert git_blob("HEAD", item["path"]) == path.read_bytes()
    for item in manifest["source_files"]:
        assert digest(git_blob(CODE, item["path"])) == item["git_blob_sha256"]
        assert git_blob("HEAD", item["path"]) == git_blob(CODE, item["path"])
        assert digest((ROOT / item["path"]).read_bytes()) == item["worktree_sha256"]
    assert git_blob("HEAD", relative(manifest_path)) == manifest_path.read_bytes()
    clean = not subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip()
    assert clean
    print(json.dumps({"verified_at_shanghai": datetime.now(ZONE).isoformat(), "code_sha": CODE, "materials_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(), "manifest_sha256": digest(manifest_path.read_bytes()), "artifacts": len(manifest["artifacts"]), "clean": clean}))
