"""Read frozen SDK inputs and record a scoped dependency closure without executing tests."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path("D:/dianzi")
AUTHOR = Path("D:/wt/r18-sdk-canonical-verification-integration")
RUN = ROOT / "reports/runs/recovery_dependency_closure_diagnosis_20261016"
SOURCE = "02ce8d6b8072253c26a5df1a49e1b574f2668498"
MATERIAL = "3db7b6cdf33ab1dc5d6c8801a54603b20137ada7"
ROOT_FREEZE = "d68b9c653aa8eced6eeb75b6d293617c6cce5094"
CACHE = Path(
    "D:/dianzi-runtime-cache/tiktoken-o200k-base-20261016/"
    "fb374d419588a4632f3f557e76b4b70aebbca790"
)
COMMANDS: list[dict[str, object]] = []


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def command(arguments: list[str], cwd: Path) -> subprocess.CompletedProcess[bytes]:
    started = now()
    result = subprocess.run(arguments, cwd=cwd, capture_output=True, check=False)
    entry: dict[str, object] = {
        "command": arguments,
        "cwd": cwd.as_posix(),
        "started_at": started,
        "finished_at": now(),
        "exit_code": result.returncode,
        "stdout_bytes": len(result.stdout),
        "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
        "stderr_bytes": len(result.stderr),
        "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
    }
    if result.stderr:
        entry["stderr"] = result.stderr.decode("utf-8", errors="replace")
    COMMANDS.append(entry)
    return result


def git(arguments: list[str], cwd: Path = AUTHOR) -> subprocess.CompletedProcess[bytes]:
    return command(["git", *arguments], cwd)


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def blob_snapshot(revision: str, relative: str, cwd: Path) -> dict[str, object]:
    blob = git(["rev-parse", "--verify", f"{revision}:{relative}"], cwd)
    if blob.returncode:
        return {"exists": False, "revision": revision}
    content = git(["show", f"{revision}:{relative}"], cwd)
    if content.returncode:
        raise RuntimeError(f"Existing frozen object unreadable: {relative}")
    return {
        "exists": True,
        "revision": revision,
        "git_blob": blob.stdout.decode().strip(),
        "git_bytes": len(content.stdout),
        "git_sha256": sha256(content.stdout),
    }


def worktree_snapshot(relative: str, cwd: Path) -> dict[str, object]:
    target = cwd / relative
    if not target.is_file():
        return {"exists": False}
    content = target.read_bytes()
    blob = git(["hash-object", f"--path={relative}", str(target)], cwd)
    if blob.returncode:
        raise RuntimeError(f"Git hashing failed: {relative}")
    return {
        "exists": True,
        "raw_bytes": len(content),
        "raw_sha256": sha256(content),
        "git_filtered_blob": blob.stdout.decode().strip(),
    }


def main() -> None:
    started = now()
    RUN.mkdir(parents=True, exist_ok=True)
    sdk_paths = git(["ls-tree", "-r", "--name-only", SOURCE, "--", "sdk/python"])
    if sdk_paths.returncode:
        raise RuntimeError("Cannot inventory frozen SDK tree")
    paths = sdk_paths.stdout.decode().splitlines()
    additions_result = git(["diff-tree", "--no-commit-id", "--name-only", "-r", SOURCE])
    additions = set(additions_result.stdout.decode().splitlines())
    paths.extend(
        [
            "contracts/schemas/public_api_v2.json",
            "contracts/schemas/public_api_v2_examples.json",
            "tests/plan/test_public_api_v2.py",
            "backend/pyproject.toml",
            "backend/uv.lock",
        ]
    )
    rows: list[dict[str, object]] = []
    imports: list[dict[str, object]] = []
    file_io: list[dict[str, object]] = []
    ast_errors: list[dict[str, object]] = []
    for relative in sorted(set(paths)):
        source = blob_snapshot(SOURCE, relative, AUTHOR)
        material = blob_snapshot(MATERIAL, relative, AUTHOR)
        baseline = blob_snapshot(ROOT_FREEZE, relative, ROOT)
        author_current = worktree_snapshot(relative, AUTHOR)
        root_current = worktree_snapshot(relative, ROOT)
        category = "baseline_test_oracle"
        if relative.startswith("sdk/python/ai_intel_client/"):
            category = "baseline_product_source"
        elif "/fixtures/" in relative:
            category = "explicit_synthetic_executable_fixture"
        elif relative in additions:
            category = "relocated_existing_test_or_path_helper"
        elif relative.startswith("contracts/"):
            category = "approved_frozen_public_contract_or_example"
        elif relative.startswith("backend/"):
            category = "baseline_environment_configuration"
        rows.append(
            {
                "path": relative,
                "category": category,
                "in_source_delta": relative in additions,
                "source": source,
                "material": material,
                "root_frozen": baseline,
                "author_worktree": author_current,
                "root_worktree": root_current,
                "root_matches_source_git": root_current.get("git_filtered_blob")
                == source.get("git_blob"),
                "author_matches_source_git": author_current.get("git_filtered_blob")
                == source.get("git_blob"),
                "material_matches_source_git": material.get("git_blob")
                == source.get("git_blob"),
            }
        )
        if not relative.endswith(".py"):
            continue
        raw = git(["show", f"{SOURCE}:{relative}"]).stdout
        try:
            tree = ast.parse(raw.decode("utf-8-sig"), filename=relative)
        except (SyntaxError, UnicodeDecodeError) as error:
            ast_errors.append({"path": relative, "error_type": type(error).__name__})
            continue
        lines = raw.decode("utf-8-sig").splitlines()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(
                    {"path": relative, "line": node.lineno, "module": item.name}
                    for item in node.names
                )
            elif isinstance(node, ast.ImportFrom):
                imports.append(
                    {
                        "path": relative,
                        "line": node.lineno,
                        "module": node.module,
                        "level": node.level,
                        "names": [item.name for item in node.names],
                    }
                )
            elif isinstance(node, ast.Call):
                function = node.func
                method = function.attr if isinstance(function, ast.Attribute) else None
                if method in {"read_bytes", "read_text", "open", "write_bytes", "write_text"}:
                    file_io.append(
                        {
                            "path": relative,
                            "line": node.lineno,
                            "method": method,
                            "expression": ast.unparse(node),
                            "source_line": lines[node.lineno - 1],
                        }
                    )
    schema = json.loads(git(["show", f"{SOURCE}:contracts/schemas/public_api_v2.json"]).stdout)
    references: list[str] = []

    def visit(value: object) -> None:
        if isinstance(value, dict):
            reference = value.get("$ref")
            if isinstance(reference, str):
                references.append(reference)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema)
    external_refs = sorted({reference for reference in references if not reference.startswith("#")})
    packages = {}
    for name in ["pytest", "mcp", "mcp-types", "httpx", "anyio", "tiktoken", "pydantic", "jsonschema", "tzdata"]:
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = "not_installed"
    cache = {"path": CACHE.as_posix(), "exists": CACHE.is_file(), "category": "official_public_vocabulary_prepared_outside_repository"}
    if CACHE.is_file():
        raw_cache = CACHE.read_bytes()
        cache.update({"bytes": len(raw_cache), "sha256": sha256(raw_cache)})
        cache.update({"matches_pinned_bytes": len(raw_cache) == 3613922 and sha256(raw_cache) == "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d"})
    rg = command(
        [
            "rg", "-n",
            "read_text|read_bytes|open\\(|Path\\(|ROOT|FIXTURES|CACHE|SDK_TEST_EVIDENCE_DIR|DIANZI_MCP_ENCODING_CACHE_FILE|from ai_intel|import ai_intel|public_api_v2|tiktoken",
            "sdk/python/ai_intel_client", "sdk/python/tests", "tests/plan/test_public_api_v2.py", "-g", "*.py",
        ], AUTHOR,
    )
    (RUN / "sdk_scoped_rg.log").write_bytes(rg.stdout)
    status = git(["status", "--short", "--untracked-files=all", "--", *paths], ROOT)
    (RUN / "sdk_scoped_root_status.log").write_bytes(status.stdout)
    evidence = {
        "started_at": started, "finished_at": now(), "exit_code": 0,
        "root_frozen_head": ROOT_FREEZE, "source_commit": SOURCE, "material_commit": MATERIAL,
        "read_scope": "Frozen SDK source/tests; two public v2 JSON inputs; one public plan test; backend pyproject and lock metadata; no secrets, holdout, or report bodies",
        "file_count": len(rows), "source_delta_count": len(additions), "files": rows,
        "imports": imports, "file_io": file_io, "ast_errors": ast_errors,
        "public_v2_external_ref_targets": external_refs,
        "cache": cache, "python": sys.version, "installed_packages": packages,
        "source_only_rg_exit_code": rg.returncode,
        "backend_business_imports": [item for item in imports if str(item.get("module")).startswith("ai_intel.")],
        "tests_executed": 0, "pg_requests": 0, "model_requests": 0, "network_requests": 0,
    }
    (RUN / "sdk_dependency_closure.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (RUN / "sdk_command_index.json").write_text(json.dumps(COMMANDS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"started_at": started, "finished_at": evidence["finished_at"], "files": len(rows), "delta": len(additions), "root_missing": [row["path"] for row in rows if not row["root_worktree"]["exists"]], "root_mismatches": [row["path"] for row in rows if not row["root_matches_source_git"]], "cache_pinned": cache.get("matches_pinned_bytes"), "backend_business_imports": len(evidence["backend_business_imports"]), "ast_errors": ast_errors, "external_schema_refs": external_refs}, ensure_ascii=False))


if __name__ == "__main__":
    main()
