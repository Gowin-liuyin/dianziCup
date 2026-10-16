"""Explicit expected-failure probe; excluded from default test filename collection."""

import json
import subprocess
from collections.abc import Callable

from pydantic import SecretStr
from sqlalchemy.engine import make_url


def test_registered_failure_redaction(
    register_sensitive_failure_value: Callable[[SecretStr], None],
) -> None:
    result = subprocess.run(
        [
            "C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/"
            "dependencies/native/powershell/pwsh.exe",
            "-NoProfile",
            "-Command",
            "$r18Protected=Get-Content -LiteralPath "
            "'D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi' -Raw; "
            "$r18Clear=$r18Protected | ConvertTo-SecureString | "
            "ConvertFrom-SecureString -AsPlainText; [Console]::Write($r18Clear)",
        ],
        capture_output=True,
        timeout=15,
        check=True,
    )
    secret = SecretStr(json.loads(result.stdout)["TEST_DATABASE_URL"])
    password = SecretStr(make_url(secret.get_secret_value()).password or "")
    register_sensitive_failure_value(secret)
    register_sensitive_failure_value(password)
    raise AssertionError(secret.get_secret_value() + " " + password.get_secret_value())
