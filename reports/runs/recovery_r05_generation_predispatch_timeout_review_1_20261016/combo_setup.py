"""只复制原reviewer测试字节并准备本人的R09组合实验；不修改其它工作树。"""

import hashlib
import json
import subprocess
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
COMBO = Path("D:/wt/gen-card-r1")
ORIGINAL = Path("C:/Users/yinha/.codex/worktrees/r09-knowledge-cards-review-1/dianzi/reports/runs/recovery_r09_knowledge_cards_review_1_20261016/test_independent_boundaries.py")
copy = RUN / "test_r09_original_boundaries.py"
copy.write_bytes(ORIGINAL.read_bytes())
result = {"original_path": str(ORIGINAL), "copy_path": str(copy), "original_sha256": hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(), "copy_sha256": hashlib.sha256(copy.read_bytes()).hexdigest(), "byte_equal": copy.read_bytes() == ORIGINAL.read_bytes(), "r09_base_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=COMBO, text=True).strip(), "r09_base_tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=COMBO, text=True).strip(), "before_overlay_diff": subprocess.check_output(["git", "diff", "--name-only"], cwd=COMBO, text=True)}
(RUN / "combo_test_origin.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
for label in ("r09_original_red", "r09_combo_green"):
    command = [str(ROOT / "backend/.venv/Scripts/python.exe"), "-m", "pytest", str(copy), "--no-cov", "-q", "-p", "no:cacheprovider", "--basetemp=" + str(RUN / (label + "_temp")), "--junitxml=" + str(RUN / (label + ".xml"))]
    (RUN / (label + ".request.json")).write_text(json.dumps({"command": command, "cwd": str(COMBO / "backend")}), encoding="utf-8", newline="")
print(json.dumps(result, ensure_ascii=False))
assert result["byte_equal"] and not result["before_overlay_diff"]
