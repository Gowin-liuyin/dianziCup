"""Verify local evidence completeness and absence of generated test passwords."""

import hashlib
import json
import pathlib
import subprocess
from datetime import datetime, timedelta, timezone


DIRECTORY = pathlib.Path(__file__).resolve().parent
ZONE = timezone(timedelta(hours=8))


def main():
    result = subprocess.run(['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec',
                             '/bin/cat', '/tmp/dianzi-docker-static-r01-20261014/runtime/'
                             'test-services/connection.json'], capture_output=True,
                            text=True, timeout=10, check=True)
    private_config = json.loads(result.stdout)
    secrets_to_check = [private_config[key] for key in
                        ('postgres_password', 'redis_password', 'TEST_DATABASE_URL', 'TEST_REDIS_URL')]
    exposed_files = []
    report_path = DIRECTORY.parent.parent / 'tasks' / 'R01-resources.md'
    report_content = report_path.read_bytes()
    if any(secret.encode() in report_content for secret in secrets_to_check):
        exposed_files.append('reports/tasks/R01-resources.md')
    source_hashes = {}
    receipts = []
    for path in DIRECTORY.iterdir():
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
    assert len(source_hashes) == 4
    failed_receipts = [item for item in receipts if item['exit_code'] != 0]
    assert [item['probe_name'] for item in failed_receipts] == ['kernel_limits_listeners']
    record = {'verified_at': datetime.now(ZONE).isoformat(timespec='seconds'),
              'evidence_receipts': sorted(receipts, key=lambda item: item['started_at']),
              'source_sha256': source_hashes, 'test_secret_values_found': False,
              'application_tests_run': 0}
    (DIRECTORY / 'evidence_index.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(json.dumps({'verified_at': record['verified_at'], 'receipts': len(receipts),
                      'expected_investigation_failures': len(failed_receipts),
                      'python_sources_compiled': len(source_hashes),
                      'test_secret_values_found': False, 'application_tests_run': 0}))


if __name__ == '__main__':
    main()
