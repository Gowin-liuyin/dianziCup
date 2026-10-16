"""Bind actual PG reflection, JUnit and raw/Git source bytes without exposing credentials."""

import hashlib
import json
import os
import subprocess
import xml.etree.ElementTree as ET

from run_checks import ROOT, RUN, now
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

SOURCE_BASELINE = "ed0e14a03a06ed104f23afd0be5407d873ed8edf"
PG_SOURCE = "2ddc8fe2ff3e7becfad3b1774a10407911eacbe6"
PG_MATERIAL = "6b10f2c4ed013f4375d51fc31e1cb317409730ac"


def git(*arguments):
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, timeout=15, check=False
    )
    assert result.returncode == 0
    return result.stdout


def main():
    code = git("rev-parse", "HEAD").decode().strip()
    owned = git("diff", "--name-only", "HEAD", "--", "backend", "docs/decisions").decode()
    assert not owned.strip()
    source_paths = git("ls-files", "backend/src").decode().splitlines()
    new_paths = git("diff-tree", "--no-commit-id", "--name-only", "-r", code).decode().splitlines()
    original_paths = [
        "backend/tests/integration/test_r11_pg_assessments.py",
        "backend/tests/integration/test_r11_assessment_raw_rechecks_pg.py",
        "backend/tests/integration/test_r12_production_indexing.py",
        "backend/tests/integration/test_t30_hybrid_retrieval.py",
    ]
    entries = []
    for name in sorted(set(source_paths + new_paths + original_paths)):
        raw = (ROOT / name).read_bytes()
        blob = git("show", code + ":" + name)
        entries.append(
            {
                "path": name,
                "worktree_sha256": hashlib.sha256(raw).hexdigest(),
                "git_blob_id": git("rev-parse", code + ":" + name).decode().strip(),
                "git_blob_sha256": hashlib.sha256(blob).hexdigest(),
                "worktree_bytes": len(raw),
                "git_blob_bytes": len(blob),
                "worktree_equals_git_blob": raw == blob,
                "crlf_to_lf_equals_git_blob": raw.replace(b"\r\n", b"\n") == blob,
            }
        )
    bindings = []
    for name in original_paths:
        reference = PG_MATERIAL if "r11_" in name else SOURCE_BASELINE
        assert git("show", code + ":" + name) == git("show", reference + ":" + name)
        bindings.append({"path": name, "reference": reference, "git_blob_unchanged": True})
    protected = [
        name
        for name in git("ls-files", "backend/migrations/versions").decode().splitlines()
        if not name.rsplit("/", 1)[-1].startswith(("0021_", "0022_"))
    ] + ["backend/src/ai_intel/assets/sbom_persistence_models.py"]
    for name in protected:
        assert git("show", code + ":" + name) == git("show", SOURCE_BASELINE + ":" + name)
    approved_business = [
        "backend/src/ai_intel/assessment/" + name + ".py"
        for name in (
            "assessment_persistence",
            "assessment_service",
            "persistence_contracts",
            "rule_persistence",
            "rule_service",
        )
    ]
    for name in approved_business:
        assert git("show", code + ":" + name) == git("show", PG_MATERIAL + ":" + name)
    counts = {}
    for path in sorted(RUN.glob("*.xml")):
        document = ET.parse(path).getroot()
        cases = document.findall(".//testcase")
        layers = {}
        for case in cases:
            name, classname = case.attrib["name"], case.attrib["classname"]
            layer = (
                "unit"
                if ".unit." in classname
                else "contract"
                if ".contract." in classname
                else "security"
                if ".security." in classname or name.startswith("test_security_")
                else "integration"
            )
            layers[layer] = layers.get(layer, 0) + 1
        counts[path.name] = {
            "tests": len(cases),
            "failed": len(document.findall(".//failure")),
            "errors": len(document.findall(".//error")),
            "skipped": len(document.findall(".//skipped")),
            "layers_disjoint": layers,
        }
    receipts = [
        json.loads(line) for line in (RUN / "schema_receipts.jsonl").read_text().splitlines()
    ]
    schema = next(
        item["schema"] for item in reversed(receipts) if item["revision"] == "0022_sbom_sidecars"
    )
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert url.database == "test_dianzi_r11_forward_rules_sbom_20261016"
    url = url.update_query_dict(
        {"options": f"-csearch_path={schema},public -cstatement_timeout=15000"}
    )
    engine = create_engine(url, hide_parameters=True)
    names = (
        "condition_rule_versions",
        "rule_support_bindings",
        "rule_leaf_reviews",
        "rule_validation_receipts",
        "assessment_results",
        "assessment_scope_watches",
        "asset_snapshot_sbom_sidecars",
    )
    reflection = {}
    inspector = inspect(engine)
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0022_sbom_sidecars"
        )
        owned_resource = {
            "database": url.database,
            "owned_schema_count": connection.scalar(
                text(
                    "SELECT count(*) FROM information_schema.schemata "
                    "WHERE schema_name LIKE 'test_r11_forward_%'"
                )
            ),
            "database_bytes": connection.scalar(
                text("SELECT pg_database_size(current_database())")
            ),
            "schema_limit": 80,
            "pool_size": 8,
            "max_overflow": 2,
            "statement_timeout_ms": 15000,
            "lock_timeout_ms": 5000,
            "command_timeout_seconds": 300,
            "captured_at": now(),
        }
        assert owned_resource["owned_schema_count"] < 80
        for name in names:
            columns = []
            for column in inspector.get_columns(name):
                columns.append({**column, "type": str(column["type"])})
            reflection[name] = {
                "columns": columns,
                "primary_key": inspector.get_pk_constraint(name),
                "foreign_keys": inspector.get_foreign_keys(name),
                "checks": inspector.get_check_constraints(name),
                "unique": inspector.get_unique_constraints(name),
                "indexes": inspector.get_indexes(name),
            }
        triggers = [
            dict(row)
            for row in connection.execute(
                text(
                    "SELECT c.relname,t.tgname,t.tgtype,p.proname,"
                    "pg_get_triggerdef(t.oid) AS definition "
                    "FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid "
                    "WHERE n.nspname=current_schema() AND NOT t.tgisinternal "
                    "ORDER BY c.relname,t.tgname"
                )
            ).mappings()
            if row["relname"] in names
        ]
        functions = [
            dict(row)
            for row in connection.execute(
                text(
                    "SELECT p.proname,p.prosrc FROM pg_proc p "
                    "JOIN pg_namespace n ON n.oid=p.pronamespace "
                    "WHERE n.nspname=current_schema() AND p.proname IN "
                    "('r11_require_append_only','r11_require_immutable_rule',"
                    "'prevent_sbom_sidecar_changes') "
                    "ORDER BY p.proname"
                )
            ).mappings()
        ]
    engine.dispose()
    for name, payload in (
        (
            "source_manifest.json",
            {
                "code_commit": code,
                "source_baseline": SOURCE_BASELINE,
                "pg_source_commit": PG_SOURCE,
                "pg_material_commit": PG_MATERIAL,
                "indexed_scope": "backend/src (assets separately)",
                "entries": entries,
                "unchanged_original_tests": bindings,
                "unchanged_prior_migrations_and_sidecar_metadata": protected,
                "unchanged_approved_business_files": approved_business,
            },
        ),
        ("test_counts.json", counts),
        ("owned_resource_snapshot.json", owned_resource),
        (
            "seven_table_reflection.json",
            {
                "schema": schema,
                "tables": reflection,
                "triggers": triggers,
                "functions": functions,
                "captured_at": now(),
            },
        ),
    ):
        (RUN / name).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                "code_commit": code,
                "source_files": len(entries),
                "reflected_tables": len(reflection),
                "xml_files": len(counts),
                "unchanged_original_test_files": len(bindings),
            }
        )
    )


if __name__ == "__main__":
    main()
