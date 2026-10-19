"""记录冻结范围、只读输入和组合实验创建命令；无业务写入。"""

import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
paths = [
    ROOT / "AGENTS.md", ROOT / "docs/plan/00_execution_map.md",
    ROOT / "docs/plan/03_data_contracts.md", ROOT / "docs/plan/05_api_and_tool_contracts.md",
    ROOT / "docs/plan/12_recovery_task_cards_20261014.md", ROOT / "docs/tasks/T18_model_clients.md",
    ROOT / "docs/tasks/T31_grounded_qa_baseline.md", ROOT / "progress/task_state.json",
    ROOT / "progress/context_handoff.md", ROOT / "backend/uv.lock",
    Path("C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md"),
    Path("D:/wt/r07-model-fields-two-root-causes-fix/backend/src/ai_intel/enrichment/model_fields.py"),
    Path("C:/Users/yinha/.codex/worktrees/r09-knowledge-cards/dianzi/backend/src/ai_intel/enrichment/card_extraction.py"),
    Path("C:/Users/yinha/.codex/worktrees/r09-knowledge-cards-review-1/dianzi/reports/reviews/recovery/G-C-R09-knowledge-cards-review-1.md"),
]
inputs = [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": len(path.read_bytes())} for path in paths]
state = json.loads((ROOT / "progress/task_state.json").read_bytes())
source = "backend/src/ai_intel/infrastructure/models/generation.py"
result = {"recorded_at": datetime.now(timezone(timedelta(hours=8))).isoformat(), "inputs": inputs,
          "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
          "tracked_diff": subprocess.check_output(["git", "diff", "--name-only"], cwd=ROOT, text=True),
          "source_blob": subprocess.check_output(["git", "rev-parse", "47c47bc2b5d537166ee47a01c2ab14c035466e3d:" + source], cwd=ROOT, text=True).strip(),
          "task_state": {name: state["tasks"][name] for name in ("T18", "T31")},
          "siblings": {str(path): subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip() for path in [Path("D:/wt/r07-model-fields-two-root-causes-fix"), Path("C:/Users/yinha/.codex/worktrees/r09-knowledge-cards/dianzi")]},
          "unexecuted": ["integration", "frontend", "e2e", "live", "manual"]}
(RUN / "scope_inputs.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
(RUN / "combo_create.request.json").write_text(json.dumps({"command": ["git", "-c", "core.longpaths=true", "worktree", "add", "-b", "codex/r05-timeout-card-combination-review-1", "D:/wt/gen-card-r1", "ed217564e9cf3571b430d0fe7caa4d3999c7320b"], "cwd": str(ROOT)}, ensure_ascii=False), encoding="utf-8", newline="")
print(json.dumps({"inputs": len(inputs), "tracked_diff": result["tracked_diff"], "siblings": result["siblings"]}, ensure_ascii=False))
