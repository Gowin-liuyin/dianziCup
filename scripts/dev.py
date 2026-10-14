"""实际质量检查与隔离 Compose 入口，不把零测试、skip 或缺资源记为通过。

退出码：0 实际通过；1 失败；2 参数错误；3 未建设/零测试；4 资源阻塞；
124 超时。其它底层工具非零退出码保留。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree
from collections.abc import Mapping
from pathlib import Path, PureWindowsPath
from urllib.parse import unquote, urlsplit

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
COMPOSE_FILE = PROJECT_ROOT / "infra" / "compose" / "compose.yaml"
SUPPORTED_SCOPES = ("unit", "contract", "integration", "security", "frontend", "e2e", "all")
REQUIRED_DEPENDENCY_SERVICES = ("postgres", "redis")
OPTIONAL_DEPENDENCY_SERVICES = ("opensearch",)


class NotImplementedErrorScope(Exception):
    """所需测试入口不存在，不允许空跑成功。"""

    def __init__(self, scope: str) -> None:
        super().__init__(f"check scope not_implemented: {scope}")
        self.scope = scope


class TestEnvironmentError(RuntimeError):
    """隔离资源输入不满足约束；错误不包含连接串或秘密值。"""


def require_isolated_test_database(environment: Mapping[str, str] | None = None) -> str:
    """仅允许显式命名、loopback、独立端口的 PostgreSQL 测试库。"""
    configured = os.environ if environment is None else environment
    run_id = configured.get("DIANZI_TEST_RUN_ID", "")
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,47}", run_id):
        raise TestEnvironmentError("DIANZI_TEST_RUN_ID must be a lowercase test identifier")
    database_url = configured.get("TEST_DATABASE_URL", "")
    try:
        parsed = urlsplit(database_url)
        port = parsed.port
    except ValueError:
        raise TestEnvironmentError("TEST_DATABASE_URL has invalid URL syntax") from None
    if parsed.scheme not in {"postgresql", "postgresql+psycopg"}:
        raise TestEnvironmentError("TEST_DATABASE_URL must use PostgreSQL")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise TestEnvironmentError("TEST_DATABASE_URL must use loopback")
    database_name = unquote(parsed.path.removeprefix("/"))
    if database_name != f"test_dianzi_{run_id}" or parsed.query or parsed.fragment:
        raise TestEnvironmentError(
            "TEST_DATABASE_URL must identify the exact isolated test database"
        )
    username = unquote(parsed.username or "")
    if not re.fullmatch(r"test_[a-z0-9_]+", username) or not parsed.password:
        raise TestEnvironmentError(
            "TEST_DATABASE_URL requires a dedicated test user and credential"
        )
    if port is None or port < 1:
        raise TestEnvironmentError("TEST_DATABASE_URL requires an explicit test port")
    if port == 5432 and (
        configured.get("DIANZI_TEST_ISOLATION") != "container" or username != database_name
    ):
        raise TestEnvironmentError("port 5432 requires isolated container and matching test user")
    return database_url


def require_test_service_url(variable: str, scheme: str, normal_port: int) -> str:
    """附属测试服务限定本地独立端口，不输出秘密连接配置。"""
    service_url = os.environ.get(variable, "")
    try:
        parsed = urlsplit(service_url)
        port = parsed.port
    except ValueError:
        raise TestEnvironmentError(f"{variable} has invalid URL syntax") from None
    if parsed.scheme != scheme or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise TestEnvironmentError(f"{variable} must identify a loopback {scheme} test service")
    if port is None or port == normal_port or parsed.fragment:
        raise TestEnvironmentError(f"{variable} requires an isolated service port")
    return service_url


def _run_command(
    command: list[str],
    working_directory: Path,
    timeout_seconds: int,
    environment: Mapping[str, str] | None = None,
    emit_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    child_environment = dict(os.environ if environment is None else environment)
    child_environment["PYTHONIOENCODING"] = "utf-8"
    if sys.platform == "win32":
        group_flags = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        group_flags = 0
    with subprocess.Popen(
        command,
        cwd=working_directory,
        env=child_environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=os.name != "nt",
        creationflags=group_flags,
    ) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
            returncode = process.returncode
        except subprocess.TimeoutExpired:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    timeout=15,
                )
            else:
                os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate(timeout=15)
            returncode = 124
    for name in ("TEST_DATABASE_URL", "TEST_REDIS_URL"):
        secret_url = child_environment.get(name)
        if secret_url:
            stdout = stdout.replace(secret_url, "[redacted test connection]")
            stderr = stderr.replace(secret_url, "[redacted test connection]")
    if emit_output:
        sys.stdout.write(stdout)
        sys.stderr.write(stderr)
    return subprocess.CompletedProcess(command, returncode, stdout, stderr)


def read_test_report(report_path: Path) -> dict[str, int]:
    """数实际 JUnit 用例，避免重复累计父子 testsuite 的汇总属性。"""
    root = ElementTree.parse(report_path).getroot()
    cases = root.findall(".//testcase")
    return {
        "tests": len(cases),
        "failed": sum(case.find("failure") is not None for case in cases),
        "errors": sum(case.find("error") is not None for case in cases),
        "skipped": sum(case.find("skipped") is not None for case in cases),
    }


def resolve_check_command(requested_scope: str, project_root: Path) -> list[str]:
    """校验 scope 和真实入口，返回首条执行命令。"""
    if requested_scope not in SUPPORTED_SCOPES:
        raise ValueError(f"unknown scope: {requested_scope}")
    if requested_scope in {"unit", "contract", "integration", "security"}:
        if not any((project_root / "backend" / "tests" / requested_scope).rglob("test_*.py")):
            raise NotImplementedErrorScope(requested_scope)
        return ["uv", "run", "--locked", "pytest", f"tests/{requested_scope}"]
    if requested_scope in {"frontend", "e2e"}:
        package_file = project_root / "frontend" / "package.json"
        if not package_file.is_file():
            raise NotImplementedErrorScope(requested_scope)
        package = json.loads(package_file.read_text(encoding="utf-8"))
        scripts = package.get("scripts", {})
        script = "test" if requested_scope == "frontend" else "test:e2e"
        if not isinstance(scripts, dict) or script not in scripts:
            raise NotImplementedErrorScope(requested_scope)
        return ["npm.cmd" if os.name == "nt" else "npm", "run", script]
    return []


def _report_result(scope: str, report_path: Path, returncode: int) -> int:
    try:
        counts = read_test_report(report_path)
    except (OSError, ElementTree.ParseError):
        print(f"ERROR {scope}: actual test report missing or invalid", file=sys.stderr)
        return returncode if returncode else 1
    print(json.dumps({"scope": scope, **counts, "tool_exit": returncode}))
    if returncode:
        return returncode
    if counts["tests"] == 0:
        return 3
    if counts["failed"] or counts["errors"]:
        return 1
    if counts["skipped"]:
        print(f"ERROR {scope}: skipped tests are not accepted", file=sys.stderr)
        return 4
    return 0


def run_scope_checks(
    requested_scope: str, timeout_seconds: int = 600, fixture_only: bool = False
) -> int:
    """执行所请求层；all 在一个层失败后仍执行其它层，输出实际各层结果。"""
    if requested_scope == "all":
        results = [
            run_scope_checks(scope, timeout_seconds, fixture_only)
            for scope in SUPPORTED_SCOPES[:-1]
        ]
        print(
            json.dumps(
                {"scope": "all", "exits": dict(zip(SUPPORTED_SCOPES[:-1], results, strict=True))}
            )
        )
        return 124 if 124 in results else next((code for code in results if code), 0)
    try:
        command = resolve_check_command(requested_scope, PROJECT_ROOT)
        if requested_scope in {"contract", "integration"} and not (
            requested_scope == "contract" and fixture_only
        ):
            require_isolated_test_database()
        with tempfile.TemporaryDirectory(prefix=f"dianzi-{requested_scope}-") as directory:
            report_path = Path(directory) / "junit.xml"
            if requested_scope in {"unit", "contract", "integration", "security"}:
                command += [f"--junitxml={report_path}"]
                if requested_scope != "unit":
                    command += ["--cov-fail-under=0"]
                if requested_scope == "contract" and fixture_only:
                    command += ["-m", "not real_pg"]
                completed = _run_command(command, BACKEND_DIR, timeout_seconds)
            else:
                frontend_directory = PROJECT_ROOT / "frontend"
                if requested_scope == "frontend":
                    for step in ("lint", "typecheck"):
                        result = _run_command(
                            [command[0], "run", step], frontend_directory, timeout_seconds
                        )
                        if result.returncode:
                            return result.returncode
                environment = dict(os.environ)
                if requested_scope == "e2e":
                    environment["PLAYWRIGHT_JUNIT_OUTPUT_FILE"] = str(report_path)
                    command += ["--", "--reporter=junit"]
                else:
                    command += ["--", "--reporter=junit", f"--outputFile={report_path}"]
                completed = _run_command(command, frontend_directory, timeout_seconds, environment)
                if requested_scope == "frontend" and completed.returncode == 0:
                    build = _run_command(
                        [command[0], "run", "build"], frontend_directory, timeout_seconds
                    )
                    if build.returncode:
                        return build.returncode
            return _report_result(requested_scope, report_path, completed.returncode)
    except NotImplementedErrorScope as not_ready:
        print(f"ERROR not_implemented: {not_ready.scope}", file=sys.stderr)
        return 3
    except TestEnvironmentError as blocked:
        print(f"ERROR blocked: {blocked}", file=sys.stderr)
        return 4
    except OSError as unavailable:
        print(
            f"ERROR blocked: check tool unavailable ({type(unavailable).__name__})", file=sys.stderr
        )
        return 4


def run_compose_services(
    *arguments: str, test_project: bool = False
) -> subprocess.CompletedProcess[str]:
    """固定文件与显式项目；可用 JSON argv 指定受控 WSL Docker，不用 shell/eval。"""
    try:
        prefix = json.loads(os.environ.get("DIANZI_DOCKER_COMMAND_JSON", '["docker"]'))
    except json.JSONDecodeError as invalid_prefix:
        raise TestEnvironmentError(
            "DIANZI_DOCKER_COMMAND_JSON must be an argument array"
        ) from invalid_prefix
    if (
        not isinstance(prefix, list)
        or not prefix
        or not all(isinstance(item, str) and item for item in prefix)
    ):
        raise TestEnvironmentError("DIANZI_DOCKER_COMMAND_JSON must be a nonempty string array")
    variable = "DIANZI_TEST_COMPOSE_PROJECT" if test_project else "DIANZI_COMPOSE_PROJECT"
    project_name = os.environ.get(variable, "")
    if not re.fullmatch(r"dianzi-(test|dev)-[a-z0-9_]{3,48}", project_name):
        raise TestEnvironmentError(f"{variable} requires an explicit dianzi test/dev project")
    if test_project:
        require_isolated_test_database()
        if project_name != f"dianzi-test-{os.environ['DIANZI_TEST_RUN_ID']}":
            raise TestEnvironmentError("test Compose project must match DIANZI_TEST_RUN_ID")
    file_variable = "DIANZI_TEST_COMPOSE_FILE" if test_project else "DIANZI_COMPOSE_FILE"
    compose_file = Path(os.environ.get(file_variable, str(COMPOSE_FILE)))
    if not compose_file.is_file():
        raise TestEnvironmentError(f"{file_variable} must refer to an existing Compose file")
    compose_argument = str(compose_file)
    if Path(prefix[0]).name.lower() == "wsl.exe":
        windows_path = PureWindowsPath(compose_file.resolve())
        compose_argument = f"/mnt/{windows_path.drive[0].lower()}/" + "/".join(
            windows_path.parts[1:]
        )
    return _run_command(
        [
            *prefix,
            "compose",
            "--project-name",
            project_name,
            "-f",
            compose_argument,
            "--profile",
            "core",
            "--profile",
            "search",
            *arguments,
        ],
        PROJECT_ROOT,
        180,
        emit_output=False,
    )


def start_development_services() -> int:
    """启动明确命名的开发项目，保留其持久卷。"""
    return run_compose_services("up", "-d").returncode


def stop_development_services(confirm_destroy: bool) -> int:
    """默认保留卷；显式销毁仅允许对应 run_id 的隔离 test 项目。"""
    arguments = ["down"]
    if confirm_destroy:
        require_isolated_test_database()
        if (
            os.environ.get("DIANZI_COMPOSE_PROJECT")
            != f"dianzi-test-{os.environ['DIANZI_TEST_RUN_ID']}"
        ):
            raise TestEnvironmentError("volume destruction project must match test run")
        arguments.append("--volumes")
    return run_compose_services(*arguments).returncode


def probe_dependency_states() -> dict[str, str]:
    """读取精确 Health 字段，不把 unhealthy 子串误判为 healthy。"""
    probe = run_compose_services("ps", "--format", "json")
    states = dict.fromkeys(
        (*REQUIRED_DEPENDENCY_SERVICES, *OPTIONAL_DEPENDENCY_SERVICES), "not_running"
    )
    if probe.returncode:
        return dict.fromkeys(states, "probe_failed")
    if probe.stdout.strip().startswith("["):
        rows = json.loads(probe.stdout)
    else:
        rows = [json.loads(line) for line in probe.stdout.splitlines() if line.strip()]
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise TestEnvironmentError("Compose health response must contain service objects")
    for row in rows:
        service_name = row.get("Service")
        if service_name in states:
            states[service_name] = (
                "healthy"
                if row.get("Health") == "healthy" and row.get("State") == "running"
                else "starting_or_unhealthy"
            )
    return states


def report_dependencies() -> int:
    """输出实际 not_ready/degraded/ready 语义。"""
    states = probe_dependency_states()
    for name, state in states.items():
        print(f"{name}: {state}")
    if any(states[name] != "healthy" for name in REQUIRED_DEPENDENCY_SERVICES):
        print("overall: not_ready")
        return 1
    if states["opensearch"] != "healthy":
        print("overall: degraded")
        return 4
    print("overall: ready")
    return 0


def build_argument_parser() -> argparse.ArgumentParser:
    """解析有限超时、显式 fixture 子集和受控服务操作。"""
    parser = argparse.ArgumentParser(prog="dev.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    checks = subparsers.add_parser("check")
    checks.add_argument("--scope", required=True, choices=SUPPORTED_SCOPES)
    checks.add_argument("--timeout-seconds", type=int, default=600)
    checks.add_argument(
        "--fixture-only", action="store_true", help="仅 contract 离线子集，不代表完整合同验证"
    )
    services = subparsers.add_parser("services")
    services.add_argument("action", choices=("up", "down", "deps-check"))
    services.add_argument("--confirm-destroy", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """区分参数错误、资源阻塞与检查失败。"""
    try:
        arguments = build_argument_parser().parse_args(argv)
    except SystemExit as parsed_exit:
        return 2 if parsed_exit.code not in (0, None) else 0
    if arguments.command == "check":
        if not 1 <= arguments.timeout_seconds <= 3600 or (
            arguments.fixture_only and arguments.scope != "contract"
        ):
            print("ERROR invalid check parameters", file=sys.stderr)
            return 2
        return run_scope_checks(arguments.scope, arguments.timeout_seconds, arguments.fixture_only)
    try:
        if arguments.confirm_destroy and arguments.action != "down":
            return 2
        if arguments.action == "up":
            return start_development_services()
        if arguments.action == "down":
            return stop_development_services(arguments.confirm_destroy)
        return report_dependencies()
    except (TestEnvironmentError, OSError, json.JSONDecodeError) as blocked:
        message = (
            str(blocked) if isinstance(blocked, TestEnvironmentError) else type(blocked).__name__
        )
        print(f"ERROR blocked: {message}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())
