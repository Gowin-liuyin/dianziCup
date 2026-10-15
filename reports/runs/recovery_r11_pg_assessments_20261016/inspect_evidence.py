"""Freeze structure, command counts and raw/source hashes without reading secrets into output."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET

from run_checks import ROOT, RUN, connection, now
from sqlalchemy import create_engine, inspect, select


def main():
    receipt = json.loads((RUN / "database_receipt.json").read_text())
    url = (
        connection()
        .set(database=receipt["database"])
        .update_query_dict({"options": "-csearch_path=" + receipt["schema"]})
    )
    engine = create_engine(url, hide_parameters=True)
    with engine.connect() as database_connection:
        inspector = inspect(database_connection)
        schema = {}
        for table in receipt["new_local_tables"]:
            columns = inspector.get_columns(table)
            schema[table] = {
                "columns": [
                    {
                        "name": column["name"],
                        "type": str(column["type"]),
                        "nullable": column["nullable"],
                    }
                    for column in columns
                ],
                "primary_key": inspector.get_pk_constraint(table),
                "foreign_keys": inspector.get_foreign_keys(table),
                "unique_constraints": inspector.get_unique_constraints(table),
                "check_constraints": inspector.get_check_constraints(table),
                "indexes": inspector.get_indexes(table),
            }
        import sys

        sys.path.insert(0, str(ROOT / "backend/src"))
        from ai_intel.assessment.assessment_persistence import assessment_results
        from ai_intel.assets.inventory_models import asset_snapshots

        results = list(
            database_connection.execute(
                select(assessment_results.c.result_payload).order_by(
                    assessment_results.c.assessment_id
                )
            ).scalars()
        )
        (RUN / "assessment_evidence_fixture_rows.json").write_text(
            json.dumps(
                {
                    "fixture_data": True,
                    "human_labels": 0,
                    "results": results,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        snapshot_checks = []
        for row in database_connection.execute(select(asset_snapshots)).mappings():
            snapshot_checks.append(
                {
                    "snapshot_id": row["snapshot_id"],
                    "raw_sha256": hashlib.sha256(bytes(row["raw_input"])).hexdigest(),
                    "saved_raw_sha256": row["raw_input_sha256"],
                    "saved_manifest_sha256": row["manifest_sha256"],
                    "canonical_manifest_sha256": row["canonical_payload"][
                        "snapshot_sha256"
                    ],
                }
            )
        assert all(
            row["raw_sha256"] == row["saved_raw_sha256"]
            and row["saved_manifest_sha256"] == row["canonical_manifest_sha256"]
            for row in snapshot_checks
        )
        (RUN / "asset_snapshot_hash_checks.json").write_text(
            json.dumps(snapshot_checks, indent=2), encoding="utf-8"
        )
    engine.dispose()
    (RUN / "six_table_reflection.json").write_text(
        json.dumps(schema, indent=2), encoding="utf-8"
    )
    counts = {}
    for path in sorted(RUN.glob("*.xml")):
        suites = ET.parse(path).getroot().findall("testsuite")
        counts[path.name] = {
            key: sum(int(suite.get(key, "0")) for suite in suites)
            for key in ("tests", "failures", "errors", "skipped")
        }
    (RUN / "test_counts.json").write_text(
        json.dumps(counts, indent=2), encoding="utf-8"
    )
    source_paths = [
        *sorted((ROOT / "backend/src/ai_intel/assessment").glob("*.py")),
        ROOT / "backend/tests/integration/test_r11_pg_assessments.py",
        ROOT / "backend/tests/unit/test_r11_pg_assessment_scope.py",
        ROOT / "backend/tests/contract/test_r11_pg_assessment_contracts.py",
        ROOT / "docs/decisions/CR-R11_pg_assessments_proposal.md",
    ]
    sources = []
    for path in source_paths:
        relative = str(path.relative_to(ROOT)).replace("\\", "/")
        git_blob = (
            subprocess.check_output(
                ["git", "hash-object", "--", relative], cwd=ROOT, timeout=10
            )
            .decode()
            .strip()
        )
        committed_blob = (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD:" + relative], cwd=ROOT, timeout=10
            )
            .decode()
            .strip()
        )
        assert committed_blob == git_blob
        blob_bytes = subprocess.check_output(
            ["git", "cat-file", "blob", git_blob], cwd=ROOT, timeout=10
        )
        sources.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "git_blob": git_blob,
                "git_blob_sha256": hashlib.sha256(blob_bytes).hexdigest(),
            }
        )
    (RUN / "source_manifest.json").write_text(
        json.dumps(sources, indent=2), encoding="utf-8"
    )
    password = url.password or ""
    scanned = [path for path in RUN.rglob("*") if path.is_file()]
    leaked = [
        path.name
        for path in scanned
        if password and password.encode() in path.read_bytes()
    ]
    (RUN / "credential_scan.json").write_text(
        json.dumps(
            {
                "recorded_at": now(),
                "files_scanned": len(scanned),
                "actual_test_password_matches": leaked,
                "external_model_calls": 0,
                "external_provider_calls": 0,
                "external_source_calls": 0,
                "live": "not_run",
                "manual": "not_run",
                "human_labels": 0,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    if leaked:
        raise AssertionError("credential leakage detected; file names only")
    print(
        f"Reflected six tables, counted {len(counts)} JUnit artifacts, hashed {len(sources)} sources."
    )


if __name__ == "__main__":
    main()
