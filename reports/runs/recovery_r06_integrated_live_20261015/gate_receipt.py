"""Keep the root's actual green/first-red context without rewriting the first full-gate result."""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
(RUN / "root_live_gate_authorization.json").write_text(json.dumps({
    "recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "live_code_sha": "1156b2ed6616e3a4297215c2893d2cbe633f5215",
    "root_authorization": "explicit root message now permits bounded actual external source phase",
    "original_pure_gate": {"passed": 1824, "failed": 1, "coverage_percent": 74.36, "failure": "new precise fixture matches lacked classification; original log preserved"},
    "direct_followup": {"security_passed": 42, "seconds": 15.52, "fixture_exact_records_added": 3, "scanner_or_roots_or_threshold_changed": False},
    "root_integrated_checks": {"postgresql_passed": 148, "frontend_unit_passed": 339, "typecheck_lint_build": "passed", "ruff_format_mypy": "passed"},
    "later_root_metadata_commit": "classification/report only; actual live worktree remains fixed SHA",
    "phase_or_full_r06_acceptance": False,
}, indent=2) + "\n", encoding="utf-8")
