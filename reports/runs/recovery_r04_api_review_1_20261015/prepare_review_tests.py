"""Copy frozen regression inputs; only the reviewer resource binding is changed."""

import hashlib
import json
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = Path("C:/Users/yinha/.codex/worktrees/recovery-r04-api-review-1/dianzi")
TARGET = RUN / "independent_tests"
TARGET.mkdir(exist_ok=True)
original = ROOT / "backend/tests/integration/test_r04_knowledge_api_pg.py"
captured = original.read_bytes()
replay = captured.decode("utf-8").replace("test_dianzi_r04_api_20261015", "test_dianzi_r04_api_review_20261015")
assert captured.decode("utf-8").count("test_dianzi_r04_api_20261015") == 1
(TARGET / "test_api_original_replay.py").write_text(replay, encoding="utf-8")
original_conftest = (ROOT / "backend/tests/conftest.py").read_text(encoding="utf-8")
bound = original_conftest.replace("PROJECT_ROOT = Path(__file__).resolve().parents[2]",
    "PROJECT_ROOT = Path('C:/Users/yinha/.codex/worktrees/recovery-r04-api-review-1/dianzi' if os.name == 'nt' else '/mnt/c/Users/yinha/.codex/worktrees/recovery-r04-api-review-1/dianzi')")
assert original_conftest != bound
(TARGET / "conftest.py").write_text(bound, encoding="utf-8")
receipt = {
    "frozen_original": str(original), "original_captured_sha256": hashlib.sha256(captured).hexdigest(),
    "replay_sha256": hashlib.sha256(replay.encode()).hexdigest(),
    "only_original_test_delta": "api_engine expected own test database name; every test assertion and input unchanged",
    "conftest_delta": "PROJECT_ROOT resource binding only; original failure redaction hooks retained",
}
(RUN / "replay_resource_binding.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(json.dumps(receipt))
