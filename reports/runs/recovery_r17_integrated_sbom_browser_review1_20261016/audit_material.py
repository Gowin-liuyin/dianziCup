"""Verify author raw archive, original test resource and independent test counts."""
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path
from offline_runner import RUN, ROOT

AUTHOR = ROOT / "reports/runs/recovery_r17_integrated_sbom_browser_20261016"
manifest = json.loads((AUTHOR / "artifact_manifest.json").read_text(encoding="utf8"))
archive_path = AUTHOR / "evidence_exact_raw.tar.gz"
assert hashlib.sha256(archive_path.read_bytes()).hexdigest() == manifest["archive_sha256"]
checkout_drifts = []
with tarfile.open(archive_path) as archive:
    for member in manifest["members"]:
        raw = archive.extractfile(member["path"]).read()
        assert len(raw) == member["size"]
        assert hashlib.sha256(raw).hexdigest() == member["raw_sha256"]
        checkout = AUTHOR / member["path"]
        if not checkout.exists() or hashlib.sha256(checkout.read_bytes()).hexdigest() != member["raw_sha256"]:
            checkout_drifts.append(member["path"])
original_unit = json.loads((RUN / "unit_fresh_result.json").read_text(encoding="utf8"))
adapted_unit = json.loads((RUN / "unit_adapter_result.json").read_text(encoding="utf8"))
assert adapted_unit["numPassedTests"] == 557 and adapted_unit["numFailedTests"] == 0 and adapted_unit["numPendingTests"] == 0 and adapted_unit["numFailedTestSuites"] == 0
summary = {"author_archive_members_verified": len(manifest["members"]), "author_archive_sha256": manifest["archive_sha256"], "author_checkout_raw_drifts": checkout_drifts, "fresh_unit": {key: original_unit[key] for key in ("numPassedTests", "numFailedTests", "numFailedTestSuites", "numPendingTests")}, "adapted_unit": {key: adapted_unit[key] for key in ("numPassedTests", "numFailedTests", "numFailedTestSuites", "numPendingTests")}, "browser": {}}
for label, expected in [("original_six_run1", 6), ("independent_probes_run1", 3)]:
    result = json.loads((RUN / (label + ".json")).read_text(encoding="utf8"))
    stats = result["stats"]
    assert (stats["expected"], stats["unexpected"], stats["skipped"], stats["flaky"]) == (expected, 0, 0, 0)
    summary["browser"][label] = stats
summary["independent_png_count"] = len(list(RUN.rglob("*.png")))
summary["independent_flow_count"] = len(list(RUN.rglob("actual-http-flow.json")))
resource_path = "reports/runs/recovery_r17_sbom_workbench_20261016/backend_contract_samples.json"
resource_revision = "6be1d1b2f2101bea58b488531dbfb1f83fcdc0ce"
resource_blob = subprocess.check_output(["git", "rev-parse", resource_revision + ":" + resource_path], cwd=ROOT, text=True).strip()
assert resource_blob == "82c40263274fb65517037ab5e3f2d3982f151d67"
summary["root_resource_revision"] = resource_revision
summary["root_resource_blob"] = resource_blob
(RUN / "material_and_results_audit.json").write_text(json.dumps(summary, indent=2), encoding="utf8")
print(json.dumps({"author_members": len(manifest["members"]), "checkout_raw_drifts": len(checkout_drifts), "fresh": summary["fresh_unit"], "adapted": summary["adapted_unit"], "pngs": summary["independent_png_count"], "flows": summary["independent_flow_count"]}))
