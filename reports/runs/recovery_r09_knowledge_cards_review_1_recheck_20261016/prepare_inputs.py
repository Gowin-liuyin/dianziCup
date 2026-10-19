"""按原始字节复制原17例并记录独有解释器和固定组合模块路径。"""

import hashlib
import json
import sys
from pathlib import Path

import ai_intel.enrichment.card_extraction as card
import ai_intel.infrastructure.models.generation as generation

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
ORIGINAL = Path("C:/Users/yinha/.codex/worktrees/r09-knowledge-cards-review-1/dianzi/reports/runs/recovery_r09_knowledge_cards_review_1_20261016/test_independent_boundaries.py")
EXPECTED = "76ca4d4064f65bfd08846a6e57a2c4fde087a10d6422d563094b412890058bbf"
raw = ORIGINAL.read_bytes()
assert hashlib.sha256(raw).hexdigest() == EXPECTED
target = RUN / "test_independent_boundaries.py"
target.write_bytes(raw)
assert hashlib.sha256(target.read_bytes()).hexdigest() == EXPECTED
assert Path(sys.prefix).resolve() == (RUN / ".venv").resolve()
assert Path(card.__file__).resolve().is_relative_to(ROOT.resolve())
assert Path(generation.__file__).resolve().is_relative_to(ROOT.resolve())
receipt = {"original_probe_sha256": EXPECTED, "original_path": str(ORIGINAL), "copy_path": str(target), "python_executable": sys.executable, "prefix": sys.prefix, "python_version": sys.version, "card_module": card.__file__, "generation_module": generation.__file__, "lock_sha256": hashlib.sha256((ROOT / "backend/uv.lock").read_bytes()).hexdigest(), "real_model_calls": 0, "real_network_calls": 0}
(RUN / "input_binding.json").write_bytes((json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode())
print(json.dumps(receipt, ensure_ascii=False, indent=2))
