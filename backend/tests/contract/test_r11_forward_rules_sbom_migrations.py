"""Frozen forward DDL snapshots must retain existing metadata, without business imports."""

import importlib.util
from collections import Counter
from pathlib import Path

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from ai_intel.assessment.assessment_persistence import ASSESSMENT_TABLES
from ai_intel.assessment.rule_persistence import APPEND_ONLY_SQL, RULE_LIFECYCLE_SQL, RULE_TABLES
from ai_intel.assets.sbom_persistence_models import (
    SIDECAR_IMMUTABILITY_SQL,
    asset_snapshot_sbom_sidecars,
)
from ai_intel.infrastructure.database import MIGRATIONS_DIR


def migration(name):
    path = MIGRATIONS_DIR / "versions" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sql_lines(statement):
    return Counter(statement.split())


@pytest.mark.parametrize(
    "revision,previous,tables,trigger_sql",
    [
        (
            "0021_condition_assessments",
            "0020_hybrid_retrieval",
            (*RULE_TABLES, *ASSESSMENT_TABLES),
            (RULE_LIFECYCLE_SQL, APPEND_ONLY_SQL),
        ),
        (
            "0022_sbom_sidecars",
            "0021_condition_assessments",
            (asset_snapshot_sbom_sidecars,),
            (SIDECAR_IMMUTABILITY_SQL,),
        ),
    ],
)
def test_forward_snapshot_preserves_every_column_constraint_and_index(
    revision, previous, tables, trigger_sql, monkeypatch
):
    module = migration(revision)
    assert module.revision == revision and module.down_revision == previous
    captured = []
    monkeypatch.setattr(module.op, "execute", lambda statement: captured.append(str(statement)))
    module.upgrade()
    dialect = postgresql.dialect()
    for table in tables:
        expected = sql_lines(str(CreateTable(table).compile(dialect=dialect)))
        assert any(sql_lines(statement) == expected for statement in captured), table.name
        for index in table.indexes:
            expected_index = " ".join(str(CreateIndex(index).compile(dialect=dialect)).split())
            assert expected_index in {" ".join(statement.split()) for statement in captured}
    for statement in trigger_sql:
        assert " ".join(statement.split()) in {" ".join(item.split()) for item in captured}
    expected_triggers = {table.name + "_immutable" for table in tables}
    actual_triggers = {
        statement.split("CREATE TRIGGER ")[1].split()[0]
        for statement in captured
        if "CREATE TRIGGER " in statement
    }
    assert expected_triggers == actual_triggers


@pytest.mark.parametrize("revision", ["0021_condition_assessments", "0022_sbom_sidecars"])
def test_history_downgrade_is_explicitly_refused(revision):
    with pytest.raises(RuntimeError, match="immutable history"):
        migration(revision).downgrade()


def test_production_snapshots_have_no_dynamic_metadata_or_automatic_creation():
    for revision in ("0021_condition_assessments", "0022_sbom_sidecars"):
        source = (Path(MIGRATIONS_DIR) / "versions" / (revision + ".py")).read_text()
        assert "create_all" not in source
        assert "ai_intel" not in source
        assert "drop_table" not in source
