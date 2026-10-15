"""Check new resource evidence and absence of generated test secrets."""

import hashlib
import json
import pathlib
import subprocess
from datetime import datetime, timedelta, timezone


DIRECTORY = pathlib.Path(__file__).resolve().parent
ZONE = timezone(timedelta(hours=8))


def main() -> None:
    secrets_to_check = []
    config_permissions = {}
    for suffix in ('r01_quality_20261014', 'r01_frontend_20261014'):
        config_path = '/tmp/dianzi-docker-static-r01-20261014/runtime/test-services-' + suffix + '/connection.json'
        result = subprocess.run(['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec',
                                 '/bin/cat', config_path], capture_output=True, text=True, timeout=10, check=True)
        private_config = json.loads(result.stdout)
        assert private_config['DIANZI_TEST_RUN_ID'] == suffix
        secrets_to_check.extend(private_config[key] for key in
                                ('postgres_password', 'redis_password', 'TEST_DATABASE_URL', 'TEST_REDIS_URL'))
        result = subprocess.run(['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec',
                                 'stat', '-c', '%a', config_path], capture_output=True, text=True, timeout=10, check=True)
        assert result.stdout.strip() == '600'
        config_permissions[suffix] = '600'
    search_config_path = '/tmp/dianzi-docker-static-r01-20261014/runtime/test-opensearch-r01_20261014/connection.json'
    result = subprocess.run(['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec',
                             'stat', '-c', '%a', search_config_path], capture_output=True,
                            text=True, timeout=10, check=True)
    assert result.stdout.strip() == '600'
    config_permissions['r01_root_opensearch_20261014'] = '600'
    source_hashes = {}
    receipts = []
    exposed_files = []
    files = list(DIRECTORY.iterdir()) + [DIRECTORY.parent.parent / 'tasks' / 'R01-resources.md']
    for path in files:
        if not path.is_file():
            continue
        content = path.read_bytes()
        if any(secret.encode() in content for secret in secrets_to_check):
            exposed_files.append(path.name)
        if path.suffix == '.py':
            compile(content.decode('utf-8-sig'), str(path), 'exec')
            source_hashes[path.name] = hashlib.sha256(content).hexdigest()
        if path.suffix == '.json':
            record = json.loads(content.decode('utf-8-sig'))
            if 'probe_name' in record:
                assert (DIRECTORY / record['stdout_file']).exists()
                assert (DIRECTORY / record['stderr_file']).exists()
                assert datetime.fromisoformat(record['ended_at']) >= datetime.fromisoformat(record['started_at'])
                receipts.append({key: record[key] for key in
                                 ('probe_name', 'started_at', 'ended_at', 'exit_code', 'timed_out')})
    assert not exposed_files
    verified_at = datetime.now(ZONE).isoformat(timespec='seconds')
    record = {'verified_at': verified_at, 'evidence_receipts': sorted(receipts, key=lambda item: item['started_at']),
              'source_sha256': source_hashes, 'test_config_modes': config_permissions,
              'test_secret_values_found': False, 'application_tests_run': 0}
    (DIRECTORY / 'evidence_index.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(json.dumps({'verified_at': verified_at, 'receipt_count': len(receipts),
                      'failed_receipts': [item['probe_name'] for item in receipts if item['exit_code'] != 0],
                      'source_count': len(source_hashes), 'test_secret_values_found': False,
                      'application_tests_run': 0}))


if __name__ == '__main__':
    main()
