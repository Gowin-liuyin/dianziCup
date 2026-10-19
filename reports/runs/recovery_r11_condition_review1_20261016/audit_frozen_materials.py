"""Read only frozen Git objects; author working directory is not an audit source."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
MATERIAL_SHA = "3865fd6a9c568b0d4e6b816e62eb808de5330427"
CODE_SHA = "ddfbf8c631a7ea002865d6ae0c1385e63bd87674"
EXPECTED_CANONICAL = "5dbcce2243ac2622309e21ab9809a7b81b48f442cf18aa3620fc7eeb2555342a"
MANIFEST = "reports/runs/recovery_r11_condition_rules_20261016/artifact_manifest.json"


def blob(path):
    return subprocess.check_output(["git", "show", f"{MATERIAL_SHA}:{path}"], cwd=ROOT)


def digest(content):
    return hashlib.sha256(content).hexdigest()


manifest = json.loads(blob(MANIFEST))
entries = manifest["entries"]
canonical = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
audits = []
for entry in entries:
    path = entry["path"]
    frozen = blob(path)
    raw = (ROOT / path).read_bytes()
    git_crlf = frozen.replace(b"\n", b"\r\n")
    variants = {
        "git_blob": frozen,
        "git_crlf_reconstruction": git_crlf,
        "checkout_raw": raw,
        "checkout_lf_normalization": raw.replace(b"\r\n", b"\n"),
    }
    matching = [name for name, content in variants.items()
                if digest(content) == entry["sha256"] and len(content) == entry["bytes"]]
    audits.append(dict(path=path, expected_author_raw_sha256=entry["sha256"],
                       expected_author_raw_bytes=entry["bytes"], expected_git_blob_sha256=None,
                       actual_git_blob_sha256=digest(frozen), actual_git_blob_bytes=len(frozen),
                       actual_checkout_raw_sha256=digest(raw), actual_checkout_raw_bytes=len(raw),
                       matching_representations=matching))
result = dict(
    recorded_at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
    code_sha=CODE_SHA, material_sha=MATERIAL_SHA, manifest_git_blob_sha256=digest(blob(MANIFEST)),
    expected_manifest_git_blob_sha256=None, manifest_entries_count=len(entries),
    expected_canonical_entries_sha256=EXPECTED_CANONICAL, actual_canonical_entries_sha256=digest(canonical),
    manifest_reported_canonical_entries_sha256=manifest["materials_sha256"],
    manifest_code_sha_matches=manifest["code_sha"] == CODE_SHA,
    material_source_diff=subprocess.check_output(["git", "diff", "--name-only", CODE_SHA, MATERIAL_SHA, "--", "backend/src", "backend/tests", "docs/decisions/CR-R11_condition_rules_proposal.md"], cwd=ROOT, text=True).splitlines(),
    author_raw_directory_read=False, author_raw_unrecoverable=[item["path"] for item in audits if not item["matching_representations"]],
    entries=audits,
)
summary = {}
for name in ("historical_lifecycle_328", "direct_unit_final", "direct_contract_final", "direct_security_final", "independent_final", "old_asset_version_regression"):
    totals = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
    for suite in ET.parse(RUN / f"{name}.xml").getroot().iter("testsuite"):
        for key in totals:
            totals[key] += int(suite.get(key, 0))
    summary[name] = totals
result["independent_junit_counts"] = summary
author_full = blob("reports/runs/recovery_r11_condition_rules_20261016/replay_full_unit.xml")
author_totals = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
for suite in ET.fromstring(author_full).iter("testsuite"):
    for key in author_totals:
        author_totals[key] += int(suite.get(key, 0))
result["frozen_author_full_unit_counts"] = author_totals
state = json.loads(blob("progress/task_state.json"))
result["frozen_task_states"] = {key: state.get("tasks", {}).get(key) for key in ("T26", "T27", "T28")}
(RUN / "frozen_material_audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: value for key, value in result.items() if key not in ("entries", "frozen_task_states")}, ensure_ascii=False, indent=2))
assert result["actual_canonical_entries_sha256"] == EXPECTED_CANONICAL == manifest["materials_sha256"]
assert result["manifest_code_sha_matches"] and not result["material_source_diff"]
assert not result["author_raw_unrecoverable"]
