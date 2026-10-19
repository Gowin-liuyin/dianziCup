"""Record real migration namespaces, constraint definitions, resources and disjoint test counts."""

import json
import os
import xml.etree.ElementTree as ET

from review_checks import DATABASE, RUN, SCHEMA_PREFIX, now
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

TABLES = (
    "condition_rule_versions",
    "rule_support_bindings",
    "rule_leaf_reviews",
    "rule_validation_receipts",
    "assessment_results",
    "assessment_scope_watches",
    "asset_snapshot_sbom_sidecars",
)


def main():
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert (url.host, url.port, url.database) == ("127.0.0.1", 25432, DATABASE)
    assert url.username and url.username.startswith("test_")
    receipts = [
        json.loads(line) for line in (RUN / "schema_receipts.jsonl").read_text().splitlines()
    ]
    schema = next(
        item["schema"] for item in reversed(receipts) if item["revision"] == "0022_sbom_sidecars"
    )
    assert schema.startswith(SCHEMA_PREFIX)
    engine = create_engine(
        url.update_query_dict(
            {
                "options": f"-c search_path={schema},public -c statement_timeout=15000 "
                "-c lock_timeout=5000"
            }
        ),
        hide_parameters=True,
    )
    reflection = {}
    inspector = inspect(engine)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_database()")) == DATABASE
            assert connection.scalar(text("SELECT current_schema()")) == schema
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "0022_sbom_sidecars"
            )
            for name in TABLES:
                reflection[name] = {
                    "columns": [
                        {**item, "type": str(item["type"])}
                        for item in inspector.get_columns(name, schema=schema)
                    ],
                    "primary_key": inspector.get_pk_constraint(name, schema=schema),
                    "foreign_keys": inspector.get_foreign_keys(name, schema=schema),
                    "checks": inspector.get_check_constraints(name, schema=schema),
                    "unique": inspector.get_unique_constraints(name, schema=schema),
                    "indexes": inspector.get_indexes(name, schema=schema),
                }
            triggers = [
                dict(item)
                for item in connection.execute(
                    text(
                        "SELECT c.relname,t.tgname,t.tgtype,t.tgenabled,pg_get_triggerdef(t.oid) "
                        "AS definition,n2.nspname AS function_schema,p.proname FROM pg_trigger t "
                        "JOIN pg_class c ON c.oid=t.tgrelid "
                        "JOIN pg_namespace n ON n.oid=c.relnamespace "
                        "JOIN pg_proc p ON p.oid=t.tgfoid "
                        "JOIN pg_namespace n2 ON n2.oid=p.pronamespace "
                        "WHERE n.nspname=:schema AND NOT t.tgisinternal "
                        "AND c.relname=ANY(:names) ORDER BY c.relname,t.tgname"
                    ),
                    {"schema": schema, "names": list(TABLES)},
                ).mappings()
            ]
            assert len(triggers) == 7 and all(
                item["function_schema"] == schema
                and item["tgtype"] == 27
                and item["tgenabled"] == "O"
                for item in triggers
            )
            functions = [
                dict(item)
                for item in connection.execute(
                    text(
                        "SELECT p.proname,p.prosrc FROM pg_proc p JOIN pg_namespace n "
                        "ON n.oid=p.pronamespace WHERE n.nspname=:schema "
                        "AND p.proname IN ('r11_require_immutable_rule','r11_require_append_only',"
                        "'prevent_sbom_sidecar_changes') ORDER BY p.proname"
                    ),
                    {"schema": schema},
                ).mappings()
            ]
            assert len(functions) == 3
            owned_count = connection.scalar(
                text(
                    "SELECT count(*) FROM information_schema.schemata "
                    "WHERE schema_name LIKE :prefix"
                ),
                {"prefix": SCHEMA_PREFIX + "%"},
            )
            assert owned_count < 80
            resource = {
                "captured_at": now(),
                "database": DATABASE,
                "schema": schema,
                "owned_schema_count": owned_count,
                "schema_limit": 80,
                "database_bytes": connection.scalar(
                    text("SELECT pg_database_size(current_database())")
                ),
                "public_revision": connection.scalar(
                    text("SELECT version_num FROM public.alembic_version")
                ),
                "schemas_retained": True,
                "statement_timeout_ms": 15000,
                "lock_timeout_ms": 5000,
                "public_is_owned_review_database": True,
            }
    finally:
        engine.dispose()
    (RUN / "seven_table_reflection.json").write_text(
        json.dumps(
            {
                "captured_at": now(),
                "schema": schema,
                "tables": reflection,
                "triggers": triggers,
                "functions": functions,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (RUN / "owned_resource_snapshot.json").write_text(
        json.dumps(resource, indent=2), encoding="utf-8"
    )
    counts = {}
    for path in RUN.glob("*.xml"):
        doc = ET.parse(path).getroot()
        cases = doc.findall(".//testcase")
        counts[path.name] = {
            "tests": len(cases),
            "passed": sum(
                not list(item)
                or not any(child.tag in {"failure", "error", "skipped"} for child in item)
                for item in cases
            ),
            "failed": len(doc.findall(".//failure")),
            "errors": len(doc.findall(".//error")),
            "skipped": len(doc.findall(".//skipped")),
        }
    v1_cases = {
        item.attrib["name"]: item
        for item in ET.parse(RUN / "independent_pg.xml").getroot().findall(".//testcase")
    }
    public_name = "test_real_empty_owned_database_public_upgrade_has_only_production_creation"
    assert public_name in v1_cases and not any(
        child.tag in {"failure", "error", "skipped"} for child in v1_cases[public_name]
    )
    v2 = ET.parse(RUN / "independent_pg_final.xml").getroot().findall(".//testcase")
    assert len(v2) == 19 and public_name not in {item.attrib["name"] for item in v2}
    assert not any(child.tag in {"failure", "error", "skipped"} for item in v2 for child in item)
    result = {
        "captured_at": now(),
        "junit_counts": counts,
        "independent_distinct_passed": 20,
        "independent_accounting": (
            "19 final cases + 1 prior successful empty-public case; "
            "v1 failures and repeated successes are not added"
        ),
        "final_original_cases": 490,
        "unique_original_plus_independent": 510,
    }
    (RUN / "test_result_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    audit = json.loads((RUN / "material_validation_frozen.json").read_text())
    differences = {
        "source_raw_differences": [
            item for item in audit["source_results"] if not item["raw_matches_author"]
        ],
        "artifact_checkout_differences": [
            item for item in audit["artifact_results"] if not item["checkout_matches"]
        ],
    }
    assert all(
        item["crlf_to_lf_equals_code_blob"] for item in differences["source_raw_differences"]
    )
    assert all(
        item["crlf_to_lf_equals_blob"] for item in differences["artifact_checkout_differences"]
    )
    (RUN / "checkout_byte_observation.json").write_text(
        json.dumps(differences, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "resources": resource,
                "results": result,
                "checkout_differences": {
                    key: [item["path"] for item in value] for key, value in differences.items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
