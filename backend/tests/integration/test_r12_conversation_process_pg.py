"""Separate Python processes share the same real PG lifecycle; no local slot is authoritative."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import func, select
from tests.r12_conversation_fixtures import context_identity as context_identity
from tests.r12_conversation_fixtures import conversation_database as conversation_database

from ai_intel.answering.conversation_models import qa_conversation_turns

pytestmark = pytest.mark.real_pg
ROOT = Path(__file__).resolve().parents[3]
WORKER = ROOT / "reports/runs/recovery_r12_conversation_context_20261016/pg_worker.py"


def execute_worker(identity, request):
    engine, _auth, _scope, token, _login = identity
    env = dict(
        os.environ,
        R12_CONTEXT_WORKER_URL=engine.url.render_as_string(hide_password=False),
        R12_CONTEXT_WORKER_SESSION=token,
    )
    result = subprocess.run(
        [sys.executable, str(WORKER)],
        input=json.dumps(request).encode(),
        env=env,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, "isolated lifecycle worker failed"
    return json.loads(result.stdout)


def test_pg_two_processes_same_key_have_one_persistent_turn(context_identity):
    request = {
        "operation": "admit",
        "payload": {"question": "Synthetic process probe", "mode": "library"},
        "key": "synthetic-process-key",
        "version": None,
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda unused: execute_worker(context_identity, request), range(2)))
    assert results[0]["turn_id"] == results[1]["turn_id"]
    assert sorted(result["replayed"] for result in results) == [False, True]
    with context_identity[0].connect() as connection:
        assert connection.scalar(select(func.count()).select_from(qa_conversation_turns)) == 1


def test_pg_later_process_reads_original_owner_context_after_restart(context_identity):
    first = execute_worker(
        context_identity,
        {
            "operation": "admit",
            "payload": {"question": "Synthetic restart probe", "mode": "library"},
            "key": "restart-key",
            "version": None,
        },
    )
    restarted = execute_worker(context_identity, {"operation": "read", "turn_id": first["turn_id"]})
    assert restarted["turn_id"] == first["turn_id"]
    assert restarted["answer_id"] == first["answer_id"]
    assert restarted["state"] == "pending"
