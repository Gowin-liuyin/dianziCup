"""R01 检查入口负例：隔离资源、实际测试计数、超时和失败必须可观察。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from scripts import dev


def _database_environment() -> dict[str, str]:
    return {
        "DIANZI_TEST_RUN_ID": "quality_20261014",
        "TEST_DATABASE_URL": "postgresql+psycopg://test_quality:synthetic@127.0.0.1:25432/test_dianzi_quality_20261014",
    }


@pytest.mark.parametrize(
    "url",
    [
        "",
        "sqlite:///test_dianzi_quality_20261014",
        "postgresql://test_quality:synthetic@127.0.0.1:5432/test_dianzi_quality_20261014",
        "postgresql://test_quality:synthetic@192.0.2.1:25432/test_dianzi_quality_20261014",
        "postgresql://ai_intel:synthetic@127.0.0.1:25432/test_dianzi_quality_20261014",
        "postgresql://test_quality:synthetic@127.0.0.1:25432/ai_intel",
        "postgresql://test_quality:synthetic@127.0.0.1:25432/test_dianzi_other",
        "postgresql://test_quality:synthetic@127.0.0.1:0/test_dianzi_quality_20261014",
        "postgresql://test_quality:synthetic@127.0.0.1:25432/test_dianzi_quality_20261014?host=example.com",
    ],
)
def test_unsafe_test_database_is_rejected_without_echoing_credentials(url) -> None:
    environment = _database_environment()
    environment["TEST_DATABASE_URL"] = url
    with pytest.raises(dev.TestEnvironmentError) as rejected:
        dev.require_isolated_test_database(environment)
    assert "synthetic" not in str(rejected.value)
    assert url == "" or url not in str(rejected.value)


def test_isolated_database_accepts_explicit_test_identity() -> None:
    environment = _database_environment()
    assert dev.require_isolated_test_database(environment) == environment["TEST_DATABASE_URL"]


def test_ci_flag_does_not_bypass_isolation_but_named_container_does() -> None:
    environment = _database_environment()
    environment["CI"] = "true"
    environment["TEST_DATABASE_URL"] = environment["TEST_DATABASE_URL"].replace("25432", "5432")
    with pytest.raises(dev.TestEnvironmentError):
        dev.require_isolated_test_database(environment)
    environment["DIANZI_TEST_ISOLATION"] = "container"
    with pytest.raises(dev.TestEnvironmentError):
        dev.require_isolated_test_database(environment)
    environment["TEST_DATABASE_URL"] = environment["TEST_DATABASE_URL"].replace(
        "test_quality:", "test_dianzi_quality_20261014:"
    )
    assert dev.require_isolated_test_database(environment) == environment["TEST_DATABASE_URL"]


@pytest.mark.parametrize(
    "scope", ["unit", "contract", "integration", "security", "frontend", "e2e"]
)
def test_missing_test_entry_is_not_implemented(scope, tmp_path) -> None:
    with pytest.raises(dev.NotImplementedErrorScope):
        dev.resolve_check_command(scope, tmp_path)


@pytest.mark.parametrize(
    "cases,tool_exit,expected",
    [
        ("", 0, 3),
        ("<testcase name='passed'/>", 0, 0),
        ("<testcase><skipped/></testcase>", 0, 4),
        ("<testcase/><testcase><skipped/></testcase>", 0, 4),
        ("<testcase><failure/></testcase>", 0, 1),
        ("<testcase><error/></testcase>", 0, 1),
        ("<testcase/>", 7, 7),
    ],
)
def test_real_junit_cases_control_success(cases, tool_exit, expected, tmp_path) -> None:
    report = tmp_path / "junit.xml"
    report.write_text(
        f"<testsuites tests='99'><testsuite tests='99'>{cases}</testsuite></testsuites>",
        encoding="utf-8",
    )
    assert dev._report_result("contract", report, tool_exit) == expected


def test_missing_or_malformed_junit_never_passes(tmp_path) -> None:
    report = tmp_path / "junit.xml"
    assert dev._report_result("contract", report, 0) == 1
    report.write_text("not xml", encoding="utf-8")
    assert dev._report_result("contract", report, 0) == 1


def test_subprocess_timeout_is_real_nonzero_and_finite(tmp_path) -> None:
    result = dev._run_command([sys.executable, "-c", "import time; time.sleep(30)"], tmp_path, 1)
    assert result.returncode == 124


def test_all_runs_every_scope_even_after_a_failure(monkeypatch, capsys) -> None:
    observed = []
    actual_runner = dev.run_scope_checks

    def record_scope(scope, timeout_seconds=600, fixture_only=False):
        observed.append(scope)
        return 1 if scope == "unit" else 0

    monkeypatch.setattr(dev, "run_scope_checks", record_scope)
    assert actual_runner("all") == 1
    assert observed == list(dev.SUPPORTED_SCOPES[:-1])
    assert json.loads(capsys.readouterr().out)["exits"]["unit"] == 1


def test_unhealthy_compose_state_is_not_healthy(monkeypatch) -> None:
    payload = '{"Service":"postgres","State":"running","Health":"unhealthy"}'
    monkeypatch.setattr(
        dev, "run_compose_services", lambda *args: subprocess.CompletedProcess([], 0, payload, "")
    )
    assert dev.probe_dependency_states()["postgres"] == "starting_or_unhealthy"


def test_services_refuse_implicit_project_before_spawning(monkeypatch) -> None:
    monkeypatch.delenv("DIANZI_COMPOSE_PROJECT", raising=False)
    with pytest.raises(dev.TestEnvironmentError):
        dev.run_compose_services("down")


def test_volume_destruction_refuses_development_project(monkeypatch) -> None:
    environment = _database_environment()
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("DIANZI_COMPOSE_PROJECT", "dianzi-dev-quality_20261014")
    with pytest.raises(dev.TestEnvironmentError):
        dev.stop_development_services(True)


def test_integration_modules_collect_without_network_or_migrations(monkeypatch) -> None:
    import importlib.util
    import socket

    def forbid_io(*args, **kwargs):
        raise AssertionError("module import must not perform IO")

    monkeypatch.setattr(socket.socket, "connect", forbid_io)
    monkeypatch.setattr(socket.socket, "connect_ex", forbid_io)
    monkeypatch.setattr(subprocess, "run", forbid_io)
    for relative in [
        "integration/test_t03_development_services.py",
        "integration/test_t05_persistence_and_raw_store.py",
        "integration/test_t07_jobs_and_outbox.py",
        "contract/test_t07_jobs_outbox.py",
    ]:
        filename = Path(__file__).parents[1] / relative
        spec = importlib.util.spec_from_file_location(filename.stem, filename)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)


def test_failed_pytest_case_redacts_connection_in_terminal_and_junit(tmp_path) -> None:
    """真实失败 outcome 保留，终端/JUnit 均不含 test 连接秘密。"""
    probe = tmp_path / "failure_probe.py"
    probe.write_text(
        "import os\ndef test_deliberate_failure():\n"
        "    assert False, os.environ['TEST_DATABASE_URL']\n",
        encoding="utf-8",
    )
    report = tmp_path / "failure.xml"
    environment = dict(os.environ)
    environment["TEST_DATABASE_URL"] = (
        "postgresql://test_quality:quality-secret-marker@127.0.0.1:25434/test_dianzi_quality"
    )
    environment["PYTHONPATH"] = str(Path(__file__).parents[1])
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--noconftest",
            "-p",
            "conftest",
            f"--rootdir={probe.parent}",
            str(probe),
            "-o",
            "addopts=",
            "-q",
            f"--junitxml={report}",
        ],
        cwd=Path(__file__).parents[2],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert completed.returncode == 1
    for output in (completed.stdout, completed.stderr, report.read_text(encoding="utf-8")):
        assert "quality-secret-marker" not in output
        assert environment["TEST_DATABASE_URL"] not in output
    assert "1 failed" in completed.stdout


@pytest.mark.parametrize("console_encoding", ["ascii", "gbk"])
def test_cli_encodes_chinese_help_as_utf8_on_legacy_console(console_encoding) -> None:
    """实际CLI不依赖调用者设置UTF8，也不因工具Unicode输出误报检查失败。"""
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = console_encoding
    completed = subprocess.run(
        [sys.executable, str(dev.PROJECT_ROOT / "scripts/dev.py"), "check", "--help"],
        capture_output=True,
        encoding="utf-8",
        env=environment,
        timeout=10,
    )
    assert completed.returncode == 0
    assert "离线子集" in completed.stdout
