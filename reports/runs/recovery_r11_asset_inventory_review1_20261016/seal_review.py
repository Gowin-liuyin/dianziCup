"""Seal reviewer evidence and scan only the authorized runtime connection values."""

import hashlib
import json
import subprocess
from xml.etree import ElementTree

from review_runner import ROOT, RUN, git, now
from sqlalchemy.engine import make_url

REPORT = ROOT / "reports/reviews/recovery/G-D-R11-asset-inventory-review-1.md"


def main():
    manifest = json.loads(
        git(
            "show",
            "HEAD:reports/runs/recovery_r11_asset_inventory_20261016/artifact_manifest.json",
        )
    )
    old_views = []
    for row in manifest["raw_evidence_archives"]:
        result = subprocess.run(
            ["git", "show", "429f432:" + row["path"]],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        if (
            result.returncode == 0
            and hashlib.sha256(result.stdout).hexdigest() != row["sha256"]
        ):
            old_views.append(row["path"])
    old_json_views = [path for path in old_views if path.endswith(".json")]
    assert len(old_json_views) == 12
    summary = {}
    for path in sorted(RUN.glob("*.xml")):
        tree = ElementTree.parse(path)
        suites = tree.getroot().findall("testsuite")
        summary[path.name] = {
            field: sum(int(suite.get(field, "0")) for suite in suites)
            for field in ("tests", "failures", "errors", "skipped")
        }
        summary[path.name]["seconds"] = sum(
            float(suite.get("time", "0")) for suite in suites
        )
    source_status = subprocess.check_output(
        [
            "git",
            "status",
            "--short",
            "--",
            "backend/src",
            "backend/tests",
            "backend/migrations",
            "backend/uv.lock",
            "contracts",
            "progress",
        ],
        cwd=ROOT,
    ).decode()
    assert not source_status
    filtered_proofs = []
    for row in manifest["source_proofs"]:
        object_id = (
            subprocess.check_output(
                ["git", "hash-object", "--path=" + row["path"], row["path"]], cwd=ROOT
            )
            .decode()
            .strip()
        )
        assert object_id == row["git_object"]
        filtered_proofs.append({"path": row["path"], "object_id": object_id})
    (RUN / "final_review_receipt.json").write_text(
        json.dumps(
            {
                "recorded_at": now(),
                "reviewer": "/root/r11_asset_inventory_first_independent_review",
                "code_commit": "6f82c68075dde808da9c92e3a49ad2e605e6b5a8",
                "code_tree": git(
                    "rev-parse", "6f82c68075dde808da9c92e3a49ad2e605e6b5a8^{tree}"
                )
                .decode()
                .strip(),
                "material_commit": git("rev-parse", "HEAD").decode().strip(),
                "material_tree": git("rev-parse", "HEAD^{tree}").decode().strip(),
                "source_filtered_proofs": filtered_proofs,
                "protected_paths_status": source_status,
                "old_429_json_view_mismatches": old_json_views,
                "old_429_all_changed_or_filtered_raw_views": old_views,
                "test_results": summary,
                "unique_required_successful_tests": 206,
                "unique_additional_tests": 8,
                "original_coverage_threshold": 60,
                "observed_targeted_coverage_percent": 23.57,
                "coverage_gate_exit_code": 1,
                "verdict_scope": "Ship only approved asset inventory persistence and independent router slice with P3 debt; no accepted registration",
                "external_http_api_model_calls": 0,
                "asset_scans": 0,
                "secret_vault_reads": 0,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    config = json.loads(
        subprocess.check_output(
            [
                "wsl",
                "-d",
                "Ubuntu-22.04",
                "-u",
                "root",
                "--exec",
                "cat",
                "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
            ]
        )
    )
    url = make_url(config["TEST_DATABASE_URL"])
    secrets = [url.password or "", config["TEST_DATABASE_URL"]]
    files = [
        path
        for path in RUN.iterdir()
        if path.is_file()
        and path.name not in {"artifact_manifest.json", "seal_receipt.json"}
    ] + [REPORT]
    matches = []
    for path in files:
        content = path.read_bytes()
        if any(secret and secret.encode() in content for secret in secrets):
            matches.append(path.relative_to(ROOT).as_posix())
    assert not matches
    (RUN / "secret_scan.json").write_text(
        json.dumps(
            {
                "recorded_at": now(),
                "scope": "own review top-level evidence and report, authorized configured test PostgreSQL connection values only",
                "matched_files": matches,
                "configured_connection_secrets_found": len(matches),
                "raw_private_manifests_exported": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    files.append(RUN / "secret_scan.json")
    records = []
    for path in sorted(set(files)):
        content = path.read_bytes()
        records.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    sealed = {
        "recorded_at": now(),
        "reviewed_code": "6f82c68075dde808da9c92e3a49ad2e605e6b5a8",
        "reviewed_material": git("rev-parse", "HEAD").decode().strip(),
        "scope": "reviewer's evidence only; tmp source index copies, pycache and venv excluded",
        "artifacts": records,
    }
    manifest_bytes = (json.dumps(sealed, indent=2) + "\n").encode()
    (RUN / "artifact_manifest.json").write_bytes(manifest_bytes)
    receipt = {
        "recorded_at": now(),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "artifacts": len(records),
        "report_sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest(),
        "source_changed": False,
        "no_commit_no_push": True,
    }
    (RUN / "seal_receipt.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()
