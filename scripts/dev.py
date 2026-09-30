"""项目运维与检查入口: 按 scope 分派质量检查, 管理本地开发依赖服务。

check 退出码合同:
- 0: 所请求的检查已实际执行且通过;
- 1: 已执行但未通过(透传底层工具退出码);
- 2: 参数错误(未知 scope 等);
- 3: 所请求 scope 尚未建设(输出 not_implemented), 绝不打印 PASS。

services 退出码合同:
- 0: 全部依赖健康或启停命令成功;
- 4: 依赖降级(可选依赖未运行), 输出 degraded, 不谎报全依赖就绪;
- 2: 参数错误; 1: 命令执行失败。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
COMPOSE_FILE = PROJECT_ROOT / "infra" / "compose" / "compose.yaml"
SUPPORTED_SCOPES = ("unit", "contract", "integration", "security", "frontend", "e2e", "all")
IMPLEMENTED_SCOPES = ("unit", "integration")

SCOPE_CHECK_COMMANDS: dict[str, list[str]] = {
    "unit": ["uv", "run", "pytest", "tests/unit"],
    "integration": ["uv", "run", "pytest", "tests/integration", "--cov-fail-under=0"],
}

REQUIRED_DEPENDENCY_SERVICES = ("postgres", "redis")
OPTIONAL_DEPENDENCY_SERVICES = ("opensearch",)


class NotImplementedErrorScope(Exception):
    """请求的检查范围尚未建设, 调用方应以退出码 3 结束而非假装通过。"""

    def __init__(self, scope: str) -> None:
        super().__init__(f"check scope not_implemented: {scope}")
        self.scope = scope


def resolve_check_command(requested_scope: str, project_root: Path) -> list[str]:
    """返回指定 scope 的检查命令; 未建设的 scope 抛出 NotImplementedErrorScope。"""
    if requested_scope not in SUPPORTED_SCOPES:
        raise ValueError(f"unknown scope: {requested_scope}")
    if requested_scope not in IMPLEMENTED_SCOPES:
        raise NotImplementedErrorScope(requested_scope)
    return list(SCOPE_CHECK_COMMANDS[requested_scope])


def run_scope_checks(requested_scope: str) -> int:
    """执行已建设 scope 的检查并透传底层退出码。"""
    command = resolve_check_command(requested_scope, PROJECT_ROOT)
    completed = subprocess.run(command, cwd=BACKEND_DIR)
    return completed.returncode


def run_compose_services(*arguments: str) -> subprocess.CompletedProcess[str]:
    """对开发编排执行 docker compose 子命令, 统一 profile 与文件路径。"""
    return subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "--profile", "core", "--profile", "search", *arguments],
        capture_output=True,
        text=True,
    )


def start_development_services() -> int:
    """启动 core+search 开发依赖; 关闭不在此路径发生。"""
    completed = run_compose_services("up", "-d")
    sys.stdout.write(completed.stdout)
    sys.stderr.write(completed.stderr)
    return 0 if completed.returncode == 0 else 1


def stop_development_services(confirm_destroy: bool) -> int:
    """关闭开发服务; 默认保留数据卷, 销毁数据必须显式确认。"""
    arguments = ["down"]
    if confirm_destroy:
        arguments.append("-v")
    completed = run_compose_services(*arguments)
    sys.stdout.write(completed.stdout)
    sys.stderr.write(completed.stderr)
    return 0 if completed.returncode == 0 else 1


def probe_dependency_states() -> dict[str, str]:
    """逐服务探测真实状态; 不可用/未运行如实记录, 不猜测。"""
    states: dict[str, str] = {}
    ps_probe = run_compose_services("ps", "--format", "{{.Service}} {{.State}} {{.Health}}")
    observed = ps_probe.stdout if ps_probe.returncode == 0 else ""
    for service in (*REQUIRED_DEPENDENCY_SERVICES, *OPTIONAL_DEPENDENCY_SERVICES):
        matching_lines = [line for line in observed.splitlines() if line.startswith(service + " ")]
        if not matching_lines:
            states[service] = "not_running"
        elif "healthy" in matching_lines[0]:
            states[service] = "healthy"
        else:
            states[service] = "starting_or_unhealthy"
    return states


def report_dependencies() -> int:
    """输出依赖就绪报告: 可选依赖未运行记 degraded, 不谎报全依赖就绪。"""
    states = probe_dependency_states()
    required_ready = all(states[name] == "healthy" for name in REQUIRED_DEPENDENCY_SERVICES)
    search_ready = states.get("opensearch") == "healthy"
    for name, state in states.items():
        print(f"{name}: {state}")
    if not required_ready:
        print("overall: not_ready (required dependency unhealthy)")
        return 1
    if not search_ready:
        print("overall: degraded (search profile not running; 检索能力降级, 非全依赖 ready)")
        return 4
    print("overall: ready")
    return 0


def build_argument_parser() -> argparse.ArgumentParser:
    """构造命令行解析器: check --scope 与 services up/down/deps-check。"""
    parser = argparse.ArgumentParser(prog="dev.py", description="项目质量检查与本地开发服务入口")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="执行指定范围的质量检查")
    check_parser.add_argument(
        "--scope",
        required=True,
        choices=SUPPORTED_SCOPES,
        help="检查范围; 未建设的范围返回 not_implemented(退出码 3)",
    )

    services_parser = subparsers.add_parser("services", help="管理本地开发依赖服务")
    services_parser.add_argument(
        "action",
        choices=["up", "down", "deps-check"],
        help="启动/关闭(默认保留数据卷)/依赖就绪检查",
    )
    services_parser.add_argument(
        "--confirm-destroy",
        action="store_true",
        help="仅 services down 有效: 显式确认删除数据卷(危险操作)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """解析参数并执行对应动作; 返回符合退出码合同的退出码。"""
    parser = build_argument_parser()
    try:
        arguments = parser.parse_args(argv)
    except SystemExit as exit_info:
        return 2 if exit_info.code not in (0, None) else 0

    if arguments.command == "check":
        try:
            return run_scope_checks(arguments.scope)
        except NotImplementedErrorScope as not_ready:
            print(f"ERROR not_implemented: {not_ready.scope}", file=sys.stderr)
            return 3
        except ValueError as invalid_scope:
            print(f"ERROR invalid scope: {invalid_scope}", file=sys.stderr)
            return 2

    if arguments.command == "services":
        if arguments.action == "up":
            return start_development_services()
        if arguments.action == "down":
            return stop_development_services(arguments.confirm_destroy)
        return report_dependencies()

    return 2


if __name__ == "__main__":
    sys.exit(main())
