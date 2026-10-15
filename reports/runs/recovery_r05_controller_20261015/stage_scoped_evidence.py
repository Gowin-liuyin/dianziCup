"""显式枚举本批已结束运行与文档；不选当前业务草稿或仍在写的review。"""

import hashlib
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[3]
owned_roots = [
    "reports/runs/recovery_r05_controller_20261015",
    "reports/runs/recovery_r05_semantic_review_1_20261015",
    "reports/runs/recovery_r04_source_jobs_20261015/live_segment_5_after_quota_reset",
    "reports/runs/recovery_r04_source_jobs_20261015/live_segment_6_source_workspace",
    "reports/runs/recovery_r04_source_jobs_20261015/frontend_live_8f6bd9_segment5",
    "reports/runs/recovery_r04_source_jobs_20261015/frontend_live_afe490_segment6",
    "reports/runs/recovery_r04_source_jobs_20261015/real_browser_artifacts",
    "reports/runs/recovery_r04_source_jobs_20261015/real_browser_segment6_recheck_artifacts",
]
paths = [
    "progress/task_state.json", "progress/context_handoff.md", "progress/blockers.md",
    "progress/recovery_workstreams.md", "reports/stages/recovery/G-B.md", "reports/tasks/R05.md",
    "reports/reviews/recovery/G-B-R05-semantic-review-1.md",
    "frontend/e2e/r04_real_sources.spec.ts", "frontend/e2e/r17_real_source_workspace.spec.ts",
]
for directory in owned_roots:
    for path in sorted((root / directory).rglob("*")):
        if path.is_file() and path.suffix in {".py", ".ps1", ".json", ".jsonl", ".xml", ".log", ".md", ".png", ".txt"}:
            paths.append(path.relative_to(root).as_posix())
source_run = "reports/runs/recovery_r04_source_jobs_20261015/"
for name in ("prepare_segment5.py", "supervise_windows_segment5.py", "launch_windows_segment5.ps1", "serve_frontend_segment5.py", "collect_live_segment5.py", "segment5_preparation.json", "prepare_segment6.py", "supervise_windows_segment6.py", "launch_windows_segment6.ps1", "serve_frontend_segment6.py", "segment6_preparation.json", "playwright_live.config.mjs", "playwright_live_recheck.config.mjs", "prepare_browser_segment6_recheck.py", "run_real_browser_segment6.py", "run_real_browser_segment6.ps1", "run_real_browser_segment6_recheck.py", "run_real_browser_segment6_recheck.ps1", "real_browser_segment6.json", "real_browser_segment6.log", "real_browser_segment6_recheck.json", "real_browser_segment6_recheck.log", "ui_timestamp/source_workspace_integrated.json", "ui_timestamp/source_workspace_integrated.log"):
    paths.append(source_run + name)
records = [{"path": path, "sha256": hashlib.sha256((root / path).read_bytes()).hexdigest(),
            "bytes": (root / path).stat().st_size} for path in dict.fromkeys(paths)]
manifest = Path(__file__).resolve().parent / "scoped_evidence_manifest.json"
assert not manifest.exists()
manifest.write_text(json.dumps({"files": records, "not_selected": ["retrieval/service.py draft", "vector foundation review in progress", "active MinIO log", "unrelated original files"]}, indent=2), encoding="utf-8")
paths.append(manifest.relative_to(root).as_posix())
for path in dict.fromkeys(paths):
    subprocess.run(["git", "add", "--", path], cwd=root, check=True, capture_output=True)
print(json.dumps({"explicitly_added": len(set(paths)), "bytes": sum(record["bytes"] for record in records)}))
