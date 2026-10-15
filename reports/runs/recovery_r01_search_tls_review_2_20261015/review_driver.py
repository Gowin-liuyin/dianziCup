"""Independent frozen-source checks with memory-only raw failure output."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCE = Path('C:/Users/yinha/.codex/worktrees/recovery-r01-tls-recheck/dianzi')
EVIDENCE = Path(__file__).resolve().parent
PYTHON = SOURCE / 'backend/.venv/Scripts/python.exe'
LINUX_SOURCE = '/mnt/c/Users/yinha/.codex/worktrees/recovery-r01-tls-recheck/dianzi'
LINUX_EVIDENCE = '/mnt/d/dianzi/reports/runs/recovery_r01_search_tls_review_2_20261015'
PRIVATE = '/tmp/dianzi-r01-tls-review2-20261015'
RUN_ID = 'r01_tls_review2_20261015'
DOCKER = ['/tmp/dianzi-docker-static-r01-20261014/portable/docker/docker', '--config',
          '/tmp/dianzi-docker-static-r01-20261014/runtime/client-config', '-H',
          'unix:///tmp/dianzi-docker-static-r01-20261014/runtime/docker.sock']
CBM = '/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp'
CBM_CACHE = '/tmp/dianzi-cbm-r01-tls-review2-20261015'
KNOWN: list[str] = []
DSNS: list[str] = []
SHA = 'f2c5873fa8c2695ae81d673e7107ada3e9b52a81'
DEFAULT_DOCKER_MODE = False
LINUX_RUNTIME = '/tmp/dianzi-r01-tls-prefix-runtime-20261015'


def now() -> str:
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')


def audit(value: str) -> dict[str, bool]:
    return {'full': any(secret in value for secret in (*KNOWN, *DSNS) if secret),
            'eight_character_fragment': any(secret[index:index + 8] in value
                for secret in KNOWN for index in range(max(0, len(secret) - 7)))}


def safe(value: str) -> str:
    for secret in sorted((*KNOWN, *DSNS), key=len, reverse=True):
        if secret:
            value = value.replace(secret, '[review redacted credential]')
    fragments = {secret[index:index + 8] for secret in KNOWN
                 for index in range(max(0, len(secret) - 7))}
    if fragments:
        value = re.sub('|'.join(re.escape(part) for part in sorted(fragments)),
                       '[review redacted fragment]', value)
    return value


def write_json(name: str, value: object) -> None:
    (EVIDENCE / (name + '.json')).write_text(safe(json.dumps(value, ensure_ascii=False, indent=2)) + '\n', encoding='utf-8')


def execute(name: str, arguments: list[str], *, cwd: Path | None = None,
            environment: dict[str, str] | None = None, timeout: int = 600,
            stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    cwd = cwd or SOURCE
    started = now()
    result = subprocess.run(arguments, cwd=cwd, env=environment, input=stdin,
                            capture_output=True, text=True, encoding='utf-8', errors='replace',
                            timeout=timeout, check=False)
    payload = result.stdout + result.stderr
    (EVIDENCE / (name + '.log')).write_text(safe(payload), encoding='utf-8')
    write_json(name, {'command': arguments, 'cwd': str(cwd), 'start': started,
        'end': now(), 'exit_code': result.returncode, 'source_sha': SHA,
        'prewrite_stdout_audit': audit(result.stdout), 'prewrite_stderr_audit': audit(result.stderr)})
    print(f'{name}: exit {result.returncode}', flush=True)
    return result


def wsl(arguments: list[str]) -> list[str]:
    return ['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', *arguments]


def connection() -> dict[str, str]:
    result = subprocess.run(wsl(['python3', '-c',
        'import pathlib; print(pathlib.Path("' + PRIVATE + '/connection.json").read_text())']),
        capture_output=True, text=True, check=True)
    values = json.loads(result.stdout)['environment']
    if values['TEST_SEARCH_TLS_PASSWORD'] not in KNOWN:
        KNOWN.append(values['TEST_SEARCH_TLS_PASSWORD'])
    public = EVIDENCE / 'public_certificates'
    public.mkdir(exist_ok=True)
    for field in ('TEST_SEARCH_TLS_CA_FILE', 'TEST_SEARCH_TLS_WRONG_CA_FILE'):
        raw = subprocess.run(wsl(['cat', values[field]]), capture_output=True, check=True).stdout
        target = public / Path(values[field]).name
        target.write_bytes(raw)
        values[field] = str(target)
    return values


MEMORY_PLUGIN = '''import base64, builtins, io, os, sys, json
original = builtins.open
buffer = None
class NativeJUnitMemory(io.StringIO):
    def close(self):
        pass
def guarded_open(file, mode="r", *args, **kwargs):
    global buffer
    if isinstance(file, (str, os.PathLike)) and os.fspath(file).endswith("review-native.xml") and "w" in mode:
        buffer = NativeJUnitMemory()
        return buffer
    return original(file, mode, *args, **kwargs)
def pytest_configure(config):
    builtins.open = guarded_open
def pytest_unconfigure(config):
    builtins.open = original
    if buffer is not None:
        print("REVIEW_MEMORY_JUNIT=" + base64.b64encode(buffer.getvalue().encode()).decode())
    observed = getattr(sys.modules.get("test_independent_failure"), "OBSERVED", [])
    print("REVIEW_MEMORY_VALUES=" + base64.b64encode(json.dumps(observed).encode()).decode())
'''


def pytest_command(name: str, selection: list[str], *, environment: dict[str, str] | None = None,
                   cwd: Path | None = None, ini: Path | None = None, timeout: int = 600,
                   remove_environment: tuple[str, ...] = ()) -> None:
    plugin = EVIDENCE / 'native_plugin'
    plugin.mkdir(exist_ok=True)
    (plugin / 'independent_memory_junit.py').write_text(MEMORY_PLUGIN, encoding='utf-8')
    env = dict(os.environ, PYTEST_ADDOPTS='', PYTHONUTF8='1', PYTHONPATH=str(plugin) + os.pathsep + str(SOURCE))
    if environment:
        env.update(environment)
    for name_to_remove in remove_environment:
        env.pop(name_to_remove, None)
    arguments = [str(PYTHON), '-m', 'pytest', '-p', 'independent_memory_junit', *selection,
        '--junitxml=review-native.xml', '-q']
    if ini:
        arguments += ['-c', str(ini)]
    started = now()
    result = subprocess.run(arguments, cwd=cwd or SOURCE / 'backend', env=env,
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout, check=False)
    lines = result.stdout.splitlines()
    xml_text = ''
    for line in lines:
        if line.startswith('REVIEW_MEMORY_VALUES='):
            KNOWN.extend(json.loads(base64.b64decode(line.split('=', 1)[1])))
        if line.startswith('REVIEW_MEMORY_JUNIT='):
            xml_text = base64.b64decode(line.split('=', 1)[1]).decode()
    stdout = '\n'.join(line for line in lines if not line.startswith(('REVIEW_MEMORY_VALUES=', 'REVIEW_MEMORY_JUNIT='))) + '\n'
    counts = None
    if xml_text:
        root = ET.fromstring(xml_text)
        counts = {key: sum(int(suite.get(key, '0')) for suite in root.iter('testsuite'))
                  for key in ('tests', 'failures', 'errors', 'skipped')}
        counts['passed'] = counts['tests'] - counts['failures'] - counts['errors'] - counts['skipped']
        (EVIDENCE / (name + '.xml')).write_text(safe(xml_text), encoding='utf-8')
    (EVIDENCE / (name + '.log')).write_text(safe(stdout + result.stderr), encoding='utf-8')
    write_json(name, {'command': arguments, 'cwd': str(cwd or SOURCE / 'backend'),
        'start': started, 'end': now(), 'source_sha': SHA, 'exit_code': result.returncode,
        'counts': counts, 'pre_outer_redaction_stdout': audit(stdout),
        'pre_outer_redaction_stderr': audit(result.stderr), 'pre_outer_redaction_junit': audit(xml_text),
        'junit_raw_memory_only': bool(xml_text), 'raw_junit_path_exists': (cwd or SOURCE / 'backend').joinpath('review-native.xml').exists()})
    print(f'{name}: exit {result.returncode}, counts {counts}', flush=True)


def basic() -> None:
    execute('source_identity', ['git', 'show', '--no-patch', '--format=%H %T %ai', SHA])
    execute('initial_status', ['git', 'status', '--porcelain'])
    execute('locked_sync', ['uv', 'sync', '--locked', '--project', 'backend'])
    execute('python_version', [str(PYTHON), '--version'])
    execute('cbm_version', wsl([CBM, '--version']))
    cbm_env = ['env', 'CBM_CACHE_DIR=' + CBM_CACHE,
               'CBM_ALLOWED_ROOT=' + LINUX_SOURCE + '/backend/src', CBM, 'cli', '--json']
    execute('cbm_index', wsl([*cbm_env, 'index_repository', '--repo-path', LINUX_SOURCE + '/backend/src',
        '--name', 'r01-tls-review2-source', '--mode', 'fast', '--persistence', 'false']))
    execute('cbm_architecture', wsl([*cbm_env, 'get_architecture', '--project', 'r01-tls-review2-source']))
    execute('cbm_trace', wsl([*cbm_env, 'trace_path', '--project', 'r01-tls-review2-source',
        '--function-name', 'create_application', '--direction', 'outbound', '--depth', '3']))
    execute('ruff', [str(PYTHON), '-m', 'ruff', 'check', '.', '../scripts/dev.py', '../scripts/prepare_search_tls_test.py'], cwd=SOURCE / 'backend')
    execute('format', [str(PYTHON), '-m', 'ruff', 'format', '--check', '.', '../scripts/dev.py', '../scripts/prepare_search_tls_test.py'], cwd=SOURCE / 'backend')
    execute('mypy', [str(PYTHON), '-m', 'mypy', '--config-file', 'pyproject.toml', 'src', '../scripts/dev.py', '../scripts/prepare_search_tls_test.py'], cwd=SOURCE / 'backend')
    env = dict(DIANZI_DOCKER_COMMAND_JSON=json.dumps(['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', *DOCKER]))
    pytest_command('unit', ['tests/unit'], environment=env)
    pytest_command('security', ['tests/security', '--no-cov'], environment=env)
    pytest_command('tls_compose_contract', ['tests/contract/test_r01_compose_configuration.py',
        'tests/contract/test_r01_search_tls_deployment.py', 'tests/contract/test_r01_migration_configuration.py', '--no-cov'], environment=env)
    execute('migration_head_offline', [str(PYTHON), '-m', 'alembic', '-c', 'alembic.ini', 'heads'], cwd=SOURCE / 'backend')


def fixture(action: str) -> None:
    wrapper = EVIDENCE / 'fixture_wrapper.py'
    wrapper.write_text('''import argparse, contextlib, importlib.util, io, json, os, pathlib, re, sys, time
source = pathlib.Path("''' + LINUX_SOURCE + '''/scripts/prepare_search_tls_test.py")
spec = importlib.util.spec_from_file_location("frozen_fixture", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
original_compose = module.compose_command
module.compose_command = lambda command, project, host: original_compose(command, project, host) + ["-f", "''' + LINUX_EVIDENCE + '''/bounded_fixture.yaml"]
directory = pathlib.Path("''' + PRIVATE + '''")
arguments = argparse.Namespace(run_id="''' + RUN_ID + '''", private_directory=directory, port=29208,
    transport_port=29308, host_network=True, github_env=directory / "github_env")
os.environ["DIANZI_DOCKER_COMMAND_JSON"] = json.dumps(''' + repr(DOCKER) + ''')
if ''' + repr(DEFAULT_DOCKER_MODE) + ''':
    os.environ.pop("DIANZI_DOCKER_COMMAND_JSON", None)
    os.environ["PATH"] = "''' + LINUX_RUNTIME + '''/bin:" + os.environ["PATH"]
buffer = io.StringIO()
code = 0
started = time.time()
with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
    try:
        if sys.argv[1] == "create":
            module.create_fixture(arguments)
        else:
            module.cleanup_fixture(arguments)
    except Exception as error:
        code = 1
        print("blocked: " + type(error).__name__)
text = buffer.getvalue()
values = None
if (directory / "connection.json").is_file():
    values = json.loads((directory / "connection.json").read_text())["environment"]
    password = values["TEST_SEARCH_TLS_PASSWORD"]
    mask_seen = "::add-mask::" + password in text
    text = text.replace(password, "[review fixture credential redacted]")
    text = re.sub("|".join(re.escape(password[i:i+8]) for i in range(len(password)-7)), "[review fixture fragment redacted]", text)
else:
    mask_seen = False
export_matches = False
exported = {}
if sys.argv[1] == "create" and (directory / "github_env").is_file():
    exported = dict(line.split("=", 1) for line in (directory / "github_env").read_text().splitlines())
    export_matches = exported == values
print(json.dumps({"action": sys.argv[1], "exit_code": code, "elapsed_seconds": time.time()-started,
    "github_mask_seen": mask_seen, "github_export_matches_connection": export_matches, "safe_output": text,
    "exported_name_count": len(exported), "exported_docker_prefix": exported.get("DIANZI_DOCKER_COMMAND_JSON"),
    "resource_overlay": "768MiB and heap384MiB", "host_network": True}))
sys.exit(code)
''', encoding='utf-8')
    (EVIDENCE / 'bounded_fixture.yaml').write_text('services:\n  opensearch:\n    mem_limit: 768m\n    environment:\n      OPENSEARCH_JAVA_OPTS: "-Xms384m -Xmx384m"\n', encoding='utf-8')
    execute('fixture_' + action, wsl(['python3', LINUX_EVIDENCE + '/fixture_wrapper.py', action]), timeout=450)
    execute('fixture_' + action + '_inventory', wsl([*DOCKER, 'ps', '-a', '--filter',
        'label=com.docker.compose.project=dianzi-test-' + RUN_ID, '--format', '{{.Names}} {{.Status}}']))
    if action == 'create':
        execute('fixture_limits', wsl([*DOCKER, 'inspect', 'dianzi-test-' + RUN_ID + '-opensearch-1', '--format',
            '{{.HostConfig.Memory}} {{.HostConfig.NanoCpus}} {{.HostConfig.PidsLimit}} {{.Config.User}} {{.State.Health.Status}} {{.State.OOMKilled}}']))
    else:
        execute('fixture_volumes_preserved', wsl([*DOCKER, 'volume', 'ls', '--filter',
            'label=com.docker.compose.project=dianzi-test-' + RUN_ID, '--format', '{{.Name}}']))


def native() -> None:
    values = connection()
    env = dict(values, DIANZI_DOCKER_COMMAND_JSON=json.dumps(['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', *DOCKER]))
    test = 'tests/integration/test_r01_search_tls_live.py'
    pytest_command('tls_live_seven', [test, '--no-cov', '--showlocals'], environment=env, timeout=240)
    wrong = secrets.token_urlsafe(48)
    KNOWN.append(wrong)
    pytest_command('forced_tls_assertion', [test, '-k', 'correct', '--no-cov', '--showlocals'], environment=dict(env, TEST_SEARCH_TLS_PASSWORD=wrong))
    pytest_command('forced_tls_fixture', [test, '-k', 'correct', '--no-cov', '--showlocals'], environment=dict(env, TEST_SEARCH_TLS_URL='https://localhost:70000'))
    missing = dict(env)
    missing.pop('TEST_SEARCH_TLS_PASSWORD')
    pytest_command('forced_tls_missing', [test, '-k', 'correct', '--no-cov', '--showlocals'], environment=dict(missing, TEST_SEARCH_TLS_PASSWORD=''))
    probe = Path(tempfile.mkdtemp(prefix='r01-tls-independent-native-'))
    (probe / 'conftest.py').write_bytes((SOURCE / 'backend/tests/conftest.py').read_bytes())
    (probe / 'pytest.ini').write_text('[pytest]\n', encoding='utf-8')
    (probe / 'test_independent_failure.py').write_text('''from ai_intel.api.authentication import AuthenticationSessionService, InMemoryUserDirectory, SessionRecord
from ai_intel.domain.access import Role
import secrets
OBSERVED = []
def test_real_session_record_failure():
    service = AuthenticationSessionService(InMemoryUserDirectory(), ("http://localhost",), False)
    password = secrets.token_urlsafe(48)
    service.create_precreated_user("independent", password, "test", Role.ANALYST)
    session_token, record = service.login("independent", password, "http://localhost", "isolated-test")
    assert isinstance(record, SessionRecord)
    session_hash = record.session_id
    csrf_token = record.csrf_token
    OBSERVED.extend([password, session_token, session_hash, csrf_token])
    print(session_token[9:29], session_hash[12:40])
    assert False, "controlled real SessionRecord native assertion"
''', encoding='utf-8')
    pytest_command('forced_real_session_record', ['test_independent_failure.py', '--showlocals', '--no-cov'], cwd=probe, ini=probe / 'pytest.ini')
    extended(values, env, probe)


def extended(values: dict[str, str], env: dict[str, str], probe: Path) -> None:
    execute('expired_ca_generate_x509', wsl(['openssl', 'x509', '-in', PRIVATE + '/pki/root-ca.pem',
        '-signkey', PRIVATE + '/pki/root-ca-key.pem', '-sha256', '-days', '-1',
        '-out', PRIVATE + '/pki/expired-root-ca.pem']))
    expired_public = subprocess.run(wsl(['cat', PRIVATE + '/pki/expired-root-ca.pem']), capture_output=True, check=True).stdout
    expired_path = EVIDENCE / 'public_certificates/expired-root-ca.pem'
    expired_path.write_bytes(expired_public)
    execute('openssl_correct_chain', wsl(['openssl', 'verify', '-CAfile', PRIVATE + '/pki/root-ca.pem',
        '-verify_hostname', 'localhost', PRIVATE + '/pki/node.pem']))
    execute('openssl_expired_chain', wsl(['openssl', 'verify', '-CAfile', PRIVATE + '/pki/expired-root-ca.pem',
        '-verify_hostname', 'localhost', PRIVATE + '/pki/node.pem']))
    (probe / 'test_extended_tls.py').write_text('''import os, socket, ssl
import httpx, pytest
from pydantic import SecretStr
from fastapi.testclient import TestClient
from ai_intel.api.app import create_application
from ai_intel.infrastructure.settings import ApplicationSettings

def settings(url=None, ca=None):
    return ApplicationSettings(app_env="test", data_mode="live", database_url=None, redis_url=None,
        opensearch_url=url or os.environ["TEST_SEARCH_TLS_URL"],
        opensearch_username=os.environ["TEST_SEARCH_TLS_USERNAME"],
        opensearch_password=SecretStr(os.environ["TEST_SEARCH_TLS_PASSWORD"]),
        opensearch_ca_file=ca or os.environ["TEST_SEARCH_TLS_CA_FILE"], dependency_timeout_seconds=3)

@pytest.mark.parametrize("case", ["missing_ca_file", "expired_ca", "plain_http"])
def test_extended_real_tls_refusal(case):
    ca = os.environ["TEST_SEARCH_TLS_CA_FILE"]
    url = os.environ["TEST_SEARCH_TLS_URL"]
    if case == "missing_ca_file":
        ca = os.environ["TEST_SEARCH_TLS_CA_FILE"] + ".does-not-exist"
    elif case == "expired_ca":
        ca = os.environ["REVIEW_EXPIRED_CA"]
    else:
        url = url.replace("https://", "http://")
    with TestClient(create_application(settings=settings(url, ca))) as client:
        response = client.get("/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["dependencies"]["search"] == {"state":"unavailable", "reason":"search connection unavailable"}
    assert os.environ["TEST_SEARCH_TLS_PASSWORD"] not in response.text
    assert "Traceback" not in response.text

def test_expired_ca_fails_actual_tls_socket():
    context = ssl.create_default_context(cafile=os.environ["REVIEW_EXPIRED_CA"])
    with socket.create_connection(("127.0.0.1",29208),timeout=3) as connection:
        with pytest.raises(ssl.SSLCertVerificationError) as error:
            context.wrap_socket(connection, server_hostname="localhost")
    assert error.value.verify_code == 10

def test_real_health_account_is_readonly():
    with httpx.Client(verify=ssl.create_default_context(cafile=os.environ["TEST_SEARCH_TLS_CA_FILE"]),
        auth=httpx.BasicAuth(os.environ["TEST_SEARCH_TLS_USERNAME"],os.environ["TEST_SEARCH_TLS_PASSWORD"]), timeout=3) as client:
        assert client.get(os.environ["TEST_SEARCH_TLS_URL"]+"/_cluster/health").status_code == 200
        for path in ("/", "/_cat/indices?format=json", "/_plugins/_security/api/internalusers"):
            assert client.get(os.environ["TEST_SEARCH_TLS_URL"]+path).status_code == 403

def test_default_module_app_uses_explicit_tls_inputs(monkeypatch):
    import importlib
    for source, target in (("TEST_SEARCH_TLS_URL","OPENSEARCH_URL"),
        ("TEST_SEARCH_TLS_USERNAME","OPENSEARCH_USERNAME"),("TEST_SEARCH_TLS_PASSWORD","OPENSEARCH_PASSWORD"),
        ("TEST_SEARCH_TLS_CA_FILE","OPENSEARCH_CA_FILE")):
        monkeypatch.setenv(target,os.environ[source])
    monkeypatch.setenv("APP_ENV","test")
    monkeypatch.setenv("DATA_MODE","live")
    monkeypatch.delenv("DATABASE_URL",raising=False)
    monkeypatch.delenv("REDIS_URL",raising=False)
    import ai_intel.api.app as entry
    module = importlib.reload(entry)
    with TestClient(module.app) as client:
        response = client.get("/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["dependencies"]["search"] == {"state":"ready"}
''', encoding='utf-8')
    pytest_command('tls_extended_actual', ['test_extended_tls.py', '--showlocals', '--no-cov'], cwd=probe,
        ini=probe / 'pytest.ini', environment=dict(env, REVIEW_EXPIRED_CA=str(expired_path)))
    pytest_command('r01_security_targeted', ['tests/security/test_r01_tls_failure_privacy.py',
        'tests/security/test_r01_dynamic_failure_privacy.py', '--no-cov'], environment=env)
    execute('fixture_permissions', wsl(['stat', '-c', '%a %U:%G %n', PRIVATE, PRIVATE + '/connection.json',
        PRIVATE + '/github_env', PRIVATE + '/pki/root-ca-key.pem', PRIVATE + '/pki/admin-key.pem',
        PRIVATE + '/pki/node-key.pem', PRIVATE + '/security', PRIVATE + '/security/internal_users.yml']))
    write_json('native_probe_identity', {'directory': str(probe), 'source_conftest_sha256': hashlib.sha256((SOURCE / 'backend/tests/conftest.py').read_bytes()).hexdigest(),
        'copied_conftest_sha256': hashlib.sha256((probe / 'conftest.py').read_bytes()).hexdigest()})
    fixture('cleanup')
    final_scan()


def extras() -> None:
    values = connection()
    env = dict(values, DIANZI_DOCKER_COMMAND_JSON=json.dumps(['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', *DOCKER]))
    pytest_command('ci_missing_docker_command_actual', ['tests/integration/test_r01_search_tls_live.py',
        '-k', 'fault', '--showlocals', '--no-cov'], environment=env,
        remove_environment=('DIANZI_DOCKER_COMMAND_JSON',))
    probe = Path(tempfile.mkdtemp(prefix='r01-tls-independent-extra-'))
    (probe / 'conftest.py').write_bytes((SOURCE / 'backend/tests/conftest.py').read_bytes())
    (probe / 'pytest.ini').write_text('[pytest]\n', encoding='utf-8')
    extended(values, env, probe)


def supplementary() -> None:
    execute('unit_dev_entry', [str(PYTHON), 'scripts/dev.py', 'check', '--scope', 'unit', '--timeout-seconds', '600'],
        environment=dict(os.environ, PYTHONUTF8='1'))
    execute('migration_head_programmatic', [str(PYTHON), '-c',
        'from alembic.config import Config; from alembic.script import ScriptDirectory; '
        'from ai_intel.infrastructure.database import MIGRATIONS_DIR; c=Config(); '
        'c.set_main_option("script_location",str(MIGRATIONS_DIR)); '
        's=ScriptDirectory.from_config(c); print("head="+s.get_current_head()); '
        'print("revisions="+str(len(list(s.walk_revisions()))))'])
    execute('migration_fresh_offline_sql', [str(PYTHON), '-c',
        'from alembic import command; from alembic.config import Config; '
        'from ai_intel.infrastructure.database import MIGRATIONS_DIR; c=Config(); '
        'c.set_main_option("script_location",str(MIGRATIONS_DIR)); '
        'c.set_main_option("sqlalchemy.url","postgresql+psycopg://unused@127.0.0.1/unused"); '
        'command.upgrade(c,"head",sql=True)'])


def finalize() -> None:
    connection()
    for owned_private in ('/tmp/dianzi-r01-tls-review2-20261015', '/tmp/dianzi-r01-tls-prefix-review2-20261015'):
        observed = subprocess.run(wsl(['python3', '-c',
            'import pathlib,json; p=pathlib.Path("' + owned_private + '/connection.json"); '
            'print(json.loads(p.read_text())["environment"]["TEST_SEARCH_TLS_PASSWORD"])']),
            capture_output=True, text=True, check=True).stdout.strip()
        if observed not in KNOWN:
            KNOWN.append(observed)
    execute('final_status', ['git', 'status', '--porcelain'])
    execute('frozen_code_diff', ['git', 'diff', '--exit-code', SHA, '--', 'backend', 'infra', 'scripts', '.github', 'config'])
    if SHA.startswith('f2c5873'):
        execute('tls_author_blob_match', ['git', 'diff', '--exit-code', 'd8be10512925d6981e07a8fbc043f87a8648b7b5', SHA, '--',
            'scripts/prepare_search_tls_test.py', 'backend/tests/conftest.py', 'backend/tests/integration/test_r01_search_tls_live.py',
            '.github/workflows/ci.yml', 'infra/compose/compose.search-secure.test.yaml', 'infra/compose/compose.search-secure.test.host.yaml'])
    execute('final_owned_containers', wsl([*DOCKER, 'ps', '-a', '--filter',
        'label=com.docker.compose.project=dianzi-test-' + RUN_ID, '--format', '{{.Names}} {{.Status}}']))
    execute('original_tls_readonly_end_status', wsl([*DOCKER, 'inspect', 'dianzi-test-r01_tls_20261015-opensearch-1',
        '--format', '{{.State.Status}} {{.State.Health.Status}} {{.State.OOMKilled}}']))
    import importlib.util
    scanner_spec = importlib.util.spec_from_file_location('original_scanner', SOURCE / 'scripts/security_scan.py')
    scanner = importlib.util.module_from_spec(scanner_spec)
    sys.modules[scanner_spec.name] = scanner
    scanner_spec.loader.exec_module(scanner)
    findings = []
    scanned = []
    for path in EVIDENCE.rglob('*'):
        if path.is_file() and path.suffix in ('.py', '.json', '.log', '.xml', '.yaml', '.pem'):
            scanned.append(path)
            content = path.read_text(encoding='utf-8', errors='replace')
            for name, pattern in scanner.PATTERNS.items():
                for match in pattern.finditer(content):
                    findings.append({'file': str(path.relative_to(EVIDENCE)), 'pattern': name,
                        'line': content[:match.start()].count('\n') + 1,
                        'match_sha256': hashlib.sha256(match.group(0).encode()).hexdigest()})
    write_json('original_patterns_evidence_scan', {'time': now(), 'original_patterns_unchanged': True,
        'files_scanned': len(scanned), 'findings': findings})
    files = ['backend/tests/conftest.py', 'backend/tests/integration/test_r01_search_tls_live.py',
        'scripts/prepare_search_tls_test.py', '.github/workflows/ci.yml',
        'infra/compose/compose.search-secure.test.yaml', 'infra/compose/compose.search-secure.test.host.yaml',
        'backend/src/ai_intel/api/app.py', 'backend/src/ai_intel/infrastructure/settings.py',
        'backend/pyproject.toml', 'backend/uv.lock', 'backend/migrations/versions/0011_job_delivery_and_cursors.py']
    tree = subprocess.run(['git', 'rev-parse', SHA + '^{tree}'], cwd=SOURCE, capture_output=True, text=True, check=True).stdout.strip()
    write_json('source_manifest', {'time': now(), 'commit': SHA, 'tree': tree,
        'files': [{'path': name, 'sha256': hashlib.sha256((SOURCE / name).read_bytes()).hexdigest(),
            'git_blob': subprocess.run(['git', 'rev-parse', SHA + ':' + name], cwd=SOURCE,
                capture_output=True, text=True, check=True).stdout.strip()} for name in files]})
    final_scan()
    report = Path('D:/dianzi/reports/reviews/recovery/G-A-R01-search-TLS-review-2.md')
    write_json('report_manifest', {'time': now(), 'report': str(report),
        'sha256': hashlib.sha256(report.read_bytes()).hexdigest(), 'bytes': report.stat().st_size})
    paths = sorted(path for path in EVIDENCE.rglob('*') if path.is_file() and '__pycache__' not in path.parts
        and path.name != 'evidence_manifest.json')
    write_json('evidence_manifest', {'time': now(), 'source_sha': SHA,
        'file_count': len(paths), 'files': [{'path': str(path.relative_to(EVIDENCE)),
            'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in paths]})
    print('original pattern findings: ' + str(len(findings)), flush=True)


def prefix_recheck() -> None:
    global SOURCE, PYTHON, LINUX_SOURCE, EVIDENCE, LINUX_EVIDENCE, PRIVATE, RUN_ID, SHA, CBM_CACHE, DEFAULT_DOCKER_MODE
    SOURCE = Path('C:/Users/yinha/.codex/worktrees/recovery-r01-tls-prefix-recheck/dianzi')
    LINUX_SOURCE = '/mnt/c/Users/yinha/.codex/worktrees/recovery-r01-tls-prefix-recheck/dianzi'
    EVIDENCE = EVIDENCE / 'a7_prefix_recheck'
    EVIDENCE.mkdir(exist_ok=True)
    LINUX_EVIDENCE += '/a7_prefix_recheck'
    PRIVATE = '/tmp/dianzi-r01-tls-prefix-review2-20261015'
    RUN_ID = 'r01_tls_prefix_review2_20261015'
    SHA = 'a7c0a4aab37b3cf1916efb3cb480f5db148ead44'
    CBM_CACHE = '/tmp/dianzi-cbm-r01-tls-prefix-review2-20261015'
    DEFAULT_DOCKER_MODE = True
    runtime_python = LINUX_RUNTIME + '/python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12'
    linux_python = LINUX_RUNTIME + '/venv/bin/python'
    execute('initial_status', ['git', 'status', '--porcelain'])
    execute('source_identity', ['git', 'show', '--no-patch', '--format=%H %T %ai', SHA])
    execute('prefix_only_change', ['git', 'show', '--format=fuller', SHA, '--', 'scripts/prepare_search_tls_test.py'])
    execute('unchanged_tls_consumer_and_hook', ['git', 'diff', '--exit-code',
        'f2c5873fa8c2695ae81d673e7107ada3e9b52a81', SHA, '--', 'backend/tests/conftest.py',
        'backend/tests/integration/test_r01_search_tls_live.py', 'backend/src/ai_intel/api/app.py',
        'backend/src/ai_intel/infrastructure/settings.py', '.github/workflows/ci.yml',
        'infra/compose/compose.search-secure.test.yaml', 'infra/compose/compose.search-secure.test.host.yaml'])
    execute('official_uv_version', wsl([LINUX_RUNTIME + '/uv', '--version']))
    execute('official_python_version', wsl([runtime_python, '--version']))
    execute('python_install_recheck', wsl([LINUX_RUNTIME + '/uv', 'python', 'install', '3.12',
        '--install-dir', LINUX_RUNTIME + '/python']), timeout=120)
    execute('runtime_hashes', wsl(['sha256sum', LINUX_RUNTIME + '/uv', runtime_python]))
    execute('locked_linux_sync', wsl(['env', 'UV_CACHE_DIR=' + LINUX_RUNTIME + '/cache',
        'UV_PROJECT_ENVIRONMENT=' + LINUX_RUNTIME + '/venv', LINUX_RUNTIME + '/uv', 'sync',
        '--locked', '--project', LINUX_SOURCE + '/backend', '--python', runtime_python]), timeout=600)
    cbm_env = ['env', 'CBM_CACHE_DIR=' + CBM_CACHE,
               'CBM_ALLOWED_ROOT=' + LINUX_SOURCE + '/backend/src', CBM, 'cli', '--json']
    execute('cbm_version', wsl([CBM, '--version']))
    execute('cbm_index', wsl([*cbm_env, 'index_repository', '--repo-path', LINUX_SOURCE + '/backend/src',
        '--name', 'r01-tls-prefix-review2-source', '--mode', 'fast', '--persistence', 'false']))
    execute('cbm_architecture', wsl([*cbm_env, 'get_architecture', '--project', 'r01-tls-prefix-review2-source']))
    execute('cbm_trace', wsl([*cbm_env, 'trace_path', '--project', 'r01-tls-prefix-review2-source',
        '--function-name', 'create_application', '--direction', 'outbound', '--depth', '3']))
    setup = '''import os,pathlib
p=pathlib.Path("''' + LINUX_RUNTIME + '''/bin")
p.mkdir(mode=0o700,exist_ok=True)
script=p/"docker"
script.write_text('#!/bin/sh\\nexec ''' + ' '.join(DOCKER) + ''' "$@"\\n')
script.chmod(0o700)
print("private PATH docker adapter ready")
'''
    execute('private_path_adapter', wsl(['python3', '-c', setup]))
    fixture('create')
    connection()
    plugin = EVIDENCE / 'native_plugin'
    plugin.mkdir(exist_ok=True)
    (plugin / 'independent_memory_junit.py').write_text(MEMORY_PLUGIN, encoding='utf-8')
    helper = EVIDENCE / 'linux_native_fault.py'
    helper.write_text('''import base64,json,os,pathlib,subprocess,re,xml.etree.ElementTree as ET,datetime
private=pathlib.Path("''' + PRIVATE + '''")
values=json.loads((private/"connection.json").read_text())["environment"]
assert json.loads(values["DIANZI_DOCKER_COMMAND_JSON"]) == ["docker"]
assert len(values)==13
environment=dict(os.environ,**values,PYTHONUTF8="1",PYTEST_ADDOPTS="",
    PYTHONPATH="''' + LINUX_EVIDENCE + '''/native_plugin:''' + LINUX_SOURCE + '''",
    PATH="''' + LINUX_RUNTIME + '''/bin:"+os.environ["PATH"])
command=["''' + linux_python + '''","-m","pytest","-p","independent_memory_junit",
    "tests/integration/test_r01_search_tls_live.py","-k","fault","--no-cov","--showlocals",
    "--junitxml=review-native.xml","-q"]
started=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="seconds")
result=subprocess.run(command,cwd="''' + LINUX_SOURCE + '''/backend",env=environment,
    capture_output=True,text=True,timeout=240)
lines=result.stdout.splitlines()
xml=next(base64.b64decode(line.split("=",1)[1]).decode() for line in lines if line.startswith("REVIEW_MEMORY_JUNIT="))
stdout="\\n".join(line for line in lines if not line.startswith(("REVIEW_MEMORY_JUNIT=","REVIEW_MEMORY_VALUES=")))
secret=values["TEST_SEARCH_TLS_PASSWORD"]
def leaked(text):
    return {"full":secret in text,"eight_character_fragment":any(secret[i:i+8] in text for i in range(len(secret)-7))}
def redact(text):
    text=text.replace(secret,"[review credential redacted]")
    return re.sub("|".join(re.escape(secret[i:i+8]) for i in range(len(secret)-7)),"[review fragment redacted]",text)
root=ET.fromstring(xml)
counts={key:sum(int(s.get(key,"0")) for s in root.iter("testsuite")) for key in ("tests","failures","errors","skipped")}
output=pathlib.Path("''' + LINUX_EVIDENCE + '''")
(output/"fault_native.log").write_text(redact(stdout+result.stderr))
(output/"fault_native.xml").write_text(redact(xml))
receipt={"command":command,"cwd":"''' + LINUX_SOURCE + '''/backend","start":started,
    "end":datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="seconds"),
    "source_sha":"''' + SHA + '''","exit_code":result.returncode,"counts":counts,
    "prepare_values_used_without_replacing_docker_json":True,"exported_value_count":len(values),
    "pre_outer_redaction_stdout":leaked(stdout),"pre_outer_redaction_junit":leaked(xml),
    "pre_outer_redaction_stderr":leaked(result.stderr),"raw_junit_memory_only":True,
    "raw_junit_path_exists":pathlib.Path("''' + LINUX_SOURCE + '''/backend/review-native.xml").exists()}
(output/"fault_native.json").write_text(json.dumps(receipt,indent=2)+"\\n")
print(json.dumps(receipt))
raise SystemExit(result.returncode)
''', encoding='utf-8')
    try:
        execute('linux_fault_entry', wsl(['python3', LINUX_EVIDENCE + '/linux_native_fault.py']), timeout=270)
        execute('fixture_after_fault_status', wsl([*DOCKER, 'inspect', 'dianzi-test-' + RUN_ID + '-opensearch-1',
            '--format', '{{.State.Status}} {{.State.Health.Status}} {{.State.OOMKilled}}']))
    finally:
        fixture('cleanup')
    execute('prepare_ruff', wsl([linux_python, '-m', 'ruff', 'check', '--config', LINUX_SOURCE + '/backend/pyproject.toml',
        LINUX_SOURCE + '/scripts/prepare_search_tls_test.py']))
    execute('prepare_format', wsl([linux_python, '-m', 'ruff', 'format', '--check', '--config', LINUX_SOURCE + '/backend/pyproject.toml',
        LINUX_SOURCE + '/scripts/prepare_search_tls_test.py']))
    finalize()


def prefix_audit_only() -> None:
    global SOURCE, LINUX_SOURCE, EVIDENCE, LINUX_EVIDENCE, PRIVATE, RUN_ID, SHA
    SOURCE = Path('C:/Users/yinha/.codex/worktrees/recovery-r01-tls-prefix-recheck/dianzi')
    LINUX_SOURCE = '/mnt/c/Users/yinha/.codex/worktrees/recovery-r01-tls-prefix-recheck/dianzi'
    EVIDENCE = EVIDENCE / 'a7_prefix_recheck'
    LINUX_EVIDENCE += '/a7_prefix_recheck'
    PRIVATE = '/tmp/dianzi-r01-tls-prefix-review2-20261015'
    RUN_ID = 'r01_tls_prefix_review2_20261015'
    SHA = 'a7c0a4aab37b3cf1916efb3cb480f5db148ead44'
    for name in ('initial_status', 'final_status', 'frozen_code_diff'):
        for suffix in ('.json', '.log'):
            path = EVIDENCE / (name + suffix)
            if path.exists():
                path.rename(path.with_name(name + '_prior_default_cwd' + suffix))
    execute('initial_status_correct_target', ['git', 'status', '--porcelain'])
    finalize()


def final_scan() -> None:
    findings = []
    count = 0
    for path in EVIDENCE.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc',):
            count += 1
            observed = audit(path.read_text(encoding='utf-8', errors='replace'))
            if any(observed.values()):
                findings.append({'file': str(path.relative_to(EVIDENCE)), 'matches': observed})
    report = Path('D:/dianzi/reports/reviews/recovery/G-A-R01-search-TLS-review-2.md')
    if report.is_file():
        count += 1
        report_audit = audit(report.read_text(encoding='utf-8'))
        if any(report_audit.values()):
            findings.append({'file': str(report), 'matches': report_audit})
    write_json('precise_secret_scan', {'start': now(), 'files_scanned': count, 'password_or_token_values': len(KNOWN),
        'full_dsns': len(DSNS), 'full_and_all_contiguous_eight_checked': True, 'findings': findings})
    print(f'precise_secret_scan: {count} files, {len(findings)} findings', flush=True)


if __name__ == '__main__':
    try:
        {'basic': basic, 'create': lambda: fixture('create'), 'cleanup': lambda: fixture('cleanup'),
         'native': native, 'supplementary': supplementary, 'extras': extras, 'finalize': finalize,
         'prefix_recheck': prefix_recheck, 'prefix_audit_only': prefix_audit_only}[sys.argv[1]]()
    except Exception as error:
        write_json('driver_error_' + sys.argv[1], {'time': now(), 'error_type': type(error).__name__,
            'message': safe(str(error)), 'business_result': 'not_assumed'})
        print('review driver stopped: ' + type(error).__name__, flush=True)
        sys.exit(1)
