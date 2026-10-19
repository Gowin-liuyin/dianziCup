"""Record independent counts, graph limits, and source guards without summing reruns."""

import json
import subprocess
import xml.etree.ElementTree as ET

from review_runner import ROOT, RUN, approved_test_url, now


def main():
    summaries = {}
    for label in (
        "pg_production_regression",
        "pg_production_regression_resource_fix",
        "pg_independent_negatives",
        "pg_independent_negatives_fixture_fix",
        "pg_independent_negatives_schema_fix",
        "pure_migration_related",
    ):
        tree = ET.parse(RUN / (label + ".xml"))
        cases = tree.findall(".//testcase")
        failures = sum(case.find("failure") is not None for case in cases)
        errors = sum(case.find("error") is not None for case in cases)
        skips = sum(case.find("skipped") is not None for case in cases)
        summaries[label] = {
            "cases": len(cases),
            "passed": len(cases) - failures - errors - skips,
            "failures": failures,
            "errors": errors,
            "skips": skips,
            "case_ids": [case.get("classname", "") + "::" + case.get("name", "") for case in cases],
        }
    graph = {}
    for label in (
        "cbm_src_index",
        "cbm_assets_index",
        "cbm_trace_import_manifest",
        "cbm_trace_save_observation",
        "cbm_trace_collect_provider_aggregate_observation",
        "cbm_trace_run_migrations",
    ):
        graph[label] = json.loads((RUN / (label + ".stdout.log")).read_text())["structuredContent"]
    changed = (
        subprocess.run(
            [
                "git",
                "diff",
                "--name-only",
                "281371b072a696d972aa3c38519b8646393c98e2",
                "99fec14d1a64f9c5adaa5beb294e804da3e1d18d",
                "--",
                "backend/tests/conftest.py",
                "contracts",
                "fixtures",
                "progress",
            ],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .splitlines()
    )
    assert changed == []
    audit = json.loads((RUN / "material_audit.json").read_text())
    test_paths = {entry["path"] for entry in audit["upstream_tests"]}
    raw_different = [entry for entry in audit["raw_verified"] if not entry["git_equals_raw"]]
    configured = approved_test_url()
    needles = [
        configured.render_as_string(hide_password=False).encode(),
        configured.password.encode(),
    ]
    leaked = []
    for path in RUN.rglob("*"):
        if path.is_file() and any(needle in path.read_bytes() for needle in needles):
            leaked.append(path.relative_to(RUN).as_posix())
    assert leaked == []
    result = {
        "observed_at": now(),
        "tests": summaries,
        "cbm": graph,
        "conftest_contract_fixture_progress_diff": changed,
        "author_original_test_unique_files": len(test_paths),
        "author_original_test_blob_comparisons": len(audit["upstream_tests"]),
        "author_manifest_actual_sha256": audit["manifest_sha256"],
        "raw_git_line_endings_differ": raw_different,
        "secret_exact_match_findings": leaked,
        "provider_model_source_calls": 0,
        "cost": "0 paid operations; stored provider fee status stays unknown",
        "bootstrap_observation": {
            "exact_initial_start_time": "not recorded before instrumentation",
            "uv_initial_exit": 0,
            "initial_capture_errors": [
                "Out-File: Could not find a part of the path to root review run uv_sync.log",
                "Out-File: Could not find a part of the path to root review run "
                "uv_sync.command.json",
            ],
            "cause": "initial New-Item used backend cwd; root run directory was created afterward",
            "followup": "uv_sync_retry captured exact command and times, exit0; no source change",
        },
    }
    (RUN / "review_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "tests": {
                    key: {name: value for name, value in row.items() if name != "case_ids"}
                    for key, row in summaries.items()
                },
                "author_raw_git_different_files": len(raw_different),
                "author_original_test_unique_files": len(test_paths),
                "secret_exact_match_findings": len(leaked),
            }
        )
    )


if __name__ == "__main__":
    main()
