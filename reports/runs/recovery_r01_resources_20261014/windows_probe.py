"""Verify Windows-to-WSL authenticated services without printing test credentials."""

import json
import socket
import subprocess
from datetime import datetime, timedelta, timezone

import psycopg


ZONE = timezone(timedelta(hours=8))
CONFIG_PATH = '/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json'


def now():
    return datetime.now(ZONE).isoformat(timespec='seconds')


def redis_send(connection, *parts):
    encoded_parts = [part.encode() for part in parts]
    payload = ('*' + str(len(parts)) + '\r\n').encode()
    for part in encoded_parts:
        payload += ('$' + str(len(part)) + '\r\n').encode() + part + b'\r\n'
    connection.sendall(payload)
    return connection.recv(4096)


def main():
    started_at = now()
    result = subprocess.run(['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec',
                             '/bin/cat', CONFIG_PATH], capture_output=True, text=True,
                            timeout=10, check=True)
    private_config = json.loads(result.stdout)
    assert private_config['DIANZI_TEST_RUN_ID'] == 'r01_20261014'
    assert private_config['postgres_database'] == 'test_dianzi_r01_20261014'
    assert private_config['postgres_user'].startswith('test_')
    postgres_parameters = {'host': private_config['postgres_host'],
                           'port': private_config['postgres_port'],
                           'dbname': private_config['postgres_database'],
                           'user': private_config['postgres_user'],
                           'password': private_config['postgres_password'],
                           'connect_timeout': 3}
    with psycopg.connect(**postgres_parameters) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_database(), current_user, '
                           '(SELECT extversion FROM pg_extension WHERE extname=\'vector\')')
            identity = cursor.fetchone()
            assert identity == ('test_dianzi_r01_20261014', 'test_dianzi_r01', '0.8.2')
            cursor.execute('SELECT payload FROM r01_resource_probe WHERE probe_id=%s',
                           ('persistent-r01',))
            assert cursor.fetchone() == ('real-pg-test',)
            cursor.execute('CREATE TABLE IF NOT EXISTS r01_windows_probe '
                           '(probe_id text PRIMARY KEY, payload text NOT NULL)')
            cursor.execute('INSERT INTO r01_windows_probe VALUES (%s,%s) '
                           'ON CONFLICT (probe_id) DO NOTHING', ('windows-auth', 'real-client'))
    rejected_password = False
    wrong_parameters = {**postgres_parameters, 'password': 'explicit-test-wrong-password'}
    try:
        with psycopg.connect(**wrong_parameters):
            raise AssertionError('PostgreSQL accepted the wrong test password')
    except psycopg.OperationalError as failure:
        rejected_password = 'password authentication failed' in str(failure)
    assert rejected_password
    with socket.create_connection(('127.0.0.1', private_config['redis_port']), timeout=3) as connection:
        assert redis_send(connection, 'PING').startswith(b'-NOAUTH')
        assert redis_send(connection, 'AUTH', 'explicit-test-wrong-password').startswith(b'-WRONGPASS')
        assert redis_send(connection, 'AUTH', private_config['redis_password']) == b'+OK\r\n'
        assert redis_send(connection, 'PING') == b'+PONG\r\n'
        assert b'real-redis-test' in redis_send(connection, 'GET', 'r01:resource:persistent')
    print(json.dumps({'started_at': started_at, 'ended_at': now(), 'postgres_identity': identity,
                      'postgres_windows_write': 'passed', 'postgres_wrong_password_rejected': True,
                      'redis_unauthenticated_rejected': True, 'redis_wrong_password_rejected': True,
                      'redis_authenticated_ping_read': 'passed'}))


if __name__ == '__main__':
    main()
