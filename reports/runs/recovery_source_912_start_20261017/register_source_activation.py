"""Register Root-owned Source-only prerequisites against the installed reviewed bytes."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

OPS = Path("D:/dianzi-runtime-cache/r06-f3-ops-20261017")
CORE = Path("D:/dianzi-runtime-cache/r06-f3-core-20261017")
RUN = Path(__file__).resolve().parent
REVIEW = Path("D:/wt/r06-activation-gate-review1/reports/runs/r06_activation_gate_review1_fix5_20261017/gate_review.json")
sys.path[:0] = [str(OPS), str(CORE)]
from configuration import ACTIVATION_FLAGS, ZONE, read_prepared, require_start_window, validate_activation
from run_binding import validate_binding, verify_frozen_files, read_object


def main() -> None:
    review = read_object(REVIEW.read_bytes())
    raw = (CORE / "runtime_binding.json").read_bytes()
    binding = read_object(raw)
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == review["actual_runtime_binding_sha256"] == "2a32f6ac2a817c18e2018cafc53f6ea2e39b23684c2772dc094789478a8e6158"
    assert binding["source_database_oid"] == review["oid"] == "10451302"
    assert binding["source_database_marker_sha256"] == review["native_comment_sha256"]
    assert binding["product_sha"] == review["product"] == "912d8b381eaab9260ead30d68f49b88fa8078384"
    validate_binding(binding, require_ready=True)
    verify_frozen_files(binding, read_prepared())
    require_start_window(datetime.now(ZONE))
    path = OPS / "activation.json"
    previous = path.read_bytes()
    activation = read_object(previous)
    assert all(activation[key] is False for key in ACTIVATION_FLAGS)
    assert not (CORE / "root_live_authorization.json").exists()
    for key in ACTIVATION_FLAGS:
        activation[key] = True
    for key in ("source_database_oid", "source_database_marker_sha256", "source_job_ledger_offset", "source_job_ledger_sha256"):
        activation[key] = binding[key]
    activation["runtime_binding_sha256"] = digest
    validate_activation(read_prepared(), activation, OPS, CORE)
    (RUN / "activation_before.json").write_bytes(previous)
    path.write_text(json.dumps(activation, indent=2) + "\n", encoding="utf-8")
    (RUN / "activation_registered.json").write_bytes(path.read_bytes())
    receipt = {
        "registered_at": datetime.now(ZONE).isoformat(),
        "review_commit": "b7a1244bf763c95ae529fc895c8019a3cab4ab9c",
        "review_sha256": hashlib.sha256(REVIEW.read_bytes()).hexdigest(),
        "review_scope": review["scope"],
        "flags": {key: True for key in ACTIVATION_FLAGS},
        "runtime_binding_sha256": digest,
        "product_sha": binding["product_sha"],
        "source_database_oid": binding["source_database_oid"],
        "historical_jobs_used": 42,
        "source_job_cap": 450,
        "remaining_source_jobs_at_registration": 408,
        "paid_requests_permitted": 0,
        "model_requests_permitted": 0,
        "cost": "unknown",
        "services_started_at_registration": 0,
        "formal_six_hour_pass": False,
        "future_actor_peak": "not_run",
    }
    (RUN / "registration_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
