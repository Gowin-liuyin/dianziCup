"""Reproduce original auth assertion failure in native child pytest without raw secret files."""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
WT = Path('C:/Users/yinha/.codex/worktrees/recovery-r02-minio-review/dianzi')
PLUGIN = '''import base64, builtins, io, json, os, sys
from dataclasses import replace
import pytest
from ai_intel.api.authentication import AuthenticationSessionService
original_open = builtins.open
junit = None
observed = {}
class MemoryJUnit(io.StringIO):
    def close(self):
        pass
def memory_open(file, mode="r", *args, **kwargs):
    global junit
    if isinstance(file, (str, os.PathLike)) and os.fspath(file).endswith("privacy.xml") and "w" in mode:
        junit = MemoryJUnit()
        return junit
    return original_open(file, mode, *args, **kwargs)
def pytest_configure(config):
    builtins.open = memory_open
@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    original_login = AuthenticationSessionService.login
    def mismatched_record(self, username, password, origin, client_key):
        token, record = original_login(self, username, password, origin, client_key)
        observed.update(token=token, session_hash=record.session_id, csrf_token=record.csrf_token, password=password)
        print(token[8:24], record.session_id[16:40], file=sys.stderr)
        return token, replace(record, session_id="controlled assertion mismatch")
    AuthenticationSessionService.login = mismatched_record
    try:
        yield
    finally:
        AuthenticationSessionService.login = original_login
def pytest_unconfigure(config):
    builtins.open = original_open
    if junit is not None:
        print("MEMORY_JUNIT=" + base64.b64encode(junit.getvalue().encode()).decode())
    print("MEMORY_VALUES=" + base64.b64encode(json.dumps(observed).encode()).decode())
'''


def now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='independent-native-auth-') as directory:
        private = Path(directory)
        (private / 'memory_probe.py').write_text(PLUGIN, encoding='utf-8')
        env = dict(os.environ, PYTHONPATH=str(private)+os.pathsep+os.environ['PYTHONPATH'],
                   PYTEST_ADDOPTS='', PYTHONDONTWRITEBYTECODE='1')
        command = [sys.executable, '-m', 'pytest', '-p', 'memory_probe',
                   'tests/integration/test_r02_auth_state.py::test_session_hash_only_is_stored',
                   '--showlocals', '--no-cov', '-o', 'addopts=', '--junitxml=privacy.xml', '-q']
        started = now()
        result = subprocess.run(command, cwd=WT/'backend', env=env,
                                capture_output=True, text=True, encoding='utf-8', timeout=50)
        transport = result.stdout.splitlines()
        junit = base64.b64decode(next(line.removeprefix('MEMORY_JUNIT=') for line in transport
                                     if line.startswith('MEMORY_JUNIT='))).decode()
        observed = json.loads(base64.b64decode(next(line.removeprefix('MEMORY_VALUES=') for line in transport
                                                   if line.startswith('MEMORY_VALUES='))))
        stdout = '\n'.join(line for line in transport if not line.startswith(('MEMORY_JUNIT=', 'MEMORY_VALUES=')))
        surfaces = {'stdout': stdout, 'stderr': result.stderr, 'junit': junit}
        exposure = {}
        for kind, credential in observed.items():
            fragments = {credential[index:index+8] for index in range(len(credential)-7)}
            exposure[kind] = {surface: {'full': credential in content,
                                       'eight_character_fragment': any(value in content for value in fragments)}
                              for surface, content in surfaces.items()}
            for surface, content in list(surfaces.items()):
                for value in (credential, *sorted(fragments, key=len, reverse=True)):
                    content = content.replace(value, '[independent probe redacted]')
                surfaces[surface] = content
        counts = dict.fromkeys(('tests', 'failures', 'errors', 'skipped'), 0)
        for suite in ET.fromstring(junit).iter('testsuite'):
            for key in counts:
                counts[key] += int(suite.get(key, '0'))
        leaked = any(flag for by_surface in exposure.values() for by_flag in by_surface.values()
                     for flag in by_flag.values())
        record = {'started_at': started, 'ended_at': now(), 'command': command,
                  'cwd': str(WT/'backend'), 'native_exit_code': result.returncode,
                  'counts': counts, 'random_values_generated_in_real_pg_login': len(observed)==4,
                  'raw_junit_file_created': (WT/'backend/privacy.xml').exists(),
                  'exposure_before_additional_review_sanitization': exposure,
                  'any_full_or_eight_character_leak': leaked}
        for surface, value in surfaces.items():
            (RUN/('native_auth_failure.'+('xml' if surface=='junit' else surface+'.log'))).write_text(value, encoding='utf-8')
        (RUN/'native_auth_failure.observed.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        print(json.dumps(record))
        expected = {'tests': 1, 'failures': 1, 'errors': 0, 'skipped': 0}
        return 0 if result.returncode==1 and counts==expected and not leaked else 1


if __name__ == '__main__':
    raise SystemExit(main())
