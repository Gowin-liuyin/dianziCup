"""Independent R01 TLS review runner; keep random credentials out of evidence."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import ssl
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCE = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r01-tls\dianzi")
OUTPUT = Path(__file__).resolve().parent
PYTHON = str(SOURCE / "backend/.venv/Scripts/python.exe")
WSL = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec"]
DOCKER = [*WSL, "/tmp/dianzi-docker-static-r01-20261014/portable/docker/docker", "--config", "/tmp/dianzi-docker-static-r01-20261014/runtime/client-config", "--host", "unix:///tmp/dianzi-docker-static-r01-20261014/runtime/docker.sock"]
PRIVATE = "/tmp/dianzi-r01-search-tls-20261015"
CONTAINER = "dianzi-test-r01_tls_20261015-opensearch-1"
CBM = [*WSL, "/usr/bin/env", "CBM_CACHE_DIR=/tmp/dianzi-cbm-r01-search-tls-review-1-20261015", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli"]
LINUX_SOURCE = "/mnt/c/Users/yinha/.codex/worktrees/recovery-r01-tls/dianzi"
ASIA = ZoneInfo("Asia/Shanghai")
connection = json.loads(subprocess.run([*WSL, "cat", PRIVATE + "/connection.json"], capture_output=True, text=True, check=True).stdout)
environment = {key: value for key, value in os.environ.items() if not key.startswith(("COMPOSE_", "POSTGRES_", "REDIS_", "OPENSEARCH_", "TEST_", "SECURE_", "DATABASE_", "AUTH_", "MODEL_"))}
environment.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", DIANZI_DOCKER_COMMAND_JSON=json.dumps(DOCKER), COMPOSE_DISABLE_ENV_FILE="1", COVERAGE_FILE=str(OUTPUT / ".coverage"))
public = Path(tempfile.mkdtemp(prefix="dianzi-r01-tls-independent-public-"))
for filename in ("root-ca.pem", "wrong-ca.pem"):
    (public / filename).write_bytes(subprocess.run([*WSL, "cat", PRIVATE + "/pki/" + filename], capture_output=True, check=True).stdout)
environment.update(TEST_SEARCH_TLS_URL="https://localhost:29202", TEST_SEARCH_TLS_USERNAME=connection["username"], TEST_SEARCH_TLS_PASSWORD=connection["password"], TEST_SEARCH_TLS_CA_FILE=str(public / "root-ca.pem"), TEST_SEARCH_TLS_WRONG_CA_FILE=str(public / "wrong-ca.pem"))
source_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=SOURCE, capture_output=True, text=True, check=True).stdout.strip()
source_tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=SOURCE, capture_output=True, text=True, check=True).stdout.strip()


def record(name: str, argv: list[str], *, cwd: Path = SOURCE, timeout: int = 180, junit: Path | None = None, env: dict[str, str] | None = None) -> int:
    if (OUTPUT / (name + ".json")).exists():
        raise RuntimeError("Evidence already exists; choose a new name")
    start = datetime.now(ASIA).isoformat(timespec="seconds")
    effective_environment = env or environment
    result = subprocess.run(argv, cwd=cwd, env=effective_environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    end = datetime.now(ASIA).isoformat(timespec="seconds")
    known_secrets = {connection["password"], effective_environment.get("TEST_SEARCH_TLS_PASSWORD", "")} - {""}
    secret_fragments = {secret[index:index + 8] for secret in known_secrets for index in range(max(0, len(secret) - 7))}
    leaks = {"stdout": any(secret in result.stdout for secret in known_secrets), "stderr": any(secret in result.stderr for secret in known_secrets)}
    fragment_leaks = {"stdout": any(fragment in result.stdout for fragment in secret_fragments), "stderr": any(fragment in result.stderr for fragment in secret_fragments)}
    raw = result.stdout + result.stderr
    for secret in sorted(known_secrets | secret_fragments, key=len, reverse=True):
        raw = raw.replace(secret, "[REDACTED-RANDOM-TEST-PASSWORD]")
    (OUTPUT / (name + ".log")).write_text(raw, encoding="utf-8")
    receipt = {"argv": argv, "cwd": str(cwd), "start": start, "end": end, "exit_code": result.returncode, "source_commit": source_sha, "source_tree": source_tree, "secret_presence_before_redaction": leaks, "secret_fragment_presence_before_redaction": fragment_leaks, "log": name + ".log"}
    if junit and junit.exists():
        text = junit.read_text(encoding="utf-8")
        receipt["secret_presence_before_redaction"]["junit"] = any(secret in text for secret in known_secrets)
        receipt["secret_fragment_presence_before_redaction"]["junit"] = any(fragment in text for fragment in secret_fragments)
        for secret in sorted(known_secrets | secret_fragments, key=len, reverse=True):
            text = text.replace(secret, "[REDACTED-RANDOM-TEST-PASSWORD]")
        junit.write_text(text, encoding="utf-8")
        suites = ET.parse(junit).getroot()
        receipt["tests"] = {key: sum(int(suite.get(key, "0")) for suite in suites.iter("testsuite")) for key in ("tests", "failures", "errors", "skipped")}
    (OUTPUT / (name + ".json")).write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: receipt.get(key) for key in ("start", "end", "exit_code", "tests", "secret_presence_before_redaction", "secret_fragment_presence_before_redaction")}))
    return result.returncode


action = sys.argv[1]
if action in {"unit", "security", "config", "live", "missing", "forced_failure", "forced_failure_showlocals", "forced_failure_showlocals_recovered", "fixture_failure", "fixture_failure_showlocals", "fixture_failure_showlocals_full", "fixture_failure_showlocals_full_retry"}:
    junit = OUTPUT / (action + ".xml")
    arguments = [PYTHON, "-m", "pytest", "-o", "cache_dir=" + str(OUTPUT / ("pytest_cache_" + action))]
    custom_environment = environment.copy()
    if action == "unit":
        arguments += ["tests/unit", "-q", "--junitxml", str(junit)]
    else:
        arguments += ["--no-cov", "-q", "--junitxml", str(junit)]
        if action == "security":
            arguments += ["tests/security"]
        elif action == "config":
            arguments += ["tests/contract/test_r01_compose_configuration.py", "tests/contract/test_r01_search_tls_deployment.py"]
        else:
            arguments += ["tests/integration/test_r01_search_tls_live.py"]
            if action == "missing":
                custom_environment.pop("TEST_SEARCH_TLS_PASSWORD", None)
                arguments += ["-k", "correct"]
            elif action.startswith("forced_failure"):
                custom_environment["TEST_SEARCH_TLS_PASSWORD"] = secrets.token_urlsafe(32)
                arguments += ["-k", "correct"]
                if "showlocals" in action:
                    arguments += ["--showlocals"]
                if "full" in action:
                    arguments += ["-vv"]
            elif action.startswith("fixture_failure"):
                custom_environment["TEST_SEARCH_TLS_URL"] = "https://localhost:29203"
                arguments += ["-k", "correct"]
                if "showlocals" in action:
                    arguments += ["--showlocals"]
                if action.endswith("full"):
                    arguments += ["-vv"]
    sys.exit(record(action, arguments, cwd=SOURCE / "backend", timeout=260, junit=junit, env=custom_environment))
if action in {"ruff", "format", "mypy"}:
    arguments = {
        "ruff": [PYTHON, "-m", "ruff", "check", "--no-cache", "src", "tests/contract/test_r01_compose_configuration.py", "tests/contract/test_r01_search_tls_deployment.py", "tests/integration/test_r01_search_tls_live.py"],
        "format": [PYTHON, "-m", "ruff", "format", "--check", "--no-cache", "src", "tests/contract/test_r01_compose_configuration.py", "tests/contract/test_r01_search_tls_deployment.py", "tests/integration/test_r01_search_tls_live.py"],
        "mypy": [PYTHON, "-m", "mypy", "--config-file", "pyproject.toml", "--cache-dir", str(OUTPUT / "mypy_cache"), "src"],
    }
    sys.exit(record(action, arguments[action], cwd=SOURCE / "backend"))
if action in {"cbm_help", "cbm_version_help", "cbm_trace_help", "cbm_index", "cbm_schema", "cbm_outline", "cbm_trace"}:
    arguments = {
        "cbm_help": [*CBM, "--help"],
        "cbm_version_help": [*WSL, "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "--help"],
        "cbm_trace_help": [*CBM, "trace_path", "--help"],
        "cbm_index": [*CBM, "index_repository", "--repo-path", LINUX_SOURCE + "/backend/src", "--name", "dianzi-r01-search-tls-review-source", "--persistence", "false"],
        "cbm_schema": [*CBM, "get_graph_schema", "--project", "dianzi-r01-search-tls-review-source"],
        "cbm_outline": [*CBM, "get_file_outline", "--project", "dianzi-r01-search-tls-review-source", "--file-path", "ai_intel/api/app.py"],
        "cbm_trace": [*CBM, "trace_path", "--project", "dianzi-r01-search-tls-review-source", "--function-name", "create_application", "--direction", "outbound", "--depth", "3", "--include-evidence", "true"],
    }
    sys.exit(record(action, arguments[action]))
if action in {"inspect", "inspect_recovered", "inspect_final"}:
    sys.exit(record(action, [*DOCKER, "inspect", CONTAINER, "--format", '{{json .State}} {{json .HostConfig.Memory}} {{json .HostConfig.NanoCpus}} {{json .HostConfig.PidsLimit}} {{json .HostConfig.NetworkMode}} {{json .Config.User}} {{json .Config.Image}} {{json .Mounts}} {{json .Config.Labels}}']))
if action == "start_own":
    sys.exit(record(action, [*DOCKER, "start", CONTAINER]))
if action == "wait_own":
    started = datetime.now(ASIA).isoformat(timespec="seconds")
    deadline = time.monotonic() + 180
    observations = []
    exit_code = 1
    while time.monotonic() < deadline:
        command = [*DOCKER, "inspect", CONTAINER, "--format", '{{.State.Status}} {{.State.Health.Status}} {{index .Config.Labels "com.docker.compose.project"}}']
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        observed = result.stdout.strip()
        observations.append({"at": datetime.now(ASIA).isoformat(timespec="seconds"), "exit": result.returncode, "status": observed})
        if observed == "running healthy dianzi-test-r01_tls_20261015":
            exit_code = 0
            break
        time.sleep(2)
    receipt = {"start": started, "end": datetime.now(ASIA).isoformat(timespec="seconds"), "argv_per_probe": command, "exit_code": exit_code, "source_commit": source_sha, "observations": observations}
    (OUTPUT / "wait_own.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({key: receipt[key] for key in ("start", "end", "exit_code")}))
    sys.exit(exit_code)
if action in {"listeners", "listeners_final"}:
    sys.exit(record(action, [*WSL, "bash", "-c", "ss -lntp '( sport = :29202 or sport = :29302 )'; stat -c '%a %u %g %n' /tmp/dianzi-r01-search-tls-20261015 /tmp/dianzi-r01-search-tls-20261015/connection.json /tmp/dianzi-r01-search-tls-20261015/pki/* /tmp/dianzi-r01-search-tls-20261015/security"]))
if action == "certificates":
    codes = [record("certificate_chain", [*WSL, "openssl", "verify", "-CAfile", PRIVATE + "/pki/root-ca.pem", "-verify_hostname", "localhost", PRIVATE + "/pki/node.pem"]), record("certificate_wrong_ca", [*WSL, "openssl", "verify", "-CAfile", PRIVATE + "/pki/wrong-ca.pem", PRIVATE + "/pki/node.pem"]), record("certificate_wrong_san", [*WSL, "openssl", "verify", "-CAfile", PRIVATE + "/pki/root-ca.pem", "-verify_ip", "127.0.0.1", PRIVATE + "/pki/node.pem"])]
    sys.exit(0 if codes == [0, 2, 2] else 1)
if action == "scrub_prior":
    started = datetime.now(ASIA).isoformat(timespec="seconds")
    fragments = {connection["password"][index:index + 8] for index in range(len(connection["password"]) - 7)}
    findings = []
    for path in sorted([*OUTPUT.glob("*.log"), *OUTPUT.glob("*.xml")]):
        original = path.read_text(encoding="utf-8")
        matched = any(fragment in original for fragment in fragments)
        if matched:
            if path.suffix == ".xml":
                document = ET.parse(path)
                for element in document.iter():
                    if element.text:
                        element.text = "\n".join("[REDACTED RANDOM TEST CREDENTIAL LINE]" if any(fragment in line for fragment in fragments) else line for line in element.text.split("\n"))
                document.write(path, encoding="unicode")
            else:
                path.write_text("\n".join("[REDACTED RANDOM TEST CREDENTIAL LINE]" if any(fragment in line for fragment in fragments) else line for line in original.split("\n")), encoding="utf-8")
        findings.append({"path": path.name, "known_credential_fragment_present_before_cleanup": matched, "present_after_cleanup": any(fragment in path.read_text(encoding="utf-8") for fragment in fragments)})
    receipt = {"start": started, "end": datetime.now(ASIA).isoformat(timespec="seconds"), "exit_code": 0, "source_commit": source_sha, "findings": findings}
    (OUTPUT / "prior_output_fragment_audit.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"checked": len(findings), "cleaned": sum(item["known_credential_fragment_present_before_cleanup"] for item in findings), "remaining": sum(item["present_after_cleanup"] for item in findings)}))
    sys.exit(0)
if action == "source_evidence":
    codes = [record("source_identity", ["git", "status", "--porcelain"]), record("source_diff", ["git", "diff", "adb86df7149d2f753f4afe1e08d721160dd780fe", "741e5da9f21b95448a03666fff881f1843cbc606", "--", "backend", "infra", "config"]), record("source_diff_check", ["git", "diff", "--check", "adb86df7149d2f753f4afe1e08d721160dd780fe", "741e5da9f21b95448a03666fff881f1843cbc606", "--", "backend", "infra", "config"]), record("source_callers_rg", ["rg", "-n", "create_application|build_health_router|create_default_context|BasicAuth|opensearch_ca_file|OPENSEARCH_CA_FILE|OPENSEARCH_USERNAME|OPENSEARCH_PASSWORD|TEST_SEARCH_TLS_|real_search_tls|test_r01_search_tls_live", "backend/src", "backend/tests/conftest.py", "backend/tests/integration/test_r01_search_tls_live.py", "infra/compose", "scripts/dev.py", ".github/workflows/ci.yml"])]
    sys.exit(0 if all(code == 0 for code in codes) else 1)
if action == "versions":
    codes = [record("source_trees", ["git", "rev-parse", "adb86df7149d2f753f4afe1e08d721160dd780fe^{tree}", "741e5da9f21b95448a03666fff881f1843cbc606^{tree}", "HEAD^{tree}"]), record("code_evidence_match", ["git", "diff", "--exit-code", "741e5da9f21b95448a03666fff881f1843cbc606", "HEAD", "--", "backend", "infra", "config", "scripts", ".github"]), record("source_ancestry", ["git", "merge-base", "--is-ancestor", "adb86df7149d2f753f4afe1e08d721160dd780fe", "HEAD"])]
    sys.exit(0 if all(code == 0 for code in codes) else 1)
if action == "permission_probe":
    import httpx

    started = datetime.now(ASIA).isoformat(timespec="seconds")
    context = ssl.create_default_context(cafile=str(public / "root-ca.pem"))
    observations = []
    with httpx.Client(verify=context, auth=httpx.BasicAuth(connection["username"], connection["password"]), trust_env=False, timeout=3) as client:
        for endpoint in ("/_cluster/health", "/", "/_cat/indices?format=json", "/_plugins/_security/api/internalusers"):
            response = client.get("https://localhost:29202" + endpoint)
            observation = {"method": "GET", "endpoint": endpoint, "status_code": response.status_code, "secret_in_response": connection["password"] in response.text}
            if endpoint == "/_cluster/health":
                observation["cluster_status"] = response.json().get("status")
            observations.append(observation)
    passed = observations[0]["status_code"] == 200 and observations[0]["cluster_status"] in {"yellow", "green"} and all(item["status_code"] == 403 for item in observations[1:]) and not any(item["secret_in_response"] for item in observations)
    receipt = {"start": started, "end": datetime.now(ASIA).isoformat(timespec="seconds"), "exit_code": 0 if passed else 1, "source_commit": source_sha, "check_hostname": context.check_hostname, "verify_mode": context.verify_mode.name, "observations": observations}
    (OUTPUT / "permission_probe.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt))
    sys.exit(receipt["exit_code"])
if action == "origins":
    sys.exit(record(action, [PYTHON, "-c", "import ai_intel.api.app as app; import ai_intel.infrastructure.settings as settings; import json; print(json.dumps({'app': app.__file__, 'settings': settings.__file__}))"], cwd=SOURCE / "backend"))
if action == "certificate_metadata":
    sys.exit(record(action, [*WSL, "openssl", "x509", "-in", PRIVATE + "/pki/node.pem", "-noout", "-subject", "-issuer", "-dates", "-ext", "subjectAltName", "-fingerprint", "-sha256"]))
if action == "default_entry":
    sys.exit(record(action, [PYTHON, str(OUTPUT / "default_entry_probe.py")], cwd=SOURCE / "backend"))
if action == "final_secret_boundary":
    started = datetime.now(ASIA).isoformat(timespec="seconds")
    fragments = {connection["password"][index:index + 8] for index in range(len(connection["password"]) - 7)}
    paths = [path for path in OUTPUT.iterdir() if path.is_file() and path.suffix in {".py", ".md", ".json", ".xml", ".log"}]
    paths.append(OUTPUT.parents[1] / "reviews/recovery/G-A-R01-search-TLS-review-1.md")
    findings = [{"path": path.name, "full_secret": connection["password"] in path.read_text(encoding="utf-8"), "secret_fragment": any(fragment in path.read_text(encoding="utf-8") for fragment in fragments)} for path in paths]
    passed = not any(item["full_secret"] or item["secret_fragment"] for item in findings)
    receipt = {"start": started, "end": datetime.now(ASIA).isoformat(timespec="seconds"), "exit_code": 0 if passed else 1, "findings": findings}
    (OUTPUT / "final_secret_boundary.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"checked": len(findings), "findings": sum(item["full_secret"] or item["secret_fragment"] for item in findings), "exit_code": receipt["exit_code"]}))
    sys.exit(receipt["exit_code"])
raise SystemExit("Unknown review action")
