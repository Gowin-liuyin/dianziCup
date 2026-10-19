"""Seal the independent report, exact file roster, source Git proof and evidence hashes."""

import hashlib
import json
from pathlib import Path
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PREP = ROOT / "reports/runs/recovery_r06_live_restart_preparation_20261016"
PRODUCT = Path("D:/wt/r06-live-e310-20261016")
PRODUCT_SHA = "e310f7735bd499c4d9fbcefe8a644e2309a16a62"
TOOL_SHA = "44c94151840213d9e5ab7c653778d4ae3219c630"
OLD_SHA = "bae3138d103427d659d7fdc0a8a195088dd42f2e"
BASE = "b08824f738ca185776916ae02689d8507f956c5c"
REPORT = ROOT / "reports/reviews/recovery/G-C-R06-six-hour-restart-guard-review-1.md"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*arguments, root=ROOT):
    return subprocess.check_output(["git", *arguments], cwd=root)


def save(name, value):
    (RUN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    assert git("rev-parse", "HEAD").decode().strip() == TOOL_SHA
    assert git("rev-parse", "HEAD", root=PRODUCT).decode().strip() == PRODUCT_SHA
    assert not git("status", "--porcelain", root=PRODUCT).strip()
    correction = json.loads((PREP / "openprocess_exact_diff.json").read_bytes())
    diff = git("diff", correction["reviewed_tool_sha"], TOOL_SHA, "--", *correction["semantic_diff_files"])
    assert diff.decode("utf-8") == correction["unified_diff"]
    freeze_outputs = []
    for name in ("artifact_manifest.json", "package_verification.json", "verify_package.log"):
        relative = (PREP / name).relative_to(ROOT).as_posix()
        raw, frozen = (PREP / name).read_bytes(), git("show", TOOL_SHA + ":" + relative)
        assert raw == frozen
        freeze_outputs.append({"path": relative, "raw_sha256": sha(raw), "git_blob_sha256": sha(frozen), "bytes": len(raw), "match": True})
    save("frozen_output_proof.json", {"tool_sha": TOOL_SHA, "files": freeze_outputs,
                                    "exact_semantic_diff_sha256": sha(diff), "exact_semantic_diff_bytes": len(diff),
                                    "exact_semantic_diff_files": correction["semantic_diff_files"]})
    sources = []
    for name in ("authorization.py", "controlled_supervise.py", "runtime_limits.py", "stop_controller.py",
                 "windows_actor.py", "deploy_runtime_entry.py", "runtime_controls.py", "owned_stop_watcher.py", "task_fence.py"):
        relative = (PREP / name).relative_to(ROOT).as_posix()
        raw = (PREP / name).read_bytes()
        frozen, old = git("show", TOOL_SHA + ":" + relative), git("show", OLD_SHA + ":" + relative)
        assert raw == frozen
        sources.append({"path": relative, "raw_sha256": sha(raw), "git_blob_sha256": sha(frozen),
                        "old_blob_sha256": sha(old), "raw_git_match": True,
                        "normalized_semantic_change": frozen.replace(b"\r\n", b"\n") != old.replace(b"\r\n", b"\n")})
    assert [Path(row["path"]).name for row in sources if row["normalized_semantic_change"]] == ["stop_controller.py", "windows_actor.py"]
    product_sources = []
    for relative in ("backend/src/ai_intel/workers/runtime.py", "backend/src/ai_intel/workers/executor.py", "backend/src/ai_intel/workers/jobs.py",
                     "backend/src/ai_intel/ingestion/source_jobs.py", "backend/src/ai_intel/ingestion/source_polling.py",
                     "backend/src/ai_intel/infrastructure/network.py", "backend/src/ai_intel/infrastructure/dns_resolver.py",
                     "backend/src/ai_intel/infrastructure/http_transport.py"):
        raw, frozen = (PRODUCT / relative).read_bytes(), git("show", PRODUCT_SHA + ":" + relative, root=PRODUCT)
        assert raw.replace(b"\r\n", b"\n") == frozen.replace(b"\r\n", b"\n")
        product_sources.append({"path": relative, "source_git_sha": PRODUCT_SHA, "raw_sha256": sha(raw),
                                "git_blob_sha256": sha(frozen), "raw_git_match": raw == frozen,
                                "normalized_match": True, "normalization": "CRLF to LF only, raw hashes kept separate"})
    save("source_git_proof.json", {"tool_sha": TOOL_SHA, "tool_sources": sources, "product_sha": PRODUCT_SHA, "product_sources": product_sources})
    own_prefix = RUN.relative_to(ROOT).as_posix() + "/"
    own_report = REPORT.relative_to(ROOT).as_posix()
    untracked = [item.decode() for item in git("ls-files", "--others", "--exclude-standard", "-z").split(b"\0") if item]
    assert all(path == own_report or path.startswith(own_prefix) for path in untracked)
    assert not git("diff", "--name-only").strip()
    assert not git("diff", "--cached", "--name-only").strip()
    changed = git("diff", "--name-only", BASE, TOOL_SHA).decode().splitlines()
    assert all(path.startswith("reports/runs/recovery_r06_live_restart_preparation_20261016/") or
               path in ("reports/tasks/R06-live-restart-preparation.md", "reports/tasks/.gitattributes") for path in changed)
    save("scoped_diff_identity.json", {"tool_sha": TOOL_SHA, "product_sha": PRODUCT_SHA,
                                       "author_changed_files_from_b088": changed,
                                       "review_owned_files_before_seal": untracked, "tracked_review_changes": [],
                                       "index_changes": [], "formal_six_hour_pass": False, "gate_absent": not (PREP / "root_live_authorization.json").exists()})
    report_raw = REPORT.read_bytes()
    save("final_receipt.json", {"sealed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
                                "report_path": str(REPORT), "report_sha256": sha(report_raw), "tool_sha": TOOL_SHA,
                                "author_manifest_sha256": sha((PREP / "artifact_manifest.json").read_bytes()),
                                "verdict": "Ship: restart guard preparation slice only", "source_http": 0, "product_pg": 0,
                                "model_provider": 0, "service_starts": 0, "formal_six_hour_pass": False})
    excluded = {"review_artifact_manifest.json", "review_artifact_manifest.sha256"}
    files = [REPORT] + sorted(path for path in RUN.rglob("*") if path.is_file() and path.name not in excluded and "tool_cache" not in path.parts)
    manifest = {"tool_sha": TOOL_SHA, "product_sha": PRODUCT_SHA, "report_sha256": sha(report_raw),
                "excluded_transient_directories": ["tool_cache"],
                "files": [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                           "sha256": sha(path.read_bytes())} for path in files]}
    save("review_artifact_manifest.json", manifest)
    manifest_sha = sha((RUN / "review_artifact_manifest.json").read_bytes())
    (RUN / "review_artifact_manifest.sha256").write_text(manifest_sha + "\n", encoding="utf-8")
    print(json.dumps({"report_sha256": sha(report_raw), "review_material_sha256": manifest_sha,
                      "author_material_sha256": sha((PREP / "artifact_manifest.json").read_bytes()),
                      "review_file_count": len(files), "author_changed_file_count": len(changed), "tool_sha": TOOL_SHA}))


if __name__ == "__main__":
    main()
