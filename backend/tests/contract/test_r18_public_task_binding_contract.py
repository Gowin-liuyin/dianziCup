"""Frozen public schemas and additive migration contract, with explicitly synthetic answers."""

import importlib.util
import inspect
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
from test_r18_public_task_bindings import TASK_ID, read_case

from ai_intel.api.public_task_bindings import (
    PublicTaskBindingService,
    public_task_bindings,
)

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = json.loads((ROOT / "contracts/schemas/public_api_extensions_v1.json").read_text())
VALIDATOR = Draft202012Validator(
    {"$ref": "#/$defs/TaskResultEnvelope", "$defs": SCHEMA["$defs"]},
    format_checker=FormatChecker(),
)


@pytest.mark.parametrize(
    "status",
    [
        "queued",
        "running",
        "retry_wait",
        "waiting_approval",
        "succeeded",
        "partial",
        "failed",
        "cancelled",
        "blocked",
    ],
)
def test_task_projection_matches_frozen_nine_status_union(status):
    service, session, actor, _, _ = read_case(status, result=status == "succeeded")
    with patch("ai_intel.api.public_task_bindings.lock_actor_reference_scope"):
        output = service.read_in_session(session, task_id=TASK_ID, actor=actor)
    VALIDATOR.validate(output)
    assert output["task"]["status"] == status


def test_binding_has_no_second_status_retry_quota_or_raw_credential_authority():
    assert set(public_task_bindings.c.keys()) == {
        "task_id",
        "schema_version",
        "task_type",
        "owner_user_id",
        "tenant_id",
        "authorized_role",
        "actor_reference",
        "public_request_json",
        "request_sha256",
        "trace_id",
        "admitted_at",
        "deadline_at",
        "result_kind",
        "result_id",
        "result_published_at",
    }
    assert {foreign.target_fullname for foreign in public_task_bindings.foreign_keys} == {
        "job_runs.job_id",
        "users.user_id",
    }
    assert {column.name for column in public_task_bindings.primary_key} == {"task_id"}
    ddl = str(CreateTable(public_task_bindings).compile(dialect=postgresql.dialect()))
    assert (
        "result_kind IS NOT NULL AND result_id IS NOT NULL AND result_published_at IS NOT NULL"
        in ddl
    )
    assert "task_type = 'ask' AND result_kind = 'qa_answer'" in ddl
    assert "task_type = 'stack_check' AND result_kind = 'stack_check'" in ddl
    assert "UNIQUE" not in ddl


def test_public_ports_do_not_own_connection_transaction_completion_or_quota():
    source = inspect.getsource(PublicTaskBindingService)
    for forbidden in [
        ".commit(",
        ".rollback(",
        ".close(",
        "engine.connect(",
        "complete_job(",
        "consume_api_key_rate_limit(",
        "generate(",
        "enqueue_job(",
    ]:
        assert forbidden not in source
    assert "clock_timestamp" in source and "require_job_lease" in source


def test_0031_is_additive_forward_only_and_preserves_job_history():
    path = ROOT / "backend/migrations/versions/0031_public_task_bindings.py"
    spec = importlib.util.spec_from_file_location("typed_task_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "0031_public_task_bindings"
    assert migration.down_revision == "0030_revalidation_actor_bindings"
    with patch.object(migration.op, "execute") as execute:
        migration.upgrade()
    statements = [call.args[0] for call in execute.call_args_list]
    assert len(statements) == 2
    assert "CREATE TABLE public_task_bindings" in statements[0]
    assert "BEFORE UPDATE OR DELETE" in statements[1]
    assert "OLD.result_kind IS NOT NULL" in statements[1]
    assert all("DROP " not in sql and "UPDATE job_runs" not in sql for sql in statements)
    with pytest.raises(RuntimeError, match="forward-only recovery"):
        migration.downgrade()
