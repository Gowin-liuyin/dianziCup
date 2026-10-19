"""Fixed identities and nonsecret control receipts for the owned R06 segment."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = Path("D:/wt/r06-live-8a-20261016")
OBSERVER_ROOT = Path("D:/wt/r06-live-observer-20261016")
OBSERVER = OBSERVER_ROOT / "reports/runs/recovery_r06_incremental_observation_preparation_20261016"
PRODUCT_SHA = "8a1b04d48346d8550f0326a77f003246a0ebbab5"
OBSERVER_SHA = "1c4cce9770bfa29d08728a0131f7fc7fe714f9bc"
DATABASE = "test_dianzi_r06_catalog_live_8a_20261016"
PREFIX = "r06-live-8a-20261016:"
QUEUE = "r06_live_8a_20261016"
RUN_ID = "r06_live_8a_20261016"


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def write(name, value):
    destination = RUN / name
    temporary = destination.with_suffix(destination.suffix + ".pending")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    temporary.replace(destination)


def verify_authorization():
    """Do not read credentials or construct engines before the frozen authorization gate."""
    gate = json.loads((RUN / "root_authorization.json").read_text(encoding="utf-8-sig"))
    assert gate["root_live_authorized"] is True
    assert gate["product_sha"] == PRODUCT_SHA and gate["observer_sha"] == OBSERVER_SHA
    assert gate["database"] == DATABASE and gate["maximum_seconds"] == 21600
    assert gate["model_requests_permitted"] == 0
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == PRODUCT_SHA
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    for name in ("observe.py", "observation_log.py", "pg_snapshot.py"):
        relative = "reports/runs/recovery_r06_incremental_observation_preparation_20261016/" + name
        blob = subprocess.check_output(["git", "show", OBSERVER_SHA + ":" + relative], cwd=OBSERVER_ROOT)
        assert (OBSERVER / name).read_bytes() == blob
    return gate


def script_manifest():
    return {str(path.relative_to(RUN)): {"size_bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in RUN.glob("*.py")}
