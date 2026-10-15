"""Seal analyzed file identities and validate the finished diagnostic proposal."""

import hashlib
import json
import subprocess
from datetime import datetime, timezone

from inspect_candidates import ROOT, RUN, security_scan

paths = [
    "AGENTS.md",
    "docs/plan/00_execution_map.md",
    "docs/tasks/T06_authentication_and_scope.md",
    "docs/plan/03_data_contracts.md",
    "docs/plan/05_api_and_tool_contracts.md",
    "docs/plan/09_operations_delivery.md",
    "progress/task_state.json",
    "progress/context_handoff.md",
    "backend/pyproject.toml",
    "backend/tests/security/test_t06_authentication_and_scope.py",
    "scripts/security_scan.py",
    "reports/security/recovery_fixture_false_positives.json",
    "reports/runs/recovery_r05_controller_20261015/gb_pure_regression.log",
    "reports/runs/recovery_r05_controller_20261015/gb_pure_regression.json",
    "reports/runs/recovery_r05_controller_20261015/gb_pure_regression.xml",
    "reports/reviews/recovery/G-B-R05-question-pipeline-review-1.md",
    "reports/reviews/recovery/G-B-R05-question-frontend-review-1.md",
    "reports/reviews/recovery/G-B-R05-grounded-answer-review-1.md",
    "reports/reviews/recovery/G-A-R01-search-tls-review-1.md",
    "reports/reviews/recovery/G-A-R02-persistence-review-1.md",
    "reports/reviews/recovery/G-A-R03-network-review-1-recheck.md",
    "reports/reviews/recovery/G-A-R03-network-review-1-recheck-2.md",
    "reports/runs/recovery_r05_grounded_answer_review_1_20261015/environment_locked.receipt.json",
    "reports/runs/recovery_r05_controller_20261015/source_rate_candidate_parser_red.json",
    "reports/runs/recovery_r01_search_tls_review_1_20261015/forced_failure_showlocals.json",
    "reports/runs/recovery_r01_search_tls_review_1_20261015/forced_failure_showlocals_recovered.json",
    "reports/runs/recovery_r02_persistence_review_1_20261015/credential_failure_probe.command.json",
    "reports/runs/recovery_r02_persistence_review_1_20261015/credential_failure_probe_v2.command.json",
    "reports/runs/recovery_r02_minio_review_1_20261015/native_auth_failure.observed.json",
    "reports/runs/recovery_r05_controller_20261015/retired_review_venvs_before.json",
    "reports/runs/recovery_r05_controller_20261015/retired_review_venvs_after.json",
    "reports/runs/recovery_r05_controller_20261015/retired_review_venvs_move.json",
    "reports/reviews/recovery/G-B-secret-fixture-classification.md",
    "reports/tasks/G-B-secret-fixture-classification.md",
    "reports/security/gb_fixture_classification_proposal.json",
]
sources = json.loads((RUN / "proposal_source_snapshots.json").read_text(encoding="utf-8"))
paths.extend(item["path"] for item in sources["files"])
origin_sources = json.loads((RUN / "origin_resolution.json").read_text(encoding="utf-8"))
paths.extend(item["path"] for item in origin_sources["source_snapshots"])
metadata = json.loads((RUN / "unclassified_metadata.json").read_text(encoding="utf-8"))
paths.extend(item["path"] for item in metadata["file_snapshots"] if "/venv/" not in item["path"])
file_snapshots=[]
for relative in sorted(set(paths)):
    path=ROOT / relative
    file_snapshots.append({"path":relative,"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"observed_at":datetime.now(timezone.utc).isoformat(),"mtime_ns":path.stat().st_mtime_ns})
for item in sources["files"]:
    assert hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() == item["sha256"]
shared_table=ROOT / "reports/security/recovery_fixture_false_positives.json"
assert hashlib.sha256(shared_table.read_bytes()).hexdigest() == metadata["manifest_sha256"]
proposal=security_scan.load_fixture_classifications(ROOT,ROOT / "reports/security/gb_fixture_classification_proposal.json")
assert len(proposal) == 15
for item in proposal:
    path=ROOT / item.path
    raw=path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == item.raw_sha256
    content=raw.decode("utf-8",errors="ignore").replace("\r\n","\n").replace("\r","\n")
    match=security_scan.PATTERNS[item.pattern_id].match(content,item.start)
    assert match is not None and match.end() == item.end
    quote_start=min(index for index, character in enumerate(match.group(0)) if character in "\"'")
    assert match.group(0)[quote_start+1:-1] == item.match_value
final_scan=security_scan.scan_repository(ROOT,security_scan.load_fixture_classifications(ROOT,RUN / "combined_fixture_manifest.json"))
rejected=[{"path":item.path,"pattern_id":item.pattern_id,"category":item.category} for item in final_scan if item.category not in security_scan.SAFE_CATEGORIES]
result={"recorded_at":datetime.now(timezone.utc).isoformat(),"head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),"file_snapshots":file_snapshots,"historical_candidate_metadata":"unclassified_metadata.json","proposal_records":len(proposal),"source_identity_rechecked":True,"shared_manifest_unchanged":True,"exact_secret_scan":"not_run","final_combined_scan_findings":len(final_scan),"rejected":rejected}
(RUN / "analyzed_file_snapshots.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
assert not rejected
print(json.dumps({"head":result["head"],"proposal_records":len(proposal),"source_identity_rechecked":True,"shared_manifest_unchanged":True,"final_combined_scan_findings":len(final_scan),"rejected_count":len(rejected),"exact_secret_scan":"not_run"}))
