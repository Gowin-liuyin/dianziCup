"""The default product worker/beat only starts after a root-owned frozen live gate."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

RUN = Path(__file__).resolve().parent
TOOL_ROOT = RUN.parents[2]
GATE = RUN / "root_live_authorization.json"
ORIGINAL_OBSERVER_SHA = "1c4cce9770bfa29d08728a0131f7fc7fe714f9bc"
PRODUCT_SHA = "e310f7735bd499c4d9fbcefe8a644e2309a16a62"
ORIGINAL_OBSERVER_RELATIVE = (
    "reports/runs/recovery_r06_incremental_observation_preparation_20261016"
)
SCRIPT_NAMES = (
    "authorization.py",
    "controlled_supervise.py",
    "runtime_limits.py",
    "stop_controller.py",
    "windows_actor.py",
    "deploy_runtime_entry.py",
    "runtime_controls.py",
    "owned_stop_watcher.py",
    "task_fence.py",
)


def verify_live_authorization() -> dict[str, object]:
    """Missing authorization stops before environment access or product imports."""
    if not GATE.is_file():
        raise RuntimeError("root frozen product and independent tool review required")
    gate = json.loads(GATE.read_bytes())
    if (
        gate.get("root_live_authorized") is not True
        or gate.get("independent_review_ship") is not True
        or gate.get("root_budget_approved") is not True
        or gate.get("integrated_key_checks_passed") is not True
    ):
        raise RuntimeError("live runtime authorization is not granted")
    for name in ("product_sha", "tool_sha"):
        if not isinstance(gate.get(name), str) or re.fullmatch("[a-f0-9]{40}", gate[name]) is None:
            raise RuntimeError("fixed runtime SHA required")
    if gate["product_sha"] != PRODUCT_SHA:
        raise RuntimeError("root combined e310 product is required")
    if (
        gate.get("maximum_seconds") != 21600
        or gate.get("source_job_cap") != 450
        or gate.get("model_requests_permitted") != 0
        or gate.get("wire_https_cap") != 35100
    ):
        raise RuntimeError("root resource parameters differ from reviewed proposal")
    product_value = gate.get("product_root")
    if not isinstance(product_value, str):
        raise RuntimeError("fixed product checkout path required")
    product_root = Path(product_value)
    if not product_root.is_absolute():
        raise RuntimeError("fixed product checkout must be absolute")
    actual_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=product_root, text=True
    ).strip()
    status = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=product_root, text=True
    ).strip()
    if actual_sha != gate["product_sha"] or status:
        raise RuntimeError("product checkout must match frozen clean SHA")
    if (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=TOOL_ROOT, text=True).strip()
        != gate["tool_sha"]
    ):
        raise RuntimeError("deployment checkout differs from independently reviewed tool SHA")
    for name in SCRIPT_NAMES:
        relative = (RUN / name).relative_to(TOOL_ROOT).as_posix()
        expected = subprocess.check_output(
            ["git", "show", f"{gate['tool_sha']}:{relative}"], cwd=TOOL_ROOT
        )
        if (RUN / name).read_bytes() != expected:
            raise RuntimeError("owned deployment script changed after review")
    for name in ("observe.py", "observation_log.py", "pg_snapshot.py"):
        relative = ORIGINAL_OBSERVER_RELATIVE + "/" + name
        expected = subprocess.check_output(
            ["git", "show", ORIGINAL_OBSERVER_SHA + ":" + relative], cwd=TOOL_ROOT
        )
        if (
            hashlib.sha256((TOOL_ROOT / relative).read_bytes()).digest()
            != hashlib.sha256(expected).digest()
        ):
            raise RuntimeError("original observer script changed")
    return gate
