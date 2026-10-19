"""Bind unchanged contracts, original tests, raw browser evidence and source commit."""

import hashlib
import json
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
BASE = "17ab90e0a6b100530a3078dd525f9086813c9728"
SOURCE = "4a17fa3fb7357a8c2b9d647f62c875958a24a27d"


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
changed = git("diff", "--name-only", BASE, SOURCE).decode().splitlines()
assert set(changed) == {"frontend/src/features/assets/sbom-detail.tsx", "frontend/src/features/assets/assets.css", "frontend/e2e/r17_integrated_sbom_api.spec.ts", "frontend/e2e/helpers/r17-sbom-inputs.ts", "frontend/e2e/helpers/r17_sbom_control.py"}
original_frontend_tests = [path for path in git("ls-tree", "-r", "--name-only", BASE, "frontend").decode().splitlines() if ".test.ts" in path or ".spec.ts" in path]
assert len(original_frontend_tests) == 58
protected = [*original_frontend_tests, "frontend/src/features/assets/asset-client.ts", "frontend/src/features/assets/asset-contracts.ts", "frontend/src/features/assets/sbom-contracts.ts", "frontend/src/features/assets/asset-detail.tsx", "frontend/src/features/assets/asset-import.tsx", "frontend/package.json", "frontend/package-lock.json", "frontend/tsconfig.tsbuildinfo", "AGENTS.md", ".gitattributes", "progress/task_state.json"]
for path in protected:
    assert git("rev-parse", SOURCE + ":" + path) == git("rev-parse", BASE + ":" + path)
    assert git("hash-object", path).strip() == git("rev-parse", SOURCE + ":" + path).strip()
assert not git("diff", BASE, SOURCE, "--", "backend", "contracts", "docs", "progress", "frontend/src/api", "frontend/src/app", "frontend/src/styles.css").strip()
main_hash = sha256(Path("D:/dianzi/frontend/tsconfig.tsbuildinfo").read_bytes())
assert main_hash == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
resource_path = "reports/runs/recovery_r17_sbom_workbench_20261016/backend_contract_samples.json"
original_resource = git("show", "5587deb124f06b9aa14fb7feb22cdc9493ae4883:" + resource_path)
assert sha256(original_resource) == "92f5a0cac56ccd97c63af16bd14418cbc1c42cf4803c3ab6627f419235a6e331"
assert (ROOT / resource_path).read_bytes() == original_resource
(RUN / "backend_contract_samples.original.json").write_bytes(original_resource)
proof = {"source": SOURCE, "base": BASE, "source_tree": git("rev-parse", SOURCE + "^{tree}").decode().strip(), "changed": changed, "sources": {path: {"raw_sha256": sha256((ROOT / path).read_bytes()), "git_blob": git("rev-parse", SOURCE + ":" + path).decode().strip(), "git_lf_sha256": sha256(git("show", SOURCE + ":" + path))} for path in changed}, "protected_frontend_test_files": len(original_frontend_tests), "protected_files": protected, "protected_main_buildinfo_sha256": main_hash, "fixture_dependency": {"path": resource_path, "original_material": "5587deb124f06b9aa14fb7feb22cdc9493ae4883", "original_blob": "82c40263274fb65517037ab5e3f2d3982f151d67", "raw_sha256": sha256(original_resource), "size": len(original_resource)}}
(RUN / "source_proof.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf8")
unit = json.loads((RUN / "unit_all_3_result.json").read_text(encoding="utf8"))
assert (unit["numPassedTests"], unit["numFailedTests"], unit["numPendingTests"], unit["numFailedTestSuites"]) == (557, 0, 0, 0)
actual = json.loads((RUN / "actual_edge_7_stale.json").read_text(encoding="utf8"))
assert (actual["stats"]["expected"], actual["stats"]["unexpected"], actual["stats"]["skipped"], actual["stats"]["flaky"]) == (6, 0, 0, 0)
artifacts = RUN / "actual_edge_7_stale_artifacts"
screenshots = list(artifacts.rglob("*.png"))
flows = list(artifacts.rglob("actual-http-flow.json"))
assert len(screenshots) == 26 and len(flows) == 6
summary = {"original_unit_passed": 557, "actual_default_api_browser_passed": 6, "before_fixture_visual_passed": 6, "final_screenshots": len(screenshots), "actual_http_flows": len(flows), "pg_upload_verifications": len(list(artifacts.rglob("pg-upload-*.json"))), "source": SOURCE, "official_design_reference": "https://www.elastic.co/docs/solutions/security/investigate/timeline", "human_acceptance": "not_run", "real_external_source_model_live": "not_run"}
(RUN / "validation_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf8")
excluded = {"artifact_manifest.json", "evidence_exact_raw.tar.gz", "seal_receipt.json"}
members = [file for file in RUN.rglob("*") if file.is_file() and "__pycache__" not in file.parts and file.name not in excluded]
with tarfile.open(RUN / "evidence_exact_raw.tar.gz", "w:gz") as archive:
    for file in members:
        archive.add(file, arcname=str(file.relative_to(RUN)).replace("\\", "/"), recursive=False)
manifest = {"members": [{"path": str(file.relative_to(RUN)).replace("\\", "/"), "size": file.stat().st_size, "raw_sha256": sha256(file.read_bytes())} for file in members], "archive_sha256": sha256((RUN / "evidence_exact_raw.tar.gz").read_bytes())}
(RUN / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf8")
with tarfile.open(RUN / "evidence_exact_raw.tar.gz", "r:gz") as archive:
    for item in manifest["members"]:
        assert sha256(archive.extractfile(item["path"]).read()) == item["raw_sha256"]
(RUN / "seal_receipt.json").write_text(json.dumps({"argv": ["D:/dianzi/backend/.venv/Scripts/python.exe", str(Path(__file__).resolve())], "cwd": str(ROOT), "started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "exit_code": 0, "member_count": len(members), "source": SOURCE}) + "\n", encoding="utf8")
print(json.dumps(summary))
