"""The README route table must not drift from the routes the application mounts.

The "已挂载的路由" section of README.md is the single public fact list of API
routes. This contract test enumerates every concrete route (path + methods)
from the FastAPI application and asserts exact set equality against the route
facts listed in that section, failing with the drift in both directions.

Enumeration and parse choices:
- Included routers are resolved recursively: FastAPI 0.142 / Starlette 1.7 wrap
  every ``include_router`` target in ``_IncludedRouter`` and only expose the
  effective routes through its original router and include prefix.
- Framework-internal routes (``/openapi.json``, ``/docs``,
  ``/docs/oauth2-redirect``, ``/redoc``) are excluded because the README table
  also excludes them; they are the only plain Starlette routes mounted, so any
  non-API route is treated as framework-internal.
- Route facts compare at (path, method) granularity: a path carrying several
  methods is several facts, so every mounted method must be documented.
  Auto-generated ``HEAD`` is ignored because the README lists primary methods.
- README rows resolve the 前缀 column plus every backtick ``METHOD /path``
  entry in the 方法与路径 column; entry paths are relative to the prefix
  column. A row whose prefix column is itself a path (``/auth``, ``/health``)
  therefore mounts ``prefix + path`` at the root plus ``/v1`` and ``/api/v1``
  per the section intro; prose-prefix rows mount under ``/v1`` and
  ``/api/v1`` only. ``GET .../suffix`` shorthand expands to the most recent
  explicit path of the same row plus ``/suffix``.
- The public-reads paragraph mounts at the prefix it declares (只挂在
  ``/api/v1``); commentary lines without a declared mount (e.g. the 422
  behavior note) carry no route facts.
- Rows that reference paths without a method (推荐) and prose summaries
  (资产 的 及快照、SBOM) contribute no route facts: a mounted route that the
  README does not list with an explicit method and path is drift.
"""

import re
from collections.abc import Iterable
from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.routing import BaseRoute, Mount

from ai_intel.api.app import create_application
from ai_intel.infrastructure.settings import ApplicationSettings

RouteKey = tuple[str, str]

README_SECTION_HEADER = "## 已挂载的路由"
DEFAULT_MOUNT_PREFIXES = ("/v1", "/api/v1")
EXCLUDED_METHODS = frozenset({"HEAD"})
METHOD_PATH_PATTERN = re.compile(
    r"`(?P<method>GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) (?P<path>[^`]+)`"
)
DECLARED_MOUNT_PATTERN = re.compile(r"^只挂在\s*`?(?P<prefix>/[\w/-]+)`?")


def find_repo_root() -> Path:
    """Locate the repository root holding both README.md and the backend package."""
    backend_root = Path(__file__).resolve().parents[2]
    for candidate in (backend_root, *backend_root.parents):
        if (candidate / "README.md").is_file() and (candidate / "backend").is_dir():
            return candidate
    raise FileNotFoundError("repository root with README.md and backend/ not found")


def enumerate_application_routes(application: FastAPI) -> set[RouteKey]:
    """Collect the exact path + method pairs the application mounts."""
    routes: set[RouteKey] = set()
    collect_routes(application.routes, "", routes)
    return routes


def collect_routes(routes: Iterable[BaseRoute], prefix: str, collected: set[RouteKey]) -> None:
    for route in routes:
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            include_prefix = prefix + route.include_context.prefix
            collect_routes(original_router.routes, include_prefix, collected)
        elif isinstance(route, Mount):
            collect_routes(route.routes, prefix + route.path, collected)
        elif isinstance(route, APIRoute):
            path = prefix + route.path_format
            for method in sorted(route.methods or ()):
                if method not in EXCLUDED_METHODS:
                    collected.add((path, method))


def extract_readme_route_section(readme_text: str) -> list[str]:
    lines = readme_text.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if line.strip() == README_SECTION_HEADER),
        None,
    )
    if start is None:
        raise ValueError(f"README section {README_SECTION_HEADER!r} not found")
    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")),
        len(lines),
    )
    return lines[start + 1 : end]


def parse_readme_route_facts(section_lines: Iterable[str]) -> set[RouteKey]:
    facts: set[RouteKey] = set()
    for line in section_lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            facts.update(parse_route_table_row(stripped))
        elif METHOD_PATH_PATTERN.search(stripped):
            facts.update(parse_declared_mount_line(stripped))
    return facts


def parse_route_table_row(row: str) -> set[RouteKey]:
    columns = [column.strip() for column in row.strip("|").split("|")]
    if len(columns) != 2:
        return set()
    prefix_cell = columns[0].strip("`")
    if prefix_cell == "前缀" or set(prefix_cell) <= {"-"}:
        return set()
    entries = extract_method_path_entries(columns[1])
    if not entries:
        return set()
    if prefix_cell.startswith("/"):
        qualified_entries = [(method, prefix_cell + path) for method, path in entries]
        return expand_mounted_entries(qualified_entries, ("", *DEFAULT_MOUNT_PREFIXES))
    return expand_mounted_entries(entries, DEFAULT_MOUNT_PREFIXES)


def parse_declared_mount_line(line: str) -> set[RouteKey]:
    declared = DECLARED_MOUNT_PATTERN.match(line)
    if declared is None:
        return set()
    return expand_mounted_entries(extract_method_path_entries(line), (declared.group("prefix"),))


def extract_method_path_entries(cell: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    last_explicit_path: str | None = None
    for match in METHOD_PATH_PATTERN.finditer(cell):
        method = match.group("method")
        path = match.group("path").strip()
        if path.startswith("..."):
            if last_explicit_path is None:
                continue
            path = last_explicit_path + path.removeprefix("...")
        else:
            last_explicit_path = path
        entries.append((method, path))
    return entries


def expand_mounted_entries(
    entries: Iterable[tuple[str, str]], mount_prefixes: Iterable[str]
) -> set[RouteKey]:
    return {
        (prefix + path, method)
        for prefix in mount_prefixes
        for method, path in entries
        if method not in EXCLUDED_METHODS
    }


def format_route(route: RouteKey) -> str:
    path, method = route
    return f"{method} {path}"


def test_readme_route_table_matches_mounted_application_routes() -> None:
    application = create_application(
        settings=ApplicationSettings(app_env="test", data_mode="fixture", _env_file=None)
    )
    code_routes = enumerate_application_routes(application)
    readme_text = (find_repo_root() / "README.md").read_text(encoding="utf-8")
    readme_routes = parse_readme_route_facts(extract_readme_route_section(readme_text))
    code_only = sorted(format_route(route) for route in code_routes - readme_routes)
    readme_only = sorted(format_route(route) for route in readme_routes - code_routes)
    assert not code_only and not readme_only, (
        "README route table drifted from the mounted application routes\n"
        f"code has routes missing from README: {code_only}\n"
        f"README lists routes not in code: {readme_only}"
    )
