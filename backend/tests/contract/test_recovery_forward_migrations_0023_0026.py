"""The forward chain freezes DDL without importing mutable runtime metadata."""

from __future__ import annotations

import ast
import importlib.util
import io
import re
from pathlib import Path
from types import ModuleType

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = ROOT / "backend/migrations"
RUN = ROOT / "reports/runs/recovery_forward_migrations_0023_0026_20261016"
REVISIONS = (
    ("0023_enrichment_input_audit", "0022_sbom_sidecars", "r07"),
    ("0024_conversation_context", "0023_enrichment_input_audit", "r12"),
    ("0025_graph_projection", "0024_conversation_context", "r10"),
    ("0026_api_key_credentials", "0025_graph_projection", "r18"),
)


def load_revision(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, MIGRATIONS / "versions" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_sql(source: str) -> str:
    return re.sub(r"\s+", " ", source).strip().rstrip(";")


def captured_sql(name: str, monkeypatch: pytest.MonkeyPatch) -> str:
    statements: list[str] = []
    module = load_revision(name)
    monkeypatch.setattr(module.op, "execute", statements.append)
    module.upgrade()
    return normalize_sql("; ".join(statements))


@pytest.mark.parametrize("name,parent,label", REVISIONS)
def test_revision_parent_and_frozen_literal_ddl(name: str, parent: str, label: str) -> None:
    module = load_revision(name)
    assert module.revision == name and module.down_revision == parent
    assert module.branch_labels is None and module.depends_on is None
    source = (MIGRATIONS / "versions" / f"{name}.py").read_text(encoding="utf-8")
    parsed = ast.parse(source)
    imports = [node for node in ast.walk(parsed) if isinstance(node, ast.ImportFrom)]
    assert [(node.module, [alias.name for alias in node.names]) for node in imports] == [
        ("alembic", ["op"])
    ]
    calls = [node for node in ast.walk(parsed) if isinstance(node, ast.Call)]
    assert all(
        not isinstance(node.func, ast.Attribute) or node.func.attr != "create_all" for node in calls
    )
    ddl_calls = [
        node
        for node in calls
        if isinstance(node.func, ast.Attribute) and node.func.attr == "execute"
    ]
    assert ddl_calls and all(
        len(node.args) == 1 and isinstance(node.args[0], ast.Constant) for node in ddl_calls
    )


@pytest.mark.parametrize("name,parent,label", REVISIONS)
def test_downgrade_refuses_historical_deletion(name: str, parent: str, label: str) -> None:
    with pytest.raises(RuntimeError, match="forward-only recovery"):
        load_revision(name).downgrade()


def test_complete_alembic_chain_has_one_head_and_no_revision_gap() -> None:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["0031_public_task_bindings"]
    history = list(scripts.walk_revisions("base", "heads"))
    assert [int(revision.revision[:4]) for revision in history] == list(range(31, 0, -1))
    assert [
        revision.revision for revision in scripts.iterate_revisions("head", REVISIONS[0][1])
    ] == [
        "0031_public_task_bindings",
        "0030_revalidation_actor_bindings",
        "0029_recommendation_receipts",
        "0028_investigation_workflows",
        "0027_recommendation_history",
        "0026_api_key_credentials",
        "0025_graph_projection",
        "0024_conversation_context",
        "0023_enrichment_input_audit",
    ]


def test_entire_chain_compiles_offline_through_0026() -> None:
    output = io.StringIO()
    config = Config(output_buffer=output)
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option(
        "sqlalchemy.url", "postgresql+psycopg://offline:offline@localhost/offline"
    )
    command.upgrade(config, "head", sql=True)
    compiled = output.getvalue()
    for name, _, _ in REVISIONS:
        assert name in compiled
    assert "CREATE TABLE api_keys" in compiled and "COMMIT;" in compiled
    assert "DROP TABLE" not in compiled


@pytest.mark.parametrize("name,parent,label", REVISIONS)
def test_frozen_input_ddl_is_preserved_with_explicit_strengthening(
    name: str, parent: str, label: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    actual = captured_sql(name, monkeypatch)
    reference = RUN / ("r07_frozen.sql" if label == "r07" else f"{label}_metadata.sql")
    if label == "r07":
        statements = reference.read_text(encoding="utf-8").strip().split(";\n\n")
    else:
        statements = reference.read_text(encoding="utf-8").strip().split(";\n\n")
    assert all(normalize_sql(statement) in actual for statement in statements)
    assert "DROP TABLE" not in actual and "UPDATE users" not in actual


def test_input_audit_is_nullable_hash_checked_and_guarded(monkeypatch: pytest.MonkeyPatch) -> None:
    sql = captured_sql(REVISIONS[0][0], monkeypatch)
    assert "ADD COLUMN input_audit_payload jsonb" in sql
    assert "ADD COLUMN input_audit_sha256 text" in sql
    assert "input_audit_payload jsonb NOT NULL" not in sql
    assert "input_audit_payload jsonb DEFAULT" not in sql
    assert "encode(sha256(convert_to(input_audit_payload::text,'UTF8')),'hex')" in sql
    assert "input audit requires a precreated step" in sql
    assert "OLD.input_audit_payload IS NOT NULL" in sql
    assert "BEFORE DELETE ON enrichment_job_steps" in sql
    assert "SET search_path FROM CURRENT" in sql


def test_turn_fks_scope_validation_and_history_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    sql = captured_sql(REVISIONS[1][0], monkeypatch)
    assert "REFERENCES grounded_answers (answer_id)" in sql
    assert "REFERENCES users (user_id)" in sql
    assert "FOREIGN KEY(conversation_id, active_turn_id)" in sql
    assert "DEFERRABLE INITIALLY DEFERRED" in sql
    assert "t.tenant_id IS DISTINCT FROM a.tenant_id" in sql
    assert "qa_owner_grounded_answers" in sql
    assert "BEFORE UPDATE OR DELETE ON qa_conversation_turns" in sql
    assert "SET search_path FROM CURRENT" in sql
    assert "BEFORE UPDATE OR DELETE ON grounded_answers" not in sql
    assert "BEFORE UPDATE OR DELETE ON qa_conversations" not in sql


def test_batch_bytes_are_checked_and_only_batches_are_frozen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sql = captured_sql(REVISIONS[2][0], monkeypatch)
    assert "CHECK (payload_sha256 = encode(sha256(payload),'hex'))" in sql
    assert "CHECK (octet_length(payload) <= 8388608)" in sql
    assert "BEFORE UPDATE OR DELETE ON graph_projection_batches" in sql
    assert "BEFORE UPDATE OR DELETE ON graph_projection_state" not in sql
    assert "FOREIGN KEY" not in sql


def test_keys_store_only_hash_and_strict_bounded_rate_constraints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sql = captured_sql(REVISIONS[3][0], monkeypatch)
    assert "token_hash TEXT NOT NULL" in sql and "UNIQUE (token_hash)" in sql
    assert "FOREIGN KEY(user_id) REFERENCES users (user_id)" in sql
    assert "FOREIGN KEY(key_id) REFERENCES api_keys (key_id)" in sql
    assert "INTERVAL '2160 hours'" in sql
    assert "resource = 'urn:dianzi:api:v1'" in sql
    assert "scopes = ARRAY['read:asset','read:public']::text[]" in sql
    assert "request_count >= 0" in sql and "WHEN 'read' THEN 60 ELSE 10 END" in sql
    assert "date_trunc('minute', window_started_at)" in sql
    assert "token TEXT" not in sql and "tenant_id" not in sql
