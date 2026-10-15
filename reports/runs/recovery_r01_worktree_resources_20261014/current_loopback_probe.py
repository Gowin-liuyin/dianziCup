"""Check current owned loopback availability after a host timing anomaly."""

import json
import socket
import urllib.request
from datetime import datetime, timedelta, timezone


ZONE = timezone(timedelta(hours=8))


def main() -> None:
    started_at = datetime.now(ZONE).isoformat(timespec='seconds')
    ports = (25432, 26379, 25434, 26381, 25435, 26382, 29200)
    results = {}
    for port in ports:
        with socket.socket() as connection:
            connection.settimeout(1)
            try:
                connection.connect(('127.0.0.1', port))
                results[str(port)] = 'connected'
            except OSError as failure:
                results[str(port)] = type(failure).__name__
    search = {'status': 'not_run'}
    if results['29200'] == 'connected':
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open('http://127.0.0.1:29200/_cluster/health', timeout=2) as response:
            cluster = json.loads(response.read())
            search = {'http_status': response.status, 'cluster_status': cluster['status']}
    print(json.dumps({'started_at': started_at, 'ended_at': datetime.now(ZONE).isoformat(timespec='seconds'),
                      'owned_port_tcp': results, 'search': search}))
    assert all(value == 'connected' for value in results.values())


if __name__ == '__main__':
    main()
