"""动态会话值与真实SQLAlchemy异常参数不依赖env，也必须保护失败报告。"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from test_r01_tls_failure_privacy import run_failure_probe


@pytest.mark.parametrize("case", ["session", "sql", "registered"])
def test_dynamic_failure_locals_and_sql_parameters_are_redacted(
    tmp_path: Path,
    case: str,
) -> None:
    result, junit, leaked = run_failure_probe(
        tmp_path,
        """import hashlib, os, secrets
from sqlalchemy.exc import ProgrammingError
from pydantic import SecretStr
OBSERVED = []
def test_failure(request):
    if os.environ["DYNAMIC_CASE"] == "registered":
        stored = secrets.token_hex(32)
        OBSERVED.append(stored)
        request.getfixturevalue("register_sensitive_failure_value")(SecretStr(stored))
        assert False, "controlled alias-value failure"
    elif os.environ["DYNAMIC_CASE"] == "session":
        token = secrets.token_urlsafe(32)
        session_hash = hashlib.sha256(token.encode()).hexdigest()
        csrf_token = secrets.token_urlsafe(32)
        secret_key = secrets.token_urlsafe(32)
        access_key = secrets.token_urlsafe(32)
        OBSERVED.extend([token, session_hash, csrf_token, secret_key, access_key])
        print(token[8:24], session_hash[16:40])
        assert False, "controlled session-state failure"
    else:
        parameters = [{"session_hash": secrets.token_hex(32),
                       "password": secrets.token_urlsafe(32)},
                      {"authorization": "Bearer " + secrets.token_urlsafe(32),
                       "cookie": secrets.token_urlsafe(32)}]
        OBSERVED.extend(value for row in parameters for value in row.values())
        positional = (secrets.token_hex(32), secrets.token_urlsafe(32))
        OBSERVED.extend(positional)
        parameters.append(positional)
        parameters.append({"cycle": parameters})
        raise ProgrammingError("INSERT INTO auth_sessions VALUES (:session_hash)",
                               parameters, RuntimeError("controlled SQL failure"))
""",
        {"DYNAMIC_CASE": case},
    )
    assert not leaked, "native pytest leaked a dynamic session or SQL credential"
    assert result.returncode == 1
    suites = ET.fromstring(junit).findall("testsuite")
    assert sum(int(suite.get("tests", "0")) for suite in suites) == 1
    assert sum(int(suite.get("failures", "0")) for suite in suites) == 1
    assert sum(int(suite.get("errors", "0")) for suite in suites) == 0
    assert sum(int(suite.get("skipped", "0")) for suite in suites) == 0
    assert "redacted test credential" in result.stdout and "redacted test credential" in junit
    assert not (tmp_path / "privacy.xml").exists()


def test_failure_collector_ignores_object_attributes_and_repr() -> None:
    from conftest import collect_failure_credentials

    class Uninspectable:
        def __getattribute__(self, name: str) -> object:
            raise AssertionError("failure collector must not read object attributes")

        def __repr__(self) -> str:
            raise AssertionError("failure collector must not call object repr")

    def failed_query() -> None:
        parameters = {"password": Uninspectable(), "session_hash": "dev-only-not-a-secret"}
        parameters["cycle"] = parameters
        raise RuntimeError("controlled query failure")

    call = pytest.CallInfo.from_call(failed_query, when="call")
    assert collect_failure_credentials(call) == ("dev-only-not-a-secret",)
