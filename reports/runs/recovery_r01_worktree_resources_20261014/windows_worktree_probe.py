"""Verify each new isolated worktree database before application migrations."""

import argparse
import json
import pathlib
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import psycopg


PRIOR_DIRECTORY = pathlib.Path(__file__).resolve().parent.parent / 'recovery_r01_resources_20261014'
sys.path.insert(0, str(PRIOR_DIRECTORY))
sys.dont_write_bytecode = True
from windows_probe import redis_send


ZONE = timezone(timedelta(hours=8))
STACKS = {'quality': ('r01_quality_20261014', 25434, 26381),
          'frontend': ('r01_frontend_20261014', 25435, 26382)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('stack', choices=STACKS)
    arguments = parser.parse_args()
    run_id, postgres_port, redis_port = STACKS[arguments.stack]
    started_at = datetime.now(ZONE).isoformat(timespec='seconds')
    config_path = '/tmp/dianzi-docker-static-r01-20261014/runtime/test-services-' + run_id + '/connection.json'
    result = subprocess.run(['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec',
                             '/bin/cat', config_path], capture_output=True, text=True, timeout=10, check=True)
    private_config = json.loads(result.stdout)
    assert private_config['DIANZI_TEST_RUN_ID'] == run_id
    assert private_config['postgres_database'] == 'test_dianzi_' + run_id
    assert private_config['postgres_user'].startswith('test_')
    assert private_config['postgres_port'] == postgres_port
    assert private_config['redis_port'] == redis_port
    parameters = {'host': '127.0.0.1', 'port': postgres_port,
                  'dbname': private_config['postgres_database'], 'user': private_config['postgres_user'],
                  'password': private_config['postgres_password'], 'connect_timeout': 3}
    with psycopg.connect(**parameters) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_database(), current_user, inet_server_addr(), inet_server_port()')
            identity = cursor.fetchone()
            assert identity[:2] == (private_config['postgres_database'], private_config['postgres_user'])
            assert str(identity[2]) == '127.0.0.1' and identity[3] == postgres_port
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
            pre_migration_tables = [row[0] for row in cursor.fetchall()]
            assert not pre_migration_tables
    wrong_parameters = {**parameters, 'password': 'explicit-test-wrong-password'}
    rejected = False
    try:
        with psycopg.connect(**wrong_parameters):
            raise AssertionError('Wrong test password accepted')
    except psycopg.OperationalError as failure:
        rejected = 'password authentication failed' in str(failure)
    assert rejected
    with socket.create_connection(('127.0.0.1', redis_port), timeout=3) as connection:
        assert redis_send(connection, 'PING').startswith(b'-NOAUTH')
        assert redis_send(connection, 'AUTH', 'explicit-test-wrong-password').startswith(b'-WRONGPASS')
        assert redis_send(connection, 'AUTH', private_config['redis_password']) == b'+OK\r\n'
        assert redis_send(connection, 'PING') == b'+PONG\r\n'
    print(json.dumps({'started_at': started_at, 'ended_at': datetime.now(ZONE).isoformat(timespec='seconds'),
                      'run_id': run_id, 'database': identity[0], 'user': identity[1],
                      'server_address': str(identity[2]), 'server_port': identity[3],
                      'pre_migration_public_tables': pre_migration_tables,
                      'postgres_wrong_password_rejected': True,
                      'redis_unauthenticated_rejected': True, 'redis_wrong_password_rejected': True,
                      'redis_authenticated_ping': 'passed'}))


if __name__ == '__main__':
    main()
