"""故意失败的子 pytest 保持失败数量，终端和内存 JUnit 均不得泄漏凭据。"""

from __future__ import annotations

import base64
import json
import os
import secrets
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import SecretStr

ROOT = Path(__file__).resolve().parents[3]
MEMORY_JUNIT_PLUGIN = """import base64, builtins, io, json, os, sys
original_open = builtins.open
junit = None
class MemoryJUnit(io.StringIO):
    def close(self):
        pass
def memory_open(file, mode="r", *args, **kwargs):
    global junit
    if (isinstance(file, (str, os.PathLike))
            and os.fspath(file).endswith("privacy.xml") and "w" in mode):
        junit = MemoryJUnit()
        return junit
    return original_open(file, mode, *args, **kwargs)
def pytest_configure(config):
    builtins.open = memory_open
def pytest_unconfigure(config):
    builtins.open = original_open
    if junit is not None:
        print("MEMORY_JUNIT=" + base64.b64encode(junit.getvalue().encode()).decode())
    observed = getattr(sys.modules.get("test_failure"), "OBSERVED", ())
    print("MEMORY_CREDENTIALS=" + base64.b64encode(json.dumps(observed).encode()).decode())
"""


def run_failure_probe(
    tmp_path: Path,
    source: str,
    environment: dict[str, str],
    credentials: tuple[SecretStr, ...] = (),
) -> tuple[subprocess.CompletedProcess[str], str, bool]:
    """JUnit只留内存；测试自身失效时，也先移除随机测试凭据再向父pytest报告。"""
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (tmp_path / "conftest.py").write_text(
        (ROOT / "backend/tests/conftest.py").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "memory_junit.py").write_text(MEMORY_JUNIT_PLUGIN, encoding="utf-8")
    (tmp_path / "test_failure.py").write_text(source, encoding="utf-8")
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            "pytest.ini",
            "-p",
            "memory_junit",
            "test_failure.py",
            "--showlocals",
            "--no-cov",
            "--junitxml=privacy.xml",
            "-q",
        ],
        cwd=tmp_path,
        env=dict(os.environ, **environment, PYTHONPATH=str(tmp_path), PYTEST_ADDOPTS=""),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    encoded = next(
        line.removeprefix("MEMORY_JUNIT=")
        for line in result.stdout.splitlines()
        if line.startswith("MEMORY_JUNIT=")
    )
    junit = base64.b64decode(encoded).decode()
    encoded = next(
        line.removeprefix("MEMORY_CREDENTIALS=")
        for line in result.stdout.splitlines()
        if line.startswith("MEMORY_CREDENTIALS=")
    )
    observed = tuple(SecretStr(value) for value in json.loads(base64.b64decode(encoded)))
    encoded = ""
    output = "\n".join(
        line
        for line in result.stdout.splitlines()
        if not line.startswith(("MEMORY_JUNIT=", "MEMORY_CREDENTIALS="))
    )
    safe_output, safe_junit, safe_stderr = output, junit, result.stderr
    for secret in (*credentials, *observed):
        for value in (
            secret.get_secret_value(),
            *(
                secret.get_secret_value()[index : index + 8]
                for index in range(len(secret.get_secret_value()) - 7)
            ),
        ):
            safe_output = safe_output.replace(value, "[privacy probe redacted]")
            safe_junit = safe_junit.replace(value, "[privacy probe redacted]")
            safe_stderr = safe_stderr.replace(value, "[privacy probe redacted]")
    leaked = (safe_output, safe_junit, safe_stderr) != (output, junit, result.stderr)
    result = subprocess.CompletedProcess(result.args, result.returncode, safe_output, safe_stderr)
    output, junit = "", ""
    evidence_directory = os.environ.get("DIANZI_PRIVACY_PROBE_EVIDENCE_DIRECTORY")
    if evidence_directory:
        directory = Path(evidence_directory)
        name = environment.get("DYNAMIC_CASE", environment.get("FAILURE_PHASE", "probe"))
        directory.mkdir(parents=True, exist_ok=True)
        evidence_output = safe_output + safe_stderr
        for marker in (
            "[redacted test credential]",
            "[redacted test credential fragment]",
            "[privacy probe redacted]",
        ):
            evidence_output = evidence_output.replace("'" + marker + "'", marker)
            evidence_output = evidence_output.replace('"' + marker + '"', marker)
        (directory / (name + ".log")).write_text(evidence_output, encoding="utf-8")
        (directory / (name + ".xml")).write_text(safe_junit, encoding="utf-8")
        (directory / (name + ".json")).write_text(
            json.dumps(
                {
                    "command": result.args,
                    "start": started,
                    "end": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
                    "exit_code": result.returncode,
                    "full_or_eight_character_leak_before_write": leaked,
                    "generated_secret_values_in_environment": bool(credentials),
                    "dynamic_values_generated_in_child": bool(observed),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return result, safe_junit, leaked


@pytest.mark.parametrize("phase", ["setup", "call"])
def test_tls_failure_report_redacts_full_and_truncated_credentials(
    tmp_path: Path,
    phase: str,
) -> None:
    secret = SecretStr(secrets.token_urlsafe(48))
    result, junit, leaked = run_failure_probe(
        tmp_path,
        """import os, pytest
@pytest.fixture
def tls_fixture():
    configured = {"password": os.environ["TEST_SEARCH_TLS_PASSWORD"]}
    if os.environ["FAILURE_PHASE"] == "setup":
        prefix = configured["password"][:24]
        suffix = configured["password"][-16:]
        raise pytest.UsageError("blocked: " + prefix + "..." + suffix)
    return configured
def test_failure(tls_fixture):
    password = tls_fixture["password"]
    print(password[8:24])
    assert False, password
""",
        {"TEST_SEARCH_TLS_PASSWORD": secret.get_secret_value(), "FAILURE_PHASE": phase},
        (secret,),
    )
    assert not leaked, "child pytest leaked a known TLS credential fragment"
    assert result.returncode == 1
    suites = ET.fromstring(junit).findall("testsuite")
    counts = {
        key: sum(int(suite.get(key, "0")) for suite in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    assert counts == {
        "tests": 1,
        "failures": int(phase == "call"),
        "errors": int(phase == "setup"),
        "skipped": 0,
    }
    assert "redacted test credential" in result.stdout and "redacted test credential" in junit
    assert not (tmp_path / "privacy.xml").exists()
