"""Seal owned artifacts and verify unchanged old entry points without publishing private bytes."""

import ast
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
BASE = "8a1b04d48346d8550f0326a77f003246a0ebbab5"
CODE = "a89e94b66e240a0c958f7b7e2b8dc22e88f79348"
REPORT = ROOT / "reports/tasks/R06-bulk-source-evidence.md"
RAW_PATH = Path("D:/dianzi-local-evidence/recovery_r06_live_segment_8a_20261016/release_raw.bin")


def git(*arguments):
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, check=True).stdout


def definition(blob, name):
    content = blob.decode()
    lines = content.splitlines(keepends=True)
    node = next(node for node in ast.parse(content).body if isinstance(node, ast.FunctionDef)
                and node.name == name)
    return "".join(lines[node.lineno - 1:node.end_lineno]).encode()


def main():
    assert git("rev-parse", "HEAD").decode().strip() == CODE
    tree = git("rev-parse", "HEAD^{tree}").decode().strip()
    assert tree == "25bcfe534c447b5b83d4bceed9b1393cfb266109"
    revisions_path = "backend/src/ai_intel/knowledge/revisions.py"
    before, after = (git("show", revision + ":" + revisions_path) for revision in (BASE, CODE))
    unchanged = {}
    for name in ("add_text_block", "attach_evidence_span", "save_document_revision",
                 "register_response_content"):
        left, right = definition(before, name), definition(after, name)
        assert left == right
        unchanged[name] = hashlib.sha256(right).hexdigest()
    old_test = "backend/tests/integration/test_r04_source_documents.py"
    old_bytes = git("show", BASE + ":" + old_test)
    assert old_bytes == git("show", CODE + ":" + old_test)
    assert not git("diff", "8d48c95ec525536435c80379f87559a42511a75e", CODE, "--", "backend/src")
    launches = []
    cutoff = "2026-10-16T04:15:51"
    for receipt_path in sorted(RUN.glob("*.command.json")):
        receipt = json.loads(receipt_path.read_text())
        actual = receipt["command"]
        if receipt["started_at"] >= cutoff:
            actual = [actual[0], str(RUN / "measure_cpu.py"), *actual[1:]]
        launches.append({"receipt": receipt_path.name, "canonical_check": receipt["command"],
                         "actual_child_argv": actual})
    (RUN / "runner_launches.json").write_text(json.dumps(launches, indent=2))
    private = json.loads(subprocess.run([
        "wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat",
        "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
    ], capture_output=True, text=True, check=True).stdout)
    sensitive = [private["postgres_password"].encode(), private["TEST_DATABASE_URL"].encode()]
    raw = RAW_PATH.read_bytes()
    assert len(raw) == 616865
    assert hashlib.sha256(raw).hexdigest() == (
        "25e00623a07dcafe8d8d6b3535e400e078ef758e965742a37fe76d5186bb69f7"
    )
    owned_paths = [REPORT, *sorted(path for path in RUN.rglob("*") if path.is_file()
                                 and "__pycache__" not in path.parts
                                 and path.name not in {"artifact_manifest.json", "material_seal.json"})]
    for path in owned_paths:
        content = path.read_bytes()
        assert raw not in content, path.name
        assert all(secret not in content for secret in sensitive), path.name
    changed_files = git("diff", "--name-only", BASE, CODE).decode().splitlines()
    code_files = [{"path": name, "bytes": len((ROOT / name).read_bytes()),
                   "sha256": hashlib.sha256((ROOT / name).read_bytes()).hexdigest()}
                  for name in changed_files]
    artifact_rows = [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                     for path in owned_paths]
    manifest = {
        "recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "status": "awaiting_review", "implementation": "complete",
        "base_commit": BASE, "code_commit": CODE, "code_tree": tree,
        "unchanged_legacy_definitions_sha256": unchanged,
        "unchanged_r04_test_blob_sha256": hashlib.sha256(old_bytes).hexdigest(),
        "code_files": code_files, "artifacts": artifact_rows,
        "raw_external_only": {"path": str(RAW_PATH), "bytes": len(raw),
                              "sha256": hashlib.sha256(raw).hexdigest()},
        "actual_author_raw_handler_invocations": 2, "live": "not_run",
        "resource_limit": "author did not apply diagnostic Windows CPU/memory caps",
        "secret_scan_passed": True, "raw_body_scan_passed": True,
    }
    manifest_path = RUN / "artifact_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    seal = {
        "code_commit": CODE, "code_tree": tree,
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "report_sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest(),
        "artifact_count": len(artifact_rows), "source_files": 3,
    }
    (RUN / "material_seal.json").write_text(json.dumps(seal, indent=2))
    print(json.dumps(seal))


if __name__ == "__main__":
    main()
