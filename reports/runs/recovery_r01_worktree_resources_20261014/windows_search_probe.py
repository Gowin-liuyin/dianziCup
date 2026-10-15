"""Read real OpenSearch state from Windows with loopback proxy bypass."""

import json
import subprocess
import urllib.request
from datetime import datetime, timedelta, timezone


ZONE = timezone(timedelta(hours=8))


def main() -> None:
    started_at = datetime.now(ZONE).isoformat(timespec='seconds')
    result = subprocess.run(['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', '/bin/cat',
                             '/tmp/dianzi-docker-static-r01-20261014/runtime/'
                             'test-opensearch-r01_20261014/connection.json'],
                            capture_output=True, text=True, timeout=10, check=True)
    private_config = json.loads(result.stdout)
    assert private_config['DIANZI_TEST_RUN_ID'] == 'r01_20261014'
    assert private_config['TEST_OPENSEARCH_URL'] == 'http://127.0.0.1:29200'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    responses = {}
    for path in ('/', '/_cluster/health', '/r01-resource-smoke/_doc/real-input'):
        with opener.open(private_config['TEST_OPENSEARCH_URL'] + path, timeout=5) as response:
            responses[path] = json.loads(response.read())
            assert response.status == 200
    assert responses['/']['version']['number'] == '2.17.0'
    assert responses['/_cluster/health']['status'] == 'green'
    assert responses['/r01-resource-smoke/_doc/real-input']['_source'] == {
        'title': 'AI vulnerability evidence', 'mode': 'test'}
    print(json.dumps({'started_at': started_at, 'ended_at': datetime.now(ZONE).isoformat(timespec='seconds'),
                      'windows_loopback_opensearch_version': '2.17.0', 'cluster_status': 'green',
                      'synthetic_test_document_read': 'passed', 'security_plugin_disabled_test_only': True}))


if __name__ == '__main__':
    main()
