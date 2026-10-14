"""管理CLI不回显数据库参数；合成异常不计真实PG验证。"""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError


@pytest.mark.parametrize("error_type", [IntegrityError, OperationalError])
def test_admin_database_errors_do_not_echo_sql_or_password_hash(
    error_type: type[IntegrityError] | type[OperationalError],
) -> None:
    module_path = Path(__file__).resolve().parents[3] / "scripts/admin_user.py"
    specification = importlib.util.spec_from_file_location("admin_user_redaction", module_path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    marker = "synthetic-private-hash-not-for-logs"
    failure = error_type("INSERT private_sql", {"password_hash": marker}, RuntimeError(marker))
    message = module.describe_user_creation_failure(failure)
    assert message.startswith("ERROR ")
    assert marker not in message and "private_sql" not in message and "password_hash" not in message
