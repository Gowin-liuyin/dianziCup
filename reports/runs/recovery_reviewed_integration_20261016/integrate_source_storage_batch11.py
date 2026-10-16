"""Integrate independently qualified storage and source-mode slices without unrelated files."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
BASE = "26fa0814a3a947a072f9d6fdf0e346814512c5d0"
MODE = "a3e918ac268fa4a7dcddd89a849ec406faf331b8"
STORE = "e2f11a687dfe1c3d7b9cbde61ab6c5ba299661c7"
mode_paths = subprocess.check_output(["git", "diff", "--name-only", BASE, MODE, "--", "backend"], cwd=ROOT, text=True).splitlines()
if len(mode_paths) != 6:
    raise RuntimeError("unexpected source-mode closure")
store_paths = ["backend/src/ai_intel/infrastructure/content_store.py", *["backend/tests/unit/" + name for name in ("test_content_store_fd_failure.py", "test_content_store_cleanup_failure.py", "test_content_store_descriptor_close_failure.py", "test_content_store_exclusive_publication.py")]]
sources = dict.fromkeys(mode_paths, MODE)
sources.update(dict.fromkeys(store_paths, STORE))
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
pending = []
for relative, source in sources.items():
    target = ROOT / relative
    tracked = subprocess.run(["git", "show", head + ":" + relative], cwd=ROOT, capture_output=True)
    if target.exists():
        if tracked.returncode or target.read_bytes().replace(b"\r\n", b"\n") != tracked.stdout.replace(b"\r\n", b"\n"):
            raise RuntimeError("existing working changes; refusing overwrite: " + relative)
    elif tracked.returncode == 0:
        raise RuntimeError("tracked file missing; refusing restoration: " + relative)
    raw = subprocess.check_output(["git", "show", source + ":" + relative], cwd=ROOT)
    pending.append((target, raw, {"path": relative, "source_sha": source, "raw_sha256": hashlib.sha256(raw).hexdigest()}))
for target, raw, _ in pending:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "baseline_sha": head, "files": [record for _, _, record in pending], "source_mode_review": "dcf1701ee258b3464d2d67de4844b2b97b82799d", "content_store_review": "cdfeff49c92dfc34da36b41f0f54b859cabe293d", "limits": "NTFS publication and source-mode persistence/explicit handlers qualified; default trusted-mode registration not yet changed or reviewed; no new live sources", "whole_tasks_accepted": False}
(RUN / "source_storage_batch11_inputs.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"files": len(pending), "whole_tasks_accepted": False}))
