"""Freeze the authorized exception-import replacement and one raises-name change."""

import ast
import copy
import hashlib
import json
from contextlib import nullcontext
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from test_r18_actor_references import NOW, TOKEN, connection_for, session_row

from ai_intel.api.actor_references import (
    InvalidActorReferenceError,
    create_actor_reference,
)
from ai_intel.api.credentials import SessionCredential
from ai_intel.api.public_task_bindings import PublicTaskBindingService

PATH = Path(__file__).resolve().parents[1] / "integration/test_r18_public_task_binding_pg.py"
CASE_NAME = "test_credential_lock_wait_denies_expired_actor_before_result_read"
BASELINE_IMPORTS_SHA256 = "09f57ef4b0027604e9d0644dc3a78066b673f7e56d991233e9f39942899d4add"
BASELINE_NONIMPORTS_SHA256 = "515ca803ed490caf03bd063d9fb786b344e89d1ebf523f701181c574668ae686"


def module_tree():
    return ast.parse(PATH.read_text(encoding="utf-8"))


def expiry_raises(tree):
    case = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == CASE_NAME
    )
    calls = [
        node
        for node in ast.walk(case)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "raises"
    ]
    assert len(calls) == 1
    return calls[0]


def import_record(module, name):
    return ast.dump(ast.ImportFrom(module=module, names=[ast.alias(name=name)], level=0))


def test_exception_import_set_replaces_only_the_unused_cookie_exception():
    records = []
    for node in module_tree().body:
        if isinstance(node, ast.ImportFrom):
            records.extend(
                ast.dump(ast.ImportFrom(module=node.module, names=[alias], level=node.level))
                for alias in node.names
            )
        elif isinstance(node, ast.Import):
            records.extend(ast.dump(ast.Import(names=[alias])) for alias in node.names)
    actor = import_record("ai_intel.api.actor_references", "InvalidActorReferenceError")
    cookie = import_record("ai_intel.api.authentication", "SessionExpiredError")
    assert records.count(actor) == 1 and cookie not in records
    records.remove(actor)
    records.append(cookie)
    assert (
        hashlib.sha256(json.dumps(sorted(records)).encode()).hexdigest() == BASELINE_IMPORTS_SHA256
    )


def test_target_raises_is_exact_actor_reference_error_not_a_broader_permission_error():
    call = expiry_raises(module_tree())
    assert len(call.args) == 1
    assert ast.dump(call.args[0]) == "Name(id='InvalidActorReferenceError', ctx=Load())"


def test_all_original_case_bodies_waits_assertions_and_fixtures_remain_identical():
    tree = copy.deepcopy(module_tree())
    call = expiry_raises(tree)
    assert isinstance(call.args[0], ast.Name) and call.args[0].id == "InvalidActorReferenceError"
    call.args[0].id = "SessionExpiredError"
    tree.body = [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
    assert hashlib.sha256(ast.dump(tree).encode()).hexdigest() == BASELINE_NONIMPORTS_SHA256


def test_direct_actor_lock_expiry_refuses_before_reader_or_business_sql():
    row = session_row()
    row["expires_at"] = NOW + timedelta(seconds=0.2)
    connection = connection_for(row)
    actor = create_actor_reference(connection, SessionCredential(TOKEN), NOW)
    reader = MagicMock()
    service = PublicTaskBindingService(MagicMock(spec=Engine), result_reader=reader)
    service._connection = MagicMock(return_value=connection)
    service._session_fence = MagicMock(side_effect=lambda session: nullcontext())
    service._now = MagicMock(return_value=NOW)
    session = MagicMock(spec=Session)
    with (
        patch("ai_intel.api.actor_references.monotonic", side_effect=[0.0, 0.4]),
        pytest.raises(InvalidActorReferenceError) as refused,
    ):
        service.read_in_session(session, task_id=uuid4(), actor=actor)
    assert refused.type is InvalidActorReferenceError
    reader.read_qa_answer_in_session.assert_not_called()
    reader.read_stack_check_in_session.assert_not_called()
    session.execute.assert_not_called()
    session.commit.assert_not_called()
