"""封存本轮独立报告与原始证据；不把缓存、index或自身hash纳入清单。"""

import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
REPORT = ROOT / "reports/reviews/recovery/G-B-R05-generation-predispatch-timeout-review-1.md"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


tracked = subprocess.check_output(["git", "diff", "--name-only"], cwd=ROOT, text=True)
staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True)
assert not tracked and not staged
status = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, text=True)
allowed = ["reports/reviews/recovery/G-B-R05-generation-predispatch-timeout-review-1.md", str(RUN.relative_to(ROOT)).replace("\\", "/") + "/"]
assert all(line.startswith("?? ") and any(line[3:].startswith(path) for path in allowed) for line in status.splitlines())
copied = RUN / "test_r09_original_boundaries.py"
original = Path("C:/Users/yinha/.codex/worktrees/r09-knowledge-cards-review-1/dianzi/reports/runs/recovery_r09_knowledge_cards_review_1_20261016/test_independent_boundaries.py")
assert copied.read_bytes() == original.read_bytes()
combo_diff = subprocess.check_output(["git", "diff", "--name-only"], cwd="D:/wt/gen-card-r1", text=True).splitlines()
assert combo_diff == ["backend/src/ai_intel/infrastructure/models/generation.py"]
records = [json.loads(path.read_bytes()) for path in sorted(RUN.glob("*.command.json"))]
index = {"recorded_at": datetime.now(timezone(timedelta(hours=8))).isoformat(), "commands": records, "main_tracked_diff": tracked, "main_staged_diff": staged, "newfile_scope_checked": True, "combo_diff": combo_diff, "r09_original_copy_unchanged": True, "unique_tests": {"regression": 289, "regression_layers": {"unit": 219, "contract": 46, "security": 24}, "independent_r05_qa": 45, "r09_original_replayed": 17, "r09_precise_new": 1}, "overlap_rule": "Earlier runs and repeated cases do not increase the denominator"}
(RUN / "command_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
excluded = {"artifact_manifest.json", "artifact_manifest.sha256", "combo_private_index"}
paths = [REPORT]
for path in sorted(RUN.rglob("*")):
    if not path.is_file() or path.name in excluded or path.name.startswith("seal_"):
        continue
    if any(part.endswith("_temp") or part.endswith("_cache") or part == "__pycache__" for part in path.relative_to(RUN).parts):
        continue
    paths.append(path)
artifacts = [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": digest(path), "bytes": path.stat().st_size} for path in paths]
manifest = {"schema_version": 1, "recorded_at": datetime.now(timezone(timedelta(hours=8))).isoformat(), "reviewer": "/root/r05_generation_predispatch_timeout_independent_review", "code_sha": "47c47bc2b5d537166ee47a01c2ab14c035466e3d", "material_sha": "df0faafb64327be190803089f0058f9b5dc2427b", "combo_tree": "b036c1b800c60405e97a7346ee6d327b00e3754a", "review_path": str(REPORT.relative_to(ROOT)).replace("\\", "/"), "verdict": "Ship limited to shared generation predispatch timeout fix", "verification": {"unit": "passed", "contract": "passed", "security": "passed", "integration": "not_run", "frontend": "not_run", "e2e": "not_run", "live": "not_run", "manual": "not_run"}, "artifacts": artifacts, "excluded": ["manifest body and sidecar", "seal command and post-seal verification receipts", "tool caches, pytest temporary files, temporary git index"], "tracked_diff_empty": True}
manifest_path = RUN / "artifact_manifest.json"
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
body_hash = digest(manifest_path)
(RUN / "artifact_manifest.sha256").write_text(body_hash + "  artifact_manifest.json\n", encoding="ascii", newline="")
print(json.dumps({"manifest_sha256": body_hash, "artifacts": len(artifacts), "report_path": str(REPORT), "report_sha256": digest(REPORT), "tracked_diff_empty": True}, ensure_ascii=False))
