"""Restore one immutable, public saved-result input without changing test expectations."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
SOURCE = "6e27d330b1113063c9401abb587220efedff1032"
RELATIVE = "reports/runs/recovery_r14_qa_citation_prompt_fix1_20261016/old_trial_probe_result.json"
EXPECTED = "769b0684ce0a1b9b6ca01adc386d2098154ffcdf8d0cd9fe6073cc8985f6aa5d"


def clock():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


started = clock()
command = ["git", "show", SOURCE + ":" + RELATIVE]
raw = subprocess.check_output(command, cwd=ROOT)
if hashlib.sha256(raw).hexdigest() != EXPECTED:
    raise RuntimeError("frozen input does not match the unchanged test's expected hash")
target = ROOT / RELATIVE
existed = target.exists()
if existed and target.read_bytes() != raw:
    raise RuntimeError("existing input differs; refusing to replace it")
if not existed:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
receipt = {
    "started_at": started,
    "ended_at": clock(),
    "source_material_sha": SOURCE,
    "command": command,
    "cwd": str(ROOT),
    "exit_code": 0,
    "input_path": RELATIVE,
    "bytes": len(raw),
    "sha256": EXPECTED,
    "already_present": existed,
    "test_oracles_modified": False,
    "initial_failure_preserved": "investigation_batch9_offline.json",
    "scope": "Saved public failed model result; not holdout or new live execution",
}
(RUN / "qa_prompt_input_closure_batch9.json").write_text(
    json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n"
)
print(json.dumps(receipt), flush=True)
