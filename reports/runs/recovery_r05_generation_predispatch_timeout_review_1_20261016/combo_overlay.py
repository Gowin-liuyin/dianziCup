"""在本人的组合工作树只叠加冻结GenerationClient，并用独立index计算树。"""

import hashlib
import json
import os
import subprocess
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
COMBO = Path("D:/wt/gen-card-r1")
SOURCE = "backend/src/ai_intel/infrastructure/models/generation.py"
CODE = "47c47bc2b5d537166ee47a01c2ab14c035466e3d"
before = (COMBO / SOURCE).read_bytes()
fixed = subprocess.check_output(["git", "show", CODE + ":" + SOURCE], cwd=ROOT)
(COMBO / SOURCE).write_bytes(fixed)
blob = subprocess.check_output(["git", "rev-parse", CODE + ":" + SOURCE], cwd=ROOT, text=True).strip()
environment = dict(os.environ, GIT_INDEX_FILE=str(RUN / "combo_private_index"))
subprocess.run(["git", "read-tree", "ed217564e9cf3571b430d0fe7caa4d3999c7320b"], cwd=COMBO, env=environment, check=True)
subprocess.run(["git", "update-index", "--cacheinfo", "100644," + blob + "," + SOURCE], cwd=COMBO, env=environment, check=True)
tree = subprocess.check_output(["git", "write-tree"], cwd=COMBO, env=environment, text=True).strip()
changed = subprocess.check_output(["git", "diff", "--name-only"], cwd=COMBO, text=True).splitlines()
result = {"combo_path": str(COMBO), "head_sha": "ed217564e9cf3571b430d0fe7caa4d3999c7320b", "fixed_source_sha": CODE, "fixed_source_blob": blob, "fixed_source_raw_sha256": hashlib.sha256(fixed).hexdigest(), "before_source_raw_sha256": hashlib.sha256(before).hexdigest(), "combined_tree": tree, "changed_paths": changed, "purpose": "R09 original 17 reviewer fixtures with this one shared module overlay; not a repaired ed commit or full R09 approval"}
(RUN / "combo_tree_binding.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
(RUN / "combo_generation.diff").write_bytes(subprocess.check_output(["git", "diff", "--", SOURCE], cwd=COMBO))
print(json.dumps(result, ensure_ascii=False))
assert changed == [SOURCE]
