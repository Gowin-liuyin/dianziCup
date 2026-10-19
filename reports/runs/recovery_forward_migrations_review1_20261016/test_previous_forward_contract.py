"""Frozen forward revisions must not import mutable business DDL or delete history."""

import ast
import importlib.util
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

MIGRATIONS = Path('D:\\wt\\recovery-forward-migrations-review1\\backend\\migrations')
REVISIONS = (
    ("0018_asset_inventory", "0017_enrichment_job_workflows"),
    ("0019_aggregate_observations", "0018_asset_inventory"),
)


def revision_module(name):
    path = MIGRATIONS / "versions" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("revision,parent", REVISIONS)
def test_revision_freezes_parent_without_business_imports(revision, parent):
    module = revision_module(revision)
    assert module.revision == revision
    assert module.down_revision == parent
    source = (MIGRATIONS / "versions" / f"{revision}.py").read_text(encoding="utf-8")
    imports = [
        node.module for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)
    ]
    assert not any(name and name.startswith("ai_intel") for name in imports)
    assert "create_all" not in source


@pytest.mark.parametrize("revision,parent", REVISIONS)
def test_downgrade_preserves_history(revision, parent):
    with pytest.raises(RuntimeError, match="forward-only recovery"):
        revision_module(revision).downgrade()


def test_production_chain_has_single_forward_head():
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["0026_api_key_credentials"]
    assert [revision.revision for revision in scripts.iterate_revisions("head", "0016")] == [
        "0026_api_key_credentials",
        "0025_graph_projection",
        "0024_conversation_context",
        "0023_enrichment_input_audit",
        "0022_sbom_sidecars",
        "0021_condition_assessments",
        "0020_hybrid_retrieval",
        "0019_aggregate_observations",
        "0018_asset_inventory",
        "0017_enrichment_job_workflows",
    ]
