"""T02 项目骨架验收测试（离线可断言部分）。

覆盖任务卡 T02-C01—C06 中无需真实安装/联网的可观察断言；
安装与构建类验证由主控命令批执行并在 reports/tasks/T02.md 登记。
"""

from __future__ import annotations

import re
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_intel.api.app import create_application

REPO_ROOT = Path(__file__).resolve().parents[3]
DEV_SCRIPT = REPO_ROOT / "scripts" / "dev.py"


def run_dev_script(scope_argument: str) -> subprocess.CompletedProcess[str]:
    """以子进程执行 scripts/dev.py check --scope <scope> 并捕获输出。"""
    return subprocess.run(
        [sys.executable, str(DEV_SCRIPT), "check", "--scope", scope_argument],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def test_unimplemented_scope_exits_nonzero_without_pass(monkeypatch, tmp_path, capsys) -> None:
    """T02-C04：隔离目录确无 integration 测试时非零，不能空跑成功。"""
    from scripts import dev

    monkeypatch.setattr(dev, "PROJECT_ROOT", tmp_path)
    assert dev.main(["check", "--scope", "integration"]) == 3
    captured = capsys.readouterr()
    assert "not_implemented" in captured.err
    assert "PASS" not in captured.out


def test_unknown_scope_is_rejected_with_argument_error() -> None:
    """未知 scope 属参数错误，退出码 2。"""
    completed = run_dev_script("not-a-scope")
    assert completed.returncode == 2


def test_dev_script_repeat_invocation_is_idempotent(monkeypatch, tmp_path) -> None:
    """同一空测试目录重复调用退出码一致且非零，不依赖未来 e2e 是否建设。"""
    from scripts import dev

    monkeypatch.setattr(dev, "PROJECT_ROOT", tmp_path)
    first = dev.main(["check", "--scope", "integration"])
    second = dev.main(["check", "--scope", "integration"])
    assert first == second == 3


def test_health_live_reports_process_liveness() -> None:
    """存活探针仅报告进程可响应。"""
    client = TestClient(create_application())
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "live"}


def test_health_ready_reports_not_ready_without_external_dependencies() -> None:
    """T02-C06 对应的诚实就绪语义：依赖未接入时 503 且 not_ready，不得谎报 ready。"""
    client = TestClient(create_application())
    response = client.get("/health/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["reason"]


def test_application_import_does_not_open_network_connections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T02-C05 对应：导入/装配应用不得发起任何网络连接。"""

    def forbid_socket_connection(*args: object, **kwargs: object) -> None:
        raise AssertionError("application assembly must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", forbid_socket_connection)
    application = create_application()
    assert application.title == "ai-intel-backend"


def test_source_files_contain_no_secret_values() -> None:
    """T02-C05 对应：源码中不得出现密钥值模式（仅允许占位配置名）。"""
    secret_pattern = re.compile(
        r"(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]",
        re.IGNORECASE,
    )
    for source_path in (REPO_ROOT / "scripts").rglob("*.py"):
        assert not secret_pattern.search(source_path.read_text(encoding="utf-8"))
    backend_sources = REPO_ROOT / "backend" / "src"
    for source_path in backend_sources.rglob("*.py"):
        assert not secret_pattern.search(source_path.read_text(encoding="utf-8"))


def test_pyproject_pins_python_312_and_keeps_type_checks_enabled() -> None:
    """T02-C02/C03 对应：锁文件合同声明 Python 3.12；类型检查不被全局关闭。"""
    pyproject_text = (REPO_ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.12,<3.13"' in pyproject_text
    assert "disallow_untyped_defs = true" in pyproject_text
    assert "mypy" in pyproject_text


def test_wrong_node_version_is_rejected_by_engine_guard() -> None:
    """T02-C02 Node 子项：engines 声明 + engine-strict 使错误 Node 版本被明确拒绝而非静默运行。"""
    package_json_text = (REPO_ROOT / "frontend" / "package.json").read_text(encoding="utf-8")
    assert '"node": ">=24.0.0 <25.0.0"' in package_json_text
    npmrc_text = (REPO_ROOT / "frontend" / ".npmrc").read_text(encoding="utf-8")
    assert "engine-strict=true" in npmrc_text
    assert (REPO_ROOT / "frontend" / ".nvmrc").read_text(encoding="utf-8").strip() == "24"


def test_mypy_rejects_injected_type_error_and_recovers(tmp_path) -> None:
    """T02-C03：临时目录类型错误被拒绝，不向业务源码写文件或干扰其它 Agent。"""
    probe_path = tmp_path / "type_probe.py"
    probe_source = (
        '"""临时类型错误探针, 验证后删除."""\n'
        "\n"
        "def _accepts_count(count: int) -> int:\n"
        "    return count\n"
        "\n"
        'PROBE_RESULT: int = _accepts_count("not-a-count")\n'
    )
    probe_path.write_text(probe_source, encoding="utf-8")
    try:
        blocked = subprocess.run(
            [sys.executable, "-m", "mypy", str(probe_path)],
            cwd=str(REPO_ROOT / "backend"),
            capture_output=True,
            text=True,
        )
        assert blocked.returncode != 0
        assert "arg-type" in blocked.stdout
    finally:
        probe_path.unlink()
    recovered = subprocess.run(
        [sys.executable, "-m", "mypy", "src"],
        cwd=str(REPO_ROOT / "backend"),
        capture_output=True,
        text=True,
    )
    assert recovered.returncode == 0


def test_lockfile_exists_for_clean_environment_install() -> None:
    """T02-C01 对应的静态部分：真实锁文件存在（干净安装由主控命令批验证并登记）。"""
    assert (REPO_ROOT / "backend" / "uv.lock").is_file()
    assert (REPO_ROOT / "frontend" / "package-lock.json").is_file()
