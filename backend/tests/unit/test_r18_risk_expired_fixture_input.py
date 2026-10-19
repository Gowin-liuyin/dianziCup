"""The expired-session input obeys the real check constraint and preserves its oracle."""

import ast
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASELINE = "9aa48972fe22c7d0cb04ad63e3b62f793606a5b1"
PG = "backend/tests/integration/test_r18_current_risk_summary_pg.py"
ISSUED_ASSIGNMENT = "    fixture_now = datetime.now(UTC)\n"
EXPIRED_VALUES = (
    "            .values(\n"
    "                issued_at=fixture_now - timedelta(seconds=2),\n"
    "                expires_at=fixture_now - timedelta(seconds=1),\n"
    "            )"
)
OLD_EXPIRED_VALUES = "            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))"


def normalize_expired_fixture_input(source: str) -> str:
    assert source.count(ISSUED_ASSIGNMENT) == 1
    assert source.count(EXPIRED_VALUES) == 1
    return source.replace(ISSUED_ASSIGNMENT, "", 1).replace(EXPIRED_VALUES, OLD_EXPIRED_VALUES, 1)


def baseline_source(path, *, reference=BASELINE):
    return subprocess.run(
        ["git", "show", reference + ":" + path],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    ).stdout


def test_expired_input_changes_only_issued_and_expiry_timestamps_in_the_original_case():
    original = ast.parse(baseline_source(PG))
    current = ast.parse(normalize_expired_fixture_input((ROOT / PG).read_text(encoding="utf-8")))
    assert ast.dump(current, include_attributes=False) == ast.dump(
        original, include_attributes=False
    )
    cases = [
        node
        for node in current.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    assert len(cases) == 11


def test_both_expired_timestamp_values_use_one_aware_observation_and_remain_expired():
    module = ast.parse((ROOT / PG).read_text(encoding="utf-8"))
    case = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "test_actual_pg_revoked_actor_cannot_read_even_unknown_request"
    )
    sample = next(
        node
        for node in case.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "fixture_now"
    )
    assert ast.dump(sample.value) == ast.dump(ast.parse("datetime.now(UTC)").body[0].value)
    values = next(
        node
        for node in ast.walk(case)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "values"
    )
    expressions = {keyword.arg: keyword.value for keyword in values.keywords}
    assert set(expressions) == {"issued_at", "expires_at"}
    observed = datetime(2026, 10, 17, 1, 30, tzinfo=UTC)
    actual = {
        key: eval(
            compile(ast.Expression(expression), "expired_fixture_input", "eval"),
            {"__builtins__": {}, "fixture_now": observed, "timedelta": timedelta},
        )
        for key, expression in expressions.items()
    }
    assert actual["issued_at"] < actual["expires_at"] < observed
    assert actual["expires_at"] - actual["issued_at"] == timedelta(seconds=1)
    assert actual["issued_at"].tzinfo is UTC and actual["expires_at"].tzinfo is UTC
    constraint = (ROOT / "backend/migrations/versions/0006_auth_state.py").read_text(
        encoding="utf-8"
    )
    assert 'CheckConstraint("expires_at > issued_at", name="ck_auth_session_expiry")' in constraint


def test_the_old_recently_issued_input_was_invalid_and_the_new_pair_is_always_legal():
    observed = datetime(2026, 10, 17, 1, 30, tzinfo=UTC)
    originally_issued = observed - timedelta(milliseconds=873)
    expired = observed - timedelta(seconds=1)
    assert expired <= originally_issued
    assert expired > observed - timedelta(seconds=2)


def test_existing_production_blobs_are_unchanged():
    for path in (
        "backend/src/ai_intel/api/public_risk_summary.py",
        "backend/src/ai_intel/api/auth_state.py",
        "backend/src/ai_intel/assessment/assessment_service.py",
        "backend/src/ai_intel/assessment/rule_persistence.py",
        "backend/src/ai_intel/assessment/rule_service.py",
        "backend/src/ai_intel/knowledge/structured_fact_proofs.py",
    ):
        reference = (
            BASELINE
            if path == "backend/src/ai_intel/api/public_risk_summary.py"
            else "0291d197587141b9f7f5da0d01800d8cbdf58d11"
        )
        assert (ROOT / path).read_text(encoding="utf-8") == baseline_source(
            path, reference=reference
        )
